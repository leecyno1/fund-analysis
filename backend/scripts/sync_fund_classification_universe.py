#!/usr/bin/env python3
"""把高置信度基金分类证据写入标准化研究表。

默认仅预览；传入 --apply 才写库。当前自动规则范围：
- 法定类型明确的货币基金；
- 合同基准明确为沪深300/中证500且名称不含增强策略的指数基金。

模糊类别不会猜测，也不会生成投资建议。
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env.local")
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

from database import get_engine
from services.fund_classification_ingestion_service import FundClassificationIngestionService


def load_funds(limit: int, fund_type: str) -> List[Dict[str, Any]]:
    where = [
        "(type IN ('货币型', '指数型', 'money', 'index') OR type ILIKE '%货币%' OR type ILIKE '%指数%')",
        "NOT (name ILIKE '%清算%' OR name ILIKE '%终止%' OR name ILIKE '%退市%')",
    ]
    if fund_type == "money":
        where.append("(type IN ('货币型', 'money') OR type ILIKE '%货币%')")
    elif fund_type == "index":
        where.append("(type IN ('指数型', 'index') OR type ILIKE '%指数%')")

    params: Dict[str, Any] = {}
    limit_clause = ""
    if limit > 0:
        params["limit"] = limit
        limit_clause = "LIMIT :limit"
    sql = text(f"""
        SELECT
            id::text AS id,
            wind_code,
            name,
            type,
            establishment_date,
            nav_date,
            raw_data
        FROM funds
        WHERE {" AND ".join(where)}
        ORDER BY wind_code ASC
        {limit_clause}
    """)
    with get_engine().connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql, params).fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description="同步高置信度基金分类标准化数据")
    parser.add_argument("--apply", action="store_true", help="实际写入；默认只预览")
    parser.add_argument("--limit", type=int, default=0, help="最多读取基金数；0 表示不限制")
    parser.add_argument("--fund-type", choices=("all", "money", "index"), default="all")
    parser.add_argument("--skip-samples", type=int, default=20, help="输出的跳过样本数量")
    args = parser.parse_args()

    funds = load_funds(max(args.limit, 0), args.fund_type)
    service = FundClassificationIngestionService()
    plan = service.build_plan(funds)
    output = {
        "mode": "apply" if args.apply else "dry_run",
        **plan["summary"],
        "eligible_examples": [
            {
                "canonical_code": group.get("canonical_code"),
                "canonical_name": group.get("canonical_name"),
                "share_codes": [share.get("wind_code") for share in group.get("shares") or []],
                "strategy_family_key": group.get("strategy_family_key"),
                "peer_group_key": group.get("peer_group_key"),
                "benchmark_code": group.get("benchmark_code"),
            }
            for group in plan["groups"][:20]
        ],
        "skipped_examples": plan["skipped"][:max(args.skip_samples, 0)],
    }
    if args.apply:
        output["write_result"] = service.apply_plan(plan)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
