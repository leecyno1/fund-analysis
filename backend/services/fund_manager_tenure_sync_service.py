"""从真实 Tushare 任职记录补齐基金经理与任期评价数据。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional

from services.manager_tenure_metric_service import ManagerTenureMetricService


class FundManagerTenureSyncService:
    """同步经理关系、现任团队起点和任期净值指标。"""

    def __init__(
        self,
        data_service: Any,
        fund_repo: Optional[Any] = None,
        manager_repo: Optional[Any] = None,
        profile_repo: Optional[Any] = None,
        classification_repo: Optional[Any] = None,
        tenure_metric_service: Optional[Any] = None,
    ):
        self.data_service = data_service
        self._fund_repo = fund_repo
        self._manager_repo = manager_repo
        self._profile_repo = profile_repo
        self._classification_repo = classification_repo
        self.tenure_metric_service = tenure_metric_service or ManagerTenureMetricService()

    def sync_fund(self, wind_code: str) -> Dict[str, Any]:
        code = str(wind_code or "").strip().upper()
        fund = self.fund_repo.get_fund(code)
        if not fund:
            return {"wind_code": code, "status": "skipped", "reason": "fund_not_found"}

        rows = self.data_service.get_fund_managers(code)
        active = [row for row in rows if row.get("is_current_manager") and row.get("manager_id")]
        active_ids = list(dict.fromkeys(str(row["manager_id"]) for row in active))
        begin_dates = sorted(
            str(row.get("begin_date"))[:10]
            for row in active
            if row.get("begin_date")
        )
        if not active_ids or not begin_dates:
            return {
                "wind_code": code,
                "status": "skipped",
                "reason": "current_manager_unavailable",
                "manager_rows": len(rows),
            }

        synced_at = datetime.now(UTC).isoformat()
        manager_write_failed = []
        manager_rows: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            manager_id = str(row.get("manager_id") or "").strip()
            if manager_id:
                manager_rows.setdefault(manager_id, []).append(row)
        for manager_id, history in manager_rows.items():
            row = next((item for item in history if item.get("is_current_manager")), None)
            row = row or max(history, key=lambda item: str(item.get("begin_date") or ""))
            is_current = bool(row.get("is_current_manager"))
            saved = self.manager_repo.upsert_manager(manager_id, {
                "name": row.get("name") or manager_id.split("|")[0],
                "education": row.get("education") or "",
                "experience_years": self._years_since(row.get("begin_date")),
                "management_years": self._years_since(row.get("begin_date")),
                "current_funds": [code] if is_current else [],
                "historical_performance": {
                    "fund_code": code,
                    "fund_tenure_start": row.get("begin_date"),
                    "fund_tenure_end": row.get("end_date"),
                    "is_current_manager": is_current,
                },
                "raw_data": {
                    "source": "tushare.fund_manager",
                    "synced_at": synced_at,
                    "fund_code": code,
                    "manager_id": manager_id,
                    "fund_manager_row": row.get("raw_data") or row,
                },
            })
            if not saved:
                manager_write_failed.append(manager_id)

        if manager_write_failed:
            return {
                "wind_code": code,
                "status": "failed",
                "reason": "manager_update_failed",
                "manager_ids": manager_write_failed,
            }

        tenure_start = max(begin_dates)
        if not self.fund_repo.update_manager_assignments(code, active_ids, {
            "source": "tushare.fund_manager",
            "synced_at": synced_at,
            "manager_ids": active_ids,
            "manager_tenure_start": tenure_start,
        }):
            return {"wind_code": code, "status": "failed", "reason": "fund_update_failed"}

        context = self.classification_repo.get_classification_context(code) or {}
        benchmark = context.get("benchmark_mapping") or {}
        self.profile_repo.upsert_manager_tenure(
            wind_code=code,
            manager_tenure_start=tenure_start,
            primary_benchmark=str(benchmark.get("benchmark_code") or benchmark.get("benchmark_name") or ""),
            peer_group=str(context.get("peer_group_name") or context.get("peer_group_key") or ""),
            evidence={
                "manager_tenure": {
                    "source": "tushare.fund_manager",
                    "current_team_latest_begin_date": tenure_start,
                    "manager_ids": active_ids,
                    "synced_at": synced_at,
                }
            },
        )
        metrics = self.tenure_metric_service.calculate_and_save_for_fund(code)
        return {
            "wind_code": code,
            "status": "synced",
            "manager_ids": active_ids,
            "manager_count": len(active_ids),
            "manager_tenure_start": tenure_start,
            "tenure_metrics_saved": int(metrics.get("saved") or 0),
            "tenure_metric_reason": metrics.get("reason"),
        }

    def sync_funds(self, wind_codes: Iterable[str]) -> Dict[str, Any]:
        results = [self.sync_fund(code) for code in wind_codes]
        return {
            "requested": len(results),
            "synced": sum(item["status"] == "synced" for item in results),
            "skipped": sum(item["status"] == "skipped" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
            "tenure_metrics_saved": sum(item.get("tenure_metrics_saved", 0) for item in results),
            "results": results,
        }

    @staticmethod
    def _years_since(value: Any) -> float:
        try:
            start = datetime.fromisoformat(str(value)[:10]).date()
        except (TypeError, ValueError):
            return 0.0
        return round(max(0, (datetime.now(UTC).date() - start).days) / 365.25, 2)

    @property
    def fund_repo(self):
        if self._fund_repo is None:
            from repositories import get_fund_repo
            self._fund_repo = get_fund_repo()
        return self._fund_repo

    @property
    def manager_repo(self):
        if self._manager_repo is None:
            from repositories import get_manager_repo
            self._manager_repo = get_manager_repo()
        return self._manager_repo

    @property
    def profile_repo(self):
        if self._profile_repo is None:
            from repositories import get_research_profile_repo
            self._profile_repo = get_research_profile_repo()
        return self._profile_repo

    @property
    def classification_repo(self):
        if self._classification_repo is None:
            from repositories import get_fund_classification_repo
            self._classification_repo = get_fund_classification_repo()
        return self._classification_repo
