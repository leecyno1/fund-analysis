"""Legacy FundScoringEngine missing-evidence regressions.

Executes the complete production engine without app package imports; only
`from services.*` statements are stripped and their pure dependencies injected.
No database, network, or service bootstrap.
"""
import __future__ as _future
import ast
import builtins
import math
import sys
import unittest
import warnings
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace


SERVICES = Path(__file__).resolve().parents[1] / "services"
SAFE_IMPORTS = {"math", "typing", "decimal", "enum", "dataclasses", "datetime", "warnings", "__future__"}


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
    # Register as a real module so @dataclass can resolve cls.__module__ on 3.12+.
    module = ModuleType(f"offline_{name}")
    module.__file__ = str(path)
    module.__dict__["__builtins__"] = {**vars(builtins), "__import__": _offline_import}
    module.__dict__.update(bindings)
    sys.modules[module.__name__] = module
    exec(compile(tree, str(path), "exec", flags=_future.annotations.compiler_flag), module.__dict__)
    return module


_contract = _load("scoring_contract")
_engine = _load(
    "scoring_engine",
    build_scoring_output=_contract.build_scoring_output,
    serialize_scoring_output=_contract.serialize_scoring_output,
)
FundScoringEngine = _engine.FundScoringEngine


def _repo(rows):
    return SimpleNamespace(get_latest_panel=lambda target_type, target_id: list(rows))


def _row(name, value):
    return {"metric_name": name, "metric_value": value, "as_of_date": "2026-05-16", "source_snapshot_id": "s1"}


class MissingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = FundScoringEngine()
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings("ignore", message=r"datetime\.datetime\.utcnow\(\) is deprecated",
                                category=DeprecationWarning)

    def test_normalize_missing_is_none_not_neutral_fifty(self):
        rule = self.engine.RISK_ADJUSTED_RULES[0]
        self.assertIsNone(rule.normalize(None))
        self.assertIsNone(rule.normalize(float("nan")))
        self.assertIsNone(rule.normalize(Decimal("NaN")))
        self.assertEqual(rule.normalize(1.0), 50.0)

    def test_missing_metrics_are_excluded_from_dimension_average(self):
        metric_scores = {}
        dimension = self.engine._score_dimension(
            self.engine.RISK_ADJUSTED_RULES, {"sharpe_ratio": 3.0}, metric_scores,
        )
        self.assertEqual(dimension["score"], 100.0)
        self.assertIs(dimension["included_in_score"], True)
        self.assertEqual(dimension["count"], 1)
        self.assertIsNone(metric_scores["sortino_normalized"])

    def test_all_missing_dimension_is_insufficient_not_neutral(self):
        dimension = self.engine._score_dimension(self.engine.RISK_RULES, {}, {})
        self.assertIsNone(dimension["score"])
        self.assertIs(dimension["included_in_score"], False)
        self.assertEqual(dimension["weighted_score"], 0.0)
        self.assertEqual(dimension["status"], "insufficient_evidence")

    def test_true_zero_is_evidence_not_missing(self):
        metric_scores = {}
        dimension = self.engine._score_dimension(
            self.engine.RISK_RULES, {"max_drawdown": 0.0, "annualized_volatility_1y": 0.03}, metric_scores,
        )
        self.assertIs(dimension["included_in_score"], True)
        self.assertEqual(dimension["count"], 2)
        self.assertEqual(metric_scores["max_drawdown_raw"], 0.0)

    def test_overall_reweights_over_present_dimensions_only(self):
        rows = [_row("annualized_return", "0.10"), _row("sharpe_ratio", "1.0")]
        result = self.engine.score_fund_from_metric_snapshots("REWEIGHT.TEST", metric_repo=_repo(rows))
        dimensions = result["dimension_scores"]
        self.assertIsNone(dimensions["risk"]["score"])
        self.assertIs(dimensions["risk"]["included_in_score"], False)
        self.assertIs(dimensions["style"]["included_in_score"], False)
        weights = self.engine.DIMENSION_WEIGHTS
        return_w = weights[self._dim("return")]
        adjusted_w = weights[self._dim("risk_adjusted")]
        expected = (dimensions["return"]["score"] * return_w
                    + dimensions["risk_adjusted"]["score"] * adjusted_w) / (return_w + adjusted_w)
        self.assertAlmostEqual(result["overall_score"], round(expected, 2), places=2)

    def test_empty_panel_scores_no_neutral_and_discloses_all_gaps(self):
        result = self.engine.score_fund_from_metric_snapshots("EMPTY.TEST", metric_repo=_repo([]))
        for name in ("return", "risk", "risk_adjusted", "style"):
            self.assertIs(result["dimension_scores"][name]["included_in_score"], False, name)
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result["overall_grade"], "insufficient_evidence")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["data_quality"]["status"], "partial")
        expected_missing = {rule.metric_name for rule in self.engine.ALL_RULES if rule.metric_name != "var_95"}
        self.assertEqual(set(result["missing_data"]), expected_missing)

    def test_partial_panel_return_only_is_not_pulled_to_fifty(self):
        rows = [_row("annualized_return", "0.05")]
        result = self.engine.score_fund_from_metric_snapshots("PARTIAL.TEST", metric_repo=_repo(rows))
        dimensions = result["dimension_scores"]
        self.assertIs(dimensions["return"]["included_in_score"], True)
        for name in ("risk", "risk_adjusted", "style"):
            self.assertIs(dimensions[name]["included_in_score"], False, name)
        self.assertAlmostEqual(result["overall_score"], dimensions["return"]["score"], places=2)
        self.assertEqual(result["data_quality"]["status"], "partial")
        self.assertTrue(result["missing_data"])

    def test_score_fund_path_excludes_missing_and_low_evidence_style(self):
        result = self.engine.score_fund({"annualized_return_1y": 0.10}, {"sharpe_ratio": 1.0}, {})
        dimensions = result["dimension_scores"]
        risk_adjusted = dimensions[self._dim("risk_adjusted")]
        self.assertIs(risk_adjusted["included_in_score"], True)
        self.assertEqual(risk_adjusted["count"], 1)
        self.assertIs(dimensions[self._dim("style")]["included_in_score"], False)
        self.assertIsNone(dimensions[self._dim("risk")]["score"])

    def test_score_fund_empty_inputs_do_not_produce_neutral_or_zero(self):
        result = self.engine.score_fund({}, {}, {})
        for dimension in result["dimension_scores"].values():
            self.assertIs(dimension["included_in_score"], False)
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result["overall_grade"], "insufficient_evidence")
        self.assertEqual(result["status"], "insufficient_evidence")

    def test_score_fund_with_evidence_keeps_numeric_score_and_ok_status(self):
        result = self.engine.score_fund({"annualized_return_1y": 0.10}, {"sharpe_ratio": 1.0}, {})
        self.assertIsInstance(result["overall_score"], float)
        self.assertEqual(result["status"], "ok")
        self.assertNotEqual(result["overall_grade"], "insufficient_evidence")

    def _dim(self, name):
        return next(key for key in self.engine.DIMENSION_WEIGHTS if key.value == name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
