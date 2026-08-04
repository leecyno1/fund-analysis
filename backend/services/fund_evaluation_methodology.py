"""分类内基金评价方法 Module。"""
import math
from typing import Any, Dict, List, Optional, Tuple


class FundEvaluationMethodology:
    """集中管理类别专属证据门禁、维度、阈值和同类代理评分。"""

    METHODOLOGY_VERSION = "category_evaluation_methodology_v1"

    PROFILES: Dict[str, Dict[str, Any]] = {
        "active_equity": {
            "return_range": (-0.10, 0.25),
            "drawdown_range": (-0.35, -0.03),
            "volatility_range": (0.35, 0.08),
        },
        "fixed_income": {
            "return_range": (0.00, 0.08),
            "drawdown_range": (-0.08, -0.005),
            "volatility_range": (0.08, 0.01),
        },
        "index_fund": {
            "required_evidence": ["tracking_error", "tracking_difference", "expense_ratio", "aum"],
        },
        "money_market": {
            "required_evidence": ["seven_day_annualized_yield", "annualized_return", "max_drawdown", "aum"],
        },
    }

    def evaluate(
        self,
        profile_key: str,
        metrics: Dict[str, Dict[str, float]],
        quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        if profile_key not in self.PROFILES:
            return self._unavailable(
                "unsupported_methodology",
                [f"{profile_key} 专属基金评价方法尚未实现"],
                profile_key,
            )
        if profile_key in {"active_equity", "fixed_income"}:
            return self._evaluate_return_risk(profile_key, metrics, quality)
        if profile_key == "index_fund":
            return self._evaluate_index(metrics, quality)
        return self._evaluate_money_market(metrics, quality)

    def score_peer(self, profile_key: str, metrics: Dict[str, Any]) -> Optional[float]:
        """用同一类别方法生成轻量同类代理分，不跨类别复用指标。"""
        if profile_key in {"active_equity", "fixed_income"}:
            profile = self.PROFILES[profile_key]
            return_low, return_high = profile["return_range"]
            drawdown_low, drawdown_high = profile["drawdown_range"]
            volatility_high, volatility_low = profile["volatility_range"]
            pieces = [
                self._normalize(self._number(metrics.get("annualized_return")), return_low, return_high),
                self._normalize(self._drawdown(metrics.get("max_drawdown")), drawdown_low, drawdown_high),
                self._normalize(
                    self._number(metrics.get("annualized_volatility")),
                    volatility_high,
                    volatility_low,
                    higher_is_better=False,
                ),
                self._normalize(self._number(metrics.get("sharpe_ratio")), 0.0, 2.0),
                self._normalize(self._number(metrics.get("positive_return_ratio")), 0.45, 0.70),
            ]
            valid = [piece for piece in pieces if piece is not None]
            return round(sum(valid) / len(valid), 2) if len(valid) >= 2 else None

        if profile_key == "index_fund":
            result = self._evaluate_index({"1y": metrics, "latest": metrics}, {"score": 100, "issues": []})
        elif profile_key == "money_market":
            result = self._evaluate_money_market({"1y": metrics, "latest": metrics}, {"score": 100, "issues": []})
        else:
            return None
        return result.get("total_score") if result.get("status") in {"ok", "partial"} else None

    def _evaluate_return_risk(
        self,
        profile_key: str,
        metrics: Dict[str, Dict[str, float]],
        quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        one_year = metrics.get("1y", {})
        core_gaps = [
            f"core_metric:1y.{metric_name}"
            for metric_name in ["annualized_return", "max_drawdown", "sharpe_ratio"]
            if one_year.get(metric_name) is None
        ]
        if core_gaps:
            return self._unavailable("insufficient_evidence", core_gaps, profile_key)

        profile = self.PROFILES[profile_key]
        weights = {
            "return": 0.25 if profile_key == "active_equity" else 0.20,
            "risk": 0.25 if profile_key == "active_equity" else 0.35,
            "risk_adjusted": 0.20 if profile_key == "active_equity" else 0.15,
            "consistency": 0.15 if profile_key == "active_equity" else 0.10,
            "manager_tenure": 0.10,
            "data_quality": 0.05 if profile_key == "active_equity" else 0.10,
        }
        dimensions = {
            "return": self._return_dimension(metrics, profile),
            "risk": self._risk_dimension(metrics, profile),
            "risk_adjusted": self._risk_adjusted_dimension(metrics),
            "consistency": self._consistency_dimension(metrics),
            "manager_tenure": self._manager_dimension(metrics, profile),
            "data_quality": self._dimension(quality.get("score", 0), ["数据质量评分进入综合修正"]),
        }
        missing = []
        for window in ["1y", "manager_tenure"]:
            if window not in metrics:
                missing.append(f"metric_window:{window}")
        missing.extend(f"quality:{issue}" for issue in quality.get("issues", []))
        return self._finalize(profile_key, dimensions, weights, metrics, missing)

    def _evaluate_index(
        self,
        metrics: Dict[str, Dict[str, float]],
        quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        tracking_error = self._first(metrics, [("1y", "tracking_error")])
        tracking_difference = self._first(metrics, [("1y", "tracking_difference"), ("1y", "excess_return")])
        expense_ratio = self._rate(self._first(metrics, [("latest", "expense_ratio"), ("1y", "expense_ratio")]))
        aum = self._asset_yi(self._first(metrics, [("latest", "aum"), ("1y", "aum")]))
        values = {
            "tracking_error": tracking_error,
            "tracking_difference": tracking_difference,
            "expense_ratio": expense_ratio,
            "aum": aum,
        }
        gaps = [f"core_metric:{name}" for name, value in values.items() if value is None]
        if gaps:
            return self._unavailable("insufficient_evidence", gaps, "index_fund")

        dimensions = {
            "tracking_quality": self._dimension(
                self._average([
                    self._normalize(tracking_error, 0.03, 0.002, higher_is_better=False),
                    self._normalize(abs(tracking_difference), 0.03, 0.001, higher_is_better=False),
                ]),
                ["跟踪误差与跟踪差异共同衡量复制质量"],
            ),
            "cost_efficiency": self._dimension(
                self._normalize(expense_ratio, 0.018, 0.0015, higher_is_better=False),
                ["管理费与托管费形成的总费率衡量长期成本拖累"],
            ),
            "scale_liquidity": self._dimension(
                self._normalize_log(aum, 1.0, 100.0),
                ["基金规模作为流动性和运营可持续性的代理证据"],
            ),
            "data_quality": self._dimension(quality.get("score", 0), ["数据质量评分进入综合修正"]),
        }
        missing = [f"quality:{issue}" for issue in quality.get("issues", [])]
        return self._finalize(
            "index_fund",
            dimensions,
            {"tracking_quality": 0.55, "cost_efficiency": 0.25, "scale_liquidity": 0.10, "data_quality": 0.10},
            metrics,
            missing,
        )

    def _evaluate_money_market(
        self,
        metrics: Dict[str, Dict[str, float]],
        quality: Dict[str, Any],
    ) -> Dict[str, Any]:
        seven_day_yield = self._rate(self._first(metrics, [
            ("latest", "seven_day_annualized_yield"),
            ("1y", "seven_day_annualized_yield"),
        ]))
        annualized_return = self._rate(self._first(metrics, [("1y", "annualized_return")]))
        max_drawdown = self._drawdown(self._first(metrics, [("1y", "max_drawdown")]))
        aum = self._asset_yi(self._first(metrics, [("latest", "aum"), ("1y", "aum")]))
        values = {
            "seven_day_annualized_yield": seven_day_yield,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "aum": aum,
        }
        gaps = [f"core_metric:{name}" for name, value in values.items() if value is None]
        if gaps:
            return self._unavailable("insufficient_evidence", gaps, "money_market")

        volatility = self._first(metrics, [("1y", "annualized_volatility")])
        positive_ratio = self._first(metrics, [("1y", "positive_return_ratio")])
        stability_gap = abs(seven_day_yield - annualized_return)
        dimensions = {
            "income_competitiveness": self._dimension(
                self._average([
                    self._normalize(seven_day_yield, 0.01, 0.035),
                    self._normalize(annualized_return, 0.01, 0.035),
                ]),
                ["七日年化收益率与近一年收益共同描述收益中枢"],
            ),
            "capital_preservation": self._dimension(
                self._average([
                    self._normalize(max_drawdown, -0.01, 0.0),
                    self._normalize(volatility, 0.02, 0.001, higher_is_better=False),
                ]),
                ["最大回撤与波动衡量净值稳定和本金保护特征"],
            ),
            "income_stability": self._dimension(
                self._average([
                    self._normalize(stability_gap, 0.02, 0.0, higher_is_better=False),
                    self._normalize(positive_ratio, 0.95, 1.0),
                ]),
                ["七日年化与一年收益差异、正收益比例衡量收益稳定性"],
            ),
            "scale_liquidity": self._dimension(
                self._normalize_log(aum, 5.0, 300.0),
                ["基金规模作为流动性管理和赎回承接能力的代理证据"],
            ),
            "data_quality": self._dimension(quality.get("score", 0), ["数据质量评分进入综合修正"]),
        }
        missing = []
        if volatility is None:
            missing.append("optional_metric:1y.annualized_volatility")
        if positive_ratio is None:
            missing.append("optional_metric:1y.positive_return_ratio")
        missing.extend(f"quality:{issue}" for issue in quality.get("issues", []))
        return self._finalize(
            "money_market",
            dimensions,
            {
                "income_competitiveness": 0.35,
                "capital_preservation": 0.30,
                "income_stability": 0.15,
                "scale_liquidity": 0.10,
                "data_quality": 0.10,
            },
            metrics,
            missing,
        )

    def _finalize(
        self,
        profile_key: str,
        dimensions: Dict[str, Dict[str, Any]],
        weights: Dict[str, float],
        metrics: Dict[str, Dict[str, float]],
        missing_data: List[str],
    ) -> Dict[str, Any]:
        total_score = 0.0
        for key, weight in weights.items():
            dimensions[key]["weight"] = weight
            dimensions[key]["weighted_score"] = round(dimensions[key]["score"] * weight, 2)
            total_score += dimensions[key]["score"] * weight
        return {
            "status": "partial" if missing_data else "ok",
            "profile_key": profile_key,
            "methodology_version": self.METHODOLOGY_VERSION,
            "calculation_method": f"{self.METHODOLOGY_VERSION}:{profile_key}",
            "total_score": round(total_score, 4),
            "dimensions": dimensions,
            "metric_scores": self._metric_scores(metrics),
            "missing_data": list(dict.fromkeys(missing_data)),
        }

    def _unavailable(self, status: str, missing_data: List[str], profile_key: str) -> Dict[str, Any]:
        return {
            "status": status,
            "profile_key": profile_key,
            "methodology_version": self.METHODOLOGY_VERSION,
            "calculation_method": f"{self.METHODOLOGY_VERSION}:{profile_key}",
            "total_score": None,
            "dimensions": {},
            "metric_scores": {},
            "missing_data": missing_data,
        }

    def _return_dimension(self, metrics: Dict[str, Dict[str, float]], profile: Dict[str, Any]) -> Dict[str, Any]:
        low, high = profile["return_range"]
        return self._dimension(self._average([
            self._normalize(metrics.get("1y", {}).get("annualized_return"), low, high),
            self._normalize(metrics.get("3y", {}).get("annualized_return"), low, high),
        ]), ["1Y/3Y 年化收益进入收益能力评分"])

    def _risk_dimension(self, metrics: Dict[str, Dict[str, float]], profile: Dict[str, Any]) -> Dict[str, Any]:
        drawdown_low, drawdown_high = profile["drawdown_range"]
        volatility_high, volatility_low = profile["volatility_range"]
        return self._dimension(self._average([
            self._normalize(metrics.get("1y", {}).get("max_drawdown"), drawdown_low, drawdown_high),
            self._normalize(metrics.get("3y", {}).get("max_drawdown"), drawdown_low, drawdown_high),
            self._normalize(
                metrics.get("1y", {}).get("annualized_volatility"),
                volatility_high,
                volatility_low,
                higher_is_better=False,
            ),
        ]), ["最大回撤和年化波动进入风险控制评分"])

    def _risk_adjusted_dimension(self, metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        return self._dimension(self._average([
            self._normalize(metrics.get("1y", {}).get("sharpe_ratio"), 0, 2.5),
            self._normalize(metrics.get("1y", {}).get("calmar_ratio"), 0, 4),
            self._normalize(metrics.get("3y", {}).get("sharpe_ratio"), 0, 2.5),
        ]), ["夏普、Calmar 进入风险调整收益评分"])

    def _consistency_dimension(self, metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        one_year = metrics.get("1y", {})
        three_year = metrics.get("3y", {})
        return_gap = None
        if one_year.get("annualized_return") is not None and three_year.get("annualized_return") is not None:
            return_gap = abs(one_year["annualized_return"] - three_year["annualized_return"])
        return self._dimension(self._average([
            self._normalize(one_year.get("positive_return_ratio"), 0.45, 0.65),
            self._normalize(return_gap, 0.12, 0.01, higher_is_better=False),
        ]), ["胜率和 1Y/3Y 收益稳定性进入一致性评分"])

    def _manager_dimension(self, metrics: Dict[str, Dict[str, float]], profile: Dict[str, Any]) -> Dict[str, Any]:
        tenure = metrics.get("manager_tenure", {})
        low, high = profile["return_range"]
        drawdown_low, drawdown_high = profile["drawdown_range"]
        return self._dimension(self._average([
            self._normalize(tenure.get("annualized_return"), low, high),
            self._normalize(tenure.get("max_drawdown"), drawdown_low, drawdown_high),
            self._normalize(tenure.get("tenure_days"), 180, 900),
        ]), ["现任经理任期内收益、回撤和任期长度进入评分"])

    def _metric_scores(self, metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        allowed = {
            "annualized_return", "max_drawdown", "annualized_volatility", "sharpe_ratio",
            "calmar_ratio", "positive_return_ratio", "tenure_days", "tracking_error",
            "tracking_difference", "excess_return", "expense_ratio", "aum",
            "seven_day_annualized_yield", "income_per_10000",
        }
        return {
            f"{window}.{metric_name}": value
            for window, window_metrics in metrics.items()
            for metric_name, value in window_metrics.items()
            if metric_name in allowed
        }

    def _first(
        self,
        metrics: Dict[str, Dict[str, float]],
        paths: List[Tuple[str, str]],
    ) -> Optional[float]:
        for window, metric_name in paths:
            value = self._number(metrics.get(window, {}).get(metric_name))
            if value is not None:
                return value
        return None

    def _dimension(self, score: Optional[float], evidence: List[str]) -> Dict[str, Any]:
        effective_score = 50.0 if score is None else score
        return {
            "score": round(max(0.0, min(100.0, effective_score)), 2),
            "weighted_score": round(max(0.0, min(100.0, effective_score)), 2),
            "evidence": evidence,
        }

    def _normalize(
        self,
        value: Optional[float],
        low: float,
        high: float,
        higher_is_better: bool = True,
    ) -> Optional[float]:
        if value is None or low == high:
            return None
        if higher_is_better:
            if value <= low:
                return 0.0
            if value >= high:
                return 100.0
            return (value - low) / (high - low) * 100.0
        if value <= high:
            return 100.0
        if value >= low:
            return 0.0
        return (low - value) / (low - high) * 100.0

    def _normalize_log(self, value: Optional[float], low: float, high: float) -> Optional[float]:
        if value is None or value <= 0:
            return None
        return self._normalize(math.log10(value), math.log10(low), math.log10(high))

    def _average(self, values: List[Optional[float]]) -> float:
        valid = [value for value in values if value is not None]
        return sum(valid) / len(valid) if valid else 50.0

    def _number(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _drawdown(self, value: Any) -> Optional[float]:
        number = self._number(value)
        return -abs(number) if number is not None else None

    def _rate(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return value / 100.0 if abs(value) > 0.20 else value

    def _asset_yi(self, value: Optional[float]) -> Optional[float]:
        if value is None or value <= 0:
            return None
        return value / 100_000_000.0 if value >= 1_000_000 else value
