"""健康检查接口。

提供系统运行状态查询，用于：
- 开发调试
- 监控系统（Prometheus、Zabbix 等）
- 负载均衡器健康检查
- K8s 探针（liveness/readiness）
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health() -> dict[str, str]:
    """健康检查。

    Returns:
        {"status": "ok"} 表示服务正常
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    """就绪检查（K8s 用）。

    检查依赖服务是否可用（数据库、缓存等）。
    如果返回非 200，K8s 不会把流量打到这个 Pod。
    """
    # MVP 阶段简化为返回 ok
    # 后续可加上数据库连接检查、向量库连接检查等
    return {"status": "ready"}
