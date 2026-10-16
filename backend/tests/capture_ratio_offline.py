"""MetricFactory.calculate_capture_ratios：上涨/下跌捕获率。

口径 = 基准上涨日基金几何日收益均值 / 基准几何日收益均值（裸 ratio，1.10=捕获 110% 上行）。
缺失不冒充：任一侧有效观测不足 / 基准几何均值<=0 / 非有限 → None。纯离线。
"""
import __future__
import ast
import math
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "metric_factory.py"


def _load_capture():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "calculate_capture_ratios":
            node.decorator_list = []
            body.append(node)
    namespace = {
        "math": math,
        # AST 仅抽取单个静态方法，注入携带阈值的类 stub 供其引用。
        "MetricFactory": type("MetricFactory", (), {"MIN_CAPTURE_OBSERVATIONS": 10}),
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(SRC), "exec", flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    return namespace["calculate_capture_ratios"]


calc = _load_capture()


def _repeat(value, n):
    return [value] * n


class CaptureRatioTest(unittest.TestCase):
    def test_up_and_down_capture_basic(self):
        # 12 上涨日：基金涨幅是基准 2 倍；12 下跌日：基金跌幅是基准一半。
        fund = _repeat(0.02, 12) + _repeat(-0.005, 12)
        bench = _repeat(0.01, 12) + _repeat(-0.01, 12)
        out = calc(fund, bench)
        self.assertAlmostEqual(out["up_capture_ratio"], 2.0, places=6)
        self.assertAlmostEqual(out["down_capture_ratio"], 0.5, places=6)
        self.assertEqual(out["up_observations"], 12)
        self.assertEqual(out["down_observations"], 12)

    def test_insufficient_up_observations_returns_none_not_fabricated(self):
        fund = _repeat(0.02, 5) + _repeat(-0.005, 12)
        bench = _repeat(0.01, 5) + _repeat(-0.01, 12)
        out = calc(fund, bench)
        self.assertIsNone(out["up_capture_ratio"])
        self.assertAlmostEqual(out["down_capture_ratio"], 0.5, places=6)
        self.assertEqual(out["up_observations"], 5)

    def test_flat_benchmark_days_excluded_from_both_sides(self):
        fund = _repeat(0.02, 12) + _repeat(-0.005, 12) + [0.5, 0.5]
        bench = _repeat(0.01, 12) + _repeat(-0.01, 12) + [0.0, 0.0]
        out = calc(fund, bench)
        self.assertEqual(out["up_observations"], 12)
        self.assertEqual(out["down_observations"], 12)
        self.assertAlmostEqual(out["up_capture_ratio"], 2.0, places=6)

    def test_empty_series_returns_none_with_zero_observations(self):
        out = calc([], [])
        self.assertIsNone(out["up_capture_ratio"])
        self.assertIsNone(out["down_capture_ratio"])
        self.assertEqual(out["up_observations"], 0)
        self.assertEqual(out["down_observations"], 0)

    def test_fund_wipeout_observation_dropped(self):
        # 某个上涨日基金收益 <= -100%（1+r<=0），该观测被剔除而非让几何均值失效。
        fund = _repeat(0.02, 11) + [-1.5]
        bench = _repeat(0.01, 12)
        out = calc(fund, bench)
        self.assertEqual(out["up_observations"], 11)
        self.assertIsNotNone(out["up_capture_ratio"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
