"""清单静态校验：AI 生成 YAML 的高频错误目录。

每一条都是一次真实会被 AI 写错的地方，也是面试里"我知道 AI 哪里会错"的证据。
不用 kubeconform 的原因（面试第三层）：它查 schema 合法性，查不出"schema 合法
但生产会出事"——缺 probe、无 limits、latest 标签都属于后者。
"""
from typing import Any


def checks(doc: dict) -> list[str]:
    """输入一个 Deployment 的 dict，返回问题列表。空列表 = 通过。"""
    problems: list[str] = []
    spec = (doc.get("spec") or {}).get("template", {}).get("spec", {})
    containers = spec.get("containers") or []

    if not containers:
        return ["spec.template.spec.containers 为空"]

    for c in containers:
        name = c.get("name", "?")
        image = c.get("image", "")

        if image.endswith(":latest") or ":" not in image.rsplit("/", 1)[-1]:
            problems.append(f"{name}: image 未固定版本（{image}）——latest 让回滚失去意义")

        res = c.get("resources") or {}
        if "requests" not in res:
            problems.append(f"{name}: 缺 resources.requests——调度器无法判断放得下放不下")
        if "limits" not in res:
            problems.append(f"{name}: 缺 resources.limits——OOMKilled 与 CPU 抢占都从这里来")
        elif "memory" in (res.get("limits") or {}) and "memory" not in (res.get("requests") or {}):
            problems.append(f"{name}: limits.memory 有而 requests.memory 无——QoS 会退化为 Burstable")

        if "livenessProbe" not in c:
            problems.append(f"{name}: 缺 livenessProbe")
        if "readinessProbe" not in c:
            problems.append(f"{name}: 缺 readinessProbe——未就绪的 Pod 会被放进 Endpoints")
        if "livenessProbe" in c and "startupProbe" not in c:
            problems.append(
                f"{name}: 有 liveness 无 startup——启动慢的服务会被反复杀死（CrashLoopBackOff 的经典成因）"
            )

        sc = c.get("securityContext") or {}
        if not sc.get("runAsNonRoot"):
            problems.append(f"{name}: 未声明 runAsNonRoot")
        if sc.get("allowPrivilegeEscalation"):
            problems.append(f"{name}: allowPrivilegeEscalation 为 true")

    return problems


def summarize(problems: list[str]) -> dict:
    """按类别聚合成一个可比较的分数，用于对比两轮生成的改进。"""
    kinds = {"probe": 0, "resource": 0, "image": 0, "security": 0}
    for p in problems:
        if "probe" in p.lower() or "startup" in p.lower():
            kinds["probe"] += 1
        elif "resources" in p or "limits" in p:
            kinds["resource"] += 1
        elif "image" in p:
            kinds["image"] += 1
        elif "runAsNonRoot" in p or "Privilege" in p:
            kinds["security"] += 1
    return {"total": len(problems), **kinds}
