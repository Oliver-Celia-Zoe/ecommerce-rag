"""数据库模型包。

集中导出所有模型，方便 Alembic 和其他模块引用。
"""

from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.product import Product
from app.models.knowledge_doc import KnowledgeDoc
from app.models.order import Order

# __all__ 定义了 from app.models import * 时导出的内容
__all__ = [
    "User",
    "Conversation",
    "Message",
    "Product",
    "KnowledgeDoc",
    "Order",
]
