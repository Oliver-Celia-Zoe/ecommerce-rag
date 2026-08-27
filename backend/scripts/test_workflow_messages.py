"""测试完整链路但不调用 LLM，只输出最终传给 LLM 的 messages。

模拟 workflow 的完整执行流程：
1. 输入处理
2. 意图分类（用关键词，不调 LLM）
3. RAG 检索（调 Qdrant + Embedding，不调 LLM）
4. 构造 system prompt + user message
5. 打印最终 messages（不调 LLM）

使用方法（在 backend/ 目录下执行）：
    .venv\Scripts\python.exe scripts\test_workflow_messages.py

可选参数：
    .venv\Scripts\python.exe scripts\test_workflow_messages.py "你的问题"
"""

import asyncio
import sys
import os

# 确保能 import backend 的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入 workflow 中的关键函数
from app.graph.workflow import _strip_markdown, _intent_to_route
from app.rag.vector_store import vector_store
from app.core.config import settings


async def simulate_workflow(question: str) -> dict:
    """模拟 workflow 执行，但不调用 LLM。

    返回：
        - intent: 意图分类结果
        - route_to: 路由目标
        - need_rag: 是否需要 RAG
        - retrieved_docs: RAG 检索到的文档
        - messages: 最终传给 LLM 的消息列表
    """
    result = {
        "question": question,
        "intent": None,
        "route_to": None,
        "need_rag": None,
        "retrieved_docs": [],
        "messages": [],
    }

    # ===== 第1步：输入处理 =====
    question = question.strip()
    print(f"\n{'='*60}")
    print(f"第1步：输入处理")
    print(f"  问题: {question}")
    print(f"  长度: {len(question)} 字符")

    # ===== 第2步：意图分类（关键词匹配，不调 LLM）=====
    question_lower = question.lower()
    keyword_rules = [
        (["订单", "物流", "快递", "发货", "退款", "退货", "换货", "到货"], "transaction"),
        (["不加热", "不工作", "坏了", "故障", "报错", "异响", "冒烟", "温度",
          "使用方法", "怎么用", "如何使用", "怎么清洗", "清洁", "保养",
          "多少度", "多长时间", "几分钟能熟", "预热", "菜单", "食谱", "做菜"], "aftersales"),
        (["多少钱", "价格", "对比", "推荐", "区别", "哪个好", "参数", "规格",
          "功率", "容量", "尺寸", "大小", "颜色", "保修",
          "介绍", "是什么", "怎么样", "好用吗", "值得买", "优缺点", "特点",
          "品牌", "型号", "系列", "适合", "适合谁"], "presales"),
    ]

    intent = None
    matched_keywords = []

    for keywords, matched_intent in keyword_rules:
        if any(kw in question_lower for kw in keywords):
            intent = matched_intent
            matched_keywords = [kw for kw in keywords if kw in question_lower]
            break

    if intent is None:
        # LLM 兜底在真实流程中会调 LLM，这里模拟返回 general
        intent = "general"
        print(f"\n第2步：意图分类（模拟 LLM 兜底 → general）")
    else:
        print(f"\n第2步：意图分类（关键词匹配）")

    need_rag = intent in ("presales", "aftersales")
    route_to = _intent_to_route(intent)

    print(f"  intent: {intent}")
    print(f"  matched_keywords: {matched_keywords}")
    print(f"  need_rag: {need_rag}")
    print(f"  route_to: {route_to}")

    result["intent"] = intent
    result["route_to"] = route_to
    result["need_rag"] = need_rag

    # ===== 第3步：RAG 检索（真实调用 Qdrant + Embedding）=====
    if need_rag:
        category = "presales" if intent == "presales" else None

        print(f"\n第3步：RAG 检索")
        print(f"  category: {category}")
        print(f"  top_k: {settings.rag_top_k}")
        print(f"  score_threshold: {settings.rag_similarity_threshold}")
        print(f"  正在调用 Qdrant...")

        docs = await vector_store.search(
            query=question,
            top_k=settings.rag_top_k,
            category=category,
            score_threshold=settings.rag_similarity_threshold,
        )

        print(f"  返回文档数: {len(docs)}")
        for i, doc in enumerate(docs):
            print(f"  [文档{i+1}] score={doc['score']:.4f} source={doc['source']}")
            print(f"           text={doc['text'][:100]}...")

        result["retrieved_docs"] = docs
    elif intent == "transaction":
        print(f"\n第3步：跳过 RAG，走工具调用（模拟）")
        result["retrieved_docs"] = []
    else:
        print(f"\n第3步：跳过 RAG（general 意图直接回复）")
        result["retrieved_docs"] = []

    # ===== 第4步：构造 messages（不调 LLM）=====
    print(f"\n第4步：构造最终 messages")

    if intent == "general":
        # general 意图的 messages
        system_prompt = """你是一个空气炸锅产品的智能助手，性格友好、热情。

用户正在进行闲聊或打招呼，请用自然、友好的语气回复。
保持简洁，1-2句话即可。如果用户有潜在的产品咨询需求，可以顺势引导。
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        print(f"  [general 路径] system_prompt 长度: {len(system_prompt)}")

    else:
        # presales / aftersales / transaction 的 messages
        docs_text = ""
        has_docs = bool(result["retrieved_docs"])
        has_tool = intent == "transaction"
        tool_result = "订单查询结果：您的订单 AF20240711001 已发货，预计 3-5 个工作日送达。" if has_tool else ""

        if has_docs:
            for i, doc in enumerate(result["retrieved_docs"]):
                clean_text = _strip_markdown(doc["text"])
                docs_text += f"[参考资料{i + 1}] (来源: {doc['source']})\n{clean_text}\n\n"
        else:
            docs_text = "（暂无参考资料）"

        if has_docs or has_tool:
            system_prompt = f"""你是一个专业的空气炸锅产品助手。请根据以下参考资料回答用户的问题。

