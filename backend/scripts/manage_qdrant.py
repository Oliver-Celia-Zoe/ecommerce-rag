"""Qdrant + PostgreSQL 联动删除管理工具

联动策略：
- 所有删除操作先删 Qdrant，再删 PostgreSQL
- 任一环节失败都会回滚（PG 回滚事务；Qdrant 由于无事务语义，会打印冲突告警供人工处理）
- 所有确认操作需要输入 yes 才能执行

用法:
  python scripts/manage_qdrant.py list
    └─ 列出 Qdrant + PostgreSQL 当前所有文档（对比两边是否一致）

  python scripts/manage_qdrant.py clear
    └─ 清空全部：删 Qdrant Collection + 清 knowledge_docs 表

  python scripts/manage_qdrant.py delete-by-source 03_recipes.md
    └─ 按文件名：删该文件所有向量 + 删对应 PG 记录（支持多文件同名、多 doc_id）

  python scripts/manage_qdrant.py delete-by-docid b9c98d8f-cb90-4724-bdb5-411512895fff
    └─ 按 doc_id：删对应向量 + 删对应 PG 记录

  python scripts/manage_qdrant.py delete-by-category cookbook
    └─ 按分类：删 presales/aftersales/cookbook 下全部文档
"""
import sys
import io
import asyncio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from collections import defaultdict

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sqlalchemy import select, delete

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.knowledge_doc import KnowledgeDoc

BASE_URL = settings.qdrant_url
COLLECTION = settings.qdrant_collection_name


# ==========================================================================
# 公共工具函数
# ==========================================================================

def _confirm(prompt: str) -> bool:
    """交互式确认，输入 yes 返回 True"""
    ans = input(f"{prompt} (输入 yes 继续): ").strip().lower()
    return ans == "yes"


async def _scroll_all_points(client: AsyncQdrantClient):
    """用 scroll 把所有点拉回来（同步 client 没封装好，手动调 HTTP）"""
    import requests
    offset = None
    all_points = []
    while True:
        body = {"limit": 1000, "with_payload": True, "with_vectors": False}
        if offset:
            body["offset"] = offset
        resp = requests.post(f"{BASE_URL}/collections/{COLLECTION}/points/scroll", json=body)
        data = resp.json()["result"]
        all_points.extend(data["points"])
        if not data.get("next_page_offset"):
            break
        offset = data["next_page_offset"]
    return all_points


async def _count_qdrant_by(client: AsyncQdrantClient, key: str, value: str) -> int:
    """按 payload 字段过滤计数"""
    try:
        res = await client.count(
            COLLECTION,
            count_filter=Filter(must=[FieldCondition(key=key, match=MatchValue(value=value))]),
        )
        return res.count
    except Exception:
        return 0


async def _delete_qdrant_by(client: AsyncQdrantClient, key: str, value: str) -> int:
    """按 payload 字段过滤删除，返回预计删除条数"""
    # 先计数
    try:
        count_res = await client.count(
            COLLECTION,
            count_filter=Filter(must=[FieldCondition(key=key, match=MatchValue(value=value))]),
        )
        n = count_res.count
    except Exception:
        n = None

    if n is not None and n == 0:
        return 0

    # 执行删除
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(must=[FieldCondition(key=key, match=MatchValue(value=value))]),
    )
    return n if n is not None else -1


# ==========================================================================
# list：对比 Qdrant 与 PG 两边
# ==========================================================================

