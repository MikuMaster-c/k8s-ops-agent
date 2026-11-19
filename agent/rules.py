"""规则层：从 describe 文本里摘出异常与"该看哪个字段"。

存在的理由（面试第一层）：模型不知道 ImagePullBackOff 的下一步是看 Events
而不是看容器日志。规则负责发现，模型只负责解释给定证据。
"""
import re

# 状态只从 State / Last State 块里读 Reason 行，不做全文包含匹配。
# 第一版是 `if state in text`，结果 ErrImagePull 命中 Events 里的
# "Error: ErrImagePull"，Error 命中无关行——source 路径和 quote 都是错的，
# 而这种错不会让评测失败（引用格式合法），只会让模型拿错证据。
STATE_BLOCK = re.compile(
    r"(State|Last State):\s+(\w+)\s*\n\s+Reason:\s+(\w+)",
)

# 每种异常状态 → (子字段, 下一步建议)。
# 子字段决定路径里是 state.waiting 还是 state.terminated；
# 前面的 state / lastState 由"它出现在哪个块里"决定，不能写死——
# 同一个 CrashLoopBackOff 出现在 State 和 Last State 里指的是两回事。
STATE_HINTS: dict[str, tuple[str, str]] = {
    "CrashLoopBackOff": (
        "waiting",
        "看 lastState.terminated 与退出码；若是启动慢被 liveness 杀，describe 只会显示 back-off，需要 logs --previous",
    ),
    "OOMKilled": (
        "terminated",
        "对比 resources.limits.memory 与实际用量；OOMKilled 藏在 lastState 里，不在 State 里",
    ),
    "ImagePullBackOff": (
        "waiting",
        "看 Events 里的拉取错误与 image 名；不是容器内部问题",
    ),
    "ErrImagePull": (
        "waiting",
        "镜像名或仓库凭据问题，先看 Events 里的具体返回码",
    ),
    "CreateContainerConfigError": (
        "waiting",
        "看引用的 ConfigMap/Secret 是否存在",
    ),
    # 容器以非 0 退出码结束时 describe 写的是 Error 而不是某个 BackOff 名。
    # 这是崩溃循环的早期形态：还没积累到 back-off 就已经是这个状态了。
    "Error": (
        "terminated",
        "非 0 退出码；看 logs --previous 拿上一次运行的输出，describe 不写崩溃原因",
    ),
}


def _path(where: str, subfield: str) -> str:
    """describe 的块名 → 字段路径。'Last State' 才是 lastState。"""
    prefix = "lastState" if where.startswith("Last") else "state"
    return f".status.containerStatuses[*].{prefix}.{subfield}.reason"

# 探针失败只出现在 Events 里，容器 State 仍是 Running——
# 所以不能靠状态匹配，要单独扫事件行。这是"状态正常但其实在反复被杀"的典型。
PROBE_EVENT = re.compile(r"^\s*Warning\s+Unhealthy\s+.*?((?:startup|liveness|readiness) probe failed:.*)$", re.I | re.M)


def scan_describe(pod: str, text: str) -> list[dict]:
    """在 describe 文本里找异常状态，返回 evidence 列表。

    按 source 去重：ErrImagePull 与 ImagePullBackOff 指向同一个字段路径，
    两个都出现时不该产出两条证据——模型会以为有两个独立问题。
    """
    found: dict[str, dict] = {}
    for where, _, reason in STATE_BLOCK.findall(text):
        if reason not in STATE_HINTS:
            continue
        subfield, hint = STATE_HINTS[reason]
        source = f"{pod}{_path(where, subfield)}"
        if source in found:
            continue
        found[source] = {
            "source": source,
            "quote": f"{where}: {reason}",
            "hint": hint,
        }

    m = PROBE_EVENT.search(text)
    if m:
        source = f"{pod}.events[probe-failed]"
        found[source] = {
            "source": source,
            "quote": m.group(1).strip(),
            "hint": "容器 State 看起来正常，但探针在反复失败并触发重启；检查探针端口与路径是否与容器实际监听的一致",
        }
    return list(found.values())
