"""唯一的模型出口。

换模型只改这两个常量。之所以集中在一个文件，是因为"模型调用散落各处"
会让评测失去意义——改一处 prompt 要跑一次全量回归，得先知道调用点在哪。
"""
from langchain_ollama import ChatOllama, OllamaEmbeddings

CHAT_MODEL = "qwen2.5:7b-instruct"   # 4.7GB，CPU 可跑，4070 上更快
EMBED_MODEL = "nomic-embed-text"     # 274MB


def llm(temperature: float = 0.0) -> ChatOllama:
    return ChatOllama(model=CHAT_MODEL, temperature=temperature)


def embed() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBED_MODEL)
