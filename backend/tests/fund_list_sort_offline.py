"""A3：基金列表排序不得把缺失指标当 0（无证据≠最优/最劣）。纯离线，仅抽取路由内的排序纯函数。"""
import __future__
import ast
import math
from pathlib import Path
import unittest


ROUTE = Path(__file__).resolve().parents[1] / "routes" / "funds.py"
WANTED_FUNCS = {"_as_float", "_risk_sort_value", "_funds_sort_value", "_sort_funds"}
WANTED_ASSIGNS = {"_FUNDS_NUMERIC_SORT_FIELDS"}


def _load_sort_helpers():
    tree = ast.parse(ROUTE.read_text(encoding="utf-8"), filename=str(ROUTE))
    body = ast.parse("from __future__ import annotations").body
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANTED_FUNCS:
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in WANTED_ASSIGNS for target in node.targets
        ):
            body.append(node)
    namespace = {"math": math}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(ROUTE), "exec", flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    return namespace


NS = _load_sort_helpers()


class FundListSortTest(unittest.TestCase):
    def setUp(self):
        self.sort_funds = NS["_sort_funds"]

    def test_missing_risk_is_not_treated_as_lowest_risk(self):
        funds = [
            {"wind_code": "A", "risk_metrics": {}},
            {"wind_code": "B", "risk_metrics": {"max_drawdown_1y": -0.20}},
            {"wind_code": "C", "risk_metrics": {"max_drawdown_1y": -0.05}},
        ]
        self.sort_funds(funds, "risk", "asc")
        self.assertEqual([fund["wind_code"] for fund in funds], ["C", "B", "A"])

    def test_real_zero_drawdown_beats_missing(self):
        funds = [
            {"wind_code": "A", "risk_metrics": {"max_drawdown_1y": None}},
            {"wind_code": "B", "risk_metrics": {"max_drawdown_1y": 0.0}},
            {"wind_code": "C", "risk_metrics": {"max_drawdown_1y": -0.10}},
        ]
        self.sort_funds(funds, "risk", "asc")
        self.assertEqual([fund["wind_code"] for fund in funds], ["B", "C", "A"])

    def test_missing_score_sorts_last_in_desc_not_as_zero(self):
        funds = [
            {"wind_code": "A", "scoring": {}},
            {"wind_code": "B", "scoring": {"overall_score": 0.0}},
            {"wind_code": "C", "scoring": {"overall_score": 90.0}},
        ]
        self.sort_funds(funds, "rank", "desc")
        self.assertEqual([fund["wind_code"] for fund in funds], ["C", "B", "A"])

    def test_return_desc_puts_missing_last(self):
        funds = [
            {"wind_code": "A", "performance": {}},
            {"wind_code": "B", "performance": {"annualized_return_1y": 0.08}},
            {"wind_code": "C", "performance": {"annualized_return_1y": 0.12}},
        ]
        self.sort_funds(funds, "return", "desc")
        self.assertEqual([fund["wind_code"] for fund in funds], ["C", "B", "A"])

    def test_name_sort_still_works(self):
        funds = [{"name": "b"}, {"name": "a"}, {"name": "c"}]
        self.sort_funds(funds, "name", "asc")
        self.assertEqual([fund["name"] for fund in funds], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
