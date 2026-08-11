"""普通用户基金浏览器 Module。"""
from typing import Any, Dict, Optional

from services.fund_research_snapshot_service import FundResearchSnapshotService
from services.professional_scoring_service import ProfessionalScoringService


class FundBrowserService:
    """用一个窄 Interface 输出基础基金研究列表。"""

    def browse(
        self,
        keyword: Optional[str] = None,
        peer_group: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ) -> Dict[str, Any]:
        from repositories import (
            get_fund_classification_repo,
            get_fund_repo,
            get_manager_repo,
            get_metric_snapshot_repo,
            get_research_profile_repo,
        )

        classification_repo = get_fund_classification_repo()
        if peer_group:
            rows = classification_repo.list_recommendation_funds(
                peer_group,
                limit=page_size,
                keyword=keyword,
            )
            total = classification_repo.count_recommendation_funds(peer_group, keyword=keyword)
            source = "standardized_peer_group_universe"
        else:
            rows, total = get_fund_repo().browse_funds(keyword=keyword, page=page, page_size=page_size)
            source = "fund_database"

        codes = [str(row.get("wind_code") or "") for row in rows if row.get("wind_code")]
        profiles = get_research_profile_repo().list_profiles(codes)
        peer_groups = classification_repo.list_fund_peer_group_map(codes)
        panels = get_metric_snapshot_repo().get_latest_panels("fund", codes)
        manager_ids = [
            manager_id
            for row in rows
            for manager_id in (row.get("manager_ids") or [])
            if manager_id
        ]
        manager_map = get_manager_repo().get_managers_by_ids(manager_ids)
        scoring_service = ProfessionalScoringService()

        funds = []
        for row in rows:
            code = str(row.get("wind_code") or "")
            peer = peer_groups.get(code) or {}
            profile = {
                **(profiles.get(code) or {}),
                "peer_group": peer.get("peer_group_name") or row.get("standardized_peer_group_name") or (profiles.get(code) or {}).get("peer_group"),
                "peer_group_id": peer.get("peer_group_id") or row.get("standardized_peer_group_id"),
                "peer_group_key": peer.get("peer_group_key") or row.get("standardized_peer_group_key"),
                "classification_confidence": peer.get("confidence"),
                "classification_source": peer.get("source"),
            }
            managers = [
                self._manager(manager_map[manager_id])
                for manager_id in (row.get("manager_ids") or [])
                if manager_id in manager_map
            ]
            try:
                classification_context = classification_repo.get_classification_context(code)
                quality = scoring_service.data_quality_service.evaluate_from_inputs(
                    row,
                    profile,
                    panels.get(code, []),
                    classification_context,
                )
                professional_scoring = scoring_service.score_from_inputs(
                    row,
                    profile,
                    panels.get(code, []),
                    quality,
                    classification_context,
                )
            except Exception:
                professional_scoring = None
            funds.append({
                **FundResearchSnapshotService.project_fund(row),
                "managers": managers,
                "research_profile": profile,
                "rolling_metrics": FundResearchSnapshotService.project_rolling_metrics(panels.get(code, [])),
                "professional_scoring": professional_scoring,
            })

        return {
            "funds": funds,
            "total": total,
            "page": page,
            "page_size": page_size,
            "peer_group": peer_group,
            "source": source,
            "product_scope": {
                "fund_browser": "core",
                "fund_classification": "core",
                "fund_evaluation": "core",
                "investment_decision": "excluded",
            },
        }

    @staticmethod
    def _manager(row: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
        return {
            "manager_id": row.get("wind_code"),
            "wind_code": row.get("wind_code"),
            "name": row.get("name"),
            "company": row.get("company"),
            "management_years": row.get("management_years"),
            "begin_date": raw_data.get("begin_date"),
            "end_date": raw_data.get("end_date"),
            "source": "tushare.fund_manager",
        }
