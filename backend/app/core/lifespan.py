"""应用生命周期管理。

控制应用启动时和关闭时执行的逻辑：
- 启动：初始化日志、建立数据库连接、初始化外部服务
- 关闭：优雅释放资源
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI

from app.core.database import engine
from app.core.config import settings
from app.core.logging import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI 应用生命周期上下文管理器。

    用法：在 main.py 中创建 app 时传入
        app = FastAPI(lifespan=lifespan)

    执行顺序：
    1. yield 之前的代码 → 应用启动时执行
    2. yield → 应用运行期间
    3. yield 之后的代码 → 应用关闭时执行
    """
    # ========== 启动阶段 ==========

    # 第一步：初始化日志系统（必须在最前面，让后续所有日志都走 structlog）
    setup_logging()
    logger.info(
        "应用启动",
        app_name=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        llm_provider=settings.llm_provider,
        database=settings.database_url.split("@")[-1],
    )

    # 检查数据库连接（开发环境自动建表，生产环境用 Alembic 迁移）
    if settings.debug:
        from app.core.database import Base
        # 必须先 import 所有模型，Base.metadata 才能收集到表结构
        # 如果不 import，Base.metadata 是空的，create_all 什么都不做
        import app.models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已创建（开发模式）")

    logger.info("应用启动完成，等待请求")

    # yield 把控制权交给 FastAPI，开始处理请求
    yield

    # ========== 关闭阶段 ==========
    logger.info("正在关闭应用")
    await engine.dispose()
    logger.info("应用已关闭")
