"""检查 Qdrant 向量库中的重复数据"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
from collections import defaultdict

BASE_URL = "http://localhost:6333"
COLLECTION = "knowledge_chunks"

# 1. 拉取全部数据
offset = None
all_points = []
while True:
    body = {"limit": 100, "with_payload": True, "with_vectors": False}
    if offset:
        body["offset"] = offset
    data = requests.post(f"{BASE_URL}/collections/{COLLECTION}/points/scroll", json=body).json()["result"]
    all_points.extend(data["points"])
    if not data.get("next_page_offset"):
        break
    offset = data["next_page_offset"]

print(f"📚 总数据: {len(all_points)} 条\n")

# 2. 按 (source, chunk_index) 分组检查
groups = defaultdict(list)
for p in all_points:
    key = (p["payload"]["source"], p["payload"]["chunk_index"])
    groups[key].append(p)

print("=" * 60)
print("🔍 按 (来源文件 + 块索引) 分组检查:")
print("=" * 60)
duplicate_count = 0
for (src, idx), points in sorted(groups.items()):
    if len(points) > 1:
        duplicate_count += 1
        print(f"\n⚠️  [重复] {src} 块#{idx} 出现 {len(points)} 次:")
        for p in points:
            txt = p["payload"]["text"][:80].replace("\n", " ")
            print(f"   - ID={p['id'][:12]}...  内容开头: {txt}")

if duplicate_count == 0:
    print("\n✅ 没有发现 (source, chunk_index) 完全相同的重复数据")

# 3. 按 (category, source) 统计
src_groups = defaultdict(list)
for p in all_points:
    key = (p["payload"]["category"], p["payload"]["source"])
    src_groups[key].append(p["payload"]["chunk_index"])

print("\n" + "=" * 60)
print("📁 各文件块索引分布:")
print("=" * 60)
for (cat, src), indices in sorted(src_groups.items()):
    indices_sorted = sorted(indices)
    print(f"\n  [{cat}] {src}")
    print(f"  块索引: {indices_sorted}")
    print(f"  块数: {len(indices_sorted)}")
    # 检查索引是否连续（0,1,2,3...）
    expected = list(range(len(indices_sorted)))
    if indices_sorted != expected:
        print(f"  ⚠️  索引不连续! 期望: {expected}")

# 4. 检查 doc_id 是否一致
docid_groups = defaultdict(set)
for p in all_points:
    docid_groups[p["payload"]["source"]].add(p["payload"]["doc_id"])
print("\n" + "=" * 60)
print("📄 每个源文件对应的 doc_id:")
print("=" * 60)
for src, doc_ids in sorted(docid_groups.items()):
    if len(doc_ids) > 1:
        print(f"\n⚠️  {src} 有 {len(doc_ids)} 个不同的 doc_id:")
        for d in doc_ids:
            print(f"   - {d[:12]}...")
    else:
        print(f"  ✅ {src} -> doc_id: {list(doc_ids)[0][:12]}...")

print("\n✅ 检查完成！")
