"""LangGraph 工作流定义。

这是整个 AI 助手的核心——状态图编排。

工作流路由图：
  input_processor
       ↓
  intent_classifier
       ↓
  ┌────────┼────────┐
  ↓        ↓        ↓
general  rag      tool       ← 三条路由，互斥
  ↓    retriever  executor
  ↓        ↓        ↓
  └────────┼────────┘
           ↓
  response_generator
           ↓
  escalation_checker
       ↓     ↓
  end_normal  end_escalated
"""

from typing import TypedDict, Literal

import re

import structlog
from langgraph.graph import StateGraph, END

from app.llm.factory import get_llm
from app.rag.vector_store import vector_store
from app.core.config import settings

logger = structlog.get_logger(__name__)


def _strip_markdown(text: str) -> str:
    """去除 Markdown 格式化，保留纯文本内容。

    小模型（如 qwen3.5:2b）对 Markdown 表格（| 管道符）等格式
    处理不稳定。去格式化后 LLM 回复更稳定。

    处理规则：
    - 表格行：提取单元格文本（去掉 | 和空格），转为逗号分隔
    - 删除分隔线行（---）
    - 删除标题标记（## 等），只保留标题文字
    - 删除加粗标记（**）
    - 列表标记（-、*）保持原样，LLM 能理解
    """
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()

        # 跳过空行（不保留，避免大量空行）
        if not stripped:
            continue

        # 跳过表格分隔行（全是 | - : 空格）
        if re.match(r"^[\|\-\s:]+$", stripped):
            continue

        # 处理表格行：提取单元格文本，转为逗号分隔
        if stripped.startswith("|"):
            cells = stripped.strip("|").split("|")
            cell_texts = [c.strip() for c in cells if c.strip()]
            if cell_texts:
                cleaned.append(", ".join(cell_texts))
            continue

        # 跳过分隔线
        if re.match(r"^[-=]{3,}$", stripped):
            continue

        # 去除标题标记（## 内容 → 内容）
        line = re.sub(r"^#+\s*", "", line)

        # 去除加粗标记
        line = line.replace("**", "")

        # 去除行内代码标记
        line = line.replace("`", "")

        cleaned.append(line)

    return "\n".join(cleaned)


# ========== 1. State 定义 ==========
# State 是贯穿整个工作流的数据载体
# 每个节点读取 State 中的字段，处理后写回 State


class WorkflowState(TypedDict):
    """LangGraph 工作流状态。

    类比：React 中的 Context / Redux Store
    所有节点共享这个状态对象。
    """

    # ---- 用户输入 ----
    user_question: str  # 用户的问题
    session_id: str  # 会话ID

    # ---- AI 处理中间结果 ----
    intent: Literal["presales", "aftersales", "transaction", "general"]  # 意图分类
    retrieved_docs: list[dict]  # RAG 检索到的文档
    tool_result: str  # 工具调用的结果（查物流等）

    # ---- 最终输出 ----
    answer: str  # 给用户看的最终回答
    need_human: bool  # 是否需要转人工

    # ---- 调试信息 ----
    debug_info: str  # 调试信息


# ========== 2. 节点函数 ==========
# 每个节点是一个纯函数，接收 State，返回更新后的 State 的增量
# 你可以理解为 Redux 的 reducer


async def node_input_processor(state: WorkflowState) -> dict:
    """节点1：输入处理。

    清洗用户输入：去首尾空格、截断过长内容。
    """
    question = state["user_question"].strip()

    if len(question) > 2000:
        logger.warning("输入过长，已截断", original_length=len(question))
        question = question[:2000]

    return {
        "user_question": question,
        "debug_info": f"输入处理完成: {len(question)} 字符",
    }


