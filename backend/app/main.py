"""FastAPI 应用入口。

这是整个后端应用的起点：
1. 创建 FastAPI 实例
2. 注册中间件（CORS、请求ID、日志等）
3. 注册 API 路由
4. 定义根路由

中间件执行顺序（和注册顺序相反，类似洋葱模型）：
    注册顺序：CORS → SlowAPI → RequestID → Timeout
    请求执行：Timeout → RequestID → SlowAPI → CORS → 路由
    响应返回：路由 → CORS → SlowAPI → RequestID → Timeout → 响应
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.exceptions import register_exception_handlers
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.timeout_middleware import TimeoutMiddleware
from app.middleware.rate_limit import limiter
from app.api.v1.router import api_router


# ========== 创建 FastAPI 应用实例 ==========
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Air Fryer AI Assistant - 基于 RAG 的智能客服系统",
    lifespan=lifespan,  # 注册生命周期管理器（日志初始化在这里）
    docs_url="/docs",
    redoc_url="/redoc",
)

# 注册全局异常处理器（必须在路由注册之前）
register_exception_handlers(app)

# 注册限流器（slowapi 需要在 app.state 上挂载）
app.state.limiter = limiter

# 注册限流超出（429）的处理器
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ========== 注册中间件（注意：后注册的先执行）==========

# CORS 中间件：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件：对全局所有路由生效（基于 default_limits 配置）
# 放在 CORS 之后注册 → 请求时 CORS 先执行（放行预检），再限流
# 放在 RequestID 之前注册 → RequestID 先执行（被限流的请求也有 request_id 方便日志追踪）
app.add_middleware(SlowAPIMiddleware)

# 请求ID中间件：给每个请求分配唯一ID，所有日志自动携带
app.add_middleware(RequestIDMiddleware)

# 注册超时中间件（后注册的先执行，放在最后确保包裹所有路由）
app.add_middleware(TimeoutMiddleware)

# ========== 注册 API 路由 ==========
app.include_router(api_router, prefix="/api/v1")


# ========== 根路由 ==========
@app.get("/")
async def root() -> dict[str, str]:
    """根路由：返回应用基本信息。"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


# ========== 健康检查 ==========
@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点：监控系统和负载均衡器用。"""
    return {"status": "ok"}
