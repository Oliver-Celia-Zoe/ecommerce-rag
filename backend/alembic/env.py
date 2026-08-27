"""Alembic 迁移环境配置。

这是 Alembic 的核心脚本，负责：
1. 加载数据库连接
2. 加载所有模型（让 Alembic 知道表结构）
3. 执行迁移命令（upgrade / downgrade）

注意：我们使用异步 SQLAlchemy，但 Alembic 迁移本身是同步操作，
所以这里用 create_engine（同步）而不是 create_async_engine。
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from alembic import context

# 加载应用配置和模型
from app.core.config import settings
from app.core.database import Base
from app.models import *  # noqa: F401, F403 —— 导入所有模型让 Alembic 识别

# ========== Alembic 配置对象 ==========
config = context.config

# 从 alembic.ini 加载日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ========== 目标元数据 ==========
# Base.metadata 包含了所有继承 Base 的模型的表结构信息
# Alembic 通过比对 metadata 和实际数据库，生成迁移脚本
target_metadata = Base.metadata


def get_sync_database_url() -> str:
    """将异步数据库 URL 转为同步 URL。

    Alembic 迁移需要同步连接，所以把 +asyncpg 替换为 +psycopg2。
    开发环境如果没有 psycopg2，可以用 postgresql://（使用 psycopg2-binary）。
    """
    url = settings.database_url
    # 替换异步驱动为同步驱动
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def run_migrations_offline() -> None:
    """离线模式运行迁移。

    用于生成 SQL 脚本（不直接连接数据库）：
        alembic upgrade head --sql
    """
    url = get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,  # 将参数直接嵌入 SQL（用于输出）
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式运行迁移。

    直接连接数据库执行结构变更（最常用）：
        alembic upgrade head
    """
    url = get_sync_database_url()

    # 使用同步引擎连接数据库
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # 检测字段类型变化（如 VARCHAR(100) → VARCHAR(200)）
        )

        with context.begin_transaction():
            context.run_migrations()


# ========== 入口 ==========
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
