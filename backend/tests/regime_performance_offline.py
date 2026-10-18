"""市场环境分段业绩：按基准 trailing 60 日收益分牛/熊/震荡，统计分段胜率。纯离线。"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "fund_regime_performance_service.py"


def _load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    wanted = {"summarize_regime_performance", "_regime_stats"}
    wanted_const = {"TRAILING_DAYS", "BULL_THRESHOLD", "BEAR_THRESHOLD", "MIN_PERIOD_DAYS", "MIN_TOTAL_DAYS"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            node.decorator_list = []
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_const for t in node.targets
        ):
            body.append(node)
    ns = {}
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                str(SRC), "exec", flags=__future__.annotations.compiler_flag),
        ns,
    )
    return ns["summarize_regime_performance"]


summarize = _load()


def _date(index):
    from datetime import date, timedelta
    return date(2023, 1, 2) + timedelta(days=index)


def _series(bench_levels, fund_returns):
    """由基准净值构造 (date, nav) 序列；基金日收益由调用方给定。"""
    bench, fund = [], []
    fund_level = 1.0
    for i, level in enumerate(bench_levels):
        bench.append((_date(i), level))
        if i > 0:
            fund_level *= 1 + fund_returns[i]
        fund.append((_date(i), fund_level))
    return fund, bench


def _rising_then_falling(n_flat=70, n_up=90, n_down=90, up=0.004, down=-0.006):
    levels = [1.0]
    for _ in range(n_flat):
        levels.append(levels[-1])
    for _ in range(n_up):
        levels.append(levels[-1] * (1 + up))
    for _ in range(n_down):
        levels.append(levels[-1] * (1 + down))
    return levels


class RegimePerformanceTest(unittest.TestCase):
    def test_segments_and_win_rate(self):
        levels = _rising_then_falling()
        # 基金在基准上涨时略强、下跌时略弱。
        bench_returns = [0.0] + [levels[i] / levels[i - 1] - 1 for i in range(1, len(levels))]
        fund_returns = [
            (r + 0.0005) if r > 0 else (r - 0.0005) if r < 0 else 0.0
            for r in bench_returns
        ]
        fund, bench = _series(levels, fund_returns)
        out = summarize(fund, bench)
        self.assertEqual(out["status"], "available")
        self.assertGreaterEqual(out["regimes"]["bull"]["period_count"], 1)
        self.assertGreaterEqual(out["regimes"]["bear"]["period_count"], 1)
        self.assertGreater(out["regimes"]["bull"]["avg_excess"], 0)
        self.assertLess(out["regimes"]["bear"]["avg_excess"], 0)
        self.assertEqual(out["regimes"]["bull"]["win_rate"], 1.0)
        self.assertEqual(out["regimes"]["bear"]["win_rate"], 0.0)

    def test_missing_benchmark_is_insufficient(self):
        fund, _ = _series(_rising_then_falling(), [0.0] * 251)
        out = summarize(fund, [])
        self.assertEqual(out["status"], "insufficient")
        self.assertIn("benchmark", out["reason"])

    def test_short_history_is_insufficient(self):
        levels = [1.0 + i * 0.001 for i in range(100)]
        fund, bench = _series(levels, [0.0] + [0.001] * 99)
        out = summarize(fund, bench)
        self.assertEqual(out["status"], "insufficient")
        self.assertIn("history", out["reason"])

    def test_flat_market_is_range_not_bull_or_bear(self):
        levels = [1.0] * 300
        fund, bench = _series(levels, [0.0] * 300)
        out = summarize(fund, bench)
        self.assertEqual(out["status"], "available")
        self.assertGreaterEqual(out["regimes"]["range"]["period_count"], 1)
        self.assertEqual(out["regimes"]["bull"]["period_count"], 0)
        self.assertEqual(out["regimes"]["bear"]["period_count"], 0)

    def test_short_periods_are_dropped(self):
        levels = [1.0] * 301
        # 制造一个 2 天的假突破，短于最小分段长度，应被剔除。
        levels = levels[:150] + [1.0, 1.2, 1.0] + levels[153:]
        fund, bench = _series(levels, [0.0] * 301)
        out = summarize(fund, bench)
        self.assertEqual(out["status"], "available")
        self.assertEqual(out["regimes"]["bull"]["period_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
