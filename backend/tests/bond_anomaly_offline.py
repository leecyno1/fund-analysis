"""FundBondAnomalyService：净值口径切换门槛、regime 不伪造、缺口日不压缩滚动窗口。纯离线。"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fund_bond_anomaly_service import FundBondAnomalyService


def _svc():
    return FundBondAnomalyService(fund_repo=object(), nav_repo=object(), classification_repo=object())


def _rows(n, accum_count):
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    return [
        {
            "date": d.strftime("%Y-%m-%d"),
            "nav": 1 + i * 0.001,
            "accum_nav": (1 + i * 0.001) if i < accum_count else None,
        }
        for i, d in enumerate(dates)
    ]


class BondLevelsTest(unittest.TestCase):
    def test_sparse_accum_does_not_switch_basis(self):
        levels, basis = FundBondAnomalyService._levels(_rows(100, accum_count=2))
        self.assertEqual(basis, "unit_nav")
        self.assertEqual(len(levels), 100)

    def test_high_coverage_accum_switches_basis(self):
        levels, basis = FundBondAnomalyService._levels(_rows(100, accum_count=95))
        self.assertEqual(basis, "accum_nav")
        self.assertEqual(len(levels), 95)


class BondRegimeTest(unittest.TestCase):
    def _target(self, n=80):
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        return pd.Series([1 + i * 0.0005 for i in range(n)], index=dates, dtype=float)

    def test_no_peers_yields_unknown_regime_not_normal(self):
        out = _svc()._analyze_series(self._target(), pd.DataFrame(), minimum_peer_count=5, window_days=60)
        self.assertEqual(out["market_regime"], "unknown")
        self.assertFalse(out["peer_model_ready_latest"])

    def test_enough_peers_yields_observable_regime(self):
        target = self._target()
        peers = pd.DataFrame(
            {f"p{i}": 0.0002 for i in range(5)},
            index=target.index,
        )
        out = _svc()._analyze_series(target, peers, minimum_peer_count=5, window_days=60)
        self.assertTrue(out["peer_model_ready_latest"])
        self.assertIn(out["market_regime"], {"normal", "adjustment"})
        self.assertNotEqual(out["market_regime"], "unknown")

    def test_sparse_peer_history_does_not_fabricate_adjustment(self):
        target = self._target()
        # 只在少数日期有同类数据，有效观测不足，不应判定为"同类债市调整"。
        peers = pd.DataFrame(index=target.index, columns=[f"p{i}" for i in range(5)], dtype=float)
        peers.iloc[:10, :] = -0.01
        out = _svc()._analyze_series(target, peers, minimum_peer_count=5, window_days=60)
        self.assertFalse(out["market_regime"] == "adjustment")
        self.assertEqual(out["market_regime"], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
