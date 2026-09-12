import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.alert_scan import AlertScanService


class FakePoolRepo:
    def __init__(self, members):
        self._members = members

    def list_pools(self):
        return [{"id": "pool-1", "name": "默认候选池"}]

    def list_members(self, pool_id: str, status=None):
        member_status = status or "watch"
        return [m for m in self._members if m.get("status", "watch") == member_status or status is None]


class FakeMetricRepo:
    def get_latest_panel(self, target_type, target_id):
        return []


class FakeAlertRepo:
    def __init__(self, existing=None):
        self.created = []
        self._existing = existing or []

    def create_event(self, **kwargs):
        self.created.append(kwargs)
        return {"id": f"event-{len(self.created)}", **kwargs}

    def event_exists(self, fund_id, event_type, detail_key, detail_value):
        for event in self._existing:
            if event.get("fund_id") != fund_id or event.get("event_type") != event_type:
                continue
            details = event.get("details") or {}
            if str(details.get(detail_key)) == str(detail_value):
                return True
        return False

    def has_open_event(self, fund_id, event_type):
        return False


class FakeManagerRepo:
    def __init__(self, contexts):
        self._contexts = contexts

    def get_current_fund_tenure_context(self, fund_code):
        return self._contexts.get(str(fund_code).strip().upper(), {})


class FakePeerService:
    def build_peer_percentiles(self, fund_id, window="1y"):
        return {"metrics": {}}


def _member(fund_id, status="watch"):
    return {
        "id": f"member-{fund_id}",
        "pool_id": "pool-1",
        "fund_id": fund_id,
        "fund_wind_code": fund_id,
        "status": status,
    }


def _run(members, contexts, existing=None):
    repo = FakeAlertRepo(existing=existing)
    service = AlertScanService(
        pool_repo=FakePoolRepo(members),
        metric_repo=FakeMetricRepo(),
        alert_repo=repo,
        peer_service=FakePeerService(),
        manager_repo=FakeManagerRepo(contexts),
        today=date.today(),
        include_peer_metrics=False,
    )
    summary = service.scan()
    return repo, summary


def main() -> int:
    recent_start = (date.today() - timedelta(days=10)).isoformat()
    old_start = (date.today() - timedelta(days=400)).isoformat()

    # 1. 新任经理（10 天前上任）的 watch 成员 → 产生 manager_change，severity=medium
    repo, summary = _run([_member("FUND-NEW-MGR")], {"FUND-NEW-MGR": {"start_date": recent_start, "manager_ids": ["M1"]}})
    events = [e for e in repo.created if e.get("event_type") == "manager_change"]
    if len(events) != 1:
        print(f"Expected one manager_change event for recent manager, got: {repo.created}")
        return 1
    event = events[0]
    if event.get("severity") != "medium":
        print(f"Watch member manager_change should be medium, got: {event.get('severity')}")
        return 1
    details = event.get("details") or {}
    if details.get("manager_start_date") != recent_start or details.get("wind_code") != "FUND-NEW-MGR":
        print(f"manager_change details incomplete: {details}")
        return 1

    # 2. candidate/core 成员 → severity=high
    repo, _ = _run([_member("FUND-CORE", status="core")], {"FUND-CORE": {"start_date": recent_start, "manager_ids": ["M1"]}})
    events = [e for e in repo.created if e.get("event_type") == "manager_change"]
    if len(events) != 1 or events[0].get("severity") != "high":
        print(f"Core member manager_change should be high, got: {repo.created}")
        return 1

    # 3. 老经理（400 天前上任）→ 不产生事件
    repo, _ = _run([_member("FUND-OLD-MGR")], {"FUND-OLD-MGR": {"start_date": old_start, "manager_ids": ["M1"]}})
    if any(e.get("event_type") == "manager_change" for e in repo.created):
        print(f"Old manager should not trigger manager_change, got: {repo.created}")
        return 1

    # 4. 无现任经理记录 → 不产生事件
    repo, _ = _run([_member("FUND-NO-MGR")], {})
    if any(e.get("event_type") == "manager_change" for e in repo.created):
        print(f"Missing manager record should not trigger manager_change, got: {repo.created}")
        return 1

    # 5. 同一经理变更已有事件（任意状态）→ 不重复创建
    existing = [{
        "fund_id": "FUND-NEW-MGR",
        "event_type": "manager_change",
        "status": "resolved",
        "details": {"manager_start_date": recent_start},
    }]
    repo, summary = _run([_member("FUND-NEW-MGR")], {"FUND-NEW-MGR": {"start_date": recent_start, "manager_ids": ["M1"]}}, existing=existing)
    if any(e.get("event_type") == "manager_change" for e in repo.created):
        print(f"Duplicate manager_change should be suppressed, got: {repo.created}")
        return 1

    print("OK manager alert scan service")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
