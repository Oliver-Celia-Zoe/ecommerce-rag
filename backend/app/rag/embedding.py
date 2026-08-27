"""Embedding 嵌入模型封装。

Embedding 的作用：把文本转换为向量（数字数组），
让计算机能计算两段文本的语义相似度。

使用的模型：nomic-embed-text（通过 Ollama 本地运行）
向量维度：768
"""

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import VectorStoreException

logger = structlog.get_logger(__name__)


class EmbeddingClient:
    """Ollama Embedding 客户端。

    调用 Ollama 的 /api/embed 接口，将文本转为向量。
    """

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_embedding_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转为向量。

        Args:
            texts: 文本列表

        Returns:
            向量列表，每个向量是一个 float 数组
            例如: [[0.12, -0.34, ...], [0.11, -0.32, ...]]

        Raises:
            VectorStoreException: Ollama 连接失败或返回错误
        """
        payload = {
            "model": self.model,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.ConnectError as e:
            logger.error("Embedding 服务连接失败", error=str(e), model=self.model)
            raise VectorStoreException(detail=f"Embedding 服务连接失败: {e}") from e
        except httpx.TimeoutException as e:
            logger.error("Embedding 服务超时", error=str(e), model=self.model)
            raise VectorStoreException(detail=f"Embedding 服务超时: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "Embedding 服务返回错误",
                status_code=e.response.status_code,
                model=self.model,
            )
            raise VectorStoreException(detail=f"Embedding 服务返回 {e.response.status_code}") from e

        data = response.json()
        # Ollama 返回格式: {"model": "...", "embeddings": [[...], [...]]}
        return data["embeddings"]

    async def embed_query(self, text: str) -> list[float]:
        """将单条查询文本转为向量（用于检索时）。

        Args:
            text: 用户的问题

        Returns:
            向量（float 数组）
        """
        results = await self.embed_texts([text])
        return results[0]


# 全局单例（避免重复创建 httpx 客户端）
embedding_client = EmbeddingClient()