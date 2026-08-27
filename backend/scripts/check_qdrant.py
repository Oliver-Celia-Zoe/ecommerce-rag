"""查看 Qdrant 向量库中的所有数据"""
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests

BASE_URL = "http://localhost:6333"
COLLECTION = "knowledge_chunks"

# 1. 查看集合信息
info = requests.get(f"{BASE_URL}/collections/{COLLECTION}").json()["result"]
print(f"📊 集合状态: {info['status']}")
print(f"📊 总点数: {info['points_count']}")
print(f"📊 向量维度: {info['config']['params']['vectors']['size']}")
print()

# 2. 分页浏览所有数据
offset = None
all_points = []
page = 0

while True:
    body = {"limit": 50, "with_payload": True, "with_vectors": False}
    if offset:
        body["offset"] = offset

    resp = requests.post(f"{BASE_URL}/collections/{COLLECTION}/points/scroll", json=body)
    data = resp.json()["result"]
    all_points.extend(data["points"])
    page += 1

    if not data.get("next_page_offset"):
        break
    offset = data["next_page_offset"]

print(f"📚 共检索到 {len(all_points)} 条数据（分 {page} 页）\n")

# 3. 分类统计
from collections import Counter
categories = Counter(p["payload"]["category"] for p in all_points)
print("📁 分类统计:")
for cat, count in categories.most_common():
    print(f"   {cat}: {count} 条")
print()

# 4. 按分类筛选展示
for cat in ["presales", "aftersales", "cookbook"]:
    cat_points = [p for p in all_points if p["payload"]["category"] == cat]
    if not cat_points:
        continue

    print(f"\n{'='*60}")
    print(f"📂 分类: {cat}（{len(cat_points)} 条）")
    print(f"{'='*60}")

    for i, p in enumerate(cat_points, 1):
        payload = p["payload"]
        text = payload["text"]
        preview = text[:200].replace("\n", " | ")
        point_id_short = p["id"][:8]
        print(f"\n  #{i} [point_id={point_id_short}] {payload['source']} 块#{payload['chunk_index']}")
        print(f"  内容: {preview}")
        if len(text) > 200:
            print(f"  ... (共 {len(text)} 字符)")

print("\n✅ 查询完成！")