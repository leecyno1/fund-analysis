"""统一基金研究快照 Module。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from services.fund_evaluation_service import FundEvaluationService
from services.performance_attribution_service import PerformanceAttributionService


class FundResearchSnapshotService:
    """一次输出详情、推荐和 AI 共用的基金研究事实。"""

    INTERFACE_VERSION = "fund_research_snapshot_v1"

    def __init__(
        self,
        evaluation_service: Optional[FundEvaluationService] = None,
        attribution_service: Optional[PerformanceAttributionService] = None,
    ):
        self.evaluation_service = evaluation_service or FundEvaluationService()
        self.attribution_service = attribution_service or PerformanceAttributionService()

    def build(
        self,
        wind_code: str,
        window: str = "1y",
        include_research: bool = True,
        include_attribution: bool = False,
        research_limit: int = 6,
    ) -> Dict[str, Any]:
        context = self.evaluation_service.load_context(wind_code)
        if not context.get("found"):
            raise ValueError(f"Fund not found: {wind_code}")

        fund = context["fund"]
        resolved_code = str(fund.get("wind_code") or wind_code)
        evaluation = self.evaluation_service.evaluate_from_context(context, window=window)
        managers = self._load_managers(fund.get("manager_ids") or [])
        research_reports = self._load_research_reports(resolved_code, research_limit) if include_research else []
        attribution = self._load_attribution(resolved_code) if include_attribution else self._not_requested_attribution()
        research_profile = context.get("profile") or {}
        style_profile = self._style_profile(research_profile, research_reports)
        missing_items = list(evaluation.get("missing_items") or [])
        if include_research and not research_reports:
            missing_items.append("没有找到已关联到该基金的调研纪要")
        if include_attribution:
            missing_items.extend(self._attribution_missing_items(attribution))

        return self._json_safe({
            "interface_version": self.INTERFACE_VERSION,
            "mode": "full",
            "status": evaluation.get("status"),
            "fund": self.project_fund(fund),
            "managers": managers,
            "research_profile": research_profile,
            "style_profile": style_profile,
            "rolling_metrics": self.project_rolling_metrics(context.get("metric_panel") or []),
            "data_quality": context.get("data_quality") or {},
            "evaluation": evaluation,
            "research_memos": {
                "status": "available" if research_reports else "empty",
                "count": len(research_reports),
                "items": research_reports,
            },
            "attribution": attribution,
            "evidence": {
                "as_of_date": (evaluation.get("target") or {}).get("as_of_date") or fund.get("nav_date"),
                "fund_data_as_of": fund.get("nav_date") or fund.get("updated_at"),
                "profile_as_of": research_profile.get("updated_at"),
                "research_latest_date": research_reports[0].get("report_date") if research_reports else None,
                "missing_items": list(dict.fromkeys(str(item) for item in missing_items if item)),
            },
            "product_scope": {
                "fund_classification": "core",
                "fund_evaluation": "core",
                "fund_recommendation": "projection",
                "performance_attribution": "on_demand_evidence",
                "ai_analysis": "on_demand_projection",
                "investment_decision": "excluded",
            },
        })

    @classmethod
    def candidate_snapshot(cls, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """把候选基金投影为与完整快照同口径的摘要。"""
        scoring = candidate.get("professional_scoring") or {}
        profile = candidate.get("research_profile") or {}
        peer_percentiles = candidate.get("peer_percentiles") or {}
        evidence = candidate.get("recommendation_evidence") or {}
        return {
            "interface_version": cls.INTERFACE_VERSION,
            "mode": "candidate_summary",
            "status": scoring.get("status"),
            "fund": cls.project_fund(candidate),
            "managers": candidate.get("managers") or [],
            "research_profile": profile,
            "style_profile": {
                "style_label": profile.get("style_label"),
                "strategy_tags": profile.get("strategy_tags") or [],
                "source": "fund_research_profile",
            },
            "rolling_metrics": candidate.get("rolling_metrics") or {},
            "evaluation": {
                "status": scoring.get("status"),
                "peer_context": {
                    "peer_group": profile.get("peer_group"),
                    "peer_group_id": profile.get("peer_group_id"),
                    "peer_group_key": profile.get("peer_group_key"),
                },
                "evaluation": {
                    "overall_score": scoring.get("overall_score"),
                    "overall_grade": scoring.get("overall_grade"),
                    "peer_percentiles": peer_percentiles.get("metrics") or {},
                    "calculation_method": scoring.get("calculation_method"),
                },
            },
            "recommendation_evidence": evidence,
            "evidence": {
                "as_of_date": evidence.get("data_as_of") or scoring.get("as_of_date") or candidate.get("nav_date"),
                "missing_items": [],
            },
        }

    @staticmethod
    def project_fund(fund: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = fund.get("raw_data") if isinstance(fund.get("raw_data"), dict) else {}
        info = raw_data.get("info") if isinstance(raw_data.get("info"), dict) else {}
        return {
            "id": fund.get("id") or fund.get("wind_code"),
            "wind_code": fund.get("wind_code"),
            "name": fund.get("name"),
            "type": fund.get("type"),
            "manager_ids": fund.get("manager_ids") or [],
            "total_asset": fund.get("total_asset"),
            "nav": fund.get("nav"),
            "nav_date": fund.get("nav_date"),
            "establishment_date": fund.get("establishment_date"),
            "updated_at": fund.get("updated_at"),
            "benchmark": info.get("benchmark") or fund.get("benchmark"),
            "performance_data": fund.get("performance_data") or fund.get("performance") or {},
            "risk_metrics": fund.get("risk_metrics") or {},
            "holding_count": fund.get("holding_count"),
        }

    def _load_managers(self, manager_ids: List[str]) -> List[Dict[str, Any]]:
        from repositories import get_manager_repo

        manager_map = get_manager_repo().get_managers_by_ids(manager_ids)
        managers = []
        for manager_id in manager_ids:
            row = manager_map.get(manager_id)
            if not row:
                continue
            raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
            managers.append({
                "manager_id": row.get("wind_code"),
                "wind_code": row.get("wind_code"),
                "name": row.get("name"),
                "company": row.get("company"),
                "education": row.get("education"),
                "work_years": row.get("work_years"),
                "management_years": row.get("management_years"),
                "current_funds": row.get("current_funds") or [],
                "begin_date": raw_data.get("begin_date"),
                "end_date": raw_data.get("end_date"),
                "source": "tushare.fund_manager",
            })
        return managers

    def _load_research_reports(self, wind_code: str, limit: int) -> List[Dict[str, Any]]:
        reports = self._mongo_research_reports(wind_code, limit)
        if len(reports) < limit:
            reports.extend(self._postgres_research_reports(wind_code, limit - len(reports)))
        deduplicated = {}
        for report in reports:
            key = str(report.get("id") or f"{report.get('title')}:{report.get('report_date')}")
            deduplicated.setdefault(key, report)
        return sorted(
            deduplicated.values(),
            key=lambda item: str(item.get("report_date") or ""),
            reverse=True,
        )[:limit]

    def _mongo_research_reports(self, wind_code: str, limit: int) -> List[Dict[str, Any]]:
        from service_registry import get_db

        db = get_db()
        if db is None:
            return []
        rows = []
        for doc in db.research_reports.find({"fund_ids": wind_code}).sort("report_date", -1).limit(limit):
            rows.append({
                "id": str(doc.get("_id", "")),
                "title": doc.get("title"),
                "report_date": doc.get("report_date"),
                "manager_id": doc.get("manager_id"),
                "manager_name": doc.get("manager_name"),
                "source": doc.get("source"),
                "summary": doc.get("summary", ""),
                "key_points": doc.get("key_points", []),
                "classifications": doc.get("classifications", []),
                "style_labels": doc.get("style_labels", []),
            })
        return rows

    def _postgres_research_reports(self, wind_code: str, limit: int) -> List[Dict[str, Any]]:
        from database import get_engine
        from sqlalchemy import text

        sql = text("""
            SELECT id, manager_id, title, report_date, source, summary, key_points, tags
            FROM research_reports
            WHERE :wind_code = ANY(COALESCE(fund_ids, ARRAY[]::TEXT[]))
            ORDER BY report_date DESC NULLS LAST, updated_at DESC
            LIMIT :limit
        """)
        with get_engine().connect() as conn:
            rows = conn.execute(sql, {"wind_code": wind_code, "limit": max(1, limit)}).fetchall()
        return [{
            "id": str(row._mapping.get("id")),
            "title": row._mapping.get("title"),
            "report_date": row._mapping.get("report_date"),
            "manager_id": row._mapping.get("manager_id"),
            "manager_name": None,
            "source": row._mapping.get("source"),
            "summary": row._mapping.get("summary") or "",
            "key_points": row._mapping.get("key_points") or [],
            "classifications": [],
            "style_labels": row._mapping.get("tags") or [],
        } for row in rows]

    def _load_attribution(self, wind_code: str) -> Dict[str, Any]:
        try:
            return self.attribution_service.analyze(wind_code)
        except Exception as exc:
            reason = f"业绩归因输入不可用：{exc.__class__.__name__}"
            return {
                "status": "insufficient_evidence",
                "barra": {
                    "status": "insufficient_evidence",
                    "method": "barra_style_risk_model",
                    "missing_items": [reason],
                },
                "brinson": {
                    "status": "insufficient_evidence",
                    "method": "brinson_fachler",
                    "missing_items": [reason],
                    "effects": [],
                },
                "nav_factor_lens": {"status": "insufficient_evidence", "missing_items": [reason]},
                "nav_return_attribution": {"status": "insufficient_evidence", "missing_items": [reason]},
            }

    @staticmethod
    def _not_requested_attribution() -> Dict[str, Any]:
        return {
            "status": "not_requested",
            "barra": {"status": "not_requested", "method": "barra_style_risk_model"},
            "brinson": {"status": "not_requested", "method": "brinson_fachler"},
            "nav_factor_lens": {"status": "not_requested", "method": "nav_behavior_factor_lens"},
            "nav_return_attribution": {"status": "not_requested", "method": "nav_return_attribution"},
        }

    @staticmethod
    def _attribution_missing_items(attribution: Dict[str, Any]) -> List[str]:
        items = []
        for key in ("barra", "brinson", "nav_factor_lens", "nav_return_attribution"):
            block = attribution.get(key) or {}
            items.extend(block.get("missing_items") or [])
        return items

    @staticmethod
    def _style_profile(profile: Dict[str, Any], reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        memo_classifications = []
        memo_style_labels = []
        for report in reports:
            memo_classifications.extend(report.get("classifications") or [])
            memo_style_labels.extend(report.get("style_labels") or [])
        return {
            "style_label": profile.get("style_label"),
            "strategy_tags": profile.get("strategy_tags") or [],
            "memo_classifications": list(dict.fromkeys(str(item) for item in memo_classifications if item)),
            "memo_style_labels": list(dict.fromkeys(str(item) for item in memo_style_labels if item)),
            "source": "fund_research_profile+research_memos",
        }

    @staticmethod
    def project_rolling_metrics(panel: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for item in panel:
            window = item.get("metric_window")
            metric_name = item.get("metric_name")
            if not window or not metric_name:
                continue
            result.setdefault(window, {})[metric_name] = item.get("metric_value")
            if item.get("as_of_date"):
                result[window]["as_of_date"] = item.get("as_of_date")
            if item.get("benchmark_code"):
                result[window]["benchmark_code"] = item.get("benchmark_code")
        return result

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        return value
