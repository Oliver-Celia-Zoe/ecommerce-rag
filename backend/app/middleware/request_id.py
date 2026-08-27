"""请求 ID 中间件。

给每个 HTTP 请求分配一个唯一的 request_id，
后续所有日志自动携带这个 ID，方便追踪请求的完整链路。

前端类比：类似 Axios 拦截器自动给每个请求加 X-Request-Id header。

日志效果示例：
    {"request_id":"abc123","event":"意图分类完成","intent":"aftersales",...}
    {"request_id":"abc123","event":"检索到 2 个文档","score":0.92,...}
    {"request_id":"abc123","event":"回答生成完成","answer_length":279,...}
    → 三条日志都带同一个 request_id，可以一键过滤出这个请求的完整链路
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求注入 request_id 的中间件。

    工作流程：
    1. 请求进入 → 生成 request_id → 存入 contextvars
    2. 执行后续处理（日志自动从 contextvars 提取 request_id）
    3. 请求结束 → 清除 contextvars → 记录耗时日志
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ---- 1. 生成 request_id ----
        # 优先使用客户端传入的 X-Request-Id（方便前后端链路追踪）
        # 如果没有，自动生成一个
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])

        # ---- 2. 绑定到 contextvars ----
        # contextvars 是 Python 的"协程安全全局变量"
        # 同一个 async 任务内的所有代码都能读到这个值
        # 不同请求之间互不干扰
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # ---- 3. 记录请求开始 ----
        start_time = time.perf_counter()
        logger.info(
            "请求开始",
            method=request.method,
            path=request.url.path,
            request_id=request_id,
        )

        # ---- 4. 执行后续处理 ----
        try:
            response = await call_next(request)
            return response
        finally:
            # ---- 5. 请求结束，记录耗时 ----
            # 无论成功还是异常，finally 都会执行
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "请求结束",
                request_id=request_id,
                duration_ms=round(duration_ms, 1),
                status_code=response.status_code if hasattr(response, "status_code") else "N/A",
            )
            # 清除 contextvars，防止内存泄漏
            structlog.contextvars.unbind_contextvars("request_id")
