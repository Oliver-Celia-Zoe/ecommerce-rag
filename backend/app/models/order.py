"""订单模型。

对应数据库表: orders
MVP 阶段用于模拟工具调用的数据，后续可对接真实订单系统。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Order(Base):
    """订单表。

    字段设计精简，MVP 阶段仅支持查询演示。
    """

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 业务单号（对外展示，如 AF20240711001）
    order_no: Mapped[str] = mapped_column(
        String(50),
        unique=True,  # 单号全局唯一
        nullable=False,
    )

    # 订单状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",  # pending / paid / shipped / delivered / cancelled
    )

    # 订单总金额（整数，单位：分）
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # 关系
    user: Mapped["User"] = relationship()
