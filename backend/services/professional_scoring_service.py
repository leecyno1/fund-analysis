"""
专业基金评分服务

基于研究画像、滚动指标、现任经理任期指标和数据质量，按基金类型使用不同权重输出可解释评分。
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from services.data_quality_service import DataQualityService
from services.scoring_contract import build_scoring_output


class ProfessionalScoringService:
    """专业评分入口。"""

    TYPE_PROFILES = {
        "active_equity": {
            "fund_types": {"stock", "hybrid", "qdii"},
            "keywords": {"主动权益", "偏股混合", "QDII"},
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
            "fund_types": {"bond"},
            "keywords": {"债券", "纯债", "持有期"},
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
        "index_or_money": {
            "fund_types": {"index", "money"},
            "keywords": {"指数", "货币", "现金管理"},
            "weights": {
                "return": 0.15,
                "risk": 0.30,
                "risk_adjusted": 0.15,
                "consistency": 0.15,
                "manager_tenure": 0.05,
                "data_quality": 0.20,
            },
            "return_range": (0.00, 0.15),
            "drawdown_range": (-0.20, -0.001),
            "volatility_range": (0.20, 0.005),
        },
    }

    def __init__(self, data_quality_service: Optional[DataQualityService] = None):
        self.data_quality_service = data_quality_service or DataQualityService()

    def score_fund(self, fund_code: str) -> Dict[str, Any]:
        from repositories import get_fund_repo, get_metric_snapshot_repo, get_research_profile_repo

        fund_repo = get_fund_repo()
        metric_repo = get_metric_snapshot_repo()
        profile_repo = get_research_profile_repo()

        fund = fund_repo.get_fund_by_identifier(fund_code) or {}
        wind_code = fund.get("wind_code") or fund_code
        profile = profile_repo.get_profile(wind_code) or {}
        panel = metric_repo.get_latest_panel("fund", wind_code)
        metrics = self._metrics_by_window(panel)
        quality = self.data_quality_service.evaluate_fund(wind_code)
        profile_key = self._profile_key(fund, profile)
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
            calculation_method="professional_metric_snapshot_v1",
        )
        output["fund_type_profile"] = profile_key
        output["peer_group"] = profile.get("peer_group")
        output["primary_benchmark"] = profile.get("primary_benchmark")
        output["data_quality"] = quality
        return output

    def _profile_key(self, fund: Dict[str, Any], profile: Dict[str, Any]) -> str:
        fund_type = str(fund.get("type") or "").lower()
        peer_group = str(profile.get("peer_group") or "")
        for key, rule_profile in self.TYPE_PROFILES.items():
            if fund_type in rule_profile["fund_types"]:
                return key
            if any(keyword in peer_group for keyword in rule_profile["keywords"]):
                return key
        return "active_equity"

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
