"""Qdrant 向量库封装。

负责：
1. 初始化 Collection（集合）
2. 写入向量数据（知识入库时用）
3. 相似度检索（RAG 检索时用）

Qdrant 核心概念：
- Collection = 文件夹（存放同一类向量）
- Point = 文件夹里的一张卡片（一个文本块 + 它的向量）
- Payload = 卡片上的标签（doc_id、category 等元数据）
"""

import asyncio
import logging
from uuid import uuid4

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

import structlog

from app.core.config import settings
from app.core.exceptions import VectorStoreException
from app.rag.embedding import embedding_client

logger = structlog.get_logger(__name__)
_retry_logger = logging.getLogger(__name__)

# Qdrant 异步客户端可能抛出的可重试异常类型
# httpx 相关异常：Qdrant 客户端底层使用 httpx，连接失败时抛出 httpx.ConnectError
_qdrant_retry_errors = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
    httpx.ConnectError,
    httpx.TimeoutException,
)


class VectorStore:
    """Qdrant 向量存储管理器。"""

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.qdrant_url)
        self.collection_name = settings.qdrant_collection_name

    async def init_collection(self, vector_size: int = 768) -> None:
        """初始化 Collection（如果不存在则创建）。

        Args:
            vector_size: 向量维度（nomic-embed-text 输出 768 维）
        """
        exists = await self.client.collection_exists(self.collection_name)

        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "创建 Qdrant Collection",
                collection=self.collection_name,
                vector_size=vector_size,
            )
        else:
            logger.info(
                "Qdrant Collection 已存在",
                collection=self.collection_name,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(_qdrant_retry_errors),
        before_sleep=before_sleep_log(_retry_logger, logging.WARNING),
        reraise=True,
    )
    async def add_documents(
        self,
        chunks: list[str],
        doc_id: str,
        category: str,
        source: str,
        product_id: str | None = None,
    ) -> int:
        """将文本块向量并存入 Qdrant。

        Args:
            chunks: 文本块列表（一篇文档被拆成多块）
            doc_id: 关联 PostgreSQL knowledge_docs 表的 ID
            category: 文档分类（presales/aftersales/cookbook）
            source: 来源文件名
            product_id: 关联商品 ID（可选）

        Returns:
            存入的向量数量
        """
        if not chunks:
            return 0

        try:
            # 1. 批量生成 Embedding 向量
            embeddings = await embedding_client.embed_texts(chunks)

            # 2. 构造 Qdrant Point 列表
            points = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point = PointStruct(
                    id=uuid4().hex,
                    vector=embedding,
                    payload={
                        "doc_id": doc_id,
                        "category": category,
                        "source": source,
                        "chunk_index": i,
                        "text": chunk,
                        "product_id": product_id,
                    },
                )
                points.append(point)

            # 3. 批量写入 Qdrant
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.info(
                "文档入库完成",
                doc_id=doc_id,
                chunk_count=len(points),
                category=category,
            )
            return len(points)
        except _qdrant_retry_errors as e:
            # 重试耗尽后会走到这里（reraise=True），转换为例外
            logger.error("文档入库失败", doc_id=doc_id, error=str(e))
            raise VectorStoreException(detail=str(e)) from e
        except Exception as e:
            logger.exception("文档入库意外异常", doc_id=doc_id, error=str(e))
            raise VectorStoreException(detail=str(e)) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(_qdrant_retry_errors),
        before_sleep=before_sleep_log(_retry_logger, logging.WARNING),
        reraise=True,
    )
    async def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """相似度检索。

        Args:
            query: 用户问题
            top_k: 返回最相似的 K 个结果
            category: 限定文档分类（如只搜售后文档）
            score_threshold: 最低相似度阈值（0-1），低于此分数的过滤掉

        Returns:
            检索结果列表，每项包含 text、score、source 等信息
        """
        try:
            # 1. 将用户问题转为向量
            query_vector = await embedding_client.embed_query(query)

            # 2. 构造过滤条件（如果指定了 category）
            search_filter = None
            if category:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="category",
                            match=MatchValue(value=category),
                        )
                    ]
                )

            # 3. 执行向量搜索
            response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=search_filter,
                score_threshold=score_threshold,
            )

            # 4. 格式化返回结果
            results = [
                {
                    "text": hit.payload["text"],
                    "score": hit.score,
                    "source": hit.payload.get("source", ""),
                    "category": hit.payload.get("category", ""),
                    "doc_id": hit.payload.get("doc_id", ""),
                }
                for hit in response.points
            ]

            logger.info(
                "向量检索完成",
                query=query[:50],
                result_count=len(results),
                category=category,
            )
            return results
        except _qdrant_retry_errors as e:
            logger.error("向量检索失败（可重试类错误）", query=query[:50], error=str(e))
            raise VectorStoreException(detail=str(e)) from e
        except Exception as e:
            logger.exception("向量检索意外异常", query=query[:50], error=str(e))
            raise VectorStoreException(detail=str(e)) from e

    async def close(self) -> None:
        """关闭 Qdrant 客户端连接。"""
        await self.client.close()


# 全局单例
vector_store = VectorStore()
