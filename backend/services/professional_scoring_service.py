"""
专业基金评分服务

基于基金分类、滚动指标、现任经理任期指标和数据质量，按评价口径输出可解释评分。
分类证据不足或尚未建立专属评价方法时显式停止，禁止默认套用主动权益评分。
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from services.data_quality_service import DataQualityService
from services.fund_classification_service import FundClassificationService
from services.fund_evaluation_methodology import FundEvaluationMethodology
from services.scoring_contract import build_scoring_output


class ProfessionalScoringService:
    """专业评分入口。"""

    TYPE_PROFILES = FundEvaluationMethodology.PROFILES

    def __init__(
        self,
        data_quality_service: Optional[DataQualityService] = None,
        classification_service: Optional[FundClassificationService] = None,
        classification_adapter: Optional[Any] = None,
        fund_repo: Optional[Any] = None,
        metric_repo: Optional[Any] = None,
        profile_repo: Optional[Any] = None,
        methodology: Optional[FundEvaluationMethodology] = None,
    ):
        self.data_quality_service = data_quality_service or DataQualityService()
        self.classification_service = classification_service or FundClassificationService()
        self._classification_adapter = classification_adapter
        self._fund_repo_adapter = fund_repo
        self._metric_repo_adapter = metric_repo
        self._profile_repo_adapter = profile_repo
        self.methodology = methodology or FundEvaluationMethodology()

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
        metrics = self._merge_metric_windows(
            self._metrics_by_window(panel),
            self._fund_fallback_metrics(fund),
        )
        methodology_result = self.methodology.evaluate(profile_key, metrics, quality)
        if methodology_result.get("status") not in {"ok", "partial"}:
            return self._unavailable_evaluation(
                wind_code,
                classification,
                quality,
                methodology_result.get("missing_data") or ["类别专属基金评价证据不足"],
                calculation_method=methodology_result.get("calculation_method"),
            )
        dimensions = methodology_result["dimensions"]
        missing_data = methodology_result.get("missing_data", [])
        output = build_scoring_output(
            target_type="fund",
            target_id=wind_code,
            total_score=methodology_result["total_score"],
            dimensions=dimensions,
            metric_scores=methodology_result.get("metric_scores", {}),
            positive_factors=self._positive_factors(dimensions, quality),
            negative_factors=self._negative_factors(dimensions, missing_data),
            missing_data=missing_data,
            as_of_date=self._latest_as_of(panel),
            calculation_method=methodology_result["calculation_method"],
        )
        output["status"] = methodology_result["status"]
        output["evaluation_scope"] = "classification_gated"
        output["classification"] = classification
        output["fund_type_profile"] = profile_key
        output["peer_group"] = classification.get("peer_group")
        output["primary_benchmark"] = classification.get("primary_benchmark")
        output["data_quality"] = quality
        output["product_scope"] = self._product_scope()
        return output

    def score_peer_metrics(self, profile_key: str, metrics: Dict[str, Any]) -> Optional[float]:
        return self.methodology.score_peer(profile_key, metrics)

    def metric_facts_from_fund(self, fund: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """把基金原始字段适配为类别评价可消费的指标事实。"""
        return self._fund_fallback_metrics(fund)

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
        calculation_method: Optional[str] = None,
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
            "calculation_method": calculation_method or "category_evaluation_methodology_v1:unavailable",
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

    def _merge_metric_windows(
        self,
        primary: Dict[str, Dict[str, float]],
        fallback: Dict[str, Dict[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        merged = {window: values.copy() for window, values in primary.items()}
        for window, values in fallback.items():
            target = merged.setdefault(window, {})
            for metric_name, value in values.items():
                if target.get(metric_name) is None and value is not None:
                    target[metric_name] = value
        return merged

    def _fund_fallback_metrics(self, fund: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        performance = fund.get("performance_data") or fund.get("performance") or {}
        risk = fund.get("risk_metrics") or {}
        performance = performance if isinstance(performance, dict) else {}
        risk = risk if isinstance(risk, dict) else {}
        raw_data = fund.get("raw_data") or {}
        info = raw_data.get("info") if isinstance(raw_data, dict) else {}
        info = info if isinstance(info, dict) else {}
        universe = raw_data.get("universe") if isinstance(raw_data, dict) else {}
        universe = universe if isinstance(universe, dict) else {}

        management_fee_source = "fund"
        management_fee = self._first_number(fund, ["management_fee"])
        if management_fee is None:
            management_fee = self._first_number(info, ["management_fee", "m_fee"])
            management_fee_source = "tushare_info"
        if management_fee is None:
            management_fee = self._first_number(universe, ["management_fee", "m_fee"])
            management_fee_source = "tushare_universe"
        custodian_fee_source = "fund"
        custodian_fee = self._first_number(fund, ["custodian_fee"])
        if custodian_fee is None:
            custodian_fee = self._first_number(info, ["custodian_fee", "c_fee"])
            custodian_fee_source = "tushare_info"
        if custodian_fee is None:
            custodian_fee = self._first_number(universe, ["custodian_fee", "c_fee"])
            custodian_fee_source = "tushare_universe"
        management_fee = self._fee_rate(management_fee, management_fee_source.startswith("tushare_"))
        custodian_fee = self._fee_rate(custodian_fee, custodian_fee_source.startswith("tushare_"))
        expense_ratio = None
        if management_fee is not None or custodian_fee is not None:
            expense_ratio = (management_fee or 0.0) + (custodian_fee or 0.0)

        max_drawdown = self._first_number(risk, ["max_drawdown_1y", "max_drawdown_2y", "max_drawdown"])
        if max_drawdown is None:
            max_drawdown = self._first_number(performance, ["max_drawdown_1y", "max_drawdown"])
        annualized_volatility = self._first_number(
            risk,
            ["annualized_volatility_1y", "volatility_1y", "volatility"],
        )
        if annualized_volatility is None:
            annualized_volatility = self._first_number(performance, ["annualized_volatility_1y", "volatility"])

        one_year = {
            "annualized_return": self._first_number(performance, ["annualized_return_1y", "return_1y", "annual_return"]),
            "max_drawdown": max_drawdown,
            "annualized_volatility": annualized_volatility,
            "sharpe_ratio": self._first_number(performance, ["sharpe_ratio", "sharpe"]),
            "calmar_ratio": self._first_number(performance, ["calmar_ratio"]),
            "positive_return_ratio": self._first_number(performance, ["positive_return_ratio", "win_rate_1y"]),
            "tracking_error": self._first_number(risk, ["tracking_error"]),
            "information_ratio": self._first_number(risk, ["information_ratio"]),
            "tracking_difference": self._first_number(performance, ["tracking_difference"]),
            "excess_return": self._first_number(performance, ["excess_return"]),
        }
        latest = {
            "expense_ratio": expense_ratio,
            "aum": self._first_number(fund, ["total_asset", "aum"]),
            "seven_day_annualized_yield": self._first_number(
                performance,
                ["seven_day_annualized_yield", "yield_7d", "seven_day_yield"],
            ),
            "income_per_10000": self._first_number(performance, ["income_per_10000", "income_10k"]),
        }
        return {
            "1y": {key: value for key, value in one_year.items() if value is not None},
            "latest": {key: value for key, value in latest.items() if value is not None},
        }

    def _first_number(self, source: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for key in keys:
            value = source.get(key)
            if value is None:
                continue
            try:
                return float(Decimal(str(value)))
            except Exception:
                continue
        return None

    def _fee_rate(self, value: Optional[float], percentage_points: bool) -> Optional[float]:
        """Tushare m_fee/c_fee 使用百分数单位；评价层统一转为小数比率。"""
        if value is None:
            return None
        return value / 100.0 if percentage_points or abs(value) >= 0.05 else value

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
