"""分类内基金评价 Module。"""
from typing import Any, Dict, List, Optional

from services.peer_comparison_service import PeerComparisonService
from services.professional_scoring_service import ProfessionalScoringService


class FundEvaluationService:
    """通过一个 Interface 汇合分类、同类组、基准、评分和同类分位。"""

    METHODOLOGY_VERSION = "fund_evaluation_v2"

    def __init__(
        self,
        scoring_service: Optional[ProfessionalScoringService] = None,
        peer_comparison_service: Optional[PeerComparisonService] = None,
    ):
        self.scoring_service = scoring_service or ProfessionalScoringService()
        self.peer_comparison_service = peer_comparison_service or PeerComparisonService(
            scoring_service=self.scoring_service
        )

    def evaluate_fund(self, wind_code: str, window: str = "1y") -> Dict[str, Any]:
        scoring = self.scoring_service.score_fund(wind_code)
        peer = self.peer_comparison_service.build_peer_percentiles(wind_code, window=window)
        classification = scoring.get("classification") or peer.get("classification") or {
            "status": "insufficient_evidence",
            "missing_items": ["基金分类结果缺失"],
        }

        missing_items = self._missing_items(scoring, peer, classification)
        status = self._status(scoring, peer, classification)
        evaluation_blocked = status == "insufficient_evidence"

        return {
            "status": status,
            "methodology_version": self.METHODOLOGY_VERSION,
            "evaluation_scope": "category_relative",
            "target": {
                "wind_code": scoring.get("target_id") or peer.get("target_id") or wind_code,
                "name": peer.get("name"),
                "fund_type": peer.get("fund_type"),
                "as_of_date": scoring.get("as_of_date"),
            },
            "classification": classification,
            "peer_context": {
                "peer_group": peer.get("peer_group") or classification.get("peer_group"),
                "peer_group_id": classification.get("peer_group_id"),
                "peer_group_key": classification.get("peer_group_key"),
                "primary_benchmark": peer.get("primary_benchmark") or classification.get("primary_benchmark"),
                "benchmark_code": classification.get("benchmark_code"),
                "benchmark_mapping": classification.get("benchmark_mapping"),
                "source": peer.get("peer_group_source"),
                "peer_count": peer.get("peer_count", 0),
                "minimum_peer_count": peer.get("minimum_valid_peer_count"),
                "sample_status": peer.get("sample_status"),
                "metric_window": peer.get("metric_window") or window,
            },
            "evaluation": {
                "overall_score": None if evaluation_blocked else scoring.get("overall_score"),
                "overall_grade": "insufficient_evidence" if evaluation_blocked else scoring.get("overall_grade"),
                "dimension_scores": {} if evaluation_blocked else scoring.get("dimension_scores", {}),
                "metric_scores": {} if evaluation_blocked else scoring.get("metric_scores", {}),
                "peer_percentiles": {} if evaluation_blocked else peer.get("metrics", {}),
                "positive_factors": scoring.get("positive_factors", []),
                "negative_factors": scoring.get("negative_factors", []),
                "calculation_method": scoring.get("calculation_method"),
                "data_quality": scoring.get("data_quality", {}),
            },
            "explanatory_evidence": {
                "barra": {
                    "role": "optional",
                    "status": "not_requested",
                    "included_in_score": False,
                },
                "brinson": {
                    "role": "optional",
                    "status": "not_requested",
                    "included_in_score": False,
                },
            },
            "missing_items": missing_items,
            "product_scope": {
                "fund_classification": "core",
                "fund_evaluation": "core",
                "explanatory_attribution": "optional",
                "reporting": "projection_only",
                "investment_decision": "excluded",
            },
        }

    def _status(
        self,
        scoring: Dict[str, Any],
        peer: Dict[str, Any],
        classification: Dict[str, Any],
    ) -> str:
        if classification.get("status") != "classified" or scoring.get("status") == "insufficient_evidence":
            return "insufficient_evidence"
        if not self._core_context_ready(peer, classification):
            return "insufficient_evidence"
        if scoring.get("status") != "ok" or peer.get("sample_status") != "sufficient":
            return "partial"
        return "ok"

    def _missing_items(
        self,
        scoring: Dict[str, Any],
        peer: Dict[str, Any],
        classification: Dict[str, Any],
    ) -> List[str]:
        items: List[str] = []
        items.extend(str(item) for item in classification.get("missing_items", []) if item)
        items.extend(str(item) for item in scoring.get("missing_data", []) if item)
        if not (peer.get("peer_group") or classification.get("peer_group")):
            items.append("缺少显式同类组，不能形成分类内基金评价")
        if not (peer.get("primary_benchmark") or classification.get("primary_benchmark")):
            items.append("缺少有效基准映射，不能形成分类内基金评价")

        sample_status = peer.get("sample_status")
        if sample_status not in {None, "sufficient"}:
            peer_count = peer.get("peer_count", 0)
            minimum = peer.get("minimum_valid_peer_count")
            items.append(f"同类组样本状态为 {sample_status}（当前 {peer_count}，最低 {minimum}）")

        gap = peer.get("peer_metric_gap") or {}
        blocking_metrics = gap.get("blocking_metrics") or []
        if blocking_metrics:
            items.append(f"同类分位缺少可用指标：{', '.join(str(item) for item in blocking_metrics)}")

        return list(dict.fromkeys(item for item in items if item))

    def _core_context_ready(
        self,
        peer: Dict[str, Any],
        classification: Dict[str, Any],
    ) -> bool:
        peer_group = peer.get("peer_group") or classification.get("peer_group")
        benchmark = peer.get("primary_benchmark") or classification.get("primary_benchmark")
        return bool(peer_group and benchmark)
