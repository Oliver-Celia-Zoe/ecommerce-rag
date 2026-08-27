"""对话接口。

提供与 AI 助手对话的能力：
- POST /api/v1/chat/ - 发送消息并获取 AI 回复（需要鉴权）
- GET /api/v1/chat/history - 获取对话历史（需要鉴权）
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user
from app.core.exceptions import ErrorResponse
from app.services.chat_service import handle_chat

router = APIRouter()


# ========== 请求/响应 Schema ==========

class ChatRequest(BaseModel):
    """对话请求体。"""

    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: str | None = Field(None, description="会话ID（新对话不传）")


class ChatResponse(BaseModel):
    """对话响应体。"""

    answer: str = Field(..., description="AI 回复")
    session_id: str = Field(..., description="会话ID")
    intent: str | None = Field(None, description="识别的意图（调试用）")
    need_human: bool = Field(False, description="是否需要转人工")


# ========== 路由 ==========

@router.post(
    "/",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorResponse, "description": "未认证或 Token 过期"},
        422: {"model": ErrorResponse, "description": "请求参数校验失败"},
        503: {"model": ErrorResponse, "description": "AI 服务不可用"},
        504: {"model": ErrorResponse, "description": "AI 服务响应超时"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),  # ← 鉴权依赖注入
) -> ChatResponse:
    """发送消息给 AI 助手（需要登录）。

    请求时需要在 Header 中带上：
      Authorization: Bearer <token>

    处理流程：
      用户消息 → LangGraph 工作流（意图分类 → RAG检索 → 回答生成）→ 返回结果

    Args:
        request: 包含用户消息和可选的会话ID
        current_user: 当前登录用户信息（由 Depends 自动注入）

    Returns:
        AI 的回复内容、意图分类、是否需要人工
    """
    result = await handle_chat(
        message=request.message,
        session_id=request.session_id,
    )

    return ChatResponse(
        answer=result["answer"],
        session_id=result["session_id"],
        intent=result["intent"],
        need_human=result["need_human"],
    )


@router.get("/history")
async def chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),  # ← 鉴权依赖注入
) -> dict:
    """获取指定会话的历史消息（需要登录）。"""
    # MVP 阶段：返回空列表
    return {"session_id": session_id, "messages": []}
