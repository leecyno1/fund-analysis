#!/usr/bin/env python3
"""
同步基金筛选榜单所需的真实净值与滚动指标。

只做基金研究筛选数据底座：
- 拉取 Tushare fund_nav
- 写入 fund_nav
- 计算 3M/6M/1Y/3Y 滚动指标
- 回写 funds.performance_data / funds.risk_metrics / 最新净值

不生成报告，不输出申赎建议，不改变销售规则/R1-R5 门禁。
"""
import argparse
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
from repositories import get_fund_repo, get_metric_snapshot_repo, get_nav_repo
from services.rolling_metric_service import RollingMetricService
from services.tushare_service import TushareDataService


def log(message: str) -> None:
    print(message, flush=True)


def number_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number_value = float(value)
    except (TypeError, ValueError):
        return None
    if number_value != number_value or number_value in (float("inf"), float("-inf")):
        return None
    return number_value


def metric_by_window(panel: Iterable[Dict[str, Any]], window: str) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for row in panel:
        if row.get("metric_window") != window:
            continue
        metric_name = str(row.get("metric_name") or "")
        metric_value = number_or_none(row.get("metric_value"))
        if metric_name and metric_value is not None:
            result[metric_name] = metric_value
    return result


def latest_nav_payload(nav_series: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not nav_series:
        return {}
    latest = nav_series[-1]
    return {
        "nav": number_or_none(latest.get("unit_nav") or latest.get("nav")),
        "nav_date": latest.get("date"),
        "total_asset": number_or_none(latest.get("total_netasset") or latest.get("net_asset")),
    }


def build_fund_metric_payload(panel: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    one_year = metric_by_window(panel, "1y")
    three_year = metric_by_window(panel, "3y")
    six_month = metric_by_window(panel, "6m")

    performance_data = {
        "source": "metric_snapshots.tushare_fund_nav",
        "annualized_return_1y": one_year.get("annualized_return"),
        "return_1y": one_year.get("total_return"),
        "total_return": one_year.get("total_return"),
        "annualized_return_3y": three_year.get("annualized_return"),
        "return_3y": three_year.get("total_return"),
        "return_6m": six_month.get("total_return"),
        "sharpe_ratio": one_year.get("sharpe_ratio"),
        "positive_return_ratio": one_year.get("positive_return_ratio"),
        "observations_1y": one_year.get("observations"),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    risk_metrics = {
        "source": "metric_snapshots.tushare_fund_nav",
        "max_drawdown_1y": one_year.get("max_drawdown"),
        "max_drawdown": one_year.get("max_drawdown"),
        "annualized_volatility_1y": one_year.get("annualized_volatility"),
        "volatility_1y": one_year.get("annualized_volatility"),
        "sortino_ratio_1y": one_year.get("sortino_ratio"),
        "calmar_ratio_1y": one_year.get("calmar_ratio"),
        "max_drawdown_3y": three_year.get("max_drawdown"),
        "annualized_volatility_3y": three_year.get("annualized_volatility"),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    clean_performance = {key: value for key, value in performance_data.items() if value is not None}
    clean_risk = {key: value for key, value in risk_metrics.items() if value is not None}
    return {"performance_data": clean_performance, "risk_metrics": clean_risk}


def select_target_codes(
    limit: int,
    fund_type: str,
    missing_only: bool,
    min_age_days: int,
    include_exchange_funds: bool,
) -> List[str]:
    where = [
        "raw_data->>'source' = 'tushare'",
        "NOT (name ILIKE '%清算%' OR name ILIKE '%终止%' OR name ILIKE '%退市%')",
    ]
    if not include_exchange_funds:
        where.append("wind_code LIKE '%.OF'")
    params: Dict[str, Any] = {"limit": limit}
    if min_age_days > 0:
        where.append("establishment_date <= CURRENT_DATE - (:min_age_days * INTERVAL '1 day')")
        params["min_age_days"] = min_age_days
    if fund_type:
        where.append("type = :fund_type")
        params["fund_type"] = fund_type
    if missing_only:
        where.append("""
            NOT EXISTS (
              SELECT 1 FROM metric_snapshots ms
              WHERE ms.target_type = 'fund'
                AND ms.target_id = funds.wind_code
                AND ms.metric_window = '1y'
                AND ms.metric_name IN ('annualized_return', 'max_drawdown', 'sharpe_ratio')
            )
        """)

    sql = text(f"""
        SELECT wind_code
        FROM funds
        WHERE {" AND ".join(where)}
        ORDER BY
          CASE
            WHEN type IN ('股票型', '混合型', '债券型', '指数型') THEN 0
            ELSE 1
          END,
          establishment_date ASC NULLS LAST,
          wind_code ASC
        LIMIT :limit
    """)
    with get_engine().connect() as conn:
        return [row.wind_code for row in conn.execute(sql, params).fetchall()]


def sync_one_fund(
    data_service: TushareDataService,
    rolling_service: RollingMetricService,
    wind_code: str,
    start_date: date,
    end_date: date,
) -> Dict[str, Any]:
    fund_repo = get_fund_repo()
    nav_repo = get_nav_repo()
    metric_repo = get_metric_snapshot_repo()

    try:
        nav_series = data_service.get_fund_nav(
            wind_code,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
    except Exception as error:
        return {"wind_code": wind_code, "status": "skipped", "reason": f"净值不可用：{error}"}
    if len(nav_series) < 20:
        return {"wind_code": wind_code, "status": "skipped", "reason": f"净值点不足 {len(nav_series)}"}

    nav_repo.upsert_nav_series(wind_code, nav_series)
    rolling_result = rolling_service.calculate_and_save_for_fund(wind_code)
    panel = metric_repo.get_latest_panel("fund", wind_code)
    metric_payload = build_fund_metric_payload(panel)
    latest_payload = latest_nav_payload(nav_series)
    existing = fund_repo.get_fund(wind_code) or {}

    ok = fund_repo.upsert_fund(
        wind_code,
        {
            "name": existing.get("name") or wind_code,
            "type": existing.get("type") or "",
            "manager_ids": existing.get("manager_ids") or [],
            "nav": latest_payload.get("nav"),
            "nav_date": latest_payload.get("nav_date"),
            "total_asset": latest_payload.get("total_asset"),
            "establishment_date": existing.get("establishment_date"),
            "performance_data": metric_payload["performance_data"],
            "risk_metrics": metric_payload["risk_metrics"],
            "raw_data": {
                "source": "tushare",
                "ranking_metrics": {
                    "source": "tushare.fund_nav",
                    "synced_at": datetime.now(UTC).isoformat(),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "nav_points": len(nav_series),
                    "saved_metric_snapshots": rolling_result.get("saved", 0),
                },
            },
        },
    )

    return {
        "wind_code": wind_code,
        "status": "synced" if ok else "failed",
        "nav_points": len(nav_series),
        "saved_metric_snapshots": rolling_result.get("saved", 0),
        "latest_nav_date": latest_payload.get("nav_date"),
        "return_1y": metric_payload["performance_data"].get("return_1y"),
        "max_drawdown_1y": metric_payload["risk_metrics"].get("max_drawdown_1y"),
        "sharpe_1y": metric_payload["performance_data"].get("sharpe_ratio"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="同步基金排行所需净值和滚动指标")
    parser.add_argument("--codes", default="", help="逗号分隔基金代码；为空则从本地库选择缺指标基金")
    parser.add_argument("--limit", type=int, default=100, help="本次最多同步数量")
    parser.add_argument("--fund-type", default="", help="可选：股票型/混合型/债券型/指数型/货币型/QDII")
    parser.add_argument("--days", type=int, default=365 * 3 + 20, help="净值回看天数")
    parser.add_argument("--min-age-days", type=int, default=430, help="自动选样时要求基金至少成立天数")
    parser.add_argument("--throttle", type=float, default=0.2, help="每只基金之间的等待秒数")
    parser.add_argument("--include-existing", action="store_true", help="不跳过已有 1Y 指标基金")
    parser.add_argument("--include-exchange-funds", action="store_true", help="自动选样时包含 .SH/.SZ 交易所代码")
    parser.add_argument("--max-errors", type=int, default=10, help="连续或累计错误上限")
    args = parser.parse_args()

    init_database()
    data_service = TushareDataService(strict_no_mock=True)
    if data_service.mock_mode:
        raise RuntimeError("Tushare 未连接真实 API。请配置 TUSHARE_TOKEN 后重试。")

    codes = [code.strip().upper() for code in args.codes.split(",") if code.strip()]
    if not codes:
        codes = select_target_codes(
            limit=max(1, args.limit),
            fund_type=args.fund_type.strip(),
            missing_only=not args.include_existing,
            min_age_days=args.min_age_days,
            include_exchange_funds=args.include_exchange_funds,
        )
    else:
        codes = codes[: max(1, args.limit)]

    if not codes:
        log("没有需要同步的基金。")
        return 0

    end_date = date.today()
    start_date = end_date - timedelta(days=max(30, args.days))
    rolling_service = RollingMetricService()
    synced = 0
    skipped = 0
    failed = 0

    log(f"开始同步基金排行指标：{len(codes)} 只，窗口 {start_date.isoformat()} ~ {end_date.isoformat()}")
    for index, wind_code in enumerate(codes, start=1):
        try:
            result = sync_one_fund(data_service, rolling_service, wind_code, start_date, end_date)
            if result["status"] == "synced":
                synced += 1
                log(
                    f"[{index}/{len(codes)}] OK {wind_code} "
                    f"NAV={result['nav_points']} 1Y={result.get('return_1y')} "
                    f"DD={result.get('max_drawdown_1y')} Sharpe={result.get('sharpe_1y')}"
                )
            else:
                skipped += 1
                log(f"[{index}/{len(codes)}] SKIP {wind_code}: {result.get('reason')}")
        except Exception as error:
            failed += 1
            log(f"[{index}/{len(codes)}] FAIL {wind_code}: {error}")
            if failed >= args.max_errors:
                raise RuntimeError(f"错误数达到上限 {args.max_errors}") from error
        if args.throttle > 0:
            time.sleep(args.throttle)

    summary = {"requested": len(codes), "synced": synced, "skipped": skipped, "failed": failed}
    log(f"同步完成：{json.dumps(summary, ensure_ascii=False)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
