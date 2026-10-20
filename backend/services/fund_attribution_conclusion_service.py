"""归因结论层：把多季 Brinson 效应聚合成"主贡献来源 + 可复制性"的判断。

只解释历史、不预测、不进入评分（ADR-0004）。每次按需计算最近 N 个已完成季度
（每季约 1.5-2s），结果在进程内缓存 1 小时；单季失败不影响其余季度。
"""
import time
from collections import Counter
from typing import Any, Dict, List, Optional

MIN_QUARTERS = 2
HIGH_STABILITY = 0.75
MEDIUM_STABILITY = 0.5
HIGH_RESIDUAL_SHARE = 0.4
MEDIUM_RESIDUAL_SHARE = 0.6

_SOURCE_LABELS = {"allocation": "行业配置", "selection": "行业内选股", "interaction": "交互"}
_REPLICABILITY_LABELS = {
    "high": "高（多数季度同一来源主导且方向一致）",
    "medium": "中（主导来源较稳定，但方向或残差有波动）",
    "low": "低（主导来源或方向不稳定）",
    "insufficient": "证据不足",
}
_CACHE_TTL_SECONDS = 3600
_CACHE: Dict[Any, Any] = {}


def _dominant_source(effects: Dict[str, float]) -> str:
    return max(
        ("allocation", "selection", "interaction"),
        key=lambda key: (abs(effects[key]), key),
    )


def _sign_consistency(values: List[float]) -> float:
    if not values:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    direction = 1 if total > 0 else -1
    return sum(1 for value in values if value * direction > 0) / len(values)


def summarize_attribution_history(
    quarters: List[Dict[str, Any]],
    min_quarters: int = MIN_QUARTERS,
) -> Dict[str, Any]:
    usable = []
    for item in quarters:
        status = str(item.get("status") or "")
        allocation = item.get("allocation")
        selection = item.get("selection")
        interaction = item.get("interaction")
        if status not in {"ok", "partial_evidence", "available"}:
            continue
        if allocation is None or selection is None or interaction is None:
            continue
        residual = item.get("residual")
        effects = {
            "allocation": float(allocation),
            "selection": float(selection),
            "interaction": float(interaction),
        }
        residual_value = float(residual) if residual is not None else None
        denom = sum(abs(value) for value in effects.values()) + (abs(residual_value) if residual_value is not None else 0.0)
        usable.append({
            "quarter": item.get("quarter"),
            "status": status,
            "effects": effects,
            "residual": residual_value,
            "portfolio_coverage": item.get("portfolio_coverage"),
            "dominant": _dominant_source(effects),
            "residual_share": (abs(residual_value) / denom) if denom > 0 and residual_value is not None else None,
        })

    if len(usable) < min_quarters:
        return {
            "status": "insufficient",
            "reason": f"insufficient_quarters({len(usable)}<{min_quarters})",
            "quarters_used": len(usable),
            "quarters": usable,
        }

    counts = Counter(item["dominant"] for item in usable)
    dominant_source = max(
        counts,
        key=lambda key: (
            counts[key],
            sum(abs(item["effects"][key]) for item in usable),
            key,
        ),
    )
    stability = counts[dominant_source] / len(usable)
    dominant_values = [item["effects"][dominant_source] for item in usable]
    sign_consistency = _sign_consistency(dominant_values)
    avg_effects = {
        key: round(sum(item["effects"][key] for item in usable) / len(usable), 6)
        for key in _SOURCE_LABELS
    }
    residual_shares = [item["residual_share"] for item in usable if item["residual_share"] is not None]
    avg_residual_share = (
        round(sum(residual_shares) / len(residual_shares), 4) if residual_shares else None
    )

    if (
        stability >= HIGH_STABILITY
        and sign_consistency >= HIGH_STABILITY
        and (avg_residual_share is None or avg_residual_share <= HIGH_RESIDUAL_SHARE)
        and len(usable) >= 3
    ):
        replicability = "high"
    elif (
        stability >= MEDIUM_STABILITY
        and sign_consistency >= MEDIUM_STABILITY
        and (avg_residual_share is None or avg_residual_share <= MEDIUM_RESIDUAL_SHARE)
    ):
        replicability = "medium"
    else:
        replicability = "low"

    label = _SOURCE_LABELS[dominant_source]
    residual_text = "—" if avg_residual_share is None else f"{avg_residual_share:.0%}"
    conclusion = (
        f"近 {len(usable)} 季超额主要来自{label}"
        f"（{counts[dominant_source]}/{len(usable)} 季为主贡献，方向一致率 {sign_consistency:.0%}）；"
        f"残差占比 {residual_text}。可复制性{_REPLICABILITY_LABELS[replicability]}。"
    )
    return {
        "status": "available",
        "methodology": "brinson_effects_aggregation_v1",
        "quarters_used": len(usable),
        "periods": [item["quarter"] for item in usable],
        "dominant_source": dominant_source,
        "dominant_source_label": label,
        "stability": round(stability, 4),
        "sign_consistency": round(sign_consistency, 4),
        "avg_effects": avg_effects,
        "avg_residual_share": avg_residual_share,
        "alpha_replicability": replicability,
        "alpha_replicability_label": _REPLICABILITY_LABELS[replicability],
        "quarters": usable,
        "conclusion": conclusion,
        "limitations": [
            "归因只解释历史，不预测，也不进入评分（ADR-0004）。",
            "主导来源=绝对效应最大的分项，不等同于能力判断；残差代表未披露持仓与模型未解释部分。",
            "公开持仓覆盖不足时，结论只代表已披露部分。",
        ],
    }


