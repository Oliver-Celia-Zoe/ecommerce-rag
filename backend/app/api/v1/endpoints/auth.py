"""认证接口。

提供用户注册和登录功能：
- POST /api/v1/auth/register - 注册新用户
- POST /api/v1/auth/login    - 用户登录获取 Token

注意：MVP 阶段使用内存字典存储用户数据。
  生产环境需要改为数据库存储 + Redis 缓存。
  这里是为了让你理解 JWT 完整流程，不是最终实现。
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

import structlog

from app.core.auth import hash_password, verify_password, create_access_token
from app.core.exceptions import ValidationException, ErrorResponse

logger = structlog.get_logger(__name__)

router = APIRouter()

# ========== MVP：内存用户存储（生产环境改为数据库）==========
# 格式：{username: {"id": int, "username": str, "hashed_password": str}}
_users_db: dict[str, dict] = {}


# ========== 请求/响应 Schema ==========

class RegisterRequest(BaseModel):
    """注册请求体。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token 响应体。"""

    access_token: str = Field(..., description="JWT Token")
    token_type: str = Field(default="bearer", description="Token 类型")
    expires_in: int = Field(..., description="过期时间（秒）")


# ========== 路由 ==========

@router.post(
    "/register",
    response_model=TokenResponse,
    responses={
        422: {"model": ErrorResponse, "description": "用户名已存在或参数校验失败"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def register(request: RegisterRequest) -> TokenResponse:
    """注册新用户并返回 Token。

    流程：
      1. 检查用户名是否已存在
      2. 密码 bcrypt 哈希后存储
      3. 签发 JWT Token 返回
    """
    if request.username in _users_db:
        raise ValidationException(message="用户名已存在")

    # 密码哈希（绝不存储明文密码）
    hashed = hash_password(request.password)

    # 存储用户（MVP 用内存字典）
    user_id = len(_users_db) + 1
    _users_db[request.username] = {
        "id": user_id,
        "username": request.username,
        "hashed_password": hashed,
    }

    logger.info("用户注册成功", username=request.username, user_id=user_id)

    # 签发 Token
    token = create_access_token(user_id=user_id, username=request.username)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=3600,  # 60 分钟
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        422: {"model": ErrorResponse, "description": "用户名或密码错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
)
async def login(request: LoginRequest) -> TokenResponse:
    """用户登录并返回 Token。

    流程：
      1. 查找用户
      2. 校验密码
      3. 签发 JWT Token 返回

    前端拿到 Token 后存储在 localStorage，
    之后每次请求在 Header 里带：Authorization: Bearer <token>
    """
    user = _users_db.get(request.username)

    if user is None:
        logger.warning("登录失败：用户不存在", username=request.username)
        raise ValidationException(message="用户名或密码错误")

    # 校验密码（bcrypt 会自动对比哈希值）
    if not verify_password(request.password, user["hashed_password"]):
        logger.warning("登录失败：密码错误", username=request.username)
        raise ValidationException(message="用户名或密码错误")

    logger.info("用户登录成功", username=request.username, user_id=user["id"])

    # 签发 Token
    token = create_access_token(user_id=user["id"], username=request.username)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=3600,
    )
