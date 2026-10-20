"""DecisionSupportService._reject_reason：None 不得当 0 参与比较。纯离线。"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "decision_support_service.py"


def _load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reject_reason":
            node.decorator_list = []
            body.append(node)
    ns = {"List": list}
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                str(SRC), "exec", flags=__future__.annotations.compiler_flag),
        ns,
    )
    return ns["_reject_reason"]


reject = _load()


def _item(sharpe=None, max_drawdown=None, annualized_return=None):
    return {"sharpe": sharpe, "max_drawdown": max_drawdown, "annualized_return": annualized_return}


class RejectReasonTest(unittest.TestCase):
    def test_lower_sharpe_is_reported(self):
        reason = reject(_item(sharpe=0.5), _item(sharpe=0.8))
        self.assertIn("Sharpe", reason)
        self.assertIn("更低", reason)

    def test_none_candidate_is_missing_not_zero(self):
        reason = reject(_item(sharpe=None), _item(sharpe=0.8))
        self.assertIn("缺失，无法比较", reason)
        self.assertNotIn("更低", reason)

    def test_real_zero_is_preserved(self):
        # 0 不是缺失：0 > -0.5，不应报"更低"。
        reason = reject(_item(sharpe=0.0), _item(sharpe=-0.5))
        self.assertNotIn("Sharpe", reason)

    def test_none_best_is_not_comparable(self):
        reason = reject(_item(sharpe=-0.5), _item(sharpe=None))
        self.assertNotIn("Sharpe", reason)

    def test_deeper_drawdown_reported(self):
        reason = reject(_item(max_drawdown=-0.30), _item(max_drawdown=-0.20))
        self.assertIn("回撤更深", reason)

    def test_all_missing_falls_back(self):
        self.assertEqual(reject(_item(), _item()), "综合得分较低")


if __name__ == "__main__":
    unittest.main(verbosity=2)
