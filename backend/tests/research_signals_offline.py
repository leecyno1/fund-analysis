"""ResearchSignalsService：单类失败不静默归零、focus 失败暴露。纯离线（扫描方法打桩）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.research_signals_service import ResearchSignalsService


class ResearchSignalsTest(unittest.TestCase):
    def _svc(self):
        return ResearchSignalsService(engine=object())

    def test_ok_when_all_scanners_succeed(self):
        svc = self._svc()
        svc._focus_funds = lambda: [{"wind_code": "000001.OF"}]
        svc._scan_manager_new_memo = lambda focus, days: [{"type": "manager_new_memo"}]
        svc._scan_attribution_degradation = lambda focus: []
        svc._scan_memo_evidence_radar = lambda focus, days: []
        out = svc.scan(days=14)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["errors"], {})
        self.assertEqual(out["total_signals"], 1)
        self.assertEqual(out["focus_fund_count"], 1)

    def test_scanner_error_marks_partial_not_zero(self):
        svc = self._svc()
        svc._focus_funds = lambda: [{"wind_code": "000001.OF"}]
        svc._scan_manager_new_memo = lambda focus, days: []

        def boom(focus):
            raise RuntimeError("attribution table unavailable")

        svc._scan_attribution_degradation = boom
        svc._scan_memo_evidence_radar = lambda focus, days: [{"type": "memo_evidence_radar"}]
        out = svc.scan(days=14)
        self.assertEqual(out["status"], "partial")
        self.assertIn("attribution_degradation", out["errors"])
        self.assertIn("attribution table unavailable", out["errors"]["attribution_degradation"])
        self.assertEqual(out["signals"]["attribution_degradation"], [])
        self.assertEqual(out["by_type"]["memo_evidence_radar"], 1)

    def test_focus_failure_exposed(self):
        svc = self._svc()

        def boom():
            raise RuntimeError("focus query down")

        svc._focus_funds = boom
        svc._scan_manager_new_memo = lambda focus, days: []
        svc._scan_attribution_degradation = lambda focus: []
        svc._scan_memo_evidence_radar = lambda focus, days: []
        out = svc.scan(days=14)
        self.assertEqual(out["status"], "partial")
        self.assertIn("focus_funds", out["errors"])
        self.assertEqual(out["focus_fund_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
