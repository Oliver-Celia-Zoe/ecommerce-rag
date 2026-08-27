"""知识库导入脚本。

将 data/knowledge/ 目录下的 Markdown 文件导入到 Qdrant 向量库。

完整流程：
1. 读取 Markdown 文件
2. 按标题拆分成小块（每个块是一个独立的语义单元）
3. 用 Embedding 模型把每块文本转为向量
4. 将向量存入 Qdrant，同时记录元数据

运行方式：
    uv run python -m scripts.import_knowledge
"""

import asyncio
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.knowledge_doc import KnowledgeDoc
from app.rag.vector_store import vector_store


# ========== 配置 ==========
KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "knowledge"
# 每个文本块的最大字符数（超过此长度会进一步拆分）
MAX_CHUNK_SIZE = 500
# 拆分时的重叠字符数（保证语义连续性）
CHUNK_OVERLAP = 50


# ========== 文本分块 ==========

def split_by_heading(text: str) -> list[str]:
    """按 Markdown 标题拆分文本。

    把一篇长文档按 ## 标题拆成多个语义块。
    每个块是一个独立的知识单元。

    Args:
        text: Markdown 原始文本

    Returns:
        文本块列表
    """
    # 按 ## 级标题拆分（保留标题作为上下文）
    # 例如: "## 使用方法\n第一步..." 和 "## 故障排除\n如果..."
    blocks = re.split(r"(?=\n## )", text)

    # 过滤空块和太短的块
    chunks = []
    for block in blocks:
        block = block.strip()
        if len(block) > 20:  # 过滤掉太短的块（没有实际内容）
            chunks.append(block)

    return chunks


def split_large_chunk(text: str, max_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """将过长的文本块进一步拆分。

    有些 Markdown 段落可能很长（比如食谱步骤），
    需要按固定长度拆分，并保留重叠部分保证语义连续。

    Args:
        text: 文本
        max_size: 最大字符数
        overlap: 重叠字符数

    Returns:
        拆分后的文本列表
    """
    if len(text) <= max_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += max_size - overlap  # 下一块从 (end - overlap) 开始，保留重叠

    return chunks


def process_document(text: str) -> list[str]:
    """处理完整文档：先按标题拆分，再把过长的块进一步拆分。"""
    heading_chunks = split_by_heading(text)
    final_chunks = []
    for chunk in heading_chunks:
        sub_chunks = split_large_chunk(chunk)
        final_chunks.extend(sub_chunks)
    return final_chunks


# ========== 主流程 ==========

async def import_file(
    file_path: Path,
    category: str,
    db_session,
) -> None:
    """导入单个文件到向量库。

    Args:
        file_path: Markdown 文件路径
        category: 文档分类（presales/aftersales/cookbook）
        db_session: 数据库会话（用于记录文档元数据）
    """
    filename = file_path.name
    text = file_path.read_text(encoding="utf-8")

    # 计算内容哈希（用于去重）
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # 检查是否已导入过（通过 content_hash 去重）
    stmt = select(KnowledgeDoc).where(KnowledgeDoc.content_hash == content_hash)
    result = await db_session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        print(f"   ⏭️  跳过（已存在）: {filename}")
        return

    # 拆分文本块
    chunks = process_document(text)
    print(f"   📄 处理: {filename} → {len(chunks)} 个文本块")

    # 生成文档 ID
    doc_id = str(uuid4())

    # 存入 Qdrant 向量库
    count = await vector_store.add_documents(
        chunks=chunks,
        doc_id=doc_id,
        category=category,
        source=filename,
    )

    # 存入 PostgreSQL（记录元数据）
    doc = KnowledgeDoc(
        id=doc_id,
        category=category,
        title=filename.replace(".md", "").replace("_", " "),
        content=text,
        content_hash=content_hash,
        chunk_count=count,
    )
    db_session.add(doc)
    await db_session.commit()

    print(f"   ✅ 入库成功: {filename} ({count} 个向量)")


async def main() -> None:
    """导入所有知识库文件。"""
    print("🚀 开始导入知识库...")
    print(f"   知识库目录: {KNOWLEDGE_DIR}")

    # 初始化 Qdrant Collection
    await vector_store.init_collection()
    print()

    # 定义文件和分类的映射
    # 文件名中包含 presales → presales 分类
    # 文件名中包含 aftersales → aftersales 分类
    # 其他 → cookbook 分类
    file_categories = {
        "product_intro": "presales",
        "aftersales": "aftersales",
        "recipes": "cookbook",
    }

    # 获取所有 Markdown 文件
    md_files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not md_files:
        print("   ⚠️  未找到 Markdown 文件")
        return

    # 逐个导入
    async with AsyncSessionLocal() as session:
        try:
            for md_file in md_files:
                # 根据文件名判断分类
                category = "cookbook"  # 默认分类
                for keyword, cat in file_categories.items():
                    if keyword in md_file.name.lower():
                        category = cat
                        break

                await import_file(md_file, category, session)

            print("\n✅ 知识库导入完成！")
        except Exception:
            await session.rollback()
            raise
        finally:
            await vector_store.close()


if __name__ == "__main__":
    asyncio.run(main())
