"""临时测试脚本：验证 RAG 检索效果。"""
import asyncio
from app.rag.vector_store import vector_store

async def test():
    await vector_store.init_collection()
    queries = ["炸红薯要多少度", "第一次使用要做什么", "空气炸锅不加热怎么办"]
    for q in queries:
        print(f"========== 搜索: {q} ==========")
        results = await vector_store.search(q, top_k=2, score_threshold=0.0)
    for i, r in enumerate(results):
        score = r["score"]
        source = r["source"]
        category = r["category"]
        text = r["text"][:200]
        print(f"--- 结果 {i+1} (相似度: {score:.4f}) ---")
        print(f"来源: {source} | 分类: {category}")
        print(f"内容: {text}")
        print()
    print()
    await vector_store.close()

asyncio.run(test())
