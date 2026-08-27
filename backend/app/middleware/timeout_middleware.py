"""请求超时中间件。

给每个请求设置最大执行时间，超过时间自动返回 504 超时响应。

为什么需要超时保护？
1. 本地 LLM 推理可能卡住（模型加载、内存不足等）
2. 防止一个慢请求占用所有 worker 线程
3. 给用户快速反馈，而不是无限等待

超时策略：
- 开发环境：120 秒
- 生产环境：30 秒
- 聊天工作流：90 秒（在 chat_service.py 中单独控制）

注意：这个中间件和 LLM 的 httpx timeout 是两回事。
  - httpx timeout：单次 HTTP 调用的超时
  - 本中间件：整个请求（包括多次 LLM 调用 + 向量检索）的总超时
"""

import asyncio
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.requests import Request

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """请求超时中间件。

    原理：
      1. 记录请求进入时间
      2. 用 asyncio.wait_for() 包裹后续处理，设置超时时间
      3. 如果超时，返回 504 而不是让请求一直挂起
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        timeout = settings.request_timeout_seconds

        # 健康检查等简单端点不设超时（防止监控误报）
        if request.url.path in ("/health", "/", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        start = time.time()
        try:
            # 用 asyncio.wait_for 设置超时
            response = await asyncio.wait_for(
                call_next(request),
                timeout=timeout,
            )
            return response
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            logger.warning(
                "请求超时",
                path=request.url.path,
                method=request.method,
                timeout=timeout,
                elapsed_seconds=round(elapsed, 1),
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "REQUEST_TIMEOUT",
                        "message": f"请求处理超时（{timeout}秒），请稍后重试",
                    }
                },
            )