"""鉴权中间件 / 依赖注入。

提供 FastAPI 的 Depends 依赖，用于保护需要登录才能访问的端点。

为什么用 Depends 而不是 Middleware？
  - Middleware：全局拦截所有请求（包括 /health、/docs 等）
  - Depends：只保护指定端点，灵活控制哪些路由需要鉴权

  企业级项目中，通常用 Depends 保护业务 API，
  而 /health、/docs 等公开端点不需要鉴权。

使用方式：
  @router.post("/chat")
  async def chat(
      request: ChatRequest,
      current_user: dict = Depends(get_current_user),  ← 加这一行
  ):
      # current_user = {"user_id": 1, "username": "admin"}
      ...
"""

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import structlog

from app.core.auth import decode_access_token
from app.core.config import settings
from app.core.exceptions import AuthenticationException

logger = structlog.get_logger(__name__)

# HTTPBearer 自动从 Authorization: Bearer <token> 头中提取 token
# 类比前端的 axios interceptors —— 自动从 headers 里取 token
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """获取当前登录用户信息（FastAPI 依赖注入）。

    前端请求时需要在 Header 中带上：
      Authorization: Bearer <token>

    Args:
        credentials: FastAPI 自动从 Authorization header 提取的凭据

    Returns:
        {"user_id": 1, "username": "admin"}

    Raises:
        AuthenticationException: 没有 token、token 无效或已过期
    """
    # 开发模式下可以通过配置跳过鉴权（方便调试）
    if settings.debug and not settings.secret_key.startswith("dev-"):
        pass  # 非默认密钥时正常鉴权
    elif settings.debug and settings.secret_key == "dev-secret-key":
        # 开发模式 + 默认密钥 → 返回模拟用户（方便开发调试）
        logger.debug("开发模式：跳过鉴权")
        return {"user_id": 0, "username": "dev_user"}

    if credentials is None:
        logger.warning("请求缺少 Authorization header")
        raise AuthenticationException("请先登录")

    token = credentials.credentials
    return decode_access_token(token)
