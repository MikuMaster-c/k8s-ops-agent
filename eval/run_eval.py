"""评测：跑 cases.jsonl，输出通过率。

判分只有三类断言，不用 LLM-as-judge——judge 自己不稳定，回归就没意义了：
  1. 引用必须指向真实存在的 evidence（bad_citations 为空）
  2. 答案必须包含期望关键词之一
  3. manifest 类必须校验通过

用法：python -m eval.run_eval
"""
import json
import os
from pathlib import Path

from agent.checks import checks
from agent.graph import run
from agent.manifest import generate

CASES = Path(__file__).parent / "cases.jsonl"


def evaluate_case(case: dict) -> dict:
    if case["kind"] == "manifest":
        out = generate(case["requirement"])
        problems = checks(out["manifest"])
        hit = any(k in json.dumps(out["manifest"], ensure_ascii=False) for k in case["expect_keywords"])
        return {"id": case["id"], "pass": not problems and hit, "detail": problems or "ok"}

    out = run(case["question"], case.get("pod", ""))
    d = out.get("diagnosis") or {}
    text = json.dumps(d, ensure_ascii=False)
    no_bad = not out.get("problems")
    hit = any(k.lower() in text.lower() for k in case["expect_keywords"])
    return {
        "id": case["id"],
        "pass": bool(no_bad and hit and d),
        "detail": "citation 越界" if not no_bad else ("未命中关键词" if not hit else "ok"),
    }


def main() -> None:
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = [evaluate_case(c) for c in cases]
    passed = sum(r["pass"] for r in results)
    for r in results:
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['id']}  {r['detail']}")
    print(f"\n{passed}/{len(results)} = {passed / len(results):.0%}")
    (Path(__file__).parent / "report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 落库失败不阻断评测：数据库是用来回答趋势的，不是评测的前提
    try:
        from agent.store import record
        record(os.getenv("PROMPT_TAG", "manual"), results)
        print("recorded to eval_runs")
    except Exception as e:
        print(f"skip db: {e}")


if __name__ == "__main__":
    main()
