"""AnomalyScannerService：错误暴露、被动过滤、被动代码前缀语义。纯离线（扫描方法打桩）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.anomaly_scanner_service import AnomalyScannerService, _is_passive_code


class AnomalyScannerTest(unittest.TestCase):
    def _service(self):
        return AnomalyScannerService(engine=object())

    def test_passive_prefixes(self):
        self.assertTrue(_is_passive_code("159915.SZ"))
        self.assertTrue(_is_passive_code("510300.SH"))
        self.assertTrue(_is_passive_code("588000.SH"))
        # 161xxx 是主动 LOF 混合区，不能整体当被动排除。
        self.assertFalse(_is_passive_code("161005.SZ"))
        self.assertFalse(_is_passive_code("000001.OF"))

    def test_scan_reports_ok_and_counts(self):
        svc = self._service()
        for name in ("_scan_scale_anomaly", "_scan_drawdown_anomaly", "_scan_manager_changes", "_scan_concentration_change"):
            setattr(svc, name, lambda limit, wind_code=None: [{"wind_code": "000001.OF", "description": "x"}])
        out = svc.scan(limit=5)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["errors"], {})
        self.assertEqual(out["total_anomalies"], 4)
        self.assertEqual(out["by_type"]["manager_change"], 1)

    def test_scan_partial_when_one_scanner_fails(self):
        svc = self._service()
        svc._scan_scale_anomaly = lambda limit, wind_code=None: []
        svc._scan_drawdown_anomaly = lambda limit, wind_code=None: []
        svc._scan_manager_changes = lambda limit, wind_code=None: [{"wind_code": "000001.OF", "description": "x"}]

        def boom(limit, wind_code=None):
            raise RuntimeError("table missing")

        svc._scan_concentration_change = boom
        out = svc.scan(limit=5)
        self.assertEqual(out["status"], "partial")
        self.assertIn("concentration_change", out["errors"])
        self.assertIn("table missing", out["errors"]["concentration_change"])
        self.assertEqual(out["anomalies"]["concentration_change"], [])
        self.assertEqual(out["by_type"]["manager_change"], 1)

    def test_passive_filtered_before_truncation(self):
        svc = self._service()
        svc._scan_scale_anomaly = lambda limit, wind_code=None: [
            {"wind_code": "510300.SH", "description": "passive"},
            {"wind_code": "000001.OF", "description": "active"},
        ]
        svc._scan_drawdown_anomaly = lambda limit, wind_code=None: []
        svc._scan_manager_changes = lambda limit, wind_code=None: []
        svc._scan_concentration_change = lambda limit, wind_code=None: []
        out = svc.scan(limit=1)
        self.assertEqual(len(out["anomalies"]["scale_anomaly"]), 1)
        self.assertEqual(out["anomalies"]["scale_anomaly"][0]["wind_code"], "000001.OF")


if __name__ == "__main__":
    unittest.main(verbosity=2)
