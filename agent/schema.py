"""结构化输出与引用校验。

Evidence 由规则产出，模型只能引用不能新增；Citation 是模型的引用，
必须能在 Evidence 里找到同名的 source。这条约束是整个项目里
"AI Output Quality Assurance" 的最小可运行形态——不是形容词，是一次集合比对。
"""
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """一条可回查的原始事实。"""
    source: str = Field(description="可回查的字段路径，或文档 chunk id")
    quote: str = Field(description="原文摘录，不改写")
    hint: str = Field(default="", description="规则建议的下一步，模型可参考")


class Citation(BaseModel):
    source: str = Field(description="必须是给定 evidence 里的 source 之一")
    quote: str = Field(description="原样摘录，不改写")


class Diagnosis(BaseModel):
    verdict: str = Field(description="一句话结论")
    root_causes: list[str] = Field(description="按可能性排序，每条一句")
    citations: list[Citation] = Field(description="每条结论对应的证据")
    next_actions: list[str] = Field(description="下一步查什么、改什么")
    confidence: float = Field(ge=0, le=1)


def bad_citations(d: Diagnosis, evidence: list[Evidence]) -> list[str]:
    """返回引用了不存在证据的 source 列表。空列表 = 通过。"""
    allowed = {e.source for e in evidence}
    return [c.source for c in d.citations if c.source not in allowed]
