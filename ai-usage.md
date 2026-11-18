# ai-usage.md

记录 AI 生成了什么、错在哪、怎么验证。这是项目叙事的核心证据，不是可选文档。

## 记录格式

```
### 日期 · 对象
- 我让 AI 做什么：
- 它给出的：
- 我验证的方式（在哪一行、跑什么命令）：
- 它错在哪：
- 我怎么改的：
```

---

## 2026-11-22 · Deployment 清单

- **我让 AI 做什么**：按"FastAPI 服务，启动要 30 秒"生成 Deployment
- **它给出的**：完整 YAML，含 readiness / liveness，缺 startupProbe
- **我验证的方式**：`agent/checks.py` 跑一遍 + 实际 apply 到 kind
- **它错在哪**：liveness 从第 0 秒计时，30 秒启动期被反复杀死，`describe` 只显示
  `Back-off restarting failed container`，看不出是探针杀的；`kubectl logs --previous`
  才看到进程收到 SIGTERM
- **我怎么改的**：加 startupProbe（`failureThreshold: 30, periodSeconds: 1`），
  让 liveness 在 startup 通过后才开始计时

## 2026-11-24 · RAG 切分

- **我让 AI 做什么**：给一份 K8s 文档选切分参数
- **它给出的**：`chunk_size=1000, chunk_overlap=200`，理由是"通用推荐"
- **我验证的方式**：20 条评测里检索相关的那几条，看 top-4 是否命中
- **它错在哪**：文档里表格和代码块多，1000 字会把一个概念和它的示例切开，
  检索到概念但拿不到示例
- **我怎么改的**：降到 600，overlap 80，并按标题先切再递归切

## 2026-11-25 · 结构化输出

- **我让 AI 做什么**：写 `with_structured_output` 的 prompt
- **它给出的**：要求模型"给出引用"，但没限定引用来源
- **我验证的方式**：`bad_citations()` 统计越界引用
- **它错在哪**：模型会编造看起来很合理的字段路径（如 `.status.reason` 实际不存在）
- **我怎么改的**：prompt 里把 evidence 的 source 显式列成白名单，并加事后校验
