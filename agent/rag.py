"""RAG：切分 / 检索 / 带来源返回。

不做向量库服务，直接用朴素余弦——两百条文档不需要 Milvus，
这个取舍本身就是面试里"为什么不选另一个"的答案。
"""
import json
import re
from pathlib import Path

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent.llm import embed

STORE = Path(__file__).parent.parent / "eval" / "index.json"

# kubernetes/website 的中文页把英文原文留在 <!-- ... --> 里，正文才是译文。
# 不剥掉的话索引里会混进近一半英文块：中文问题检索到英文证据，
# 模型只能读英文写中文——bad_quotes() 会把这种"转述"如实判为失败。
# 剥注释放在建索引时做，docs/ 保留原始素材，随时可以重建。
COMMENT = re.compile(r"<!--.*?-->", re.S)


def strip_comments(text: str) -> str:
    return COMMENT.sub("", text)


def build(docs_dir: Path) -> None:
    """把 docs_dir 下的 .md 切块并写入索引。"""
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        body = strip_comments(path.read_text(encoding="utf-8"))
        for i, piece in enumerate(splitter.split_text(body)):
            chunks.append({"id": f"{path.stem}#{i}", "text": piece})
    vectors = embed().embed_documents([c["text"] for c in chunks])
    STORE.write_text(
        json.dumps({"chunks": chunks, "vectors": vectors}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"indexed {len(chunks)} chunks")


def search(query: str, k: int = 4) -> list[dict]:
    data = json.loads(STORE.read_text(encoding="utf-8"))
    q = np.array(embed().embed_query(query))
    mat = np.array(data["vectors"])
    scores = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-9)
    top = np.argsort(scores)[::-1][:k]
    return [
        {
            "source": data["chunks"][i]["id"],
            "quote": data["chunks"][i]["text"],
            "hint": f"相似度 {scores[i]:.3f}",
        }
        for i in top
    ]
