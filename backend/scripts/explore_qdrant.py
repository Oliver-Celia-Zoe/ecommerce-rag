"""Qdrant 向量库交互式探索脚本。

用法:
    cd backend
    uv run python -m scripts.explore_qdrant

可以修改下面的参数来观察不同查询条件下的结果差异。
"""

import asyncio

from app.rag.vector_store import vector_store
from app.rag.embedding import embedding_client


async def search_and_print(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    score_threshold: float = 0.0,
) -> None:
    """执行查询并打印结果。"""
    print(f"\n{'='*60}")
    print(f"🔍 查询: \"{query}\"")
    print(f"   top_k={top_k}, category={category}, threshold={score_threshold}")
    print(f"{'='*60}")

    docs = await vector_store.search(
        query=query,
        top_k=top_k,
        category=category,
        score_threshold=score_threshold,
    )

    if not docs:
        print("   ⚠️  未检索到任何文档")
        return

    print(f"   ✅ 检索到 {len(docs)} 个结果:\n")
    for i, doc in enumerate(docs, 1):
        # 截断文本，避免输出太长
        text = doc["text"].replace("\n", " ")[:120]
        if len(doc["text"]) > 120:
            text += "..."

        print(f"   [{i}] score={doc['score']:.4f} | {doc['category']} | {doc['source']}")
        print(f"       {text}")
        print()


async def demo_explain_embedding() -> None:
    """演示：文本如何变成向量。"""
    print("\n" + "="*60)
    print("📐 演示：Embedding 把文本转成向量")
    print("="*60)

    texts = [
        "空气炸锅不加热",
        "炸锅加热故障",
        "空气炸锅食谱",
        " completely unrelated text",
    ]

    # 获取第一个文本的向量（只展示前10个维度）
    vectors = await embedding_client.embed_texts(texts)

    for text, vector in zip(texts, vectors):
        # 计算和第一个文本的相似度
        similarity = cosine_similarity(vectors[0], vector)
        print(f"\n   \"{text}\"")
        print(f"   向量前10维: [{', '.join(f'{v:.3f}' for v in vector[:10])}]")
        print(f"   和\"空气炸锅不加热\"的相似度: {similarity:.4f}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


async def main() -> None:
    print("🚀 Qdrant 向量库交互式探索")
    print("=" * 60)

    # ========== 实验 1: 基础查询 ==========
    await search_and_print("空气炸锅不加热怎么办")

    # ========== 实验 2: 调整 top_k ==========
    print("\n" + "-"*60)
    print("📊 对比：top_k 参数的影响")
    print("-"*60)
    await search_and_print("空气炸锅怎么用", top_k=2)
    await search_and_print("空气炸锅怎么用", top_k=5)

    # ========== 实验 3: 调整 score_threshold ==========
    print("\n" + "-"*60)
    print("📊 对比：score_threshold 参数的影响")
    print("-"*60)
    await search_and_print("空气炸锅", score_threshold=0.0)
    await search_and_print("空气炸锅", score_threshold=0.7)

    # ========== 实验 4: category 过滤 ==========
    print("\n" + "-"*60)
    print("📊 对比：category 过滤的影响")
    print("-"*60)
    await search_and_print("空气炸锅", category=None)
    await search_and_print("空气炸锅", category="presales")
    await search_and_print("空气炸锅", category="aftersales")

    # ========== 实验 5: 语义相似度演示 ==========
    await demo_explain_embedding()

    # 关闭连接
    await vector_store.close()
    print("\n✅ 探索完成")


if __name__ == "__main__":
    asyncio.run(main())
