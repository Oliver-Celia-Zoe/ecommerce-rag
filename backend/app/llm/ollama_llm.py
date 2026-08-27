"""Ollama LLM 实现。

通过 Ollama 的 REST API 调用本地模型。
这是开发阶段的主要 LLM 后端。

为什么不用 langchain-ollama 的 ChatOllama？
  - langchain 的封装是通用型的，内部做了很多我们不需要的处理
  - 直接调 REST API 更轻量、更透明、出问题更容易排查
  - 你能清楚看到每一次 LLM 调用到底传了什么、返回了什么
  - 企业级项目通常会在框架封装之上再做一层自己的抽象
"""

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

import structlog
import logging

from app.core.config import settings
from app.core.exceptions import LLMException, LLMTimeoutException
from app.llm.base import BaseLLM

logger = structlog.get_logger(__name__)
# tenacity 的 before_sleep_log 需要标准 logging logger
_retry_logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """Ollama LLM 客户端。"""

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        logger.info("OllamaLLM 初始化", base_url=self.base_url, model=self.model)

    @retry(
        # 最多重试 3 次（即最多调用 4 次：1次原始 + 3次重试）
        stop=stop_after_attempt(3),
        # 指数退避：第1次等2s，第2次等4s，第3次等8s，上限10s
        wait=wait_exponential(multiplier=1, min=2, max=10),
        # 只在以下异常时重试：HTTP错误、连接失败、超时
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
        ),
        # 每次重试前记录日志
        before_sleep=before_sleep_log(_retry_logger, logging.WARNING),
        # 重试耗尽后重新抛出原始异常，由下面的 except 捕获并转换
        reraise=True,
    )
    async def chat(self, messages: list[dict[str, str]]) -> str:
        """调用 Ollama API 进行对话。

        配置了自动重试：
        - 连接失败、HTTP 5xx、超时 时自动重试最多 3 次
        - 重试间隔指数退避（2s → 4s → 8s）
        - 重试耗尽后抛出自定义 LLMException

        Args:
            messages: OpenAI 格式的消息列表
                [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

        Returns:
            LLM 生成的回复文本

        Raises:
            LLMTimeoutException: 多次重试后仍然超时
            LLMException: 多次重试后仍然失败
        """
        # 消息规范化验证：确保每条消息都有 role 和 content，且 content 不为空
        validated_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            # 跳过 content 为空的消息（避免传空字符串给模型）
            if not content or not content.strip():
                logger.warning("跳过空内容消息", role=role)
                continue
            validated_messages.append({"role": role, "content": content})

        # 确保至少有一条 user 消息
        if not validated_messages:
            logger.error("所有消息都为空，无法调用 LLM")
            raise LLMException(detail="消息列表为空")

        # 确保消息顺序规范：system 在前，user 在后
        # Ollama 要求 messages 按对话顺序排列
        if (
            len(validated_messages) >= 2
            and validated_messages[0]["role"] == "system"
            and validated_messages[1]["role"] == "user"
        ):
            # 标准格式：system + user，直接使用
            pass
        elif validated_messages[0]["role"] == "user":
            # 只有 user 消息，没有 system，也能工作
            pass
        else:
            logger.warning(
                "消息顺序不规范",
                roles=[m["role"] for m in validated_messages],
            )

        payload = {
            "model": self.model,
            "messages": validated_messages,
            "stream": False,
        }

        logger.info("最后的meesage",validated_messages)

        # 调试日志：记录传给 LLM 的消息概况
        logger.info(
            "LLM请求Payload",
            message_count=len(payload["messages"]),
            roles=[m["role"] for m in payload["messages"]],
            total_content_length=sum(len(m["content"]) for m in payload["messages"]),
        )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as e:
            logger.error("Ollama 调用超时", error=str(e), model=self.model)
            raise LLMTimeoutException() from e
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            logger.error("Ollama 调用失败", error=str(e), model=self.model)
            raise LLMException(detail=str(e)) from e

        data = response.json()
        content = data["message"]["content"]

        # 调试日志：记录 LLM 返回内容概况
        logger.info(
            "LLM返回内容",
            content_length=len(content),
            is_empty=not content.strip(),
            preview=content[:100] if content.strip() else "(空)",
        )

        return content
