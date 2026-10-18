"""收益来源结论：基准回归得 Beta/Alpha/R²/IR，再按滚动年度 Alpha 判断可复制性。纯离线。

只解释历史、不预测、不进入评分（ADR-0004）。基准缺失或样本不足返回 insufficient。
"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "return_source_service.py"


def _load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    wanted = {"build_return_source_conclusion", "_alpha_stats"}
    wanted_const = {
        "TRADING_DAYS", "MIN_OBSERVATIONS", "ROLLING_WINDOWS", "MIN_ROLLING_OBS",
        "ALPHA_SIGNIFICANCE_T", "_SOURCE_LABELS", "_REPLICABILITY_LABELS",
    }
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            node.decorator_list = []
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_const for t in node.targets
        ):
            body.append(node)
    ns = {"math": __import__("math")}
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                str(SRC), "exec", flags=__future__.annotations.compiler_flag),
        ns,
    )
    return ns["build_return_source_conclusion"]


build = _load()


def _points(n, bench_ret, fund_ret):
    from datetime import date, timedelta
    start = date(2023, 1, 2)
    bench, fund = [], []
    b_level = f_level = 1.0
    for i in range(n):
        if i > 0:
            b_level *= 1 + bench_ret(i)
            f_level *= 1 + fund_ret(i)
        bench.append((start + timedelta(days=i), b_level))
        fund.append((start + timedelta(days=i), f_level))
    return fund, bench


class ReturnSourceTest(unittest.TestCase):
    def _bench(self, i):
        import math
        return 0.0003 + 0.01 * math.sin(i)

    def _run(self, fund_ret, n=760):
        fund, bench = _points(n, self._bench, fund_ret)
        return build(fund, bench)

    def test_positive_alpha_detected(self):
        import math
        out = self._run(lambda i: 0.0004 + 1.1 * self._bench(i) + 0.001 * math.cos(i * 1.7))
        self.assertEqual(out["status"], "available")
        self.assertAlmostEqual(out["beta"], 1.1, places=1)
        self.assertGreater(out["alpha_annualized"], 0)
        self.assertEqual(out["classification"], "alpha_positive")

    def test_pure_beta_is_market_driven(self):
        out = self._run(lambda i: self._bench(i))
        self.assertEqual(out["status"], "available")
        self.assertAlmostEqual(out["beta"], 1.0, places=2)
        self.assertAlmostEqual(out["alpha_annualized"], 0.0, places=3)
        self.assertGreater(out["r_squared"], 0.99)
        self.assertEqual(out["classification"], "market_driven")

    def test_negative_alpha_detected(self):
        import math
        out = self._run(lambda i: -0.0004 + self._bench(i) + 0.001 * math.cos(i * 1.3))
        self.assertLess(out["alpha_annualized"], 0)
        self.assertEqual(out["classification"], "alpha_negative")

    def test_missing_benchmark_is_insufficient(self):
        fund, _ = _points(760, self._bench, self._bench)
        out = build(fund, [])
        self.assertEqual(out["status"], "insufficient")
        self.assertIn("benchmark", out["reason"])

    def test_short_history_is_insufficient(self):
        out = self._run(lambda i: self._bench(i), n=120)
        self.assertEqual(out["status"], "insufficient")
        self.assertIn("insufficient_history", out["reason"])

    def test_rolling_windows_present(self):
        out = self._run(lambda i: 0.0004 + self._bench(i))
        self.assertEqual(out["status"], "available")
        self.assertGreaterEqual(len(out["rolling_windows"]), 2)
        self.assertIn("alpha_replicability", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
