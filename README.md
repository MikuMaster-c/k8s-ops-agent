# k8s-ops-agent

基于本地大模型的 Kubernetes 故障诊断服务。规则先产出证据，模型只在给定证据范围内作答，
每条结论都带可回查的字段路径。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/diagnose` | 输入 Pod 名与问题，返回结论、根因排序、引用与下一步动作 |
| POST | `/manifest` | 输入自然语言需求，生成 Deployment 并静态校验；校验不通过时带问题重生成，限两轮 |

## 快速开始

需要 Python 3.12 与 [Ollama](https://ollama.com)。`/diagnose` 的故障排查路径还需要 `kubectl`。

```bash
uv sync

ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

bash scripts/docs.sh              # 拉取 K8s 中文文档并建向量索引
uvicorn agent.app:app --reload    # http://127.0.0.1:8000/docs
```

浏览器打开 `/docs` 可以直接调接口。

部署到 kind 集群：

```bash
bash scripts/build.sh                       # 建集群、载镜像、apply
kubectl apply -f chaos/pods.yaml            # 可选：四个故障 Pod，用于故障排查用例
```

## 工作方式

1. **分类**：按请求是否指定 Pod 分流，指定则查集群，否则检索文档。这一步不调用模型。
2. **取证据**：集群侧解析 `kubectl describe`，把异常状态映射到对应字段路径；
   文档侧按余弦相似度取前四个片段。
3. **生成**：模型按固定结构输出结论、根因、下一步动作和证据编号。
   引用的原文由程序按编号回填，模型不生成引文文本。

## 评测

20 条用例，覆盖概念问答、故障排查和清单生成三类。判定用确定性断言：引用编号在范围内、
命中期望关键词、生成的清单通过静态校验。

```bash
python -m eval.run_eval     # 全量跑一遍
python -m eval.compare      # 同一批用例对照 7B 与 3B
```

当前结果（RTX 4070 Laptop 8GB，7B 常驻显存）：

| 模型 | 通过 | P50 | P95 |
|---|---|---|---|
| qwen2.5:7b-instruct | 15/20 | 7.3s | 9.0s |
| qwen2.5:3b-instruct | 3/20 | 4.0s | 9.6s |

## 已知限制

- 检索用朴素余弦，没有重排，少数问题的目标片段排在前四之外。
- 清单重生成不保证修好，两轮后仍不合格会原样返回并标出问题。
- 故障排查类用例依赖 `chaos/pods.yaml` 里那四个 Pod，集群里没有时查不到证据。
- 只在单卡 8GB 上验证过。7B 量化后占 4.8GB，两档模型不能同时常驻，
  所以没有启用模型级联。

## 文件

| 路径 | 内容 |
|---|---|
| `agent/` | 服务代码，模型调用集中在 `llm.py` |
| `eval/` | 用例、评测脚本、模型对照实验 |
| `chaos/` | 四类故障的复现清单与说明 |
| `k8s/` | 部署清单（出厂状态故意留了两处缺陷，用于复现） |
| `scripts/` | 建索引、构建部署 |
| `ai-usage.md` | 开发过程中 AI 参与的部分、出错方式和验证手段 |
