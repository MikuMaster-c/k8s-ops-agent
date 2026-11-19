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
from agent.schema import Diagnosis, Evidence, bad_citations, resolve

MAX_STEPS = 8  # 含 LLM 调用在内的总步数上限


class State(TypedDict, total=False):
    question: str
    pod: str
    model: str                               # 留空 = llm.CHAT_MODEL；只有对照实验会指定别的
    kind: Literal["knowledge", "incident"]   # 检索型 / 排障型
    evidence: list[dict]                     # [{source, quote, hint}]
    diagnosis: dict
    problems: list[str]


def classify(state: State) -> State:
    """不调模型：用关键词分流，省一次往返，也更容易测。

    分界只有一个判据：**有没有 Pod 名**。

    这里试过两版更"聪明"的规则，都被评测推翻了：
      - 把"为什么"当故障信号 → "为什么必须配 startupProbe"这类概念题被送去跑 kubectl
      - 把"OOM/重启"等术语当故障信号 → "OOMKilled 在哪个字段"同样被误判，
        因为这些词本身就是概念题的题干
    疑问词和术语名都说明不了该查哪里，只有"用户指了哪个 Pod"能。
    """
    return {"kind": "incident" if state.get("pod") else "knowledge"}


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


# prompt 单独抽成模块常量，是为了能在同一批用例上对比不同措辞的影响。
# 引用转述问题就是靠这个变量做 A/B 才定位清楚的——不给 prompt 留一个可替换的点，
# 就只能靠"感觉改好了"，而评测要的恰恰不是感觉。
# 结论：改措辞不管用（三种写法分别 7/12、6/12、1/12），真正的解法是改结构。
INSTRUCTIONS = (
    "你是 Kubernetes 排障助手。只能依据下面的证据作答。\n"
    "citations 至少给出 1 条，每条只填 evidence（证据前的方括号数字，从 0 开始）"
    "和 why（这条证据支持了哪个结论）。不要复制原文，原文由程序填。\n"
)


def build_prompt(question: str, evidence: list[Evidence]) -> str:
    block = "\n\n".join(f"[{i}] {e.source}\n{e.quote}\n提示：{e.hint}" for i, e in enumerate(evidence))
    return f"{INSTRUCTIONS}\n{block}\n\n问题：{question}"


def diagnose(state: State) -> State:
    evidence = [Evidence(**e) for e in state["evidence"]]
    prompt = build_prompt(state["question"], evidence)
    result = llm(model=state.get("model")).with_structured_output(Diagnosis).invoke(prompt)
    problems = [f"证据编号越界: {s}" for s in bad_citations(result, evidence)]
    return {"diagnosis": resolve(result, evidence), "problems": problems}


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


def run(question: str, pod: str = "", model: str | None = None) -> dict:
    return APP.invoke(
        {"question": question, "pod": pod, "model": model or "", "evidence": []},
        config={"recursion_limit": MAX_STEPS},
    )