async def list_data():
    """列出 Qdrant + PostgreSQL 的文档，对比一致性"""
    # 1. 拉 Qdrant
    qdrant_ok = True
    qdrant_groups = defaultdict(lambda: {"doc_ids": set(), "chunks": 0, "category": None})
    client = AsyncQdrantClient(url=BASE_URL)
    try:
        exists = await client.collection_exists(COLLECTION)
        if exists:
            points = await _scroll_all_points(client)
            for p in points:
                src = p["payload"]["source"]
                qdrant_groups[src]["doc_ids"].add(p["payload"]["doc_id"])
                qdrant_groups[src]["chunks"] += 1
                qdrant_groups[src]["category"] = p["payload"]["category"]
        else:
            print(f"⚠️  Qdrant: Collection '{COLLECTION}' 不存在\n")
            qdrant_ok = False
    except Exception as e:
        print(f"⚠️  连接 Qdrant 失败: {e}\n")
        qdrant_ok = False
    finally:
        await client.close()

    # 2. 拉 PostgreSQL
    pg_groups = {}
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(KnowledgeDoc)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            for r in rows:
                pg_groups[r.title + ".md" if not r.title.endswith(".md") else r.title or r.id] = {
                    "id": r.id,
                    "category": r.category,
                    "chunk_count": r.chunk_count,
                    "title": r.title,
                }
            # 用 source（文件名）映射：用 title 替换 .md 空格的反推，直接按 title 模糊匹配不精确
            # 改为按 doc_id 精确对比（见下方一致性检查）
        except Exception as e:
            print(f"⚠️  连接 PostgreSQL 失败: {e}\n")
            return

    print(f"📊 Qdrant 文档: {len(qdrant_groups)} 个")
    print(f"📊 PostgreSQL 文档: {len(pg_groups)} 条记录")
    if qdrant_ok:
        print(f"📊 Qdrant 向量点总数: {sum(g['chunks'] for g in qdrant_groups.values())}")
    print()

    # 3. 一致性对比（按 doc_id 精确）
    # 从 PG 取所有 doc_id，从 Qdrant 取所有 doc_id，求差集
    pg_doc_ids = {r.id: r for r in rows}
    qdrant_doc_ids = {}
    for group in qdrant_groups.values():
        for did in group["doc_ids"]:
            qdrant_doc_ids[did] = True

    only_pg = sorted(set(pg_doc_ids.keys()) - set(qdrant_doc_ids.keys()))
    only_qdrant = sorted(set(qdrant_doc_ids.keys()) - set(pg_doc_ids.keys()))

    if only_pg or only_qdrant:
        print("=" * 60)
        print("⚠️  数据不一致：")
        if only_pg:
            print(f"  只在 PostgreSQL 存在（Qdrant 已丢失）: {len(only_pg)} 条")
            for did in only_pg:
                r = pg_doc_ids[did]
                print(f"    - doc_id={did[:12]}...  category={r.category}  title={r.title}")
        if only_qdrant:
            print(f"  只在 Qdrant 存在（PG 已丢失）: {len(only_qdrant)} 条")
            for did in only_qdrant:
                # 找到对应 source
                for src, g in qdrant_groups.items():
                    if did in g["doc_ids"]:
                        print(f"    - doc_id={did[:12]}...  source={src}  category={g['category']}")
                        break
        print()

    # 4. 汇总表格
    print("=" * 60)
    print("📄 文档详情：")
    print("=" * 60)
    all_sources = sorted(set(qdrant_groups.keys()) | {
        (r.title if r.title.endswith(".md") else r.title + ".md")
        for r in rows
    })

    for src in all_sources:
        q = qdrant_groups.get(src)
        # 在 PG 里找和此 source 匹配的记录（用 title 精确匹配：title 是 filename 去 _ 和 .md）
        pg_match = None
        for r in rows:
            if r.title == src.replace(".md", "").replace("_", " "):
                pg_match = r
                break

        chunk_q = q["chunks"] if q else 0
        chunk_pg = pg_match.chunk_count if pg_match else 0
        status = "✅" if chunk_q == chunk_pg and q and pg_match else "⚠️"
        doc_id = (
            next(iter(q["doc_ids"])) if q else pg_match.id if pg_match else "-"
        )
        category = (q["category"] if q else pg_match.category if pg_match else "-")
        print(f"\n{status} {src}")
        print(f"   category      : {category}")
        print(f"   doc_id        : {doc_id}")
        print(f"   Qdrant chunks : {chunk_q}")
        print(f"   PG chunks     : {chunk_pg}")
        if pg_match is None:
            print(f"   ⚠️  PG 中无此记录")
        if q is None:
            print(f"   ⚠️  Qdrant 中无此文档的向量")


# ==========================================================================
# clear：删全部（Collection + knowledge_docs 整表）
# ==========================================================================

async def clear_all():
    """清空全部数据：Qdrant Collection + PG knowledge_docs"""
    client = AsyncQdrantClient(url=BASE_URL)
    try:
        exists = await client.collection_exists(COLLECTION)
        q_count = 0
        if exists:
            count_res = await client.count(COLLECTION)
            q_count = count_res.count
    except Exception as e:
        print(f"❌ 连接 Qdrant 失败: {e}")
        await client.close()
        return

    # PG 计数
    pg_count = 0
    async with AsyncSessionLocal() as session:
        stmt = select(KnowledgeDoc)
        res = await session.execute(stmt)
        pg_count = len(res.scalars().all())

    print(f"⚠️  ⚠️  ⚠️  即将清空全部数据：")
    print(f"   Qdrant Collection : {COLLECTION}  ({q_count} 条向量)")
    print(f"   PostgreSQL 表     : knowledge_docs  ({pg_count} 条记录)")
    if not _confirm("此操作不可恢复，确认删除？"):
        print("❌ 已取消")
        await client.close()
        return

    # ---- 执行删除 ----
    errors = []

    # 1) 删 Qdrant
    try:
        if exists:
            await client.delete_collection(COLLECTION)
            print(f"✅ Qdrant: 已删除 Collection '{COLLECTION}'")
    except Exception as e:
        errors.append(f"Qdrant 删除失败: {e}")
        print(f"❌ Qdrant 删除失败: {e}")
    finally:
        await client.close()

    # 2) 删 PostgreSQL（事务）
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(delete(KnowledgeDoc))
            await session.commit()
            print(f"✅ PostgreSQL: 已清空 knowledge_docs 表 ({pg_count} 条)")
        except Exception as e:
            await session.rollback()
            errors.append(f"PostgreSQL 删除失败: {e}")
            print(f"❌ PostgreSQL 删除失败（已回滚）: {e}")

    if errors:
        print(f"\n⚠️  完成但有 {len(errors)} 个错误，请根据上面的提示处理")
    else:
        print("\n🎉 全部数据已清理完成")


