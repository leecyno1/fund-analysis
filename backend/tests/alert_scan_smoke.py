import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.alert_scan import AlertScanService


class FakePoolRepo:
    def list_pools(self):
        return [{"id": "pool-1", "name": "默认候选池"}]

    def list_members(self, pool_id: str, status=None):
        return [
            {
                "id": "member-1",
                "pool_id": pool_id,
                "fund_id": "FUND-TEST-001",
                "status": status or 'watch',
            }
        ]


class FakeMetricRepo:
    def get_latest_panel(self, target_type, target_id):
        return [
            {"metric_name": "max_drawdown", "metric_value": "-0.22"},
            {"metric_name": "annualized_return", "metric_value": "0.08"},
        ]


class FakeManagerRepo:
    def get_current_fund_tenure_context(self, fund_code):
        return {}


class FakeAlertRepo:
    def __init__(self, open_events=None):
        self.created = []
        self._open_events = open_events or []

    def create_event(self, **kwargs):
        self.created.append(kwargs)
        return {"id": f"event-{len(self.created)}", **kwargs}

    def has_open_event(self, fund_id, event_type):
        return any(
            event.get("fund_id") == fund_id and event.get("event_type") == event_type
            for event in self._open_events
        )


def main() -> int:
    repo = FakeAlertRepo()
    service = AlertScanService(
        pool_repo=FakePoolRepo(),
        metric_repo=FakeMetricRepo(),
        alert_repo=repo,
        manager_repo=FakeManagerRepo(),
    )
    summary = service.scan()
    if summary.get('created', 0) < 1:
        print(f"Expected at least one alert event, got: {summary}")
        return 1
    if not any(event.get('event_type') == 'drawdown' for event in repo.created):
        print(f"Expected drawdown alert event, got: {repo.created}")
        return 1

    # 已有未解决 drawdown 事件时不重复创建，避免每日调度堆积重复事件
    repo = FakeAlertRepo(open_events=[{"fund_id": "FUND-TEST-001", "event_type": "drawdown", "status": "new"}])
    service = AlertScanService(
        pool_repo=FakePoolRepo(),
        metric_repo=FakeMetricRepo(),
        alert_repo=repo,
        manager_repo=FakeManagerRepo(),
    )
    summary = service.scan()
    if any(event.get('event_type') == 'drawdown' for event in repo.created):
        print(f"Expected drawdown dedup against open event, got: {repo.created}")
        return 1
    print('OK alert scan service')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
