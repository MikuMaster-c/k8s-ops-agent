"""对照实验：同一批用例跑两个模型，比通过率与延迟。

回答一个问题——"级联值不值得上线"。如果 3B 的通过率掉得厉害、或者没有明显更快，
那就说明小模型那一跳只是多一次调用；如果它又准又快，再把 router 加回来。
先有数据再有结论，这是本项目对"为什么不上级联"的回答。

用法：
    python -m eval.compare                     # 7B 与 3B 各跑全量 20 条
    python -m eval.compare --limit 6           # 先跑前 6 条，看通路是否通

模型是串行跑的：先跑完一档再跑另一档。原因写在 agent/llm.py 里——
两个模型同时驻留会顶爆 8GB 显存，切换时的重载时间会污染延迟数据。
"""
import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np

from agent.llm import CHAT_MODEL, COMPARE_MODEL
from eval.run_eval import evaluate_case

CASES = Path(__file__).parent / "cases.jsonl"


def measure(model: str, cases: list[dict]) -> dict:
    """跑一档模型，返回通过数、失败 id 与逐步耗时。"""
    latencies, failed = [], []
    for c in cases:
        t0 = time.perf_counter()
        r = evaluate_case(c, model=model)
        latencies.append(time.perf_counter() - t0)
        if not r["pass"]:
            failed.append({"id": r["id"], "detail": r["detail"]})
        print(f"  {'PASS' if r['pass'] else 'FAIL'}  {r['id']}  {latencies[-1]:.1f}s")
    return {
        "model": model,
        "passed": len(cases) - len(failed),
        "total": len(cases),
        "failed": failed,
        "p50": round(statistics.median(latencies), 2),
        "p95": round(float(np.percentile(latencies, 95)), 2),
    }


def report(runs: list[dict]) -> None:
    print("\n模型\t通过率\tP50(s)\tP95(s)")
    for r in runs:
        print(f"{r['model']}\t{r['passed']}/{r['total']}\t{r['p50']}\t{r['p95']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条，0 表示全量")
    args = ap.parse_args()

    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]

    runs = []
    for model in (CHAT_MODEL, COMPARE_MODEL):
        print(f"\n== {model} ==")
        runs.append(measure(model, cases))

    report(runs)
    out = Path(__file__).parent / "compare.json"
    out.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {out}")


if __name__ == "__main__":
    main()