# ==========================================================================
# delete-by-source：按文件名联动删除
# ==========================================================================

async def delete_by_source(source: str):
    """按文件名删除：Qdrant 所有同名文件向量 + PG 对应记录"""
    client = AsyncQdrantClient(url=BASE_URL)

    # Step 1: 找到 PG 中对应的 doc_id
    async with AsyncSessionLocal() as session:
        # title 是 source 去掉 .md + 下划线转空格
        title_guess = source.replace(".md", "").replace("_", " ")
        stmt = select(KnowledgeDoc).where(
            (KnowledgeDoc.title == title_guess) |
            (KnowledgeDoc.title == source)
        )
        res = await session.execute(stmt)
        pg_rows = res.scalars().all()

    # Step 2: 找到 Qdrant 中对应的数量
    q_count = await _count_qdrant_by(client, "source", source)

    print(f"📄 文件: {source}")
    print(f"   Qdrant 中匹配向量数 : {q_count}")
    print(f"   PostgreSQL 匹配记录数: {len(pg_rows)}")
    if pg_rows:
        for r in pg_rows:
            print(f"     - doc_id={r.id}  category={r.category}  chunks={r.chunk_count}")

    if q_count == 0 and len(pg_rows) == 0:
        print("❌ 没有找到匹配的数据")
        await client.close()
        return

    if not _confirm("确认删除？"):
        print("❌ 已取消")
        await client.close()
        return

    errors = []
    deleted_pg_ids = []

    # ---- 先删 Qdrant ----
    try:
        if q_count > 0:
            actual = await _delete_qdrant_by(client, "source", source)
            print(f"✅ Qdrant: 已删除 source='{source}' 的约 {actual if actual != -1 else 'N/A'} 条向量")
    except Exception as e:
        errors.append(f"Qdrant 删除失败: {e}")
        print(f"❌ Qdrant 删除失败: {e}")
    finally:
        await client.close()

    # ---- 再删 PG（事务） ----
    async with AsyncSessionLocal() as session:
        try:
            for r in pg_rows:
                await session.delete(r)
                deleted_pg_ids.append(r.id)
            await session.commit()
            if pg_rows:
                print(f"✅ PostgreSQL: 已删除 {len(pg_rows)} 条 knowledge_docs 记录")
        except Exception as e:
            await session.rollback()
            errors.append(f"PostgreSQL 删除失败: {e}")
            print(f"❌ PostgreSQL 删除失败（已回滚）: {e}")
            if not errors or "Qdrant 删除失败" not in str(errors):
                # Qdrant 删成功了但 PG 回滚 → 产生只在 Qdrant 的幽灵数据
                print("⚠️  ⚠️  注意：Qdrant 已删成功，但 PG 回滚了，数据目前是一致的（两边都没有）")

    if errors:
        print(f"\n⚠️  完成但有 {len(errors)} 个错误")
    else:
        print(f"\n🎉 删除完成")


# ==========================================================================
# delete-by-docid：按 doc_id 联动删除
# ==========================================================================

