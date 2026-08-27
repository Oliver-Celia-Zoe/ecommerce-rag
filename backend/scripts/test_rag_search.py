"""测试向量库检索：输入"介绍一下空气炸锅"，看 Qdrant 返回什么文档。

使用方法（在 backend/ 目录下执行）：
    .venv\Scripts\python.exe scripts\test_rag_search.py

不需要启动 FastAPI 服务器，直接连接 Qdrant 和 Ollama。
"""
import asyncio
import sys
import os

# 确保能 import backend 的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from app.rag.vector_store import vector_store

    query = "介绍一下空气炸锅"

    print(f"{'='*60}")
    print(f"查询: {query}")
    print(f"{'='*60}\n")

    # 测试1：不限分类（搜全部）
    print("--- 测试1：不限分类（category=None）---")
    docs = await vector_store.search(
        query=query,
        top_k=5,
        category=None,
        score_threshold=0.3,
    )
    print(f"返回文档数: {len(docs)}")
    for i, doc in enumerate(docs):
        print(f"\n[文档{i+1}] 相似度: {doc['score']:.4f} | 来源: {doc['source']}")
        print(f"内容预览: {doc['text'][:150]}...")
        print(f"{'-'*40}")

    # 测试2：只搜 presales 分类
    print(f"\n\n--- 测试2：只搜 presales 分类 ---")
    docs_presales = await vector_store.search(
        query=query,
        top_k=5,
        category="presales",
        score_threshold=0.3,
    )
    print(f"返回文档数: {len(docs_presales)}")
    for i, doc in enumerate(docs_presales):
        print(f"\n[文档{i+1}] 相似度: {doc['score']:.4f} | 来源: {doc['source']}")
        print(f"内容预览: {doc['text'][:150]}...")
        print(f"{'-'*40}")

    # 测试3：embedding 向量长度（确认 embedding 服务正常）
    from app.rag.embedding import embedding_client
    print(f"\n\n--- 测试3：Embedding 向量 ---")
    vector = await embedding_client.embed_query(query)
    print(f"向量维度: {len(vector)}")
    print(f"前5个值: {vector[:5]}")

    print(f"\n{'='*60}")
    print("测试完成！")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())