class FundAttributionConclusionService:
    """多季 Brinson 结论（按需计算 + 1 小时进程内缓存）。"""

    def __init__(self, attribution_service: Optional[Any] = None, quarters: int = 4):
        if attribution_service is None:
            from services.performance_attribution_service import PerformanceAttributionService

            attribution_service = PerformanceAttributionService()
        self.attribution_service = attribution_service
        self.quarters = max(2, min(int(quarters or 4), 6))

    @staticmethod
    def recent_quarters(count: int, today: Optional[Any] = None) -> List[str]:
        from datetime import date

        current = today or date.today()
        quarter = (current.month - 1) // 3 + 1
        year = current.year
        quarter -= 1  # 最近一个已完成季度
        if quarter == 0:
            quarter, year = 4, year - 1
        result = []
        for _ in range(count):
            result.append(f"{year}Q{quarter}")
            quarter -= 1
            if quarter == 0:
                quarter, year = 4, year - 1
        return result

    def get(self, wind_code: str, force_refresh: bool = False) -> Dict[str, Any]:
        from datetime import date

        code = str(wind_code or "").strip().upper()
        if not code:
            raise ValueError("wind_code is required")
        cache_key = (code, self.quarters, date.today().isoformat())
        now = time.monotonic()
        cached = _CACHE.get(cache_key)
        if cached is not None and not force_refresh and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        periods = self.recent_quarters(self.quarters)
        history: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for quarter in periods:
            try:
                bundle = self.attribution_service.analyze(code, quarter=quarter, save_history=False)
                brinson = bundle.get("brinson") or {}
                effects = {
                    str(item.get("name")): item.get("value")
                    for item in brinson.get("effects") or []
                }
                history.append({
                    "quarter": quarter,
                    "status": brinson.get("status"),
                    "allocation": effects.get("allocation"),
                    "selection": effects.get("selection"),
                    "interaction": effects.get("interaction"),
                    "residual": effects.get("residual"),
                    "portfolio_coverage": (brinson.get("coverage") or {}).get("portfolio_coverage"),
                })
            except Exception as exc:
                errors.append({"quarter": quarter, "error": f"{type(exc).__name__}: {exc}"})

        result = summarize_attribution_history(history)
        result.update({
            "wind_code": code,
            "requested_quarters": periods,
            "errors": errors,
            "source": "local.postgres+tushare.brinson",
            "simulation_used": False,
            "product_scope": {"fund_evaluation": "supporting_evidence", "investment_decision": "excluded"},
        })
        _CACHE[cache_key] = (now, result)
        return result