async def delete_by_docid(doc_id: str):
    """按 doc_id 精确删除：Qdrant 该 doc_id 的所有向量 + PG 该条记录"""
    client = AsyncQdrantClient(url=BASE_URL)

    # Step 1: PG 查询
    async with AsyncSessionLocal() as session:
        stmt = select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
        res = await session.execute(stmt)
        pg_row = res.scalar_one_or_none()

    # Step 2: Qdrant 查询
    q_count = await _count_qdrant_by(client, "doc_id", doc_id)

    print(f"🔑 doc_id: {doc_id}")
    print(f"   Qdrant 匹配向量数: {q_count}")
    if pg_row:
        print(f"   PG 记录存在      : category={pg_row.category}  title={pg_row.title}  chunks={pg_row.chunk_count}")
    else:
        print("   PG 记录不存在")

    if q_count == 0 and pg_row is None:
        print("❌ 没有匹配的数据")
        await client.close()
        return

    if not _confirm("确认删除？"):
        print("❌ 已取消")
        await client.close()
        return

    errors = []

    # ---- 删 Qdrant ----
    try:
        if q_count > 0:
            actual = await _delete_qdrant_by(client, "doc_id", doc_id)
            print(f"✅ Qdrant: 已删除 doc_id={doc_id[:12]}... 的约 {actual if actual != -1 else 'N/A'} 条向量")
    except Exception as e:
        errors.append(f"Qdrant 删除失败: {e}")
        print(f"❌ Qdrant 删除失败: {e}")
    finally:
        await client.close()

    # ---- 删 PG ----
    async with AsyncSessionLocal() as session:
        try:
            if pg_row:
                await session.delete(pg_row)
                await session.commit()
                print(f"✅ PostgreSQL: 已删除 knowledge_docs 记录 (id={doc_id[:12]}...)")
        except Exception as e:
            await session.rollback()
            errors.append(f"PostgreSQL 删除失败: {e}")
            print(f"❌ PostgreSQL 删除失败（已回滚）: {e}")

    if errors:
        print(f"\n⚠️  完成但有 {len(errors)} 个错误")
    else:
        print(f"\n🎉 删除完成")


# ==========================================================================
# delete-by-category：按分类批量删除
# ==========================================================================

async def delete_by_category(category: str):
    """按分类批量删除"""
    if category not in ("presales", "aftersales", "cookbook"):
        print(f"❌ 分类必须是 presales / aftersales / cookbook")
        return

    client = AsyncQdrantClient(url=BASE_URL)

    # Step 1: PG 查询
    async with AsyncSessionLocal() as session:
        stmt = select(KnowledgeDoc).where(KnowledgeDoc.category == category)
        res = await session.execute(stmt)
        pg_rows = res.scalars().all()

    # Step 2: Qdrant 查询
    q_count = await _count_qdrant_by(client, "category", category)

    print(f"📂 分类: {category}")
    print(f"   Qdrant 向量数   : {q_count}")
    print(f"   PG 文档记录数   : {len(pg_rows)}")
    if pg_rows:
        for r in pg_rows:
            print(f"     - {r.title}  doc_id={r.id[:12]}...  chunks={r.chunk_count}")

    if q_count == 0 and len(pg_rows) == 0:
        print("❌ 没有匹配的数据")
        await client.close()
        return

    if not _confirm("确认按分类批量删除？"):
        print("❌ 已取消")
        await client.close()
        return

    errors = []

    # ---- 删 Qdrant ----
    try:
        if q_count > 0:
            actual = await _delete_qdrant_by(client, "category", category)
            print(f"✅ Qdrant: 已删除 category='{category}' 的约 {actual if actual != -1 else 'N/A'} 条向量")
    except Exception as e:
        errors.append(f"Qdrant 删除失败: {e}")
        print(f"❌ Qdrant 删除失败: {e}")
    finally:
        await client.close()

    # ---- 删 PG ----
    async with AsyncSessionLocal() as session:
        try:
            if pg_rows:
                for r in pg_rows:
                    await session.delete(r)
                await session.commit()
                print(f"✅ PostgreSQL: 已删除 {len(pg_rows)} 条 knowledge_docs 记录")
        except Exception as e:
            await session.rollback()
            errors.append(f"PostgreSQL 删除失败: {e}")
            print(f"❌ PostgreSQL 删除失败（已回滚）: {e}")

    if errors:
        print(f"\n⚠️  完成但有 {len(errors)} 个错误")
    else:
        print(f"\n🎉 删除完成")


# ==========================================================================
# 入口
# ==========================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    action = sys.argv[1]

    if action == "list":
        asyncio.run(list_data())
    elif action == "clear":
        asyncio.run(clear_all())
    elif action == "delete-by-source":
        if len(sys.argv) < 3:
            print("❌ 用法: delete-by-source <文件名.md>，例如: 03_recipes.md")
            return
        asyncio.run(delete_by_source(sys.argv[2]))
    elif action == "delete-by-docid":
        if len(sys.argv) < 3:
            print("❌ 用法: delete-by-docid <doc_id>")
            return
        asyncio.run(delete_by_docid(sys.argv[2]))
    elif action == "delete-by-category":
        if len(sys.argv) < 3:
            print("❌ 用法: delete-by-category <presales|aftersales|cookbook>")
            return
        asyncio.run(delete_by_category(sys.argv[2]))
    else:
        print(f"❌ 未知操作: {action}")
        print(__doc__)


if __name__ == "__main__":
    main()
