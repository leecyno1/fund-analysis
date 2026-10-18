"""收益来源结论：把基金日收益对基准日收益回归，得到 Beta/Alpha/R²/IR，
再用滚动年度 Alpha 判断"这种钱能不能继续赚"。

只解释历史、不预测、不进入评分（ADR-0004）。基准缺失或样本不足返回 insufficient。
"""
import math
from typing import Any, Dict, List, Optional, Tuple

TRADING_DAYS = 252
MIN_OBSERVATIONS = 250
ROLLING_WINDOWS = 3
MIN_ROLLING_OBS = 60
ALPHA_SIGNIFICANCE_T = 1.96  # 双侧 5% 显著性，避免把 t=1.5 量级过度称为"显著"

_SOURCE_LABELS = {
    "market_driven": "市场 Beta 驱动",
    "alpha_positive": "显著正 Alpha",
    "alpha_negative": "负 Alpha",
    "mixed": "Alpha 与 Beta 混合",
}
_REPLICABILITY_LABELS = {
    "high": "高（各滚动期方向一致且多数显著）",
    "medium": "中（多数滚动期为正）",
    "low": "低（滚动期方向不一致）",
    "not_significant": "不适用（Alpha 不显著）",
    "insufficient": "证据不足",
}


def _alpha_stats(fund_returns: List[float], bench_returns: List[float]) -> Dict[str, Any]:
    n = len(fund_returns)
    if n < 2 or n != len(bench_returns):
        return {}
    mean_f = sum(fund_returns) / n
    mean_b = sum(bench_returns) / n
    var_b = sum((value - mean_b) ** 2 for value in bench_returns) / n
    if var_b <= 0:
        return {}
    cov = sum((fund_returns[i] - mean_f) * (bench_returns[i] - mean_b) for i in range(n)) / n
    beta = cov / var_b
    alpha_daily = mean_f - beta * mean_b
    residuals = [fund_returns[i] - (alpha_daily + beta * bench_returns[i]) for i in range(n)]
    ss_res = sum(value * value for value in residuals)
    ss_tot = sum((value - mean_f) ** 2 for value in fund_returns)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None
    resid_std = math.sqrt(ss_res / (n - 2)) if n > 2 else 0.0
    alpha_t = (
        alpha_daily / (resid_std / math.sqrt(n))
        if resid_std > 0 else None
    )
    active = [fund_returns[i] - bench_returns[i] for i in range(n)]
    active_mean = sum(active) / n
    active_var = sum((value - active_mean) ** 2 for value in active) / n
    active_std = math.sqrt(active_var)
    information_ratio = (active_mean / active_std * math.sqrt(TRADING_DAYS)) if active_std > 0 else None

    def _finite(value):
        return value if value is not None and math.isfinite(value) else None

    return {
        "observations": n,
        "beta": _finite(beta),
        "alpha_annualized": _finite(alpha_daily * TRADING_DAYS),
        "alpha_t_stat": _finite(alpha_t),
        "r_squared": _finite(r_squared),
        "information_ratio": _finite(information_ratio),
        "fund_annualized": _finite(mean_f * TRADING_DAYS),
        "market_annualized": _finite(beta * mean_b * TRADING_DAYS),
    }


