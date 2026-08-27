"""对话服务。

封装 LangGraph 工作流的调用，是 API 层和工作流之间的桥梁。

分层说明：
  API 层（chat.py）→  只处理 HTTP 请求/响应
  服务层（chat_service.py）→ 编排业务逻辑（含超时保护）
  工作流层（graph/workflow.py）→ AI 处理
"""

import asyncio
import uuid as uuid_module

import structlog

from app.core.config import settings
from app.core.exceptions import LLMTimeoutException
from app.graph.workflow import get_workflow, WorkflowState

logger = structlog.get_logger(__name__)


async def handle_chat(message: str, session_id: str | None = None) -> dict:
    """处理一条用户消息。

    完整的处理流程：
      用户消息 → LangGraph 工作流 → AI 回答

    超时保护：
      工作流执行超过 chat_timeout_seconds 秒后自动中断，
      返回超时提示，而不是让用户无限等待。

    Args:
        message: 用户发送的问题
        session_id: 会话ID（新对话不传）

    Returns:
        {
            "answer": "AI的回答",
            "session_id": "...",
            "intent": "aftersales",
            "need_human": False
        }

    Raises:
        LLMTimeoutException: 工作流执行超时
    """
    if not session_id:
        session_id = str(uuid_module.uuid4())

    initial_state: WorkflowState = {
        "user_question": message,
        "session_id": session_id,
        "intent": "general",
        "retrieved_docs": [],
        "tool_result": "",
        "answer": "",
        "need_human": False,
        "debug_info": "",
    }

    workflow = await get_workflow()
    logger.info("开始执行工作流", session_id=session_id, timeout=settings.chat_timeout_seconds)

    try:
        # 用 asyncio.wait_for 设置工作流超时
        # 如果 LLM 卡住或 Qdrant 连接超时，这里会抛出 TimeoutError
        final_state = await asyncio.wait_for(
            workflow.ainvoke(initial_state),
            timeout=settings.chat_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "工作流执行超时",
            session_id=session_id,
            timeout=settings.chat_timeout_seconds,
        )
        raise LLMTimeoutException(
            message=f"AI 处理超时（{settings.chat_timeout_seconds}秒），请简化问题后重试"
        ) from None
    except Exception:
        logger.exception("工作流执行异常")  # exception 会自动附带 traceback
        raise

    logger.info(
        "工作流完成",
        intent=final_state.get("intent"),
        answer_length=len(final_state.get("answer", "")),
        need_human=final_state.get("need_human", False),
    )

    return {
        "answer": final_state.get("answer", "抱歉，处理你的问题时出现错误。"),
        "session_id": final_state["session_id"],
        "intent": final_state.get("intent", "unknown"),
        "need_human": final_state.get("need_human", False),
    }