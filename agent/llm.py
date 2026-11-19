"""唯一的模型出口。

换模型只改这里的常量。之所以集中在一个文件，是因为"模型调用散落各处"
会让评测失去意义——改一处 prompt 要跑一次全量回归，得先知道调用点在哪。

两档模型都跑在 4070 Laptop 的 8GB 显存上，但**不同时常驻**：
7B 是线上唯一一档，3B 只出现在 eval/compare.py 的对照实验里。
同时挂两个（4.7 + 1.9GB）会顶到桌面占掉的显存，Ollama 要么把层退回 CPU，
要么换出整个模型；下次调用要重新从磁盘加载 7B，那几秒比省下的解码时间还长。
这就是"级联没有上线"的实测依据，不是没做。
"""
from langchain_ollama import ChatOllama, OllamaEmbeddings

CHAT_MODEL = "qwen2.5:7b-instruct"     # Q4 约 4.7GB；跑之前关掉浏览器，把显存让出来
COMPARE_MODEL = "qwen2.5:3b-instruct"  # Q4 约 1.9GB；仅用于对照实验，不对外提供服务
EMBED_MODEL = "nomic-embed-text"       # 274MB，跟着谁在用就一起加载


def llm(temperature: float = 0.0, model: str | None = None) -> ChatOllama:
    return ChatOllama(model=model or CHAT_MODEL, temperature=temperature)


def embed() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBED_MODEL)
