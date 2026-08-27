"""用户模型。

对应数据库表: users
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    # ---------- 主键 ----------
    # Mapped[UUID] 是 SQLAlchemy 2.0 的新语法
    # 表示 "这个字段在 Python 里是 UUID 类型"
    # mapped_column(primary_key=True) 表示 "数据库里这是主键"
    id: Mapped[str] = mapped_column(
        String(36),  # UUID 存成字符串，长度 36
        primary_key=True,
        default=lambda: str(uuid4()),  # 插入时自动生成 UUID
    )

    # ---------- 基本信息 ----------
    # Mapped[str | None] 表示 "字符串，可以为空"
    # String(100) 限制数据库里最多 100 个字符
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20), default=None)
    email: Mapped[str | None] = mapped_column(String(200), default=None)

    # ---------- 审计字段 ----------
    # 每条记录都有的 "创建时间" 和 "更新时间"
    # server_default 表示数据库层面的默认值
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,  # 每次更新时自动刷新
    )

    # ---------- 关系 ----------
    # relationship 不是数据库字段，是 SQLAlchemy 的 "魔法"
    # 它表示："这个用户有很多条对话"
    # back_populates="user" 表示 Conversation 模型里也有个 user 字段指向这里
    # lazy="selectin" 表示查询用户时，自动把关联的对话也查出来
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",  # 删除用户时，级联删除所有对话
    )
