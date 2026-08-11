#!/usr/bin/env python3
"""为基金选择器同步真实基金经理关系和任期评价指标。"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List

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

from database import get_engine, init_database
from service_registry import get_strict_tushare_service
from services.fund_manager_tenure_sync_service import FundManagerTenureSyncService


def select_research_linked_codes(limit: int, missing_only: bool) -> List[str]:
    missing_sql = ""
    if missing_only:
        missing_sql = """
          AND (
            COALESCE(cardinality(fund.manager_ids), 0) = 0
            OR profile.manager_tenure_start IS NULL
            OR NOT EXISTS (
              SELECT 1 FROM metric_snapshots metric
              WHERE metric.target_type = 'fund'
                AND metric.target_id = linked.wind_code
                AND metric.metric_window = 'manager_tenure'
                AND metric.metric_name = 'tenure_days'
            )
          )
        """
    sql = text(f"""
        WITH linked AS (
          SELECT DISTINCT proposal->>'value' AS wind_code
          FROM research_reports report
          CROSS JOIN LATERAL jsonb_array_elements(COALESCE(report.review_proposals, '[]')) proposal
          WHERE proposal->>'kind' = 'fund'
            AND proposal->>'extraction_source' = 'tushare.fund_manager'
        )
        SELECT linked.wind_code
        FROM linked
        JOIN funds fund ON fund.wind_code = linked.wind_code
        JOIN fund_share_classes share
          ON share.wind_code = linked.wind_code AND share.status = 'active'
        JOIN fund_entities entity ON entity.id = share.entity_id
        JOIN strategy_families family ON family.id = entity.strategy_family_id
        LEFT JOIN fund_research_profiles profile ON profile.wind_code = linked.wind_code
        WHERE family.key NOT IN ('index_broad', 'index_fixed_income', 'cash_management')
          {missing_sql}
        ORDER BY linked.wind_code
        LIMIT :limit
    """)
    with get_engine().connect() as conn:
        return [row.wind_code for row in conn.execute(sql, {"limit": max(1, limit)}).fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description="同步真实基金经理关系和任期指标")
    parser.add_argument("--codes", default="", help="逗号分隔基金代码")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--throttle", type=float, default=0.15)
    args = parser.parse_args()

    init_database()
    codes = [item.strip().upper() for item in args.codes.split(",") if item.strip()]
    if not codes:
        codes = select_research_linked_codes(args.limit, missing_only=not args.include_existing)
    else:
        codes = codes[:max(1, args.limit)]
    if not codes:
        print("没有需要同步经理任期的基金。")
        return 0

    service = FundManagerTenureSyncService(get_strict_tushare_service())
    results = []
    for index, code in enumerate(codes, start=1):
        result = service.sync_fund(code)
        results.append(result)
        print(
            f"[{index}/{len(codes)}] {result['status'].upper()} {code} "
            f"经理={result.get('manager_count', 0)} 任期起点={result.get('manager_tenure_start') or '-'} "
            f"指标={result.get('tenure_metrics_saved', 0)}"
        )
        if args.throttle > 0:
            time.sleep(args.throttle)

    summary = {
        "requested": len(results),
        "synced": sum(item["status"] == "synced" for item in results),
        "skipped": sum(item["status"] == "skipped" for item in results),
        "failed": sum(item["status"] == "failed" for item in results),
        "tenure_metrics_saved": sum(item.get("tenure_metrics_saved", 0) for item in results),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
