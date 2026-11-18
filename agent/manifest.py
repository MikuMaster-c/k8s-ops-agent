"""自然语言 → Deployment 清单 → 规则校验 → 带问题重新生成。

两轮上限是刻意的：第三轮之后模型通常不会改进，只会换一种说法，
而每一轮都是一次完整调用，成本线性上涨、收益趋零。
这个观察本身是面试里"条件变了怎么办"的答案——规模变大就先降轮次再加缓存。
"""
import yaml

from agent.checks import checks, summarize
from agent.llm import llm

SYSTEM = """你输出 Kubernetes Deployment YAML，只输出 YAML，不加解释。
必须包含：固定版本的 image 标签、resources.requests 与 limits、startupProbe、
readinessProbe、livenessProbe、securityContext.runAsNonRoot: true。"""


def generate(requirement: str, rounds: int = 2) -> dict:
    history = []
    problems: list[str] = []
    doc: dict = {}

    for i in range(rounds):
        hint = "" if not problems else "\n上一版存在以下问题，逐条修正：\n" + "\n".join(f"- {p}" for p in problems)
        raw = llm().invoke(f"{SYSTEM}\n\n需求：{requirement}{hint}").content
        doc = _parse(raw)
        problems = checks(doc)
        history.append({"round": i + 1, "problems": problems, "score": summarize(problems)})
        if not problems:
            break

    return {"manifest": doc, "history": history, "ok": not problems}


def _parse(raw: str) -> dict:
    # 模型常见错误之一：把 YAML 包在 ```yaml 里
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return {}


def check_only(path: str) -> list[str]:
    """不调模型的纯校验入口：yaml 文件 → 问题列表。"""
    with open(path, encoding="utf-8") as f:
        return checks(yaml.safe_load(f))
