"""状态图：意图 → 检索 / 规则 → 综合 → 结构化输出。

两个设计点（面试第二层）：
  - 用条件边而不是一条直线：只有"是什么"类问题才需要检索文档，
    "为什么崩了"直接进规则 + 工具，省一次模型调用与一次检索。
  - 循环上限用 recursion_limit 交给 LangGraph，不在节点里手写计数器：
    图引擎本来就有这个护栏，自己再实现一遍是重复。
"""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agent import cache, rules, tools
from agent.llm import llm
from agent.rag import search
from agent.schema import Diagnosis, Evidence, bad_citations

MAX_STEPS = 8  # 含 LLM 调用在内的总步数上限


class State(TypedDict, total=False):
    question: str
    pod: str
    kind: Literal["knowledge", "incident"]   # 检索型 / 排障型
    evidence: list[dict]                     # [{source, quote, hint}]
    diagnosis: dict
    problems: list[str]


def classify(state: State) -> State:
    """不调模型：用关键词分流，省一次往返，也更容易测。"""
    q = state["question"]
    incident_words = ("为什么", "崩", "重启", "pending", "错误", "失败", "OOM", "crash")
    kind = "incident" if any(w.lower() in q.lower() for w in incident_words) else "knowledge"
    return {"kind": kind}


def gather_knowledge(state: State) -> State:
    return {"evidence": state.get("evidence", []) + search(state["question"])}


def gather_incident(state: State) -> State:
    """规则先跑，产出 evidence；模型拿到的只是这些 evidence。"""
    # describe 走 Redis 缓存 30 秒：规则和模型读同一份，避免同一请求里取两次
    text = cache.cached_describe(state["pod"], "default", tools.describe_pod)
    found = rules.scan_describe(state["pod"], text)
    if not found:
        # 没有命中规则时，把原始 describe 尾部交给模型，但标注来源
        found = [{"source": f"{state['pod']}.describe", "quote": text[-1500:], "hint": ""}]
    return {"evidence": found}


def diagnose(state: State) -> State:
    evidence = [Evidence(**e) for e in state["evidence"]]
    block = "\n\n".join(f"[{e.source}]\n{e.quote}\n提示：{e.hint}" for e in evidence)
    prompt = (
        "你是 Kubernetes 排障助手。只能依据下面的证据作答，"
        "每条结论都必须给出 citation，citation.source 必须是下列方括号中的路径之一。\n\n"
        f"{block}\n\n问题：{state['question']}"
    )
    result = llm().with_structured_output(Diagnosis).invoke(prompt)
    problems = bad_citations(result, evidence)
    return {"diagnosis": result.model_dump(), "problems": problems}


def route(state: State) -> str:
    return "gather_knowledge" if state["kind"] == "knowledge" else "gather_incident"


def build():
    g = StateGraph(State)
    g.add_node("classify", classify)
    g.add_node("gather_knowledge", gather_knowledge)
    g.add_node("gather_incident", gather_incident)
    g.add_node("diagnose", diagnose)

    g.add_edge(START, "classify")
    g.add_conditional_edges("classify", route)
    g.add_edge("gather_knowledge", "diagnose")
    g.add_edge("gather_incident", "diagnose")
    g.add_edge("diagnose", END)
    return g.compile()


APP = build()


def run(question: str, pod: str = "") -> dict:
    return APP.invoke(
        {"question": question, "pod": pod, "evidence": []},
        config={"recursion_limit": MAX_STEPS},
    )