async def node_intent_classifier(state: WorkflowState) -> dict:
    """节点2：意图分类。

    采用「关键词优先 + LLM 兜底」的混合策略：
    1. 先用关键词匹配（快速、稳定、免费）
    2. 关键词匹配不到时，再用 LLM 分类（灵活、可扩展）

    这是企业级 AI 应用的常见做法——简单任务用规则，复杂任务用模型。
    """
    question = state["user_question"].lower()
    intent = None

    # ---- 第一步：关键词匹配（快速路径）----
    keyword_rules = [
        # transaction（事务类——最明确的意图，优先匹配）
        (["订单", "物流", "快递", "发货", "退款", "退货", "换货", "到货"], "transaction"),
        # aftersales（售后类）
        (
            [
                "不加热",
                "不工作",
                "坏了",
                "故障",
                "报错",
                "异响",
                "冒烟",
                "温度",
                "使用方法",
                "怎么用",
                "如何使用",
                "怎么清洗",
                "清洁",
                "保养",
                "多少度",
                "多长时间",
                "几分钟能熟",
                "预热",
                "菜单",
                "食谱",
                "做菜",
            ],
            "aftersales",
        ),
        # presales（售前类——了解产品、比较、选购）
        (
            [
                "多少钱",
                "价格",
                "对比",
                "推荐",
                "区别",
                "哪个好",
                "参数",
                "规格",
                "功率",
                "容量",
                "尺寸",
                "大小",
                "颜色",
                "保修",
                "介绍",
                "是什么",
                "怎么样",
                "好用吗",
                "值得买",
                "优缺点",
                "特点",
                "品牌",
                "型号",
                "系列",
                "适合",
                "适合谁",
            ],
            "presales",
        ),
    ]

    for keywords, matched_intent in keyword_rules:
        if any(kw in question for kw in keywords):
            intent = matched_intent
            matched_keywords = [kw for kw in keywords if kw in question]
            # need_rag: 只有 presales 和 aftersales 需要 RAG
            need_rag = matched_intent in ("presales", "aftersales")
            route_to = _intent_to_route(matched_intent)
            logger.info(
                "意图分类完成",
                method="keyword",
                intent=intent,
                matched_keywords=matched_keywords,
                need_rag=need_rag,
                route_to=route_to,
            )
            break

    # ---- 第二步：LLM 兜底（关键词没匹配到时）----
    if intent is None:
        llm = get_llm()

        system_prompt = """你是一个意图分类器。根据用户的问题，判断属于以下哪种意图：
- presales：售前咨询（了解产品、比较、推荐、价格、功能）
- aftersales：售后问题（使用方法、故障排除、退换货、清洁保养、菜谱）
- transaction：事务处理（查物流、查订单、退换货操作）
- general：通用闲聊（问候、感谢、非产品相关问题）
【重要】只返回一个英文单词作为意图标签。
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["user_question"]},
        ]

        response = await llm.chat(messages)
        intent = response.strip().lower()

        # 中文→英文映射
        intent_alias = {
            "售前": "presales",
            "售后": "aftersales",
            "事务": "transaction",
            "一般": "general",
            "通用": "general",
            "闲聊": "general",
        }
        intent = intent_alias.get(intent, intent)

        # 确保有效性
        valid_intents = ["presales", "aftersales", "transaction", "general"]
        if intent not in valid_intents:
            logger.warning("LLM返回无效意图，降级为general", raw_intent=intent)
            intent = "general"

        need_rag = intent in ("presales", "aftersales")
        route_to = _intent_to_route(intent)
        logger.info(
            "意图分类完成",
            method="llm",
            llm_raw_response=repr(response.strip()),
            intent=intent,
            need_rag=need_rag,
            route_to=route_to,
        )

    return {
        "intent": intent,
        "debug_info": state["debug_info"] + f" | 意图: {intent}",
    }


async def node_rag_retriever(state: WorkflowState) -> dict:
    """节点3-1：RAG 检索。

    从 Qdrant 向量库中检索与用户问题最相似的文档片段。
    只有 presales 和 aftersales 意图会走到这个节点。
    """
    intent = state["intent"]

    # 根据意图限定检索的文档分类
    # presales → 只搜售前文档；其他意图 → 搜全部（不限制 category）
    if intent == "presales":
        category = "presales"
    else:
        category = None

    docs = await vector_store.search(
        query=state["user_question"],
        top_k=5,
        category=category,
        score_threshold=0.3,
    )
    # 结构化日志：检索结果的关键指标
    logger.info(
        "RAG检索到的文档内容",
        query=state["user_question"],
        docs=docs,
        intent=intent,
    )

    # 结构化日志：检索结果的关键指标
    logger.info(
        "RAG检索完成",
        intent=intent,
        category=category,
        doc_count=len(docs),
        top_scores=[round(d["score"], 4) for d in docs[:3]],  # 前3个分数
        sources=[d["source"] for d in docs[:3]],  # 前3个来源
    )

    return {
        "retrieved_docs": docs,
        "debug_info": state["debug_info"] + f" | 检索到 {len(docs)} 个文档",
    }


async def node_tool_executor(state: WorkflowState) -> dict:
    """节点3-2：工具调用（MVP 简化版）。

    只有 transaction 意图会走到这个节点。
    """
    mock_result = "订单查询结果：您的订单 AF20240711001 已发货，预计 3-5 个工作日送达。"

    logger.info("工具调用完成", method="mock")

    return {
        "tool_result": mock_result,
        "debug_info": state["debug_info"] + " | 工具调用完成（模拟）",
    }


async def node_general_responder(state: WorkflowState) -> dict:
    """节点3-3：通用闲聊响应。

    只有 general 意图会走到这个节点。
    直接生成回复，不经过 RAG 检索，节省一次向量计算 + 一次 Qdrant 查询。
    """
    llm = get_llm()

    system_prompt = """你是一个空气炸锅产品的智能助手，性格友好、热情。

