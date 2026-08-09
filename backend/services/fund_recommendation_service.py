"""面向普通用户的分类内候选基金组。"""
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from services.fund_classification_service import FundClassificationService
from services.professional_scoring_service import ProfessionalScoringService


class FundRecommendationService:
    """扫描完整同类组，返回不超过十只证据充分的候选基金。"""

    METHODOLOGY_VERSION = "fund_candidate_group_v1"
    MAX_CANDIDATES = 10
    PEER_UNIVERSE_LIMIT = 2000

    STYLE_ALIASES: Dict[str, Tuple[str, ...]] = {
        "大盘成长": ("大盘成长", "large growth", "large_growth"),
        "成长": ("成长", "growth"),
        "价值": ("价值", "value"),
        "均衡": ("均衡", "平衡", "混合", "blend", "balanced"),
        "质量": ("质量", "品质", "quality"),
        "红利": ("红利", "股息", "dividend"),
        "小盘": ("小盘", "small cap", "small_cap", "small"),
        "行业主题": ("行业", "主题", "sector", "thematic"),
        "低波稳健": ("低波", "稳健", "low volatility", "low_volatility", "defensive"),
    }

    def __init__(
        self,
        classification_repo: Optional[Any] = None,
        metric_repo: Optional[Any] = None,
        profile_repo: Optional[Any] = None,
        scoring_service: Optional[ProfessionalScoringService] = None,
    ):
        self._classification_repo = classification_repo
        self._metric_repo = metric_repo
        self._profile_repo = profile_repo
        self.scoring_service = scoring_service or ProfessionalScoringService()

    def build_candidate_group(
        self,
        peer_group: str,
        style: Optional[str] = None,
        limit: int = MAX_CANDIDATES,
    ) -> Dict[str, Any]:
        normalized_group = str(peer_group or "").strip()
        normalized_style = str(style or "").strip()
        if not normalized_group:
            raise ValueError("请先选择基金类别")

        rows = self.classification_repo.list_recommendation_funds(
            normalized_group,
            limit=self.PEER_UNIVERSE_LIMIT,
        )
        exact_rows = [row for row in rows if self._belongs_to_group(row, normalized_group)]
        codes = [str(row.get("wind_code") or "").strip() for row in exact_rows]
        codes = [code for code in codes if code]
        panels = self.metric_repo.get_latest_panels("fund", codes)
        profiles = self.profile_repo.list_profiles(codes)

        eligible: List[Dict[str, Any]] = []
        excluded_reason_counts: Dict[str, int] = {}
        for row in exact_rows:
            code = str(row.get("wind_code") or "").strip()
            profile = profiles.get(code) or {}
            panel = panels.get(code) or []
            candidate, reason = self._evaluate_candidate(row, profile, panel)
            if candidate is None:
                excluded_reason_counts[reason] = excluded_reason_counts.get(reason, 0) + 1
                continue
            eligible.append(candidate)

        available_styles = self._available_styles({
            str(candidate.get("wind_code") or ""): candidate.get("research_profile") or {}
            for candidate in eligible
        })
        self._attach_score_percentiles(eligible)
        styled = [
            candidate
            for candidate in eligible
            if self._matches_style(candidate, normalized_style)
        ]
        styled.sort(key=self._candidate_sort_key)

        candidate_limit = max(1, min(int(limit), self.MAX_CANDIDATES))
        candidates = styled[:candidate_limit]
        for candidate in candidates:
            alternatives = self._alternative_candidates(candidate, styled)
            candidate["recommendation_evidence"] = {
                **self._recommendation_evidence(candidate),
                "alternatives": alternatives,
            }

        return {
            "peer_group": normalized_group,
            "style": normalized_style or None,
            "peer_universe_count": len(exact_rows),
            "evidence_eligible_count": len(eligible),
            "style_matched_count": len(styled),
            "excluded_count": len(exact_rows) - len(eligible),
            "excluded_reason_counts": excluded_reason_counts,
            "available_styles": available_styles,
            "limit": candidate_limit,
            "returned": len(candidates),
            "candidates": candidates,
            "methodology_version": self.METHODOLOGY_VERSION,
            "source": "full_peer_group_category_evaluation",
            "scope": {
                "fund_classification": "required",
                "category_evaluation": "required",
                "explanatory_attribution": "optional",
            },
        }

    @property
    def classification_repo(self):
        if self._classification_repo is None:
            from repositories import get_fund_classification_repo

            self._classification_repo = get_fund_classification_repo()
        return self._classification_repo

    @property
    def metric_repo(self):
        if self._metric_repo is None:
            from repositories import get_metric_snapshot_repo

            self._metric_repo = get_metric_snapshot_repo()
        return self._metric_repo

    @property
    def profile_repo(self):
        if self._profile_repo is None:
            from repositories import get_research_profile_repo

            self._profile_repo = get_research_profile_repo()
        return self._profile_repo

    def _evaluate_candidate(
        self,
        row: Dict[str, Any],
        profile: Dict[str, Any],
        panel: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        profile_key = self._evaluation_profile_key(row)
        if not profile_key:
            return None, "evaluation_method_missing"

        metrics = self._merge_metric_windows(
            self._metrics_by_window(panel),
            self.scoring_service.metric_facts_from_fund(row),
        )
        metric_configs = self.scoring_service.methodology.peer_metric_configs(profile_key)
        if not metric_configs:
            return None, "evaluation_method_missing"

        metric_evidence = {
            config["metric_name"]: self._metric_value(metrics, config)
            for config in metric_configs
        }
        missing_required = [
            config["metric_name"]
            for config in metric_configs
            if config.get("required_for_sample", True)
            and metric_evidence.get(config["metric_name"]) is None
        ]
        if missing_required:
            return None, "required_category_evidence_missing"

        flat_metrics = {
            **metrics.get("latest", {}),
            **metrics.get("1y", {}),
            **metric_evidence,
        }
        score = self.scoring_service.score_peer_metrics(profile_key, flat_metrics)
        if score is None:
            return None, "category_score_unavailable"

        code = str(row.get("wind_code") or "")
        as_of_date = self._latest_as_of(panel, row)
        research_profile = {
            **profile,
            "peer_group": row.get("standardized_peer_group_name") or profile.get("peer_group"),
            "peer_group_id": row.get("standardized_peer_group_id"),
            "peer_group_key": row.get("standardized_peer_group_key"),
        }
        candidate = {
            **row,
            "wind_code": code,
            "research_profile": research_profile,
            "rolling_metrics": self._rolling_metric_panel(panel),
            "professional_scoring": {
                "status": "ok",
                "overall_score": round(float(score), 4),
                "overall_grade": self._grade(float(score)),
                "calculation_method": f"{self.METHODOLOGY_VERSION}:{profile_key}",
                "fund_type_profile": profile_key,
                "as_of_date": as_of_date,
            },
            "peer_percentiles": {"metrics": {}},
            "_candidate_metrics": metric_evidence,
            "_candidate_profile_key": profile_key,
            "_candidate_data_as_of": as_of_date,
        }
        return candidate, ""

    def _attach_score_percentiles(self, candidates: List[Dict[str, Any]]) -> None:
        ordered = sorted(
            candidates,
            key=lambda item: (
                -float(item["professional_scoring"]["overall_score"]),
                str(item.get("wind_code") or ""),
            ),
        )
        peer_count = len(ordered)
        for rank, candidate in enumerate(ordered, start=1):
            percentile = 100.0 if peer_count == 1 else (peer_count - rank) / (peer_count - 1) * 100
            candidate["peer_percentiles"] = {
                "metrics": {
                    "professional_score": {
                        "value": candidate["professional_scoring"]["overall_score"],
                        "percentile": round(percentile, 2),
                        "rank": rank,
                        "peer_count": peer_count,
                        "sample_status": "sufficient",
                    }
                }
            }

    def _recommendation_evidence(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        metrics = candidate.pop("_candidate_metrics", {})
        profile_key = candidate.pop("_candidate_profile_key", "")
        data_as_of = candidate.pop("_candidate_data_as_of", None)
        reasons: List[str] = []
        risks: List[str] = []

        if profile_key == "index_fund":
            reasons.extend(self._metric_reason(metrics, "tracking_error", "1 年跟踪误差", "percent"))
            reasons.extend(self._metric_reason(metrics, "absolute_tracking_difference", "1 年跟踪差异", "percent"))
            reasons.extend(self._metric_reason(metrics, "expense_ratio", "综合费率", "percent"))
            reasons.extend(self._metric_reason(metrics, "aum", "基金规模", "asset"))
            risks.append("指数基金净值会随所跟踪指数波动，当前跟踪表现不代表未来持续。")
        elif profile_key == "money_market":
            reasons.extend(self._metric_reason(metrics, "seven_day_annualized_yield", "七日年化", "percent"))
            reasons.extend(self._metric_reason(metrics, "annualized_return", "近 1 年年化收益", "percent"))
            reasons.extend(self._metric_reason(metrics, "aum", "基金规模", "asset"))
            risks.append("货币基金收益率会随市场利率变化，也不等同于银行存款。")
        else:
            reasons.extend(self._metric_reason(metrics, "annualized_return", "近 1 年年化收益", "percent"))
            reasons.extend(self._metric_reason(metrics, "max_drawdown", "近 1 年最大回撤", "percent"))
            reasons.extend(self._metric_reason(metrics, "sharpe_ratio", "近 1 年 Sharpe", "number"))
            risks.append("历史业绩和同类位置可能随市场风格变化，短期领先不代表长期持续。")

        if not reasons:
            reasons.append("已满足当前类别的核心评价证据门槛。")
        if not candidate.get("research_profile", {}).get("style_label"):
            risks.append("风格标签证据仍待补充，当前候选主要依据量化与分类证据。")
        return {
            "reasons": reasons[:4],
            "risks": risks[:3],
            "data_as_of": data_as_of,
            "methodology_version": self.METHODOLOGY_VERSION,
            "score_scope": "category_relative",
        }

    def _alternative_candidates(
        self,
        candidate: Dict[str, Any],
        peer_candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        target_code = str(candidate.get("wind_code") or "")
        target_style = self._normalize_style(
            str((candidate.get("research_profile") or {}).get("style_label") or "")
        )
        same_style: List[Dict[str, Any]] = []
        other_style: List[Dict[str, Any]] = []
        for option in peer_candidates:
            code = str(option.get("wind_code") or "")
            if not code or code == target_code:
                continue
            option_style_label = str((option.get("research_profile") or {}).get("style_label") or "")
            alternative = {
                "wind_code": code,
                "name": option.get("name") or code,
                "style_label": option_style_label or None,
                "overall_score": option.get("professional_scoring", {}).get("overall_score"),
                "reason": "同类别、同风格候选"
                if target_style and self._normalize_style(option_style_label) == target_style
                else "同类别其他高分候选",
            }
            if target_style and self._normalize_style(option_style_label) == target_style:
                same_style.append(alternative)
            else:
                other_style.append(alternative)
        return (same_style + other_style)[:2]

    @staticmethod
    def _belongs_to_group(row: Dict[str, Any], peer_group: str) -> bool:
        return peer_group in {
            str(row.get("standardized_peer_group_name") or "").strip(),
            str(row.get("standardized_peer_group_key") or "").strip(),
            str(row.get("standardized_peer_group_id") or "").strip(),
        }

    @staticmethod
    def _evaluation_profile_key(row: Dict[str, Any]) -> str:
        family_key = str(row.get("strategy_family_key") or "").strip()
        meta = FundClassificationService.FAMILY_META.get(family_key) or {}
        return str(meta.get("evaluation_profile_key") or "")

    def _matches_style(self, candidate: Dict[str, Any], style: str) -> bool:
        if not style:
            return True
        profile = candidate.get("research_profile") or {}
        style_text = " ".join([
            str(profile.get("style_label") or ""),
            " ".join(str(item) for item in (profile.get("strategy_tags") or [])),
            str(candidate.get("type") or ""),
        ])
        normalized_text = self._normalize_style(style_text)
        aliases = self.STYLE_ALIASES.get(style, (style,))
        if any(self._normalize_style(alias) in normalized_text for alias in aliases):
            return True
        if style == "低波稳健":
            drawdown = (candidate.get("_candidate_metrics") or {}).get("max_drawdown")
            return drawdown is not None and abs(float(drawdown)) <= 0.12
        return False

    @staticmethod
    def _available_styles(profiles: Dict[str, Dict[str, Any]]) -> List[str]:
        values: List[str] = []
        for profile in profiles.values():
            for value in [profile.get("style_label"), *(profile.get("strategy_tags") or [])]:
                normalized = str(value or "").strip()
                if normalized and normalized not in values:
                    values.append(normalized)
        return values[:50]

    @staticmethod
    def _normalize_style(value: str) -> str:
        return " ".join(str(value or "").lower().replace("型", "").replace("_", " ").replace("-", " ").split())

    @staticmethod
    def _metrics_by_window(panel: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        for item in panel:
            name = item.get("metric_name")
            value = FundRecommendationService._number(item.get("metric_value"))
            if not name or value is None:
                continue
            result.setdefault(str(item.get("metric_window") or "latest"), {})[str(name)] = value
        return result

    @staticmethod
    def _merge_metric_windows(
        primary: Dict[str, Dict[str, float]],
        fallback: Dict[str, Dict[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        merged = {window: values.copy() for window, values in primary.items()}
        for window, values in fallback.items():
            target = merged.setdefault(window, {})
            for name, value in values.items():
                if target.get(name) is None and value is not None:
                    target[name] = value
        return merged

    def _metric_value(self, metrics: Dict[str, Dict[str, float]], config: Dict[str, Any]) -> Optional[float]:
        value = None
        for window, name in config.get("paths") or []:
            effective_window = "1y" if window == "selected" else window
            value = self._number(metrics.get(effective_window, {}).get(name))
            if value is not None:
                break
        if value is not None and config.get("transform") == "absolute":
            value = abs(value)
        valid_range = config.get("valid_range")
        if value is not None and valid_range and not (valid_range[0] <= value <= valid_range[1]):
            return None
        return value

    @staticmethod
    def _rolling_metric_panel(panel: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for item in panel:
            window = item.get("metric_window")
            name = item.get("metric_name")
            if not window or not name:
                continue
            result.setdefault(str(window), {})[str(name)] = item.get("metric_value")
            result[str(window)]["as_of_date"] = item.get("as_of_date")
        return result

    @staticmethod
    def _latest_as_of(panel: List[Dict[str, Any]], row: Dict[str, Any]) -> Optional[str]:
        dates = [str(item.get("as_of_date")) for item in panel if item.get("as_of_date")]
        dates.extend(str(row.get(key)) for key in ("nav_date", "updated_at") if row.get(key))
        return sorted(dates)[-1][:10] if dates else None

    @staticmethod
    def _candidate_sort_key(candidate: Dict[str, Any]) -> Tuple[float, str]:
        score = float(candidate.get("professional_scoring", {}).get("overall_score") or 0)
        return -score, str(candidate.get("wind_code") or "")

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 85:
            return "A"
        if score >= 70:
            return "B"
        if score >= 55:
            return "C"
        return "D"

    @staticmethod
    def _metric_reason(metrics: Dict[str, Any], key: str, label: str, unit: str) -> List[str]:
        value = FundRecommendationService._number(metrics.get(key))
        if value is None:
            return []
        if unit == "percent":
            display = f"{value * 100:.2f}%"
        elif unit == "asset":
            display = f"{value:.1f} 亿元"
        else:
            display = f"{value:.2f}"
        return [f"{label} {display}"]

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(Decimal(str(value)))
        except Exception:
            return None
