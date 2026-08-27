"""JWT 鉴权核心模块。

负责：
1. 密码哈希（注册时加密，登录时校验）
2. JWT Token 生成（登录成功后签发）
3. JWT Token 验证（每次请求时校验）

JWT 原理（类比前端 localStorage + JWT）：
  登录 → 服务器返回 Token → 客户端存在 localStorage
  → 每次请求在 Header 里带上 Token → 服务器验证

JWT 三段式：
  Header（算法类型）. Payload（用户信息+过期时间）. Signature（签名防篡改）
  例如：
  eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3MH0.xxxxx

安全要点：
  - 密码绝不明文存储，用 bcrypt 哈希
  - secret_key 生产环境必须换为随机长字符串
  - Token 有过期时间，泄露后影响有限
"""

from datetime import datetime, timedelta, timezone

import jwt
import bcrypt

import structlog

from app.core.config import settings
from app.core.exceptions import AuthenticationException

logger = structlog.get_logger(__name__)

# ========== 1. 密码哈希 ==========

# bcrypt 直接使用（避免 passlib 版本兼容问题）
# bcrypt 自动加盐（salt），相同密码每次哈希结果不同
# 计算故意较慢（约 0.1s），防止暴力破解


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。

    Args:
        password: 用户输入的明文密码

    Returns:
        哈希后的密码字符串（如 $2b$12$xxxx...）
    """
    # 将密码转为 bytes 后哈希
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验密码是否正确。

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码

    Returns:
        True 如果密码正确，False 如果不正确
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ========== 2. JWT Token ==========

# Token 的加密算法（HS256 = HMAC-SHA256，对称加密）
ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    username: str,
    expires_delta: timedelta | None = None,
) -> str:
    """生成 JWT Token。

    Args:
        user_id: 用户ID
        username: 用户名
        expires_delta: 自定义过期时间（None 则用配置默认值）

    Returns:
        JWT Token 字符串

    Token Payload 中包含的信息：
      - sub: 用户ID（JWT 标准中 sub = subject，即"这个 token 是给谁的"）
      - username: 用户名（方便后续使用，不需要再查数据库）
      - exp: 过期时间（秒级时间戳）
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Payload：要放进 Token 里的数据
    payload = {
        "sub": str(user_id),       # subject（是谁）
        "username": username,
        "exp": expire,             # 过期时间
        "iat": now,                # issued at（签发时间）
    }

    # 用 secret_key 对 payload 进行签名
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    logger.info("Token 已签发", user_id=user_id, username=username, expires_in=expires_delta)

    return token


def decode_access_token(token: str) -> dict:
    """验证并解码 JWT Token。

    Args:
        token: 客户端传来的 JWT Token

    Returns:
        解码后的 payload 字典（包含 user_id、username 等）

    Raises:
        AuthenticationException: Token 无效、过期、格式错误

    验证流程：
      1. 用 secret_key 解码并验证签名（如果 token 被篡改，签名不匹配）
      2. 检查 exp 是否过期
      3. 返回 payload
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username")

        if user_id is None or username is None:
            logger.warning("Token 缺少必要字段", payload_keys=list(payload.keys()))
            raise AuthenticationException("Token 格式无效")

        return {
            "user_id": int(user_id),
            "username": username,
        }
    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        raise AuthenticationException("Token 已过期，请重新登录")
    except jwt.InvalidTokenError as e:
        logger.warning("Token 无效", error=str(e))
        raise AuthenticationException("Token 无效，请重新登录")
