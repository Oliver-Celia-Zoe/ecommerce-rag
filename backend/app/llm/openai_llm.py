"""OpenAI 兼容 LLM 实现。

通过 httpx 异步调用 OpenAI 兼容的 Chat Completions API。
可服务任何兼容 OpenAI 协议的服务：
  - OpenAI 官方          → base_url=https://api.openai.com/v1
  - DeepSeek            → base_url=https://api.deepseek.com/v1
  - 智谱、Moonshot、本地 vLLM 等 → 只需改 base_url 和模型名

设计要点（与 OllamaLLM 对齐）：
  1. 构造时由 factory 注入 base_url / api_key / model，本类不读取 settings
     → 解耦：本类完全不知道自己在调 OpenAI 还是 DeepSeek
  2. tenacity 自动重试：网络抖动、5xx、限流 429 时自动退避重试
  3. 结构化日志：记录每次调用的关键指标，便于排查
"""

import logging

import httpx
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.exceptions import LLMException, LLMTimeoutException
from app.llm.base import BaseLLM

logger = structlog.get_logger(__name__)
# tenacity 的 before_sleep_log 需要标准 logging logger
_retry_logger = logging.getLogger(__name__)


class OpenAILLM(BaseLLM):
    """OpenAI 兼容 LLM 客户端。

    通过 httpx 异步调用 OpenAI 兼容的 Chat Completions API。

    构造参数由 factory.py 注入（依赖注入）：
        llm = OpenAILLM(
            base_url="https://api.deepseek.com/v1",
            api_key="sk-xxx",
            model="deepseek-chat",
        )
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        provider_name: str = "openai",  # 仅用于日志标识
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider_name = provider_name
        if not self.api_key:
            raise ValueError(f"[{provider_name}] 需要 API Key")
        logger.info(
            "OpenAILLM 初始化",
            provider=provider_name,
            base_url=self.base_url,
            model=self.model,
        )

    @retry(
        # 最多重试 3 次（即最多调用 4 次：1 次原始 + 3 次重试）
        stop=stop_after_attempt(3),
        # 指数退避：第1次等2s，第2次等4s，第3次等8s，上限10s
        wait=wait_exponential(multiplier=1, min=2, max=10),
        # 只在以下异常时重试：HTTP错误、连接失败、超时
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
        ),
        # 每次重试前记录日志
        before_sleep=before_sleep_log(_retry_logger, logging.WARNING),
        # 重试耗尽后重新抛出原始异常
        reraise=True,
    )
    async def chat(self, messages: list[dict[str, str]]) -> str:
        """调用 OpenAI 兼容 API 进行对话。

        Args:
            messages: OpenAI 格式的消息列表
                [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

        Returns:
            LLM 生成的回复文本

        Raises:
            LLMTimeoutException: 多次重试后仍然超时
            LLMException: 多次重试后仍然失败 / API Key 缺失
        """
        # 消息规范化：过滤空 content，避免传空字符串
        validated_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content or not content.strip():
                logger.warning("跳过空内容消息", provider=self.provider_name, role=role)
                continue
            validated_messages.append({"role": role, "content": content})

        if not validated_messages:
            raise LLMException(detail=f"[{self.provider_name}] 消息列表为空")

        payload = {
            "model": self.model,
            "messages": validated_messages,
            "temperature": 0.7,
            "stream": False,
        }

        logger.info(
            "LLM 请求 Payload",
            provider=self.provider_name,
            message_count=len(payload["messages"]),
            roles=[m["role"] for m in payload["messages"]],
            total_content_length=sum(len(m["content"]) for m in payload["messages"]),
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as e:
            logger.error(
                "LLM 调用超时",
                provider=self.provider_name,
                error=str(e),
                model=self.model,
            )
            raise LLMTimeoutException() from e
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            logger.error(
                "LLM 调用失败",
                provider=self.provider_name,
                error=str(e),
                model=self.model,
            )
            raise LLMException(detail=str(e)) from e

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        logger.info(
            "LLM 返回内容",
            provider=self.provider_name,
            content_length=len(content),
            is_empty=not content.strip(),
            preview=content[:100] if content.strip() else "(空)",
        )

        return content
