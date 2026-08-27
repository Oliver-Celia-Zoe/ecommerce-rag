"""知识文档模型。

对应数据库表: knowledge_docs
存储原始文档信息，与 Qdrant 中的向量 chunk 通过 doc_id 关联。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KnowledgeDoc(Base):
    """知识文档表。

    为什么需要这张表？
    Qdrant 只存向量 chunk，不存原始文档的完整信息。
    这张表记录原始文档的元数据，方便管理和追溯。
    """

    __tablename__ = "knowledge_docs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # 关联商品（可为空，表示通用文档）
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        default=None,
    )

    # 文档分类：presales（售前）/ aftersales（售后）/ cookbook（菜谱）
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    # 文档标题
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    # 原始内容（完整文本，用于重新分块或审计）
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 内容哈希（SHA-256），用于检测文档是否重复上传
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # 分块数量（这篇文档在 Qdrant 中被分成了几个 chunk）
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # 关系
    product: Mapped["Product | None"] = relationship(back_populates="knowledge_docs")
