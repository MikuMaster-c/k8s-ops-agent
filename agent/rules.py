"""规则层：从 describe 文本里摘出异常与"该看哪个字段"。

存在的理由（面试第一层）：模型不知道 ImagePullBackOff 的下一步是看 Events
而不是看容器日志。规则负责发现，模型只负责解释给定证据。
"""
import re

# 每种异常状态 → 该回查的字段路径。source 会被模型用作 citation，
# 所以这里写的路径必须真的能在 describe 输出里找到。
STATE_HINTS: dict[str, tuple[str, str]] = {
    "CrashLoopBackOff": (
        ".status.containerStatuses[*].lastState.terminated.reason",
        "看 lastState.terminated 与退出码；若是启动慢被 liveness 杀，describe 只会显示 back-off，需要 logs --previous",
    ),
    "OOMKilled": (
        ".status.containerStatuses[*].lastState.terminated.reason",
        "对比 resources.limits.memory 与实际用量；OOMKilled 藏在 lastState 里，不在 State 里",
    ),
    "ImagePullBackOff": (
        ".status.containerStatuses[*].state.waiting.reason",
        "看 Events 里的拉取错误与 image 名；不是容器内部问题",
    ),
    "ErrImagePull": (
        ".status.containerStatuses[*].state.waiting.reason",
        "镜像名或仓库凭据问题，先看 Events 里的具体返回码",
    ),
    "Pending": (
        ".status.conditions[*]",
        "看 Events 里的 Insufficient cpu/memory 或 node affinity 不匹配",
    ),
    "CreateContainerConfigError": (
        ".status.containerStatuses[*].state.waiting.reason",
        "看引用的 ConfigMap/Secret 是否存在",
    ),
}

# 探针缺失不是状态异常，是清单层面的缺陷，单独走一遍
PROBE_CHECK = ("spec.template.spec.containers[*].livenessProbe", "未配 startupProbe 时，liveness 会从启动第 0 秒开始计时")


def scan_describe(pod: str, text: str) -> list[dict]:
    """在 describe 文本里找异常状态，返回 evidence 列表。"""
    found = []
    for state, (path, hint) in STATE_HINTS.items():
        if state in text:
            found.append({
                "source": f"{pod}{path}",
                "quote": _line_with(text, state),
                "hint": hint,
            })
    return found


def _line_with(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    return needle