规则：
1. 优先根据参考资料回答，不要编造信息
2. 如果参考资料中没有相关信息，请诚实告知用户
3. 回答要简洁、专业、友好
4. 如果涉及温度和时间，请给出具体数值

参考资料：
{docs_text}

工具调用结果：
{tool_result or "（无）"}
"""
        else:
            system_prompt = f"""你是一个专业的空气炸锅产品助手。

当前知识库暂无该问题的相关文档，请你基于通用知识友好地回答用户。

规则：
1. 可以基于你的训练知识回答，但要确保信息准确
2. 如果不确定，请诚实告知用户
3. 回答要简洁、专业、友好
4. 如果涉及温度和时间，请给出具体数值
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        print(f"  system_prompt 长度: {len(system_prompt)} 字符")
        print(f"  user_message 长度: {len(question)} 字符")
        print(f"  has_docs: {has_docs}")
        print(f"  has_tool: {has_tool}")

    result["messages"] = messages

    return result


async def main():
    # 从命令行参数获取问题，默认用"介绍一下空气炸锅"
    question = sys.argv[1] if len(sys.argv) > 1 else "介绍一下空气炸锅"

    result = await simulate_workflow(question)

    # ===== 输出最终结果 =====
    print(f"\n{'='*60}")
    print(f"最终传给 LLM 的 messages（不调用 LLM）")
    print(f"{'='*60}")

    messages = result["messages"]

    print(f"\n消息数量: {len(messages)}")
    for i, msg in enumerate(messages):
        print(f"\n--- message[{i}] ---")
        print(f"role: {msg['role']}")
        print(f"content 长度: {len(msg['content'])} 字符")
        print(f"content 是否为空: {not msg['content'].strip()}")
        print(f"\ncontent 完整内容:")
        print(f"{'─'*40}")
        print(msg["content"])
        print(f"{'─'*40}")

    # ===== 规范性检查 =====
    print(f"\n{'='*60}")
    print(f"消息规范性检查")
    print(f"{'='*60}")

    issues = []
    for i, msg in enumerate(messages):
        if not msg.get("role"):
            issues.append(f"message[{i}] 缺少 role")
        if not msg.get("content"):
            issues.append(f"message[{i}] 缺少 content")
        elif not msg["content"].strip():
            issues.append(f"message[{i}] content 为空字符串")

    if len(messages) >= 2:
        if messages[0]["role"] != "system":
            issues.append("第一条消息不是 system 角色")
        if messages[1]["role"] != "user":
            issues.append("第二条消息不是 user 角色")

    if issues:
        print(f"发现问题 {len(issues)} 个:")
        for issue in issues:
            print(f"  ❌ {issue}")
    else:
        print("✅ 消息格式规范，无问题")

    print(f"\n{'='*60}")
    print(f"测试完成")
    print(f"测试完成")
    print(f"{messages}")


if __name__ == "__main__":
    asyncio.run(main())
