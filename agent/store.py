"""MySQL：把每次评测结果落库，用来回答"prompt 改完之后到底变好没有"。

一张表就够：每次跑评测写一行，通过率和失败用例 id 都存。
之所以不存 case 的详细输出：那是 report.json 的事，数据库只回答趋势。
"""
import json
import os

import pymysql

DDL = """
CREATE TABLE IF NOT EXISTS eval_runs (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  ran_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  prompt_tag  VARCHAR(64)  NOT NULL,
  total       INT          NOT NULL,
  passed      INT          NOT NULL,
  failed_ids  JSON         NULL
)
"""


def conn():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "agent_ops"),
        charset="utf8mb4",
    )


def record(prompt_tag: str, results: list[dict]) -> None:
    """results 的每一项形如 {"id": "c01", "pass": True, ...}"""
    passed = [r for r in results if r["pass"]]
    failed_ids = [r["id"] for r in results if not r["pass"]]
    with conn() as c, c.cursor() as cur:
        cur.execute(DDL)
        cur.execute(
            "INSERT INTO eval_runs (prompt_tag, total, passed, failed_ids) VALUES (%s,%s,%s,%s)",
            (prompt_tag, len(results), len(passed), json.dumps(failed_ids, ensure_ascii=False)),
        )


def history(limit: int = 10) -> list[dict]:
    """最近 N 次，用来在终端里看趋势。"""
    with conn() as c, c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT * FROM eval_runs ORDER BY id DESC LIMIT %s", (limit,))
        return cur.fetchall()
