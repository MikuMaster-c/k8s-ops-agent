# agent-ops

一个跑在它自己要观测的集群上的 K8s 运维诊断 Agent。两层：

```
应用层  规则发现 → LLM 解释 → 结构化输出 → 评测回归
交付层  kind 部署 → 三层探针 → Prometheus 观测
```

## 两个入口

| 接口 | 做什么 | 值得看的设计 |
|---|---|---|
| `POST /diagnose` | 给一个 Pod 名和问题，返回带引用的诊断 | 规则先摘异常，模型只解释证据 |
| `POST /manifest` | 给自然语言需求，返回 Deployment 并按规则校验 | 校验失败带着问题重新生成，限两轮 |

## 为什么规则在前

模型不知道 `ImagePullBackOff` 该看 Events 而不是容器日志。所以 `rules.py` 用一张
状态到字段路径的映射表先产出 evidence，模型只在这些 evidence 里做解释。
引用越界由 `schema.bad_citations()` 事后检查——这就是本项目的
"AI output validation"，一次集合比对，不是形容词。

## 跑起来

```bash
uv sync
ollama pull qwen2.5:7b-instruct && ollama pull nomic-embed-text
bash scripts/docs.sh          # 拉 k8s 中文文档 → 建索引
uvicorn agent.app:app --reload

python -m eval.run_eval       # 20 条评测
bash scripts/build.sh         # kind 部署
```

## 三个刻意的减法

1. **没有向量库服务。** 两百条文档用朴素余弦，`rag.py` 里 8 行。Milvus 解决的是十万级以上的问题。
2. **没有重试和兜底。** 调用失败就是失败，评测会告诉你失败率。
3. **没有抽象层。** `kubectl` 一个函数、模型一个出口、数据源就两个。加抽象等有第三个数据源再说。
