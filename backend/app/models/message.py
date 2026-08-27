"""消息模型。

对应数据库表: messages
存储对话中的每一条消息（用户提问 + AI 回复 + 系统消息）。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    """消息表。

    一条对话（conversation）包含多条消息（message）。
    消息角色（role）：
    - user: 用户发送的消息
    - assistant: AI 的回复
    - system: 系统提示（不展示给用户）
    - tool: 工具调用的结果
    """

    __tablename__ = "messages"

    # ---------- 主键 ----------
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # ---------- 外键 ----------
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ---------- 业务字段 ----------
    # 消息角色：user / assistant / system / tool
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # 消息内容（可能很长，用 Text 类型）
    # Text 在 PostgreSQL 中对应 TEXT，无长度限制
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 元数据（JSON 类型）：存储检索结果、工具调用、模型信息等
    # PostgreSQL 中 JSON 会自动处理为 JSONB（二进制 JSON，可索引）
    meta: Mapped[dict | None] = mapped_column(
        JSON,
        default=None,
    )

    # ---------- 审计字段 ----------
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # ---------- 关系 ----------
    # 多对一：多条消息属于一个会话
    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages",
    )
