"""归因结论层：从多季 Brinson 效应聚合主贡献来源、稳定性与可复制性。纯离线。"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "fund_attribution_conclusion_service.py"


def _load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    wanted = {"summarize_attribution_history", "_dominant_source", "_sign_consistency"}
    wanted_const = {"MIN_QUARTERS", "HIGH_STABILITY", "MEDIUM_STABILITY", "HIGH_RESIDUAL_SHARE", "MEDIUM_RESIDUAL_SHARE", "_SOURCE_LABELS", "_REPLICABILITY_LABELS"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            node.decorator_list = []
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_const for t in node.targets
        ):
            body.append(node)
    ns = {"math": __import__("math"), "Counter": __import__("collections").Counter}
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                str(SRC), "exec", flags=__future__.annotations.compiler_flag),
        ns,
    )
    return ns["summarize_attribution_history"]


summarize = _load()


def _q(quarter, a, s, i, r, status="partial_evidence"):
    return {
        "quarter": quarter,
        "status": status,
        "allocation": a,
        "selection": s,
        "interaction": i,
        "residual": r,
        "portfolio_coverage": 0.6,
    }


class AttributionConclusionTest(unittest.TestCase):
    def test_stable_allocation_dominant_is_high(self):
        out = summarize([
            _q("2025Q4", 0.04, 0.01, 0.005, 0.01),
            _q("2026Q1", 0.03, 0.012, 0.004, 0.008),
            _q("2026Q2", 0.05, 0.008, 0.002, 0.006),
        ])
        self.assertEqual(out["status"], "available")
        self.assertEqual(out["dominant_source"], "allocation")
        self.assertEqual(out["dominant_source_label"], "行业配置")
        self.assertEqual(out["stability"], 1.0)
        self.assertEqual(out["sign_consistency"], 1.0)
        self.assertEqual(out["alpha_replicability"], "high")

    def test_selection_dominant_detected(self):
        out = summarize([
            _q("2025Q4", 0.01, 0.05, 0.005, 0.01),
            _q("2026Q1", 0.012, 0.04, 0.004, 0.008),
            _q("2026Q2", 0.008, 0.06, 0.002, 0.006),
        ])
        self.assertEqual(out["dominant_source"], "selection")
        self.assertEqual(out["dominant_source_label"], "行业内选股")

    def test_mixed_direction_reduces_replicability(self):
        out = summarize([
            _q("2025Q4", 0.04, 0.01, 0.005, 0.01),
            _q("2026Q1", -0.03, 0.012, 0.004, 0.008),
            _q("2026Q2", 0.05, 0.008, 0.002, 0.006),
        ])
        self.assertLess(out["sign_consistency"], 1.0)
        self.assertNotEqual(out["alpha_replicability"], "high")

    def test_high_residual_share_lowers_replicability(self):
        out = summarize([
            _q("2025Q4", 0.01, 0.01, 0.005, 0.20),
            _q("2026Q1", 0.012, 0.012, 0.004, 0.22),
            _q("2026Q2", 0.008, 0.008, 0.002, 0.25),
        ])
        self.assertGreater(out["avg_residual_share"], 0.6)
        self.assertNotEqual(out["alpha_replicability"], "high")

    def test_single_quarter_is_insufficient(self):
        out = summarize([_q("2026Q2", 0.04, 0.01, 0.005, 0.01)])
        self.assertEqual(out["status"], "insufficient")
        self.assertIn("quarters", out["reason"])

    def test_quarters_without_effects_are_excluded(self):
        out = summarize([
            _q("2026Q2", 0.04, 0.01, 0.005, 0.01),
            {"quarter": "2026Q1", "status": "insufficient_evidence", "allocation": None, "selection": None, "interaction": None, "residual": None},
        ])
        self.assertEqual(out["status"], "insufficient")


if __name__ == "__main__":
    unittest.main(verbosity=2)