用户正在进行闲聊或打招呼，请用自然、友好的语气回复。
保持简洁，1-2句话即可。如果用户有潜在的产品咨询需求，可以顺势引导。
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state["user_question"]},
    ]

    response = await llm.chat(messages)

    # 兜底
    if not response.strip():
        response = "您好！我是空气炸锅智能助手，请问有什么可以帮助您的？"
        logger.warning("通用回复LLM返回空，使用兜底回复")

    logger.info(
        "通用闲聊回复完成",
        answer_length=len(response),
    )

    return {
        "answer": response,
        "need_human": False,  # 闲聊永远不需要转人工
        "debug_info": state["debug_info"] + f" | 闲聊回复完成 ({len(response)} 字符)",
    }


async def node_response_generator(state: WorkflowState) -> dict:
    """节点4：回答生成。

    根据检索结果（或工具调用结果），生成最终的自然语言回答。
    这是第二次 LLM 调用。
    general 意图不会走到这里（由 general_responder 直接处理）。

    MVP 阶段知识库可能为空，因此采用动态策略：
    - 有参考资料时：要求严格依据资料回答
    - 无参考资料时：允许 LLM 基于通用知识友好回答
    """
    llm = get_llm()

    # ---- 构造上下文 ----
    docs_text = ""
    has_docs = bool(state.get("retrieved_docs"))
    has_tool = bool(state.get("tool_result"))

    if has_docs:
        for i, doc in enumerate(state["retrieved_docs"]):
            # 去除 Markdown 格式（小模型对表格格式不稳定）
            clean_text = _strip_markdown(doc["text"])
            docs_text += f"[参考资料{i + 1}] (来源: {doc['source']})\n{clean_text}\n\n"
    else:
        docs_text = "（暂无参考资料）"

    # 动态系统 Prompt：有文档时严格依据文档，无文档时允许通用知识
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
{state.get("tool_result", "") or "（无）"}
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
        {"role": "user", "content": state["user_question"]},
    ]

    response = await llm.chat(messages)

    # 兜底：LLM 返回空时（小模型偶尔发生），根据意图返回友好提示
    if not response.strip():
        intent = state.get("intent", "general")
        # 引导用户换一种问法，而不是直接说"抱歉"
        response = "抱歉，我暂时没能理解您的问题。您可以尝试换个方式描述，比如：\n- 空气炸锅怎么清洗？\n- 空气炸锅可以做哪些菜？\n- 推荐一款好用的空气炸锅"
        logger.warning("LLM返回空，使用兜底回复", intent=intent)

    logger.info(
        "回答生成完成",
        answer_length=len(response),
        has_docs=has_docs,
        has_fallback=response.startswith("您好") or response.startswith("抱歉"),
    )

    return {
        "answer": response,
        "debug_info": state["debug_info"] + f" | 回答生成完成 ({len(response)} 字符)",
    }


