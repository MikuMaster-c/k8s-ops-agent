"""结构化输出与引用校验。

Evidence 由规则产出，模型只能引用不能新增；Citation 是模型的引用，
必须能在 Evidence 里找到同名的 source。这条约束是整个项目里
"AI Output Quality Assurance" 的最小可运行形态——不是形容词，是一次集合比对。
"""
from pydantic import BaseModel, Field, field_validator


class Evidence(BaseModel):
    """一条可回查的原始事实。"""
    source: str = Field(description="可回查的字段路径，或文档 chunk id")
    quote: str = Field(description="原文摘录，不改写")
    hint: str = Field(default="", description="规则建议的下一步，模型可参考")


class Citation(BaseModel):
    """模型只给证据编号和理由，不给原文。

    第一版让模型复制原文当作 quote，再校验"是不是原文子串"。实测 qwen2.5 会把
    英文证据翻译成中文再当引用提交，换三种 prompt 措辞都没有改善（A/B 见 ai-usage.md），
    强约束那版还会让它陷入重复输出把 Ollama 打挂。
    所以改成结构上堵死：模型只说"我引用第几条"，原文由代码取出填进去。
    模型没有机会转述，因为转述的通道根本不存在。
    """
    evidence: int = Field(description="所引用证据的编号（证据前的方括号数字），从 0 开始")
    why: str = Field(description="这条证据支持了哪个结论，一句话")


class Diagnosis(BaseModel):
    verdict: str = Field(description="一句话结论")
    root_causes: list[str] = Field(description="按可能性排序，每条一句")
    citations: list[Citation] = Field(description="每条结论对应的证据编号")
    next_actions: list[str] = Field(description="下一步查什么、改什么")
    confidence: float = Field(ge=0, le=1, description="0 到 1 之间的小数")

    @field_validator("confidence", mode="before")
    @classmethod
    def _percent_to_ratio(cls, v):
        """模型常把置信度写成 85 而不是 0.85（qwen2.5 实测如此）。

        大于 1 就按百分制换算，而不是抛异常——一次格式化偏差不该让整次诊断作废。
        这是"AI 输出校验"的另一个真实样本：结构合法不等于数值合法。
        """
        if isinstance(v, (int, float)) and v > 1:
            return v / 100
        return v


def bad_citations(d: Diagnosis, evidence: list[Evidence]) -> list[str]:
    """返回越界或空引用的证据编号。空列表 = 通过。

    校验从"字符串是否出现在原文里"退化成"整数是否落在范围内"，
    更强也更快：模型没法靠改一个字蒙混，因为它根本不产出文本。

    空 citations 也算失败：改编号方案后模型一度干脆不引用直接作答，
    而没有引用的诊断就是这个项目要避免的那种"像样的答案"。
    """
    if not d.citations:
        return ["未给出任何引用"]
    n = len(evidence)
    return [str(c.evidence) for c in d.citations if not 0 <= c.evidence < n]


def resolve(d: Diagnosis, evidence: list[Evidence]) -> dict:
    """把编号换成原文。quote 由代码填，不经过模型。"""
    return {
        **d.model_dump(exclude={"citations"}),
        "citations": [
            {
                "source": evidence[c.evidence].source,
                "quote": evidence[c.evidence].quote,
                "why": c.why,
            }
            for c in d.citations
            if 0 <= c.evidence < len(evidence)
        ],
    }