def build_return_source_conclusion(
    fund_points: List[Tuple[Any, float]],
    bench_points: List[Tuple[Any, float]],
    min_observations: int = MIN_OBSERVATIONS,
    rolling_windows: int = ROLLING_WINDOWS,
) -> Dict[str, Any]:
    """把对齐后的基金/基准净值序列汇总为收益来源结论。"""
    fund_by_date = {str(day)[:10]: value for day, value in fund_points if value and value > 0}
    bench_by_date = {str(day)[:10]: value for day, value in bench_points if value and value > 0}
    if not bench_by_date:
        return {"status": "insufficient", "reason": "benchmark_missing"}
    shared = sorted(set(fund_by_date) & set(bench_by_date))
    if len(shared) < min_observations + 1:
        return {
            "status": "insufficient",
            "reason": f"insufficient_history({len(shared)}<{min_observations + 1})",
            "observations": len(shared),
        }

    dates = shared[1:]
    fund_returns = []
    bench_returns = []
    for index in range(1, len(shared)):
        prev_day, day = shared[index - 1], shared[index]
        fund_returns.append(fund_by_date[day] / fund_by_date[prev_day] - 1)
        bench_returns.append(bench_by_date[day] / bench_by_date[prev_day] - 1)

    stats = _alpha_stats(fund_returns, bench_returns)
    if not stats:
        return {"status": "insufficient", "reason": "benchmark_zero_variance", "observations": len(shared)}

    alpha_ann = stats.get("alpha_annualized")
    alpha_t = stats.get("alpha_t_stat")
    r_squared = stats.get("r_squared")
    if alpha_ann is None:
        classification = "mixed"
    elif r_squared is not None and r_squared >= 0.75 and abs(alpha_ann) < 0.02:
        classification = "market_driven"
    elif alpha_t is None:
        # 残差为 0（完全由基准解释）时 t 值无定义，按 Alpha 符号判断。
        classification = "alpha_positive" if alpha_ann > 0 else "alpha_negative" if alpha_ann < 0 else "market_driven"
    elif r_squared is not None and r_squared >= 0.75 and abs(alpha_t) < ALPHA_SIGNIFICANCE_T:
        classification = "market_driven"
    elif alpha_ann > 0 and alpha_t >= ALPHA_SIGNIFICANCE_T:
        classification = "alpha_positive"
    elif alpha_ann < 0 and alpha_t <= -ALPHA_SIGNIFICANCE_T:
        classification = "alpha_negative"
    else:
        classification = "mixed"

    chunk_size = max(MIN_ROLLING_OBS, len(fund_returns) // max(1, rolling_windows))
    rolling = []
    for start in range(0, len(fund_returns), chunk_size):
        end = min(start + chunk_size, len(fund_returns))
        if end - start < MIN_ROLLING_OBS:
            continue
        chunk_stats = _alpha_stats(fund_returns[start:end], bench_returns[start:end])
        if not chunk_stats:
            continue
        rolling.append({
            "start_date": dates[start],
            "end_date": dates[end - 1],
            "observations": end - start,
            "alpha_annualized": chunk_stats.get("alpha_annualized"),
            "alpha_t_stat": chunk_stats.get("alpha_t_stat"),
            "beta": chunk_stats.get("beta"),
        })

    if classification == "market_driven":
        replicability = "not_significant"
    elif len(rolling) < 2:
        replicability = "insufficient"
    else:
        positive = sum(1 for item in rolling if (item.get("alpha_annualized") or 0) > 0)
        significant = sum(1 for item in rolling if (item.get("alpha_t_stat") or 0) >= ALPHA_SIGNIFICANCE_T)
        if positive == len(rolling) and significant >= max(2, math.ceil(len(rolling) * 0.6)):
            replicability = "high"
        elif positive >= math.ceil(len(rolling) * 0.5):
            replicability = "medium"
        else:
            replicability = "low"

    beta = stats.get("beta")
    r2_text = "—" if r_squared is None else f"{r_squared:.0%}"
    t_text = "—" if alpha_t is None else f"{alpha_t:.1f}"
    ann_text = "—" if alpha_ann is None else f"{alpha_ann:+.2%}"
    if classification == "market_driven":
        conclusion = (
            f"近 {stats['observations']} 个交易日收益主要由市场 Beta 解释"
            f"（Beta {beta:.2f}，R² {r2_text}，年化 Alpha {ann_text}，t={t_text}），主动贡献不显著。"
        )
    elif classification == "alpha_positive":
        conclusion = (
            f"存在统计显著的主动 Alpha（年化 {ann_text}，t={t_text}，Beta {beta:.2f}）；"
            f"滚动 {len(rolling)} 段中 {sum(1 for i in rolling if (i.get('alpha_annualized') or 0) > 0)} 段为正，"
            f"可复制性{_REPLICABILITY_LABELS[replicability]}。"
        )
    elif classification == "alpha_negative":
        conclusion = (
            f"主动管理为负贡献（年化 {ann_text}，t={t_text}），收益主要靠市场 Beta。"
        )
    else:
        conclusion = (
            f"Alpha 与市场 Beta 难以区分（年化 {ann_text}，t={t_text}，R² {r2_text}），需更多证据。"
        )

    return {
        "status": "available",
        "methodology": "nav_ols_beta_alpha_with_rolling_alpha_v1",
        "observations": stats["observations"],
        "start_date": dates[0],
        "end_date": dates[-1],
        "beta": beta,
        "r_squared": r_squared,
        "alpha_annualized": alpha_ann,
        "alpha_t_stat": alpha_t,
        "information_ratio": stats.get("information_ratio"),
        "fund_annualized": stats.get("fund_annualized"),
        "market_annualized": stats.get("market_annualized"),
        "classification": classification,
        "classification_label": _SOURCE_LABELS.get(classification, classification),
        "alpha_replicability": replicability,
        "alpha_replicability_label": _REPLICABILITY_LABELS.get(replicability, replicability),
        "rolling_windows": rolling,
        "conclusion": conclusion,
        "limitations": [
            "回归只解释历史收益来源，不预测未来，也不进入评分。",
            "年化按算术口径（日均×252）；未控制风格因子，Alpha 可能包含未纳入的风格暴露。",
            "滚动期分段等长切分，仅用于判断方向稳定性，不等同于逐年业绩。",
        ],
    }


class FundReturnSourceService:
    """按基金真实净值与同基准净值计算收益来源结论（只读）。"""

    def __init__(self, nav_repo: Optional[Any] = None, years: int = 3):
        if nav_repo is None:
            from repositories import get_nav_repo

            nav_repo = get_nav_repo()
        self.nav_repo = nav_repo
        self.years = years

    def get(self, wind_code: str) -> Dict[str, Any]:
        from datetime import date, timedelta

        from services.fund_regime_performance_service import FundRegimePerformanceService

        code = str(wind_code or "").strip().upper()
        if not code:
            raise ValueError("wind_code is required")
        end = date.today()
        start = end - timedelta(days=max(1, self.years) * 365 + 30)
        rows = self.nav_repo.get_nav_series(code, start.isoformat(), end.isoformat()) or []
        if not rows:
            raise ValueError(f"No NAV data for {code}")
        fund_points, basis = FundRegimePerformanceService._fund_series(rows)
        bench_points = FundRegimePerformanceService._benchmark_series(rows)
        result = build_return_source_conclusion(fund_points, bench_points)
        result.update({
            "wind_code": code,
            "nav_basis": basis,
            "window_years": self.years,
            "source": "local.postgres.fund_nav",
            "simulation_used": False,
            "product_scope": {"fund_evaluation": "supporting_evidence", "investment_decision": "excluded"},
        })
        return result
