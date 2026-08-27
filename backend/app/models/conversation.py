"""会话模型。

对应数据库表: conversations
一个用户可以有多个会话（conversation），
一个会话包含多条消息（message）。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    """会话表。

    为什么单独一张表？
    因为用户可能今天问一个问题，明天又问一个。
    每个会话有独立的状态和标题，方便管理和展示。
    """

    __tablename__ = "conversations"

    # ---------- 主键 ----------
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # ---------- 外键 ----------
    # ForeignKey("users.id") 表示：
    # "这个字段的值必须在 users 表的 id 字段中存在"
    # ondelete="CASCADE" 表示：
    # "如果 users 表里的某条记录被删了，自动删除关联的 conversations 记录"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,  # 每条会话必须属于一个用户
    )

    # ---------- 业务字段 ----------
    # 会话标题（可由 AI 自动生成摘要，或用户手动修改）
    title: Mapped[str | None] = mapped_column(
        String(200),
        default="新对话",
    )

    # 会话状态：active（活跃）/ closed（已关闭）/ escalated（已转人工）
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
    )

    # ---------- 审计字段 ----------
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # ---------- 关系 ----------
    # 多对一：多个会话属于一个用户
    user: Mapped["User"] = relationship(back_populates="conversations")

    # 一对多：一个会话有多条消息
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        lazy="selectin",
        order_by="Message.created_at",  # 按时间排序
        cascade="all, delete-orphan",
    )
