"""FundWatchService：total_asset 单位换算与阈值比较（亿元存储 vs 元阈值）。纯离线。

funds.total_asset 以亿元存储；watch.threshold 与 triggered_value 约定为元
（前端 formatThreshold 用 value/1e8 显示"亿"）。缺失不冒充：无法取值的 watch 计入未评估。
"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "fund_watch_service.py"


def _load(names):
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            body.append(node)
    ns = {}
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                str(SRC), "exec", flags=__future__.annotations.compiler_flag),
        ns,
    )
    return ns


ns = _load({"_normalize_threshold", "_comparable_value", "_check_threshold"})


class WatchUnitTest(unittest.TestCase):
    def test_yi_threshold_is_converted_to_yuan(self):
        # 200 视为 200 亿 → 2e10 元。
        self.assertAlmostEqual(ns["_normalize_threshold"]("total_asset", 200), 2e10)

    def test_yuan_threshold_is_kept(self):
        self.assertAlmostEqual(ns["_normalize_threshold"]("total_asset", 2e10), 2e10)

    def test_non_asset_threshold_untouched(self):
        self.assertAlmostEqual(ns["_normalize_threshold"]("max_drawdown", -0.2), -0.2)

    def test_asset_value_yi_is_converted_to_yuan(self):
        self.assertAlmostEqual(ns["_comparable_value"]("total_asset", 250.5), 2.505e10)

    def test_non_asset_value_untouched(self):
        self.assertAlmostEqual(ns["_comparable_value"]("max_drawdown", -0.18), -0.18)

    def test_none_value_stays_none(self):
        self.assertIsNone(ns["_comparable_value"]("total_asset", None))

    def test_watch_actually_fires_after_unit_alignment(self):
        # 存量 watch：threshold=2e10（200亿），基金规模 250.5亿 → 应触发。
        value = ns["_comparable_value"]("total_asset", 250.5)
        threshold = ns["_normalize_threshold"]("total_asset", 2e10)
        self.assertTrue(ns["_check_threshold"](value, ">=", threshold))

    def test_old_broken_comparison_would_not_fire(self):
        # 反证：不换算时 250.5(亿元) >= 2e10(元) 为假，正是修复前的"永不触发"。
        self.assertFalse(ns["_check_threshold"](250.5, ">=", 2e10))


if __name__ == "__main__":
    unittest.main(verbosity=2)
