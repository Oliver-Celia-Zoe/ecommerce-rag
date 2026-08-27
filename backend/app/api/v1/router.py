"""API v1 路由总入口。

把所有 v1 版本的子路由聚合到这里，main.py 只需要 import 这一个 router。
这样新增模块时，只需在这里注册，不需要改 main.py。
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, chat, auth

# 创建 v1 版本的总路由
api_router = APIRouter()

# 注册子路由
# prefix 表示该模块下所有路由的前缀
# tags 用于 Swagger UI 分组显示
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
