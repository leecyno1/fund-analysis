"""research_pipeline_service.build_pipeline_steps：研究动线 7 步就绪度。

纯函数离线测：身份→业绩→归因→持仓→同类→异常→结论。缺失降级不冒充。纯离线。
"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "research_pipeline_service.py"


def _load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    wanted_fn = {"build_pipeline_steps", "_step"}
    wanted_const = {"_STEP_DEFS", "_NAV_READY", "_NAV_PARTIAL", "_PEER_READY", "_BENCHMARK_MIN"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted_fn:
            node.decorator_list = []
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_const for t in node.targets
        ):
            body.append(node)
    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(SRC), "exec", flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    return namespace["build_pipeline_steps"]


build = _load()


def _full_facts():
    return {
        "has_fund": True,
        "peer_group": "混合偏股",
        "benchmark_code": "000300.SH",
        "style_label": "成长",
        "style_snapshots": 3,
        "nav_observations": 480,
        "benchmark_observations": 480,
        "capture": {"up_capture_ratio": 1.12, "down_capture_ratio": 0.88},
        "holdings_count": 87,
        "holding_quarters": 4,
        "peer_group_size": 120,
        "peer_percentile_ready": True,
        "anomaly_open": 2,
        "anomaly_status": "ok",
        "has_score": True,
        "has_report": True,
    }


def _step(out, key):
    return next(s for s in out["steps"] if s["key"] == key)


class ResearchPipelineTest(unittest.TestCase):
    def test_all_ready_is_complete_with_seven_steps(self):
        out = build(_full_facts())
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["ready_count"], 7)
        self.assertEqual(len(out["steps"]), 7)
        self.assertEqual([s["order"] for s in out["steps"]], [1, 2, 3, 4, 5, 6, 7])
        self.assertIsNone(out["first_gap"])

    def test_missing_peer_group_blocks_identity_and_is_first_gap(self):
        facts = _full_facts()
        facts["peer_group"] = None
        facts["peer_group_size"] = 0
        facts["peer_percentile_ready"] = False
        out = build(facts)
        self.assertEqual(_step(out, "identity")["status"], "blocked")
        self.assertEqual(_step(out, "peer")["status"], "blocked")
        self.assertEqual(out["first_gap"]["key"], "identity")

    def test_identity_partial_when_style_missing(self):
        facts = _full_facts()
        facts["style_snapshots"] = 0
        out = build(facts)
        self.assertEqual(_step(out, "identity")["status"], "partial")
        self.assertIn("风格", _step(out, "identity")["gap"])

    def test_performance_blocked_on_sparse_nav(self):
        facts = _full_facts()
        facts["nav_observations"] = 30
        out = build(facts)
        self.assertEqual(_step(out, "performance")["status"], "blocked")

    def test_capture_absent_when_benchmark_sparse_but_performance_still_ready(self):
        facts = _full_facts()
        facts["benchmark_observations"] = 10
        facts["capture"] = None
        out = build(facts)
        perf = _step(out, "performance")
        self.assertEqual(perf["status"], "ready")
        self.assertNotIn("capture", perf["evidence"])

    def test_holdings_partial_when_single_period(self):
        facts = _full_facts()
        facts["holding_quarters"] = 1
        out = build(facts)
        self.assertEqual(_step(out, "holdings")["status"], "partial")
        self.assertIn("变化", _step(out, "holdings")["gap"])

    def test_attribution_blocked_without_holdings(self):
        facts = _full_facts()
        facts["holdings_count"] = 0
        facts["holding_quarters"] = 0
        out = build(facts)
        self.assertEqual(_step(out, "attribution")["status"], "blocked")
        self.assertEqual(_step(out, "holdings")["status"], "blocked")

    def test_conclusion_blocked_without_score_or_report(self):
        facts = _full_facts()
        facts["has_score"] = False
        facts["has_report"] = False
        out = build(facts)
        self.assertEqual(_step(out, "conclusion")["status"], "blocked")
        self.assertEqual(out["status"], "blocked")

    def test_empty_facts_all_blocked(self):
        out = build({"has_fund": False})
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(out["ready_count"], 0)
        self.assertTrue(all(s["status"] == "blocked" for s in out["steps"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
