"""AlertScanService：覆盖计数、fail-closed 去重、逐成员错误隔离。纯离线（repo 打桩）。"""
import os
import sys
from datetime import date
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.alert_scan import AlertScanService


class _PoolRepo:
    def __init__(self, members):
        self._members = members

    def list_pools(self):
        return [{"id": "pool-1"}]

    def list_members(self, pool_id, status=None):
        return list(self._members) if status == "core" else []


class _MetricRepo:
    def __init__(self, panel=None, fail_for=None):
        self.panel = panel or []
        self.fail_for = fail_for

    def get_latest_panel(self, target_type, target_id):
        if self.fail_for and target_id == self.fail_for:
            raise RuntimeError("panel unavailable")
        return self.panel


class _AlertRepo:
    def __init__(self, has_open_raises=False):
        self.has_open_raises = has_open_raises
        self.created = []

    def has_open_event(self, fund_id, event_type):
        if self.has_open_raises:
            raise RuntimeError("dedup store down")
        return False

    def create_event(self, **kwargs):
        self.created.append(kwargs)
        return kwargs

    def event_exists(self, **kwargs):
        return False


class _ManagerRepo:
    def get_current_fund_tenure_context(self, wind_code):
        return {}

    def list_fund_manager_departures(self, wind_code, start, end):
        return []


class _Peer:
    def build_peer_percentiles(self, fund_id, window="1y"):
        return {"metrics": {}}


def _member(code):
    return {"id": f"m-{code}", "fund_id": f"uuid-{code}", "fund_wind_code": code, "next_review_date": None}


class AlertScanCoverageTest(unittest.TestCase):
    def _svc(self, members, metric_repo=None, alert_repo=None, max_members=2, include_peer=False):
        return AlertScanService(
            pool_repo=_PoolRepo(members),
            metric_repo=metric_repo or _MetricRepo(),
            alert_repo=alert_repo or _AlertRepo(),
            peer_service=_Peer(),
            manager_repo=_ManagerRepo(),
            today=date(2026, 10, 16),
            max_members_per_status=max_members,
            include_peer_metrics=include_peer,
        )

    def test_coverage_reports_truncation(self):
        out = self._svc([_member("A"), _member("B"), _member("C")]).scan()
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["coverage"]["total_members"], 3)
        self.assertEqual(out["coverage"]["scanned_members"], 2)
        self.assertEqual(out["coverage"]["skipped_members"], 1)
        self.assertEqual(out["skipped"][0]["reason"], "status_quota")
        self.assertFalse(out["coverage"]["peer_metrics_included"])

    def test_member_error_isolated_and_marked_partial(self):
        out = self._svc(
            [_member("A"), _member("B")],
            metric_repo=_MetricRepo(fail_for="A"),
        ).scan()
        self.assertEqual(out["status"], "partial")
        self.assertEqual(out["coverage"]["member_errors"], 1)
        self.assertEqual(out["coverage"]["scanned_members"], 1)
        self.assertIn("panel unavailable", out["skipped"][0]["reason"])

    def test_dedup_failure_is_fail_closed(self):
        panel = [{"metric_name": "max_drawdown", "metric_window": "1y", "metric_value": "-0.20"}]
        alert_repo = _AlertRepo(has_open_raises=True)
        out = self._svc(
            [_member("A")],
            metric_repo=_MetricRepo(panel=panel),
            alert_repo=alert_repo,
        ).scan()
        # 去重校验失败时不得创建重复告警。
        self.assertEqual(out["created"], 0)
        self.assertEqual(alert_repo.created, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