async def node_escalation_checker(state: WorkflowState) -> dict:
    """节点5：升级检查。

    判断是否需要转人工客服。
    - 关键词触发：用户主动要求转人工/投诉
    - 业务判断：业务意图（presales/aftersales/transaction）但没有检索到任何参考文档
    - general 意图不参与此判断（由 general_responder 直接处理）
    """
    question = state["user_question"].lower()

    need_human = False

    # 用户主动要求转人工
    if any(kw in question for kw in ["转人工", "投诉", "人工客服"]):
        need_human = True
        reason = "keyword"
    # 业务意图但没有任何参考信息（RAG 没命中 + 无工具结果）
    elif not state.get("retrieved_docs") and not state.get("tool_result"):
        need_human = True
        reason = "no_docs"
    else:
        reason = "none"

    if need_human:
        logger.info("触发转人工", reason=reason)

    return {
        "need_human": need_human,
        "debug_info": state["debug_info"] + f" | 转人工: {need_human}",
    }


# ========== 3. 路由函数 ==========


def _intent_to_route(intent: str) -> str:
    """意图 → 路由目标 的映射。

    三条互斥路由：
    - general       → general_responder（直接回答，不走 RAG）
    - transaction   → tool_executor（工具调用，查物流等）
    - presales/ aftersales → rag_retriever（知识库检索）
    """
    if intent == "general":
        return "general_responder"
    elif intent == "transaction":
        return "tool_executor"
    else:
        return "rag_retriever"


def route_by_intent(state: WorkflowState) -> str:
    """根据意图路由到不同节点。"""
    intent = state.get("intent", "general")
    return _intent_to_route(intent)


def route_by_escalation(state: WorkflowState) -> Literal["end_normal", "end_escalated"]:
    """根据升级检查结果路由到不同出口。"""
    if state.get("need_human", False):
        return "end_escalated"
    return "end_normal"


# ========== 4. 构建状态图 ==========


async def create_workflow() -> StateGraph:
    """创建并编译 LangGraph 工作流。"""
    builder = StateGraph(WorkflowState)

    builder.add_node("input_processor", node_input_processor)
    builder.add_node("intent_classifier", node_intent_classifier)
    builder.add_node("rag_retriever", node_rag_retriever)
    builder.add_node("tool_executor", node_tool_executor)
    builder.add_node("general_responder", node_general_responder)
    builder.add_node("response_generator", node_response_generator)
    builder.add_node("escalation_checker", node_escalation_checker)

    builder.set_entry_point("input_processor")
    builder.add_edge("input_processor", "intent_classifier")

    # 意图分类后 → 三条互斥路由
    builder.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "rag_retriever": "rag_retriever",
            "tool_executor": "tool_executor",
            "general_responder": "general_responder",
        },
    )

    # RAG / 工具 → 回答生成 → 升级检查
    builder.add_edge("rag_retriever", "response_generator")
    builder.add_edge("tool_executor", "response_generator")
    builder.add_edge("response_generator", "escalation_checker")

    # 通用闲聊 → 直接结束（跳过升级检查）
    builder.add_edge("general_responder", END)

    # 升级检查 → 结束
    builder.add_conditional_edges(
        "escalation_checker",
        route_by_escalation,
        {"end_normal": END, "end_escalated": END},
    )

    return builder.compile()


# 全局单例
_workflow = None


async def get_workflow():
    """获取工作流实例（单例模式）。"""
    global _workflow
    if _workflow is None:
        _workflow = await create_workflow()
    return _workflow
