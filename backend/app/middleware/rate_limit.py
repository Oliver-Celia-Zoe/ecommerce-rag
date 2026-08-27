"""请求限流配置。

使用 slowapi 实现基于 IP 的请求限流。

为什么需要限流？
1. 防止恶意攻击（短时间大量请求耗尽服务器资源）
2. 防止客户端 bug 导致无限重试
3. 公平分配资源（一个用户刷请求不影响其他用户）

限流策略：
- 开发环境：60 次/分钟（宽松，方便调试）
- 生产环境：10 次/分钟（严格，保护后端）

原理：
  slowapi 在内存中维护一个计数器，记录每个 IP 在时间窗口内的请求次数。
  当次数超过阈值时，返回 429 Too Many Requests。
"""

import structlog
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = structlog.get_logger(__name__)


def get_limiter() -> Limiter:
    """创建并返回限流器实例。

    使用 `get_remote_address` 作为限流 key（基于客户端 IP）。
    注意：如果应用部署在反向代理（Nginx）后面，需要配置
    `ProxyHeadersMiddleware` 才能获取真实 IP。

    限流规则格式："[次数]/[时间单位]"
    例如： "10/minute" 表示每分钟 10 次
          "100/hour"   表示每小时 100 次
    """
    if not settings.rate_limit_enabled:
        logger.info("请求限流未启用")
        return Limiter(key_func=get_remote_address, enabled=False)

    # 根据环境调整限流阈值
    if settings.debug:
        # 开发环境：60 次/分钟
        rate = "60/minute"
        logger.info("限流已启用（开发模式）", rate=rate)
    else:
        # 生产环境：10 次/分钟
        rate = f"{settings.rate_limit_requests}/{settings.rate_limit_window}second"
        logger.info("限流已启用（生产模式）", rate=rate)

    return Limiter(
        key_func=get_remote_address,
        default_limits=[rate],
    )


# 全局单例
limiter = get_limiter()