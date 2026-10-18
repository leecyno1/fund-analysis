"""市场环境分段业绩：按基准 trailing 60 日收益分为牛/熊/震荡，统计分段胜率。

口径：每个交易日用基准过去 60 个交易日收益分类（>=+5% 牛、<=-5% 熊、其余震荡），
连续同类日合成一个片段；片段收益由基金/基准日收益连乘，胜率=跑赢基准的片段占比。
只解释、不预测，也不进入评分。缺失基准或历史不足时返回 insufficient（不冒充）。
"""
from typing import Any, Dict, List, Optional, Tuple

TRAILING_DAYS = 60
BULL_THRESHOLD = 0.05
BEAR_THRESHOLD = -0.05
MIN_PERIOD_DAYS = 5
MIN_TOTAL_DAYS = 250


def _regime_stats(periods: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not periods:
        return {
            "period_count": 0,
            "total_days": 0,
            "avg_fund_return": None,
            "avg_benchmark_return": None,
            "avg_excess": None,
            "win_rate": None,
        }
    count = len(periods)
    wins = sum(1 for item in periods if item["excess"] > 0)
    return {
        "period_count": count,
        "total_days": sum(item["days"] for item in periods),
        "avg_fund_return": round(sum(item["fund_return"] for item in periods) / count, 6),
        "avg_benchmark_return": round(sum(item["bench_return"] for item in periods) / count, 6),
        "avg_excess": round(sum(item["excess"] for item in periods) / count, 6),
        "win_rate": round(wins / count, 4),
    }


def summarize_regime_performance(
    fund_points: List[Tuple[Any, float]],
    bench_points: List[Tuple[Any, float]],
    trailing_days: int = TRAILING_DAYS,
    bull_threshold: float = BULL_THRESHOLD,
    bear_threshold: float = BEAR_THRESHOLD,
    min_period_days: int = MIN_PERIOD_DAYS,
    min_total_days: int = MIN_TOTAL_DAYS,
) -> Dict[str, Any]:
    """把对齐后的基金/基准净值序列汇总为分段业绩。"""
    fund_by_date = {str(day)[:10]: value for day, value in fund_points if value and value > 0}
    bench_by_date = {str(day)[:10]: value for day, value in bench_points if value and value > 0}
    shared = sorted(set(fund_by_date) & set(bench_by_date))
    if not bench_by_date:
        return {"status": "insufficient", "reason": "benchmark_missing", "regimes": {}}
    if len(shared) < min_total_days:
        return {
            "status": "insufficient",
            "reason": f"insufficient_history({len(shared)}<{min_total_days})",
            "observations": len(shared),
            "regimes": {},
        }

    fund_levels = [fund_by_date[day] for day in shared]
    bench_levels = [bench_by_date[day] for day in shared]

    def _classify(trailing_return: float) -> str:
        if trailing_return >= bull_threshold:
            return "bull"
        if trailing_return <= bear_threshold:
            return "bear"
        return "range"

    periods: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for index in range(trailing_days, len(shared)):
        trailing_return = bench_levels[index] / bench_levels[index - trailing_days] - 1
        regime = _classify(trailing_return)
        fund_ret = fund_levels[index] / fund_levels[index - 1] - 1
        bench_ret = bench_levels[index] / bench_levels[index - 1] - 1
        if current is not None and current["regime"] == regime:
            current["fund_compound"] *= 1 + fund_ret
            current["bench_compound"] *= 1 + bench_ret
            current["days"] += 1
        else:
            if current is not None:
                periods.append(current)
            current = {
                "regime": regime,
                "days": 1,
                "fund_compound": 1 + fund_ret,
                "bench_compound": 1 + bench_ret,
            }
    if current is not None:
        periods.append(current)

    buckets: Dict[str, List[Dict[str, Any]]] = {"bull": [], "bear": [], "range": []}
    for item in periods:
        if item["days"] < min_period_days:
            continue
        fund_return = item["fund_compound"] - 1
        bench_return = item["bench_compound"] - 1
        buckets[item["regime"]].append({
            "days": item["days"],
            "fund_return": fund_return,
            "bench_return": bench_return,
            "excess": fund_return - bench_return,
        })

    return {
        "status": "available",
        "methodology": "benchmark_trailing_60d_regime_v1",
        "observations": len(shared),
        "start_date": shared[0],
        "end_date": shared[-1],
        "thresholds": {
            "trailing_days": trailing_days,
            "bull": bull_threshold,
            "bear": bear_threshold,
            "min_period_days": min_period_days,
        },
        "regimes": {key: _regime_stats(items) for key, items in buckets.items()},
        "limitations": [
            "市场环境由基准自身 trailing 收益划分，不是官方牛熊判定。",
            "分段只解释历史表现，不预测未来，也不进入评分。",
        ],
    }


class FundRegimePerformanceService:
    """按基金真实净值与同基准净值计算分段业绩（只读）。"""

    def __init__(self, nav_repo: Optional[Any] = None, years: int = 3):
        if nav_repo is None:
            from repositories import get_nav_repo

            nav_repo = get_nav_repo()
        self.nav_repo = nav_repo
        self.years = years

    def get(self, wind_code: str) -> Dict[str, Any]:
        from datetime import date, timedelta

        code = str(wind_code or "").strip().upper()
        if not code:
            raise ValueError("wind_code is required")
        end = date.today()
        start = end - timedelta(days=max(1, self.years) * 365 + 30)
        rows = self.nav_repo.get_nav_series(code, start.isoformat(), end.isoformat()) or []
        if not rows:
            raise ValueError(f"No NAV data for {code}")
        fund_points, basis = self._fund_series(rows)
        bench_points = self._benchmark_series(rows)
        result = summarize_regime_performance(fund_points, bench_points)
        result.update({
            "wind_code": code,
            "nav_basis": basis,
            "window_years": self.years,
            "source": "local.postgres.fund_nav",
            "simulation_used": False,
            "product_scope": {"fund_evaluation": "supporting_evidence", "investment_decision": "excluded"},
        })
        return result

    @staticmethod
    def _fund_series(rows: List[Dict[str, Any]]) -> Tuple[List[Tuple[Any, float]], str]:
        parsed = []
        for row in rows:
            day = str(row.get("date") or row.get("trade_date") or "")[:10]
            unit = _positive(row.get("nav") or row.get("unit_nav"))
            accum = _positive(row.get("accum_nav"))
            if day and (unit is not None or accum is not None):
                parsed.append((day, unit, accum))
        if not parsed:
            return [], "unavailable"
        accum_count = sum(1 for _, _, accum in parsed if accum is not None)
        use_accum = accum_count >= max(2, int(len(parsed) * 0.9))
        points = {}
        for day, unit, accum in parsed:
            value = accum if use_accum else unit
            if value is not None and value > 0:
                points[day] = value
        return sorted(points.items()), "accum_nav" if use_accum else "unit_nav"

    @staticmethod
    def _benchmark_series(rows: List[Dict[str, Any]]) -> List[Tuple[Any, float]]:
        points = {}
        for row in rows:
            day = str(row.get("date") or row.get("trade_date") or "")[:10]
            value = _positive(row.get("benchmark_nav"))
            if day and value is not None:
                points[day] = value
        return sorted(points.items())


def _positive(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
