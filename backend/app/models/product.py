"""商品模型。

对应数据库表: products
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    """商品表。

    价格用整数存储（单位：分），避免浮点精度问题。
    例如 29.9 元存为 2990。
    """

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    # 价格存为整数（分），展示时除以 100
    # 比如 2990 表示 29.90 元
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    # 商品分类
    category: Mapped[str] = mapped_column(String(50), default="general")

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # 一个商品有多条知识文档
    knowledge_docs: Mapped[list["KnowledgeDoc"]] = relationship(
        back_populates="product",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
