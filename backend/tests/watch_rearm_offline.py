"""观察项 re-arm 与自选池缺数标记。纯离线（repo/engine 打桩）。"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fund_watch_service import FundWatchService
from services.fund_watchlist_service import FundWatchlistService


class _FakeConn:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append((str(sql), params or {}))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeEngine:
    def __init__(self):
        self.log = []

    def begin(self):
        return _FakeConn(self.log)


def _watch(value_id, operator, threshold):
    return {
        "id": value_id,
        "fund_wind_code": "000001.OF",
        "metric_field": "max_drawdown",
        "operator": operator,
        "threshold": threshold,
        "status": "triggered",
    }


class WatchRearmTest(unittest.TestCase):
    def _svc(self, triggered, current):
        engine = _FakeEngine()
        svc = FundWatchService(engine=engine)
        svc.list_watches = lambda status=None: [] if status == "active" else list(triggered)
        svc._get_current_value = lambda code, field: current
        return svc, engine

    def test_condition_cleared_rearms_watch(self):
        svc, engine = self._svc([_watch("w1", "<=", -0.15)], current=-0.05)
        out = svc.scan()
        self.assertEqual(out["rearmed_count"], 1)
        self.assertEqual(out["rearmed"][0]["id"], "w1")
        self.assertTrue(any("status = 'active'" in sql for sql, _ in engine.log))

    def test_condition_still_met_stays_triggered(self):
        svc, engine = self._svc([_watch("w1", "<=", -0.15)], current=-0.20)
        out = svc.scan()
        self.assertEqual(out["rearmed_count"], 0)
        self.assertFalse(any("status = 'active'" in sql for sql, _ in engine.log))

    def test_unavailable_metric_does_not_rearm(self):
        svc, engine = self._svc([_watch("w1", "<=", -0.15)], current=None)
        out = svc.scan()
        self.assertEqual(out["rearmed_count"], 0)
        self.assertEqual(engine.log, [])


class _FakePoolRepo:
    def __init__(self, members):
        self._members = members

    def list_members(self, pool_id=None, status=None):
        return list(self._members)


class WatchlistMissingTest(unittest.TestCase):
    def _svc(self, member):
        svc = FundWatchlistService.__new__(FundWatchlistService)
        svc.repo = _FakePoolRepo([member])
        return svc

    def _member(self):
        return {
            "id": "m1", "pool_id": "p1", "status": "watch",
            "fund_wind_code": "999999.OF", "fund_name": "缺失基金",
        }

    def test_missing_fund_gets_explicit_marker(self):
        svc = self._svc(self._member())
        with patch("services.fund_watchlist_service.FundBrowserService.enrich_rows", return_value=[]):
            rows = svc.list_members("p1")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["data_missing"])
        self.assertEqual(rows[0]["wind_code"], "999999.OF")
        self.assertTrue(rows[0]["missing_items"])

    def test_present_fund_is_not_marked_missing(self):
        svc = self._svc(self._member())
        enriched = [{"wind_code": "999999.OF", "name": "真实名称"}]
        with patch("services.fund_watchlist_service.FundBrowserService.enrich_rows", return_value=enriched):
            rows = svc.list_members("p1")
        self.assertFalse(rows[0]["data_missing"])
        self.assertEqual(rows[0]["name"], "真实名称")
        self.assertEqual(rows[0]["missing_items"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
