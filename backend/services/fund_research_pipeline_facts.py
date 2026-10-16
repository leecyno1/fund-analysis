"""研究动线事实包取数（只读）。

每项事实独立 try/except：单点失败只降级对应步骤，不拖垮整个动线端点。
捕获率复用 MetricFactory.calculate_capture_ratios，基准缺失/样本不足时返回 None（不冒充）。
"""
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple


def _positive(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nav_basis_series(rows: List[Dict[str, Any]]) -> List[Tuple[Any, float]]:
    """基金净值序列：复权优先（覆盖>=90%）否则单位净值，与横向比较口径一致。"""
    parsed = []
    for row in rows:
        day = row.get("date") or row.get("trade_date")
        accum = _positive(row.get("accum_nav"))
        unit = _positive(row.get("nav") or row.get("unit_nav"))
        if day is not None and (accum is not None or unit is not None):
            parsed.append((day, unit, accum))
    if not parsed:
        return []
    use_accum = sum(1 for _, _, a in parsed if a is not None) >= max(2, int(len(parsed) * 0.9))
    series = {}
    for day, unit, accum in parsed:
        value = accum if use_accum else unit
        if value is not None:
            series[day] = value
    return sorted(series.items())


def _benchmark_series(rows: List[Dict[str, Any]]) -> List[Tuple[Any, float]]:
    series = {}
    for row in rows:
        day = row.get("date") or row.get("trade_date")
        bench = _positive(row.get("benchmark_nav"))
        if day is not None and bench is not None:
            series[day] = bench
    return sorted(series.items())


def _returns(points: List[Tuple[Any, float]]) -> List[float]:
    out = []
    for index in range(1, len(points)):
        prev, cur = points[index - 1][1], points[index][1]
        if prev > 0:
            out.append(cur / prev - 1.0)
    return out


def _capture_from_rows(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    from services.metric_factory import MetricFactory

    fund_points = _nav_basis_series(rows)
    bench_points = _benchmark_series(rows)
    if len(fund_points) < 2 or len(bench_points) < 2:
        return None
    fund_by_date = {d: v for d, v in fund_points}
    bench_by_date = {d: v for d, v in bench_points}
    shared = sorted(set(fund_by_date) & set(bench_by_date))
    if len(shared) < 2:
        return None
    aligned_fund = [(d, fund_by_date[d]) for d in shared]
    aligned_bench = [(d, bench_by_date[d]) for d in shared]
    return MetricFactory.calculate_capture_ratios(_returns(aligned_fund), _returns(aligned_bench))


def gather_pipeline_facts(wind_code: str, repo_getter: Callable[[str], Any]) -> Dict[str, Any]:
    facts: Dict[str, Any] = {"has_fund": False}
    code = str(wind_code or "").strip().upper()
    if not code:
        return facts

    def _repo(name: str):
        return repo_getter(name)

    try:
        fund = _repo("fund").get_fund_by_identifier(code)
        facts["has_fund"] = bool(fund)
        facts["_fund_row"] = fund or {}
    except Exception:
        facts["has_fund"] = False
        facts["_fund_row"] = {}

    try:
        ctx = _repo("fund_classification").get_classification_context(code) or {}
        facts["peer_group"] = ctx.get("peer_group_name") or ctx.get("peer_group_key")
        facts["benchmark_code"] = ctx.get("benchmark_code")
        facts["peer_group_size"] = int(ctx.get("peer_group_membership_count") or 0)
    except Exception:
        facts.setdefault("peer_group", None)
        facts.setdefault("peer_group_size", 0)

    try:
        styles = _repo("holding_style_snapshot").list_history(code, limit=6) or []
        facts["style_snapshots"] = len(styles)
    except Exception:
        facts["style_snapshots"] = 0

    try:
        end = date.today()
        start = end - timedelta(days=400)
        rows = _repo("nav").get_nav_series(code, start.isoformat(), end.isoformat()) or []
        facts["nav_observations"] = sum(1 for r in rows if _positive(r.get("nav") or r.get("unit_nav")))
        facts["benchmark_observations"] = sum(1 for r in rows if _positive(r.get("benchmark_nav")))
        capture = _capture_from_rows(rows)
        if capture and capture.get("up_capture_ratio") is not None:
            facts["capture"] = capture
    except Exception:
        facts.setdefault("nav_observations", 0)
        facts.setdefault("benchmark_observations", 0)

    try:
        history = _repo("holding").get_holdings_history(code) or []
        quarters = {str(r.get("quarter")) for r in history if r.get("quarter")}
        facts["holding_quarters"] = len(quarters)
        latest_quarter = _repo("holding").get_latest_weighted_quarter(code) or (max(quarters) if quarters else None)
        facts["holdings_count"] = len(_repo("holding").get_holdings(code, latest_quarter)) if latest_quarter else 0
    except Exception:
        facts.setdefault("holding_quarters", 0)
        facts.setdefault("holdings_count", 0)

    try:
        panel = _repo("metric_snapshot").get_latest_panel("fund", code) or []
        facts["peer_percentile_ready"] = any(
            str(m.get("metric_name")) == "annualized_return" and str(m.get("metric_window")) == "1y"
            for m in panel
        )
    except Exception:
        facts["peer_percentile_ready"] = False

    try:
        facts["has_score"] = bool(_repo("fund_evaluation_snapshot").list_history(code, limit=1))
    except Exception:
        facts["has_score"] = False

    try:
        from database import get_engine
        from sqlalchemy import text
        with get_engine().connect() as conn:
            facts["has_report"] = bool(conn.execute(
                text("SELECT 1 FROM research_reports WHERE :code = ANY(COALESCE(fund_ids, ARRAY[]::TEXT[])) LIMIT 1"),
                {"code": code},
            ).fetchone())
    except Exception:
        facts["has_report"] = False

    # 异常步：被动计数该基金未结告警，不触发扫描（§18.5 已知扫描子系统有缺陷，结果需复核）。
    try:
        fund_row = facts.get("_fund_row") or {}
        fund_uuid = str(fund_row.get("id") or "")
        engine = _repo("alert").engine
        from sqlalchemy import text
        with engine.connect() as conn:
            facts["anomaly_open"] = int(conn.execute(
                text(
                    "SELECT COUNT(*) FROM alert_events "
                    "WHERE (fund_id = :code OR (:fu <> '' AND fund_id = :fu)) "
                    "AND COALESCE(status,'') NOT IN ('resolved','closed','dismissed')"
                ),
                {"code": code, "fu": fund_uuid},
            ).scalar() or 0)
        facts["anomaly_status"] = "ok"
    except Exception:
        facts.setdefault("anomaly_open", None)
        facts["anomaly_status"] = "unknown"

    return facts
