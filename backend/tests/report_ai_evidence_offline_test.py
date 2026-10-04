"""报告/AI/纪要事实链回归（B1/B2/B3/B5）；纯离线，不连库、不联网、不调用 LLM。

只剥离应用层 `from services.*` 导入，方法体不改动；纯净依赖从真实源码注入。
"""
import __future__
import ast
import builtins
from pathlib import Path
from types import SimpleNamespace
import unittest


SERVICES = Path(__file__).resolve().parents[1] / "services"
SAFE_IMPORTS = {
    "math", "typing", "datetime", "time", "decimal", "collections",
    "re", "warnings", "__future__", "os", "json", "logging", "urllib",
}


def _offline_import(name, *args, **kwargs):
    if name.split(".")[0] not in SAFE_IMPORTS:
        raise AssertionError(f"Offline test forbids import: {name}")
    return builtins.__import__(name, *args, **kwargs)


def _load(name, **bindings):
    path = SERVICES / f"{name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and (node.module or "").startswith("services.")
    )]
    namespace = {
        "__name__": f"offline_{name}",
        "__builtins__": {**vars(builtins), "__import__": _offline_import},
        **bindings,
    }
    exec(compile(tree, str(path), "exec", flags=__future__.annotations.compiler_flag), namespace)
    return SimpleNamespace(**namespace)


ai_report = _load(
    "ai_report",
    LlmCircuitOpen=type("LlmCircuitOpen", (Exception,), {}),
    get_llm_runtime_guard=lambda *a, **k: SimpleNamespace(),
)
evidence_report = _load("evidence_report")
memo_module = _load(
    "research_memo_service",
    DataQualityService=object,
    ProfessionalScoringService=object,
)


class AiReportHoldingWeightTest(unittest.TestCase):
    """B1：持仓权重为 None 时不得用 {:.2%} 格式化而崩溃，也不得伪造 0.00%。"""

    def _prompt(self, holdings):
        gen = ai_report.ClaudeReportGenerator.__new__(ai_report.ClaudeReportGenerator)
        return gen._build_fund_prompt(
            {"name": "测试基金", "wind_code": "000001.OF"}, {}, {}, holdings, {}, {}, []
        )

    def test_none_weight_does_not_crash_or_fabricate_zero_percent(self):
        prompt = self._prompt([
            {"stock_name": "平安银行", "stock_code": "000001", "weight": None, "industry": "银行"},
        ])
        self.assertIn("待补", prompt)
        self.assertNotIn("0.00%", prompt)

    def test_finite_weight_still_renders_percent(self):
        prompt = self._prompt([
            {"stock_name": "平安银行", "stock_code": "000001", "weight": 0.0812, "industry": "银行"},
        ])
        self.assertIn("8.12%", prompt)


