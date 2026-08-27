"""异常处理与错误响应标准。

企业级应用的错误处理原则：
1. 内部错误不暴露给客户端（防止信息泄露）
2. 所有错误返回统一的 JSON 格式
3. 错误码便于前端根据类型做不同处理
4. 日志记录完整堆栈，方便排查

FastAPI 异常处理机制：
  路由层抛异常 → 全局异常处理器捕获 → 统一格式返回给客户端
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import structlog

logger = structlog.get_logger(__name__)


# ========== 1. 错误响应 Schema（所有错误都用这个格式返回）==========


class ErrorResponse(BaseModel):
    """标准错误响应体。

    前端收到任何错误时，都按这个结构解析。

    示例:
        {
            "error": {
                "code": "LLM_TIMEOUT",
                "message": "AI 服务响应超时，请稍后重试",
                "detail": "..."
            }
        }
    """

    class _ErrorDetail(BaseModel):
        code: str = "UNKNOWN_ERROR"
        message: str = "服务器内部错误"
        detail: str | None = None

    error: _ErrorDetail


# ========== 2. 业务异常基类 ==========


class BusinessException(Exception):
    """业务异常基类。

    所有自定义异常都继承这个类。
    携带 code + message + status_code，供全局处理器直接转为 HTTP 响应。

    Args:
        code: 错误码（大写下划线，如 LLM_TIMEOUT）
        message: 给用户看的友好错误信息
        status_code: HTTP 状态码
        detail: 调试详情（不会暴露给客户端）
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class LLMException(BusinessException):
    """LLM 调用异常（模型不可达、响应超时、返回格式错误等）。"""

    def __init__(self, message: str = "AI 服务调用失败", detail: str | None = None) -> None:
        super().__init__(
            code="LLM_ERROR",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class LLMTimeoutException(BusinessException):
    """LLM 响应超时。"""

    def __init__(self, message: str = "AI 服务响应超时，请稍后重试") -> None:
        super().__init__(
            code="LLM_TIMEOUT",
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class VectorStoreException(BusinessException):
    """向量库异常（Qdrant 连接失败、查询错误等）。"""

    def __init__(self, message: str = "向量库查询失败", detail: str | None = None) -> None:
        super().__init__(
            code="VECTOR_STORE_ERROR",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class ValidationException(BusinessException):
    """请求参数校验异常。"""

    def __init__(self, message: str = "请求参数不合法", detail: str | None = None) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class NotFoundException(BusinessException):
    """资源不存在异常。"""

    def __init__(self, resource: str = "资源") -> None:
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource}不存在",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AuthenticationException(BusinessException):
    """认证失败异常（预留，4.4 鉴权阶段使用）。"""

    def __init__(self, message: str = "认证失败，请重新登录") -> None:
        super().__init__(
            code="AUTHENTICATION_ERROR",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class RateLimitException(BusinessException):
    """请求限流异常（预留，4.3 限流阶段使用）。"""

    def __init__(self, message: str = "请求过于频繁，请稍后再试") -> None:
        super().__init__(
            code="RATE_LIMIT",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


# ========== 3. 全局异常处理器 ==========


def _make_error_response(code: str, message: str, detail: str | None = None) -> dict[str, Any]:
    """构造统一错误响应字典。"""
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if detail:
        payload["error"]["detail"] = detail
    return payload


async def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    """处理所有自定义业务异常。"""
    logger.warning(
        "业务异常",
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        path=request.url.path,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_make_error_response(exc.code, exc.message, exc.detail),
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理 Pydantic / FastAPI 参数校验异常。"""
    # FastAPI 原生校验异常有两种类型，这里统一处理
    from fastapi.exceptions import RequestValidationError

    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        # 把第一个错误信息作为 message，全部错误作为 detail
        first_msg = errors[0].get("msg", "参数校验失败") if errors else "参数校验失败"
        detail = {"errors": errors}
        logger.warning(
            "参数校验失败",
            path=request.url.path,
            errors=errors,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_make_error_response("VALIDATION_ERROR", first_msg, str(detail)),
        )
    raise exc


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理 FastAPI HTTPException（如 404、403 等）。"""
    from starlette.exceptions import HTTPException as StarletteHTTPException

    if isinstance(exc, StarletteHTTPException):
        logger.warning(
            "HTTP 异常",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_make_error_response(
                f"HTTP_{exc.status_code}",
                str(exc.detail) if exc.detail else "请求出错",
            ),
        )
    raise exc


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """捕获所有未处理的异常（最后一道防线）。

    原则：内部错误信息绝不暴露给客户端，只记录到日志。
    """
    logger.exception(
        "未捕获的异常",
        path=request.url.path,
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_make_error_response(
            code="INTERNAL_ERROR",
            message="服务器内部错误，请稍后重试",
            detail=None,  # 生产环境不暴露堆栈
        ),
    )


# ========== 4. 注册函数 ==========

def register_exception_handlers(app) -> None:
    """在 FastAPI 应用上注册所有异常处理器。

    调用时机：app/main.py 中创建 FastAPI 实例后立刻调用。

    处理器优先级（FastAPI 按注册顺序倒序匹配，先注册的最后被尝试）：
      1. 业务异常（最具体）
      2. HTTP 异常
      3. 校验异常
      4. 未处理异常（最通用，最后一道防线）
    """
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # ④ 最通用的兜底处理器（最先注册，最后被匹配）
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ③ FastAPI 校验异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # ② HTTP 异常（如 404 Not Found）
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # ① 业务异常（最后注册，最先被匹配）
    app.add_exception_handler(BusinessException, business_exception_handler)
