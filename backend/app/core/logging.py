"""structlog 日志配置。

企业级日志系统的核心配置文件。

功能：
1. 配置 structlog 的 Processor 管道
2. 开发环境用彩色终端输出，生产环境用 JSON 输出
3. 支持请求ID自动注入（方便追踪一个请求的完整链路）

在 app/main.py 中调用 setup_logging() 初始化。
"""

import logging
import sys

import structlog
from structlog.dev import ConsoleRenderer

from app.core.config import settings


def setup_logging() -> None:
    """初始化 structlog 日志系统。

    在 FastAPI 启动时调用一次（lifespan.py 中）。

    Processor 管道的工作流程（类比前端 Webpack Loader 链）：
        原始日志事件 → ContextVars 注入 → 加日志级别 → 加时间戳
        → 格式化输出(JSON/彩色终端) → 交给标准输出
    """
    # ---- 共享的 Processor 链（所有输出格式都经过这些处理）----
    shared_processors: list[structlog.types.Processor] = [
        # 自动注入 contextvars（如 request_id）
        # contextvars 是 Python 的"线程安全全局变量"
        # 每个请求设置一个 request_id，所有日志自动带上这个 ID
        structlog.contextvars.merge_contextvars,

        # 从标准 logging 模块添加日志级别和模块名
        # 这让 structlog 能和 SQLAlchemy/Uvicorn 等第三方库的日志共存
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,

        # 添加 ISO 格式时间戳
        # 输出示例: "2026-07-15T16:01:41.123Z"
        structlog.processors.TimeStamper(fmt="iso"),

        # 自动添加调用位置的文件名和行号（方便排查）
        structlog.processors.StackInfoRenderer(),

        # 把异常信息格式化为可读的字符串
        structlog.processors.UnicodeDecoder(),
    ]

    # ---- 根据环境选择输出格式 ----
    if settings.debug:
        # 开发环境：彩色终端输出，人类可读
        renderer = ConsoleRenderer(
            colors=True,          # 彩色
            level_styles={       # 不同级别不同颜色
                "debug": "cyan",
                "info": "green",
                "warning": "yellow",
                "error": "red",
                "critical": "bold_red",
            },
        )
        # 开发环境下额外加一个 Processor：让日志更紧凑
        chain = shared_processors + [
            # 把 event 和其他字段组合成一行
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # 生产环境：JSON 格式，机器可读
        # ELK / Grafana Loki 可以直接采集
        renderer = structlog.processors.JSONRenderer(
            ensure_ascii=False,  # 支持中文输出（不转义 Unicode）
        )
        chain = shared_processors + [
            renderer,
        ]

    # ---- 配置 structlog ----
    structlog.configure(
        processors=chain,
        # 底层使用标准 logging 模块
        # 这样 SQLAlchemy/Uvicorn 的日志也能被统一处理
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        # 缓存 logger 实例（同一模块名返回同一个 logger）
        cache_logger_on_first_use=True,
    )

    # ---- 配置标准 logging（让第三方库的日志也走 structlog）----
    # 设置 uvicorn 和 sqlalchemy 的日志级别
    # debug 模式下全部输出，生产环境下只输出 WARNING 以上
    log_level = logging.DEBUG if settings.debug else logging.WARNING

    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # 控制台日志也要走 structlog 的格式
    # 这样整个应用的日志风格统一
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=settings.debug),
            foreign_pre_chain=shared_processors,
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取 logger 实例。

    用法:
        from app.core.logging import get_logger
        logger = get_logger()
        logger.info("意图分类完成", intent="aftersales", score=0.92)

    Args:
        name: 模块名（通常传 __name__）。为 None 时使用调用者的模块名。

    Returns:
        配置好的 structlog logger
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
