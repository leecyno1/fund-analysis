"""
专业基金评分服务

基于基金分类、滚动指标、现任经理任期指标和数据质量，按评价口径输出可解释评分。
分类证据不足或尚未建立专属评价方法时显式停止，禁止默认套用主动权益评分。
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from services.data_quality_service import DataQualityService
from services.fund_classification_service import FundClassificationService
from services.scoring_contract import build_scoring_output


class ProfessionalScoringService:
    """专业评分入口。"""

    TYPE_PROFILES = {
        "active_equity": {
            "weights": {
                "return": 0.25,
                "risk": 0.25,
                "risk_adjusted": 0.20,
                "consistency": 0.15,
                "manager_tenure": 0.10,
                "data_quality": 0.05,
            },
            "return_range": (-0.10, 0.25),
            "drawdown_range": (-0.35, -0.03),
            "volatility_range": (0.35, 0.08),
        },
        "fixed_income": {
            "weights": {
                "return": 0.20,
                "risk": 0.35,
                "risk_adjusted": 0.15,
                "consistency": 0.10,
                "manager_tenure": 0.10,
                "data_quality": 0.10,
            },
            "return_range": (0.00, 0.08),
            "drawdown_range": (-0.08, -0.005),
            "volatility_range": (0.08, 0.01),
        },
    }

    def __init__(
        self,
        data_quality_service: Optional[DataQualityService] = None,
        classification_service: Optional[FundClassificationService] = None,
        classification_adapter: Optional[Any] = None,
        fund_repo: Optional[Any] = None,
        metric_repo: Optional[Any] = None,
        profile_repo: Optional[Any] = None,
    ):
        self.data_quality_service = data_quality_service or DataQualityService()
        self.classification_service = classification_service or FundClassificationService()
        self._classification_adapter = classification_adapter
        self._fund_repo_adapter = fund_repo
        self._metric_repo_adapter = metric_repo
        self._profile_repo_adapter = profile_repo

    def score_fund(self, fund_code: str) -> Dict[str, Any]:
        fund_repo = self._get_fund_repo()
        metric_repo = self._get_metric_repo()
        profile_repo = self._get_profile_repo()

        fund = fund_repo.get_fund_by_identifier(fund_code) or {}
        wind_code = fund.get("wind_code") or fund_code
        profile = profile_repo.get_profile(wind_code) or {}
        panel = metric_repo.get_latest_panel("fund", wind_code)
        quality = self.data_quality_service.evaluate_fund(wind_code)
        classification_context = self._get_classification_adapter().get_classification_context(wind_code)
        return self.score_from_inputs(fund, profile, panel, quality, classification_context)

    def score_from_inputs(
        self,
        fund: Dict[str, Any],
        profile: Dict[str, Any],
        panel: List[Dict[str, Any]],
        quality: Dict[str, Any],
        standardized_classification: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """通过稳定 Interface 对已经取得的基金事实执行分类门禁和专业评分。"""
        wind_code = fund.get("wind_code") or fund.get("ts_code") or fund.get("id") or "unknown"
        classification = self.classification_service.classify(fund, profile, standardized_classification)
        profile_key = classification.get("evaluation_profile_key")
        if classification.get("status") != "classified":
            return self._unavailable_evaluation(
                wind_code,
                classification,
                quality,
                classification.get("missing_items") or ["基金分类证据不足，不能选择评价方法"],
            )
        if profile_key not in self.TYPE_PROFILES:
            return self._unavailable_evaluation(
                wind_code,
                classification,
                quality,
                [f"{profile_key} 专属基金评价方法尚未实现，禁止复用其他类别评分"],
            )

        metrics = self._metrics_by_window(panel)
        core_metric_gaps = self._missing_core_metrics(metrics)
        if core_metric_gaps:
            return self._unavailable_evaluation(
                wind_code,
                classification,
                quality,
                core_metric_gaps,
            )
        rule_profile = self.TYPE_PROFILES[profile_key]

        dimensions = {
            "return": self._return_score(metrics, rule_profile),
            "risk": self._risk_score(metrics, rule_profile),
            "risk_adjusted": self._risk_adjusted_score(metrics),
            "consistency": self._consistency_score(metrics),
            "manager_tenure": self._manager_tenure_score(metrics, rule_profile),
            "data_quality": self._dimension(quality.get("score", 0), ["数据质量评分进入综合修正"]),
        }
        weights = rule_profile["weights"]
        total_score = sum(dimensions[key]["score"] * weights[key] for key in weights)
        for key, weight in weights.items():
            dimensions[key]["weight"] = weight
            dimensions[key]["weighted_score"] = round(dimensions[key]["score"] * weight, 2)

        missing_data = self._missing_data(metrics, quality)
        output = build_scoring_output(
            target_type="fund",
            target_id=wind_code,
            total_score=total_score,
            dimensions=dimensions,
            metric_scores=self._metric_scores(metrics),
            positive_factors=self._positive_factors(dimensions, quality),
            negative_factors=self._negative_factors(dimensions, missing_data),
            missing_data=missing_data,
            as_of_date=self._latest_as_of(panel),
            calculation_method="professional_metric_snapshot_v2",
        )
        output["status"] = "partial" if missing_data else "ok"
        output["evaluation_scope"] = "classification_gated"
        output["classification"] = classification
        output["fund_type_profile"] = profile_key
        output["peer_group"] = classification.get("peer_group")
        output["primary_benchmark"] = classification.get("primary_benchmark")
        output["data_quality"] = quality
        output["product_scope"] = self._product_scope()
        return output

    def _get_classification_adapter(self):
        if self._classification_adapter is None:
            from repositories import get_fund_classification_repo

            self._classification_adapter = get_fund_classification_repo()
        return self._classification_adapter

    def _get_fund_repo(self):
        if self._fund_repo_adapter is None:
            from repositories import get_fund_repo

            self._fund_repo_adapter = get_fund_repo()
        return self._fund_repo_adapter

    def _get_metric_repo(self):
        if self._metric_repo_adapter is None:
            from repositories import get_metric_snapshot_repo

            self._metric_repo_adapter = get_metric_snapshot_repo()
        return self._metric_repo_adapter

    def _get_profile_repo(self):
        if self._profile_repo_adapter is None:
            from repositories import get_research_profile_repo

            self._profile_repo_adapter = get_research_profile_repo()
        return self._profile_repo_adapter

    def _unavailable_evaluation(
        self,
        wind_code: str,
        classification: Dict[str, Any],
        quality: Dict[str, Any],
        missing_data: List[str],
    ) -> Dict[str, Any]:
        return {
            "status": "insufficient_evidence",
            "target_type": "fund",
            "target_id": wind_code,
            "overall_score": None,
            "overall_grade": "insufficient_evidence",
            "dimension_scores": {},
            "metric_scores": {},
            "positive_factors": [],
            "negative_factors": ["分类或评价方法证据不足，不能输出综合分"],
            "missing_data": list(missing_data),
            "source_snapshot_ids": [],
            "as_of_date": None,
            "calculation_method": "professional_metric_snapshot_v2",
            "evaluation_scope": "classification_gated",
            "classification": classification,
            "fund_type_profile": classification.get("evaluation_profile_key"),
            "peer_group": classification.get("peer_group"),
            "primary_benchmark": classification.get("primary_benchmark"),
            "data_quality": quality,
            "product_scope": self._product_scope(),
        }

    def _product_scope(self) -> Dict[str, str]:
        return {
            "fund_classification": "core",
            "fund_evaluation": "core",
            "explanatory_attribution": "optional",
            "reporting": "projection_only",
            "investment_decision": "excluded",
        }

    def _metrics_by_window(self, panel: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        metrics: Dict[str, Dict[str, float]] = {}
        for item in panel:
            window = item.get("metric_window") or "latest"
            name = item.get("metric_name")
            value = item.get("metric_value")
            if not name or value is None:
                continue
            try:
                metrics.setdefault(window, {})[name] = float(Decimal(str(value)))
            except Exception:
                continue
        return metrics

    def _return_score(self, metrics: Dict[str, Dict[str, float]], rule_profile: Dict[str, Any]) -> Dict[str, Any]:
        one_year = metrics.get("1y", {})
        three_year = metrics.get("3y", {})
        low, high = rule_profile["return_range"]
        pieces = [
            self._normalize(one_year.get("annualized_return"), low, high),
            self._normalize(three_year.get("annualized_return"), low, high),
        ]
        return self._dimension(self._average(pieces), ["1Y/3Y 年化收益进入收益能力评分"])

    def _risk_score(self, metrics: Dict[str, Dict[str, float]], rule_profile: Dict[str, Any]) -> Dict[str, Any]:
        one_year = metrics.get("1y", {})
        three_year = metrics.get("3y", {})
        drawdown_low, drawdown_high = rule_profile["drawdown_range"]
        volatility_high, volatility_low = rule_profile["volatility_range"]
        pieces = [
            self._normalize(one_year.get("max_drawdown"), drawdown_low, drawdown_high),
            self._normalize(three_year.get("max_drawdown"), drawdown_low, drawdown_high),
            self._normalize(one_year.get("annualized_volatility"), volatility_high, volatility_low, higher_is_better=False),
        ]
        return self._dimension(self._average(pieces), ["最大回撤和年化波动进入风险控制评分"])

    def _risk_adjusted_score(self, metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        one_year = metrics.get("1y", {})
        three_year = metrics.get("3y", {})
        pieces = [
            self._normalize(one_year.get("sharpe_ratio"), 0, 2.5),
            self._normalize(one_year.get("calmar_ratio"), 0, 4),
            self._normalize(three_year.get("sharpe_ratio"), 0, 2.5),
        ]
        return self._dimension(self._average(pieces), ["夏普、Calmar 进入风险调整收益评分"])

    def _consistency_score(self, metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        one_year = metrics.get("1y", {})
        three_year = metrics.get("3y", {})
        positive_ratio_score = self._normalize(one_year.get("positive_return_ratio"), 0.45, 0.65)
        return_gap = None
        if one_year.get("annualized_return") is not None and three_year.get("annualized_return") is not None:
            return_gap = abs(one_year["annualized_return"] - three_year["annualized_return"])
        stability_score = self._normalize(return_gap, 0.12, 0.01, higher_is_better=False)
        return self._dimension(self._average([positive_ratio_score, stability_score]), ["胜率和 1Y/3Y 收益稳定性进入一致性评分"])

    def _manager_tenure_score(self, metrics: Dict[str, Dict[str, float]], rule_profile: Dict[str, Any]) -> Dict[str, Any]:
        tenure = metrics.get("manager_tenure", {})
        low, high = rule_profile["return_range"]
        drawdown_low, drawdown_high = rule_profile["drawdown_range"]
        pieces = [
            self._normalize(tenure.get("annualized_return"), low, high),
            self._normalize(tenure.get("max_drawdown"), drawdown_low, drawdown_high),
            self._normalize(tenure.get("tenure_days"), 180, 900),
        ]
        return self._dimension(self._average(pieces), ["现任经理任期内收益、回撤和任期长度进入评分"])

    def _metric_scores(self, metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        selected: Dict[str, Any] = {}
        for window in ["1y", "3y", "manager_tenure"]:
            for metric_name, value in metrics.get(window, {}).items():
                if metric_name in {"annualized_return", "max_drawdown", "sharpe_ratio", "calmar_ratio", "positive_return_ratio", "tenure_days"}:
                    selected[f"{window}.{metric_name}"] = value
        return selected

    def _missing_data(self, metrics: Dict[str, Dict[str, float]], quality: Dict[str, Any]) -> List[str]:
        missing = []
        for window in ["1y", "manager_tenure"]:
            if window not in metrics:
                missing.append(f"metric_window:{window}")
        for issue in quality.get("issues", []):
            missing.append(f"quality:{issue}")
        return missing

    def _missing_core_metrics(self, metrics: Dict[str, Dict[str, float]]) -> List[str]:
        one_year = metrics.get("1y", {})
        return [
            f"core_metric:1y.{metric_name}"
            for metric_name in ["annualized_return", "max_drawdown", "sharpe_ratio"]
            if one_year.get(metric_name) is None
        ]

    def _positive_factors(self, dimensions: Dict[str, Any], quality: Dict[str, Any]) -> List[str]:
        factors = [f"{name} 维度得分较高" for name, item in dimensions.items() if item.get("score", 0) >= 75]
        if quality.get("status") == "complete":
            factors.append("数据质量完整，评分可信度较高")
        return factors[:6]

    def _negative_factors(self, dimensions: Dict[str, Any], missing_data: List[str]) -> List[str]:
        factors = [f"{name} 维度需要复核" for name, item in dimensions.items() if item.get("score", 0) < 55]
        if missing_data:
            factors.append("存在缺失数据，需降低结论确定性")
        return factors[:6]

    def _latest_as_of(self, panel: List[Dict[str, Any]]) -> Optional[str]:
        dates = sorted({str(item.get("as_of_date")) for item in panel if item.get("as_of_date")})
        return dates[-1] if dates else None

    def _dimension(self, score: float, evidence: List[str]) -> Dict[str, Any]:
        return {
            "score": round(max(0, min(100, score)), 2),
            "weighted_score": round(max(0, min(100, score)), 2),
            "evidence": evidence,
        }

    def _normalize(self, value: Optional[float], low: float, high: float, higher_is_better: bool = True) -> Optional[float]:
        if value is None:
            return None
        if higher_is_better:
            if value <= low:
                return 0
            if value >= high:
                return 100
            return (value - low) / (high - low) * 100
        if value <= high:
            return 100
        if value >= low:
            return 0
        return (low - value) / (low - high) * 100

    def _average(self, values: List[Optional[float]]) -> float:
        valid = [value for value in values if value is not None]
        return sum(valid) / len(valid) if valid else 50.0
