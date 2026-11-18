# chaos

四个坑的复现记录。**坑三、坑四只要求讲得出来，不要求复现**——9 天里前两个能真跑就够。

## 坑一 · startupProbe 缺失 → CrashLoopBackOff ✅ 复现

`k8s/deployment.yaml` 出厂状态即为此坑。

```bash
kubectl get pods                  # CrashLoopBackOff
kubectl describe pod <name>       # 只有 Back-off restarting failed container
kubectl logs <name> --previous    # 才看到 SIGTERM / 启动日志被截断
```

要点：`describe` 的 Events 只说 back-off，不说谁杀的。`--previous` 是唯一能看到
上一次容器生命迹象的地方。修复 = 加 startupProbe。

## 坑二 · limits.memory 过小 → OOMKilled ✅ 复现

把 `limits.memory` 改到 `128Mi`，加载模型后即被杀。

```bash
kubectl describe pod <name> | grep -A5 "Last State"
```

要点：`State` 显示 `Running`，`Last State` 才显示 `Terminated: OOMKilled`。
这是人最容易漏看的位置。修复 = 提 limits，并设 requests=limits 进 Guaranteed QoS。

## 坑三 · 网关重试放大 QPS ⚠️ 只讲不复现

网关重试 3 次 = 单次失败产生 4 次下游请求。上游 QPS 500、失败率 10% 时，
下游实际承受 500×0.9 + 500×0.1×3 = 600，看起来只多 20%；
但失败率升到 50% 时变成 1000，翻倍——**失败率越高，放大越狠，正反馈**。
发现手段：Grafana 上入口 QPS 与下游 QPS 的比例曲线。修复 = 重试预算 + 指数退避 + 熔断。

## 坑四 · HPA 不扩容 ⚠️ 只讲不复现

CPU 30%、P95 8s、HPA 按 CPU 目标 70% → 永远不触发。瓶颈不在 CPU（可能在 I/O
或下游）。修复 = 换指标（队列长度、并发数），或用 `AverageValue` 而非 `Utilization`。
