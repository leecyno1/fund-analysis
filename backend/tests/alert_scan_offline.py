"""alert_scan._metric_map 必须按窗口取值，不能靠遍历顺序（否则字典序最后窗口覆盖 1y）。纯离线。"""
import __future__
import ast
from decimal import Decimal
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "alert_scan.py"


def _load_metric_map():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_metric_map":
            node.decorator_list = []
            body.append(node)
    namespace = {"Decimal": Decimal}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(SRC), "exec", flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    return namespace["_metric_map"]


_metric_map = _load_metric_map()


class MetricMapWindowTest(unittest.TestCase):
    def test_drawdown_uses_1y_window_not_last_alphabetical(self):
        panel = [
            {"metric_name": "max_drawdown", "metric_window": "1y", "metric_value": "-0.03"},
            {"metric_name": "max_drawdown", "metric_window": "3m", "metric_value": "0.0"},
            {"metric_name": "max_drawdown", "metric_window": "3y", "metric_value": "-0.12"},
            {"metric_name": "max_drawdown", "metric_window": "6m", "metric_value": "-0.05"},
            {"metric_name": "max_drawdown", "metric_window": "manager_tenure", "metric_value": "-0.22"},
        ]
        self.assertEqual(_metric_map(panel)["max_drawdown"], Decimal("-0.03"))

    def test_metric_without_1y_window_is_absent_not_borrowed(self):
        panel = [{"metric_name": "max_drawdown", "metric_window": "3y", "metric_value": "-0.30"}]
        self.assertNotIn("max_drawdown", _metric_map(panel))

    def test_none_value_is_skipped(self):
        panel = [{"metric_name": "max_drawdown", "metric_window": "1y", "metric_value": None}]
        self.assertNotIn("max_drawdown", _metric_map(panel))


if __name__ == "__main__":
    unittest.main(verbosity=2)
