"""数据库连接管理。

使用 SQLAlchemy 2.0 的异步 API 管理 PostgreSQL 连接。
提供连接池和会话管理，支持 FastAPI 的依赖注入。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# ========== SQLAlchemy 基础组件 ==========

# 声明式基类：所有模型都继承这个类
# 它告诉 SQLAlchemy "这个类对应数据库里的一张表"
Base = declarative_base()

# 异步数据库引擎：管理连接池
# - pool_pre_ping=True: 使用前检查连接是否有效，避免用断掉的连接
# - echo=False: 不打印 SQL 语句（生产环境关闭，调试时可打开）
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
)

# 异步会话工厂：用于创建数据库会话
# - expire_on_commit=False: 提交后不自动过期对象，方便后续使用
# - autoflush=False: 不自动刷新，需要手动控制
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ========== 依赖注入函数 ==========

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（FastAPI 依赖注入用）。

    用法：
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    为什么用 async generator？
    - FastAPI 的 Depends 需要可调用对象
    - async generator 确保会话正确关闭（即使发生异常）
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # 正常结束时自动提交
        except Exception:
            await session.rollback()  # 异常时自动回滚
            raise
        finally:
            await session.close()  # 无论成败都关闭会话
