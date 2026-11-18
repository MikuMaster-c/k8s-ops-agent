"""kubectl 只读封装。

三个约束，每个都是一句可讲的决策：
  1. 参数白名单：模型只能选动词和名字，不能拼任意命令行
  2. 超时：避免一个卡住的 describe 拖死整个请求
  3. 只读：没有 apply/delete/exec —— 诊断 agent 不应该有写权限
"""
import subprocess

# 白名单只覆盖诊断需要的三个动词
VERBS = {"get", "describe", "logs"}


def kubectl(args: list[str], timeout: int = 10) -> str:
    if not args or args[0] not in VERBS:
        return f"拒绝：只允许 {sorted(VERBS)}"
    try:
        out = subprocess.run(
            ["kubectl", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return (out.stdout or out.stderr)[-6000:]  # 截断，防止撑爆上下文
    except subprocess.TimeoutExpired:
        return f"超时：kubectl {' '.join(args)} 超过 {timeout}s"


def describe_pod(name: str, namespace: str = "default") -> str:
    return kubectl(["describe", "pod", name, "-n", namespace])


def pod_logs(name: str, namespace: str = "default", tail: int = 50) -> str:
    return kubectl(["logs", name, "-n", namespace, f"--tail={tail}"])