class EvidenceConcentrationGateTest(unittest.TestCase):
    """B2：持仓权重缺失时集中度闸门不得静默放行。"""

    def test_missing_weights_do_not_silently_pass_concentration_gate(self):
        holdings = [
            {"stock_name": f"S{i}", "stock_code": str(i), "industry": "科技", "weight": None}
            for i in range(12)
        ]
        summary = evidence_report.build_buy_before_decision_summary(None, None, holdings, None)
        self.assertTrue(
            any("集中度" in flag and "无法核验" in flag for flag in summary["cautionFlags"]),
            summary["cautionFlags"],
        )

    def test_disclosed_concentration_still_flags(self):
        holdings = [
            {"stock_name": f"S{i}", "stock_code": str(i), "industry": "科技", "weight": 0.10}
            for i in range(10)
        ]
        summary = evidence_report.build_buy_before_decision_summary(None, None, holdings, None)
        self.assertTrue(any("前十大持仓集中度" in flag for flag in summary["cautionFlags"]))

    def test_no_holdings_does_not_claim_concentration_unknown(self):
        summary = evidence_report.build_buy_before_decision_summary(None, None, [], None)
        self.assertFalse(any("集中度无法核验" in flag for flag in summary["cautionFlags"]))

    def test_partial_weight_coverage_flags_lower_bound(self):
        holdings = [
            {"stock_name": "A", "stock_code": "1", "industry": "科技", "weight": 0.4},
            {"stock_name": "B", "stock_code": "2", "industry": "医药", "weight": None},
            {"stock_name": "C", "stock_code": "3", "industry": "消费", "weight": None},
        ]
        summary = evidence_report.build_buy_before_decision_summary(None, None, holdings, None)
        self.assertTrue(
            any("低估" in flag for flag in summary["cautionFlags"]),
            summary["cautionFlags"],
        )

    def test_industry_rows_show_placeholder_when_weights_undisclosed(self):
        holdings = [
            {"stock_name": f"S{i}", "stock_code": str(i), "industry": "科技", "weight": None}
            for i in range(3)
        ]
        rows = evidence_report._industry_rows(holdings, evidence_report._industry_buckets(holdings))
        self.assertNotIn("0.00%", rows)
        self.assertIn("待补", rows)

    def test_industry_rows_show_percent_when_weights_disclosed(self):
        holdings = [
            {"stock_name": f"S{i}", "stock_code": str(i), "industry": "科技", "weight": 0.3}
            for i in range(3)
        ]
        rows = evidence_report._industry_rows(holdings, evidence_report._industry_buckets(holdings))
        self.assertIn("90.00%", rows)

    def test_weight_coverage_ratio(self):
        self.assertEqual(evidence_report._holding_weight_coverage([]), 1.0)
        self.assertEqual(
            evidence_report._holding_weight_coverage([{"weight": 0.4}, {"weight": None}]), 0.5
        )
        self.assertEqual(evidence_report._holding_weight_coverage([{"weight": None}]), 0.0)


class ResearchMemoScoringIntegrityTest(unittest.TestCase):
    """B3：评分异常/缺失不得虚构 overall_score=50，也不得据此给高置信。"""

    def _service(self, scoring_service):
        return memo_module.ResearchMemoService(
            data_quality_service=SimpleNamespace(), scoring_service=scoring_service
        )

    def test_scoring_exception_does_not_fabricate_score(self):
        class Boom:
            def score_fund(self, code):
                raise RuntimeError("db down")

        result = self._service(Boom())._safe_scoring("000001.OF")
        self.assertIsNone(result.get("overall_score"))
        self.assertNotEqual(result.get("overall_grade"), "D")

    def test_inferences_with_missing_score_are_low_confidence(self):
        evidence_ids = {
            "score": "E1", "quality": "E2", "one_year_return": "E3",
            "three_year_return": "E4", "one_year_drawdown": "E5",
        }
        inferences = self._service(SimpleNamespace())._build_inferences(
            {"overall_score": None}, {"score": 90}, {}, {}, evidence_ids
        )
        first = inferences[0]
        self.assertEqual(first["confidence"], "low")
        self.assertIn("评分缺失", first["statement"])


class ResearchMemoJsonSafetyTest(unittest.TestCase):
    """B5：NaN/Inf 不得透传，否则 Starlette allow_nan=False 会 500。"""

    def setUp(self):
        self.svc = memo_module.ResearchMemoService(
            data_quality_service=SimpleNamespace(), scoring_service=SimpleNamespace()
        )

    def test_to_float_rejects_non_finite(self):
        self.assertIsNone(self.svc._to_float(float("nan")))
        self.assertIsNone(self.svc._to_float(float("inf")))
        self.assertIsNone(self.svc._to_float(float("-inf")))
        self.assertEqual(self.svc._to_float("1.5"), 1.5)
        self.assertIsNone(self.svc._to_float(None))

    def test_json_safe_neutralizes_non_finite_floats(self):
        self.assertIsNone(self.svc._json_safe(float("nan")))
        self.assertEqual(self.svc._json_safe({"a": float("nan"), "b": 1.0}), {"a": None, "b": 1.0})
        self.assertEqual(self.svc._json_safe([float("inf"), 2]), [None, 2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
