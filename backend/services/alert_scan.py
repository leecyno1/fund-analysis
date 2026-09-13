"""
预警扫描服务
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from repositories import get_alert_repo, get_fund_pool_repo, get_manager_repo, get_metric_snapshot_repo

# 现任经理上任多少天内视为“经理变更”，需要重估经理维度结论
MANAGER_CHANGE_ALERT_DAYS = 30


class AlertScanService:
    def __init__(
        self,
        pool_repo=None,
        metric_repo=None,
        alert_repo=None,
        peer_service=None,
        manager_repo=None,
        today: Optional[date] = None,
        max_members_per_status: Optional[int] = None,
        include_peer_metrics: bool = True,
    ):
        self.pool_repo = pool_repo or get_fund_pool_repo()
        self.metric_repo = metric_repo or get_metric_snapshot_repo()
        self.alert_repo = alert_repo or get_alert_repo()
        self.manager_repo = manager_repo or get_manager_repo()
        if peer_service is None:
            from services.peer_comparison_service import PeerComparisonService

            peer_service = PeerComparisonService()
        self.peer_service = peer_service
        self.today = today or date.today()
        self.max_members_per_status = max_members_per_status
        self.include_peer_metrics = include_peer_metrics

    def scan(self) -> Dict[str, Any]:
        created_events: List[Dict[str, Any]] = []
        pools = self.pool_repo.list_pools()

        for pool in pools:
            for status in ["watch", "core", "candidate"]:
                members = self.pool_repo.list_members(pool["id"], status=status)
                if self.max_members_per_status is not None:
                    members = members[:max(0, self.max_members_per_status)]
                for member in members:
                    metric_map = self._metric_map(self.metric_repo.get_latest_panel("fund", member["fund_id"]))
                    drawdown = metric_map.get("max_drawdown")
                    if drawdown is not None and drawdown <= Decimal("-0.15") and not self._has_open(member["fund_id"], "drawdown"):
                        created_events.append(self.alert_repo.create_event(
                            rule_id=None,
                            fund_id=member["fund_id"],
                            pool_member_id=member["id"],
                            event_type="drawdown",
                            severity="high" if drawdown <= Decimal("-0.2") else "medium",
                            title="回撤超过阈值",
                            message=f"当前最大回撤 {drawdown}，已超过监控阈值",
                            status="new",
                            details={"current_drawdown": float(drawdown), "pool_id": pool["id"]},
                        ))
                    review_date = self._parse_date(member.get("next_review_date"))
                    if review_date is not None and review_date < self.today and not self._has_open(member["fund_id"], "review_due"):
                        overdue_days = (self.today - review_date).days
                        created_events.append(self.alert_repo.create_event(
                            rule_id=None,
                            fund_id=member["fund_id"],
                            pool_member_id=member["id"],
                            event_type="review_due",
                            severity="high" if overdue_days >= 30 and status == "core" else "medium",
                            title="基金池成员复核到期",
                            message=f"下次复核日 {review_date.isoformat()} 已过期 {overdue_days} 天",
                            status="new",
                            details={"pool_id": pool["id"], "member_status": status, "overdue_days": overdue_days},
                        ))
                    weak_peer_metrics = self._weak_peer_metrics(member["fund_id"]) if self.include_peer_metrics else []
                    if weak_peer_metrics and not self._has_open(member["fund_id"], "peer_percentile"):
                        created_events.append(self.alert_repo.create_event(
                            rule_id=None,
                            fund_id=member["fund_id"],
                            pool_member_id=member["id"],
                            event_type="peer_percentile",
                            severity="high" if any(item["percentile"] <= 20 for item in weak_peer_metrics) else "medium",
                            title="同类分位进入尾部区间",
                            message="；".join([f"{item['label']} 分位 {item['percentile']}" for item in weak_peer_metrics]),
                            status="new",
                            details={"pool_id": pool["id"], "member_status": status, "weak_peer_metrics": weak_peer_metrics},
                        ))
                    manager_change_event = self._manager_change_event(member, pool, status)
                    if manager_change_event is not None:
                        created_events.append(manager_change_event)

        return {
            "status": "completed",
            "created": len(created_events),
            "events": created_events,
        }

    def _has_open(self, fund_id: str, event_type: str) -> bool:
        try:
            return bool(self.alert_repo.has_open_event(fund_id, event_type))
        except Exception:
            return False

    def _manager_change_event(self, member: Dict[str, Any], pool: Dict[str, Any], status: str) -> Optional[Dict[str, Any]]:
        wind_code = self._member_wind_code(member)
        if not wind_code:
            return None
        try:
            context = self.manager_repo.get_current_fund_tenure_context(wind_code)
        except Exception:
            return None
        start_date = self._parse_date(context.get("start_date"))
        if start_date is None:
            return None
        days_since_start = (self.today - start_date).days
        if days_since_start < 0 or days_since_start > MANAGER_CHANGE_ALERT_DAYS:
            return None
        if self.alert_repo.event_exists(
            fund_id=member["fund_id"],
            event_type="manager_change",
            detail_key="manager_start_date",
            detail_value=start_date.isoformat(),
        ):
            return None
        return self.alert_repo.create_event(
            rule_id=None,
            fund_id=member["fund_id"],
            pool_member_id=member["id"],
            event_type="manager_change",
            severity="high" if status in {"candidate", "core"} else "medium",
            title=f"经理变更：现任经理上任不足 {MANAGER_CHANGE_ALERT_DAYS} 天",
            message=f"现任经理团队 {start_date.isoformat()} 上任（{days_since_start} 天前），既有经理维度结论需按新任经理重估",
            status="new",
            details={
                "pool_id": pool["id"],
                "member_status": status,
                "wind_code": wind_code,
                "manager_start_date": start_date.isoformat(),
                "days_since_manager_start": days_since_start,
                "manager_ids": list(context.get("manager_ids") or []),
            },
        )

    def _weak_peer_metrics(self, fund_id: str) -> List[Dict[str, Any]]:
        try:
            percentiles = self.peer_service.build_peer_percentiles(fund_id, window="1y").get("metrics", {})
        except Exception:
            return []
        watched = {
            "professional_score": "专业评分",
            "annualized_return": "1Y 年化收益",
        }
        weak_metrics = []
        for metric_name, label in watched.items():
            metric = percentiles.get(metric_name) or {}
            percentile = metric.get("percentile")
            if percentile is None:
                continue
            try:
                percentile_value = float(percentile)
            except Exception:
                continue
            if percentile_value <= 25:
                weak_metrics.append({
                    "metric_name": metric_name,
                    "label": label,
                    "percentile": round(percentile_value, 2),
                })
        return weak_metrics

    @staticmethod
    def _member_wind_code(member: Dict[str, Any]) -> str:
        return str(
            member.get("fund_wind_code")
            or member.get("wind_code")
            or member.get("fund_code")
            or member.get("fund_id")
            or ""
        ).strip().upper()

    @staticmethod
    def _metric_map(panel: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        result: Dict[str, Decimal] = {}
        for item in panel:
            name = item.get("metric_name")
            value = item.get("metric_value")
            if name is None or value is None:
                continue
            try:
                result[name] = Decimal(str(value))
            except Exception:
                continue
        return result

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except Exception:
            return None
