"""Fixed-input scoring regressions; no package bootstrap, DB, network or services.

Only application import statements are removed by the AST loader. Method bodies
are unmodified; their pure dependencies are injected from the actual source.
Unexpected application imports (including lazy repository access) fail closed.
"""
import __future__
import ast
import builtins
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
import warnings


SERVICES = Path(__file__).resolve().parents[1] / "services"
SAFE_IMPORTS = {"math", "typing", "datetime", "time", "decimal", "collections", "re", "warnings", "__future__"}


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


Methodology = _load("fund_evaluation_methodology").FundEvaluationMethodology
History = _load("fund_evaluation_history_service").FundEvaluationHistoryService
Catalog = _load("fund_classification_catalog").FundClassificationCatalog
Classification = _load(
    "fund_classification_service", FundClassificationCatalog=Catalog,
).FundClassificationService
Scoring = _load(
    "professional_scoring_service",
    FundEvaluationMethodology=Methodology,
    FundClassificationService=Classification,
    metric_details_coverage_status=_load("manager_tenure_coverage").metric_details_coverage_status,
    build_scoring_output=_load("scoring_contract").build_scoring_output,
).ProfessionalScoringService

QUALITY = {"score": 92.0, "issues": []}
COMPLETE = {
    "1y": {
        "annualized_return": 0.07, "max_drawdown": -0.08,
        "annualized_volatility": 0.11, "sharpe_ratio": 0.9,
        "calmar_ratio": 1.2, "positive_return_ratio": 0.58,
    },
    "3y": {"annualized_return": 0.06, "max_drawdown": -0.12, "sharpe_ratio": 0.8},
    "manager_tenure": {"annualized_return": 0.08, "max_drawdown": -0.09, "tenure_days": 720},
}
INDEX = {
    "1y": {"tracking_error": 0.006, "tracking_difference": -0.004},
    "latest": {"expense_ratio": 0.006, "aum": 45.0},
}
ENHANCED = {
    "1y": {"excess_return": 0.035, "information_ratio": 0.85,
           "tracking_error": 0.06, "max_drawdown": -0.16},
    "latest": {"expense_ratio": 0.012, "aum": 35.0},
}
MONEY = {
    "1y": {"annualized_return": 0.021, "max_drawdown": -0.0004,
           "annualized_volatility": 0.0018, "positive_return_ratio": 0.99},
    "latest": {"seven_day_annualized_yield": 0.019, "aum": 120.0,
               "benchmark_annualized_rate": 0.015, "benchmark_yield_spread": 0.004},
}


def _one_year():
    metrics = deepcopy(COMPLETE)
    del metrics["3y"]
    del metrics["1y"]["positive_return_ratio"]
    return metrics


def _panel(metrics):
    return [{"metric_window": window, "metric_name": key, "metric_value": value}
            for window, values in metrics.items() for key, value in values.items()]


class NumericTruthTests(unittest.TestCase):
    def setUp(self):
        self.method = Methodology()

    def test_empty_average_is_missing_not_neutral(self):
        self.assertIsNone(self.method._average([None, None]))
        self.assertIsNone(self.method._average([]))
        self.assertEqual(self.method._average([None, 0.0]), 0.0)

    def test_empty_dimension_is_excluded_and_disclosed(self):
        dimension = self.method._dimension(None, ["No numeric input"])
        self.assertIsNone(dimension["score"])
        self.assertEqual(dimension["weighted_score"], 0.0)
        self.assertIs(dimension["included_in_score"], False)
        self.assertTrue(dimension.get("missing_data"))

    def test_true_zero_remains_available(self):
        dimension = self.method._dimension(0.0, ["Observed zero"])
        self.assertEqual(dimension["score"], 0.0)
        self.assertIsNot(dimension.get("included_in_score"), False)
        self.assertEqual(self.method._average([0.0, None, 100.0]), 50.0)

    def test_finalizer_does_not_include_null_score_even_with_stale_flag(self):
        result = self.method._finalize("active_equity", {
            "return": {"score": 80.0},
            "consistency": {"score": None, "included_in_score": True},
        }, {"return": 0.75, "consistency": 0.25}, {}, [])
        self.assertEqual(result["total_score"], 80.0)
        self.assertEqual(result["dimensions"]["return"]["effective_weight"], 1.0)
        self.assertIs(result["dimensions"]["consistency"]["included_in_score"], False)
        self.assertTrue(result["missing_data"])

    def test_one_year_and_manager_do_not_invent_consistency(self):
        result = self.method.evaluate("active_equity", _one_year(), QUALITY)
        dimension = result["dimensions"]["consistency"]
        self.assertIsNone(dimension["score"])
        self.assertEqual(dimension["weighted_score"], 0.0)
        self.assertEqual(dimension["effective_weight"], 0.0)
        self.assertIs(dimension["included_in_score"], False)
        self.assertEqual(set(dimension["missing_data"]), {
            "optional_metric:1y.positive_return_ratio", "optional_metric:3y.annualized_return",
        })
        self.assertEqual(result["status"], "partial")
        included = [d for d in result["dimensions"].values() if d["included_in_score"]]
        expected = sum(d["score"] * d["weight"] for d in included) / 0.85
        self.assertAlmostEqual(result["total_score"], expected, places=4)
        self.assertAlmostEqual(sum(d["effective_weight"] for d in included), 1.0, places=5)

    def test_one_year_coverage_counts_actual_inputs_not_dimension_presence(self):
        result = self.method.evaluate("active_equity", _one_year(), QUALITY)
        coverage = History._evidence_coverage(result["dimensions"])
        self.assertEqual(coverage["coverage_percent"], 57.5)
        self.assertEqual(coverage["covered_weight"], 0.575)
        self.assertIn("consistency", coverage["missing_dimensions"])

    def test_partial_dimensions_disclose_absent_long_term_inputs(self):
        result = self.method.evaluate("active_equity", _one_year(), QUALITY)
        for key, metric in (("return", "annualized_return"), ("risk", "max_drawdown"),
                            ("risk_adjusted", "sharpe_ratio")):
            with self.subTest(dimension=key):
                gap = f"optional_metric:3y.{metric}"
                self.assertIn(gap, result["dimensions"][key].get("missing_data", []))
                self.assertIn(gap, result["missing_data"])
        self.assertEqual(len(result["missing_data"]), len(set(result["missing_data"])))

    def test_ratio_only_consistency_is_scored_but_not_full_coverage(self):
        metrics = _one_year()
        metrics["1y"]["positive_return_ratio"] = 0.58
        result = self.method.evaluate("active_equity", metrics, QUALITY)
        self.assertEqual(result["dimensions"]["consistency"]["score"], 65.0)
        self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 65.0)
        self.assertIn("optional_metric:3y.annualized_return", result["missing_data"])

    def test_gap_only_consistency_is_scored_but_discloses_missing_ratio(self):
        metrics = deepcopy(COMPLETE)
        del metrics["1y"]["positive_return_ratio"]
        result = self.method.evaluate("active_equity", metrics, QUALITY)
        self.assertEqual(result["dimensions"]["consistency"]["score"], 100.0)
        self.assertIn("optional_metric:1y.positive_return_ratio", result["missing_data"])
        self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 92.5)

    def test_three_year_cannot_use_a_self_comparison_as_evidence(self):
        result = self.method.evaluate("active_equity", COMPLETE, QUALITY, "3y")
        self.assertIsNone(result["dimensions"]["consistency"]["score"])
        self.assertIn("optional_metric:3y.positive_return_ratio", result["missing_data"])
        self.assertLess(History._evidence_coverage(result["dimensions"])["coverage_percent"], 100)

    def test_complete_three_year_has_no_self_comparison_gap(self):
        metrics = deepcopy(COMPLETE)
        metrics["3y"].update(annualized_volatility=0.12, calmar_ratio=1.0, positive_return_ratio=0.55)
        result = self.method.evaluate("active_equity", metrics, QUALITY, "3y")
        self.assertEqual(result["dimensions"]["consistency"]["score"], 50.0)
        self.assertEqual(result["missing_data"], [])
        self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 100)

    def test_six_month_gaps_use_selected_window(self):
        metrics = _one_year()
        metrics["6m"] = metrics.pop("1y")
        result = self.method.evaluate("active_equity", metrics, QUALITY, "6m")
        self.assertIn("optional_metric:6m.positive_return_ratio", result["missing_data"])
        self.assertFalse(any("1y." in gap for gap in result["missing_data"]))

    def test_missing_manager_payloads_are_not_neutral_evidence(self):
        for tenure in ({}, {"unrelated": 1.0}, {"annualized_return": None}):
            with self.subTest(tenure=tenure):
                metrics = deepcopy(COMPLETE)
                metrics["manager_tenure"] = tenure
                result = self.method.evaluate("active_equity", metrics, QUALITY)
                self.assertIsNone(result["dimensions"]["manager_tenure"]["score"])
                self.assertIs(result["dimensions"]["manager_tenure"]["included_in_score"], False)
                self.assertTrue(result["dimensions"]["manager_tenure"].get("missing_data"))
                self.assertEqual(result["status"], "partial")

    def test_partial_manager_inputs_remain_scored_and_disclosed(self):
        metrics = deepcopy(COMPLETE)
        metrics["manager_tenure"] = {"tenure_days": 180.0}
        result = self.method.evaluate("active_equity", metrics, QUALITY)
        dimension = result["dimensions"]["manager_tenure"]
        self.assertEqual(dimension["score"], 0.0)
        self.assertIs(dimension["included_in_score"], True)
        self.assertIn("optional_metric:manager_tenure.annualized_return", result["missing_data"])
        self.assertIn("optional_metric:manager_tenure.max_drawdown", result["missing_data"])
        self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 93.33)

    def test_missing_quality_is_not_an_observed_zero(self):
        for profile, metrics in (("active_equity", COMPLETE), ("index_fund", INDEX),
                                 ("qdii_index", INDEX), ("index_enhanced", ENHANCED),
                                 ("money_market", MONEY)):
            with self.subTest(profile=profile):
                result = self.method.evaluate(profile, metrics, {})
                self.assertIsNone(result["dimensions"]["data_quality"]["score"])
                self.assertIs(result["dimensions"]["data_quality"]["included_in_score"], False)
                self.assertIn("quality:score", result["missing_data"])
                zero = self.method.evaluate(profile, metrics, {"score": 0})
                self.assertEqual(zero["dimensions"]["data_quality"]["score"], 0.0)
                self.assertIs(zero["dimensions"]["data_quality"]["included_in_score"], True)

    def test_money_market_partial_evidence_is_disclosed_per_dimension(self):
        metrics = deepcopy(MONEY)
        del metrics["1y"]["annualized_volatility"]
        del metrics["1y"]["positive_return_ratio"]
        metrics["6m"] = metrics.pop("1y")
        result = self.method.evaluate("money_market", metrics, QUALITY, "6m")
        for key, metric in (("capital_preservation", "annualized_volatility"),
                            ("income_stability", "positive_return_ratio")):
            self.assertIn(f"optional_metric:6m.{metric}", result["dimensions"][key].get("missing_data", []))
        self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 77.5)
        self.assertFalse(any("1y." in gap for gap in result["missing_data"]))

    def test_history_never_covers_null_score_despite_included_flag(self):
        coverage = History._evidence_coverage({
            "return": {"score": 0.0, "weight": 0.8},
            "consistency": {"score": None, "weight": 0.2, "included_in_score": True},
        })
        self.assertEqual(coverage["coverage_percent"], 80.0)
        self.assertEqual(coverage["missing_dimensions"], ["consistency"])

    def test_legacy_history_coverage_remains_compatible(self):
        dimensions = {"return": {"score": 0.0, "weight": 0.5},
                      "risk": {"score": 70.0, "weight": 0.4},
                      "manager_tenure": {"score": None, "weight": 0.1, "included_in_score": False}}
        coverage = History._evidence_coverage(dimensions)
        self.assertEqual(coverage["coverage_percent"], 90.0)
        self.assertEqual(coverage["missing_dimensions"], ["manager_tenure"])
        self.assertIsNone(History._evidence_coverage({})["coverage_percent"])

    def test_history_unweighted_partial_coverage_is_not_complete(self):
        coverage = History._evidence_coverage({
            "return": {"score": 80.0, "evidence_coverage": 0.5},
            "consistency": {"score": None, "included_in_score": False},
        })
        self.assertEqual(coverage["coverage_percent"], 25.0)

    def test_version_changes_interpretation_and_prevents_comparison(self):
        self.assertEqual(self.method.METHODOLOGY_VERSION, "category_evaluation_methodology_v7")
        current = {"methodology_version": "fund_evaluation_v3", "overall_score": 80,
                   "calculation_method": self.method.evaluate("active_equity", COMPLETE, QUALITY)["calculation_method"]}
        previous = {**current, "calculation_method": "category_evaluation_methodology_v6:active_equity:1y"}
        change = History._change(current, previous)
        self.assertFalse(change["comparable"])
        self.assertIsNone(change["score_delta"])

    def test_peer_methodology_change_prevents_rank_comparison(self):
        base = {
            "methodology_version": "fund_evaluation_v3",
            "calculation_method": "category_evaluation_methodology_v7:active_equity:1y",
            "peer_group_id": "g1", "overall_score": 80.0, "overall_grade": "A",
            "peer_rank": 3, "peer_count": 10, "peer_percentile": 50.0,
            "peer_methodology_version": "category_peer_percentiles_v7",
            "dimension_scores": {}, "data_quality": {}, "missing_items": [],
        }
        previous = {**base, "peer_methodology_version": "category_peer_percentiles_v6",
                    "peer_rank": 5, "peer_percentile": 40.0, "overall_score": 78.0}
        change = History._change(base, previous)
        self.assertTrue(change["peer_methodology_changed"])
        self.assertFalse(change["comparable"])
        self.assertIsNone(change["rank_change"])
        self.assertIsNone(change["percentile_delta"])
        self.assertEqual(change["comparison_status"], "peer_methodology_changed")
        same = History._change(base, {**base, "peer_rank": 5, "peer_percentile": 40.0})
        self.assertFalse(same["peer_methodology_changed"])
        self.assertTrue(same["comparable"])
        self.assertIsNotNone(same["rank_change"])
        self.assertEqual(same["comparison_status"], "comparable")
        self.assertIn("同类", same["summary"])

    def test_public_item_exposes_peer_methodology_version_from_snapshot_blob(self):
        item = History._public_item({
            "wind_code": "HIST.OF", "evaluation_window": "1y",
            "snapshot": {"peer_context": {"peer_methodology_version": "category_peer_percentiles_v7"}},
        })
        self.assertEqual(item["peer_methodology_version"], "category_peer_percentiles_v7")
        self.assertIsNone(History._public_item({"wind_code": "X", "snapshot": {}})["peer_methodology_version"])

    def test_same_snapshot_distinguishes_peer_methodology_version(self):
        base = {"wind_code": "H", "evaluation_window": "1y", "overall_score": 80,
                "peer_methodology_version": "category_peer_percentiles_v7"}
        self.assertTrue(History._same_snapshot(base, dict(base)))
        self.assertFalse(History._same_snapshot(
            base, {**base, "peer_methodology_version": "category_peer_percentiles_v6"}))


class PreservedGatesTests(unittest.TestCase):
    def setUp(self):
        self.method = Methodology()
        self.enterContext(warnings.catch_warnings())
        # The unchanged serialization clock uses utcnow on newer Python versions.
        warnings.filterwarnings("ignore", message=r"datetime\.datetime\.utcnow\(\) is deprecated",
                                category=DeprecationWarning, module="offline_scoring_contract")

    def test_complete_inputs_keep_pre_fix_scores_for_all_categories(self):
        # Captured from v6 before the fix; ordered dimension scores and peer totals.
        baselines = {
            "active_equity": (62.6445, [47.14, 81.71, 32.67, 82.5, 69.23, 92.0], 63.77),
            "fixed_income": (44.4335, [81.25, 0.0, 32.67, 82.5, 58.33, 92.0], 36.9),
            "fixed_income_plus": (51.8067, [60.71, 39.01, 32.67, 82.5, 64.37, 92.0], 50.33),
            "fof_balanced": (57.2815, [63.89, 53.64, 32.67, 82.5, 68.58, 92.0], 56.41),
            "fof_bond": (37.5186, [77.27, 6.94, 32.67, 82.5, 58.78, 92.0], 39.93),
            "fof_equity": (62.3015, [55.77, 70.79, 32.67, 82.5, 69.87, 92.0], 61.11),
            "index_enhanced": (73.7, [65.38, 76.93, 78.38, 61.9, 77.2, 92.0], 74.5),
            "index_fund": (83.8725, [87.68, 72.73, 82.66, 92.0], 84.6725),
            "money_market": (72.479, [40.0, 95.89, 85.0, 77.62, 92.0], 73.279),
            "multi_asset": (62.3381, [55.77, 69.43, 32.67, 82.5, 69.65, 92.0], 60.18),
            "multi_asset_balanced": (58.4505, [57.5, 59.39, 32.67, 82.5, 67.8, 92.0], 57.28),
            "multi_asset_bond": (42.0635, [70.83, 14.77, 32.67, 82.5, 61.47, 92.0], 43.26),
            "multi_asset_equity": (61.4395, [51.79, 74.01, 32.67, 82.5, 69.05, 92.0], 61.66),
            "qdii_bond": (52.534, [67.65, 34.07, 32.67, 82.5, 64.78, 92.0], 49.67),
            "qdii_equity": (65.3825, [47.78, 89.29, 32.67, 82.5, 71.31, 92.0], 66.66),
            "qdii_index": (91.059, [94.74, 82.61, 84.93, 92.0], 91.859),
            "qdii_multi_asset": (63.869, [55.0, 72.95, 32.67, 82.5, 70.0, 92.0], 61.65),
        }
        self.assertEqual(set(baselines), set(self.method.PROFILES))
        special = {"index_fund": INDEX, "qdii_index": INDEX,
                   "index_enhanced": ENHANCED, "money_market": MONEY}
        for profile, (total, dimensions, peer_total) in baselines.items():
            with self.subTest(profile=profile):
                metrics = special.get(profile, COMPLETE)
                result = self.method.evaluate(profile, metrics, QUALITY)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["total_score"], total)
                self.assertEqual([d["score"] for d in result["dimensions"].values()], dimensions)
                self.assertEqual(result["missing_data"], [])
                self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 100.0)
                peer = self.method.score_peer_details(profile, {**metrics["1y"], **metrics.get("latest", {})})
                self.assertEqual(peer["overall_score"], peer_total)

    def test_sparse_return_risk_profiles_exclude_consistency_without_reweighting_coverage(self):
        for profile in sorted(self.method.RETURN_RISK_PROFILES):
            with self.subTest(profile=profile):
                result = self.method.evaluate(profile, _one_year(), QUALITY)
                self.assertIsNone(result["dimensions"]["consistency"]["score"])
                self.assertEqual(result["dimensions"]["consistency"]["effective_weight"], 0.0)
                included = [d for d in result["dimensions"].values() if d["included_in_score"]]
                weight = sum(d["weight"] for d in included)
                expected = sum(d["score"] * d["weight"] for d in included) / weight
                self.assertAlmostEqual(result["total_score"], expected, places=4)
                self.assertLess(History._evidence_coverage(result["dimensions"])["coverage_percent"], 100)

    def test_zero_consistency_is_evidence_not_a_missing_dimension(self):
        metrics = deepcopy(COMPLETE)
        metrics["1y"].update(positive_return_ratio=0.0, annualized_return=0.25)
        result = self.method.evaluate("active_equity", metrics, QUALITY)
        dimension = result["dimensions"]["consistency"]
        self.assertEqual(dimension["score"], 0.0)
        self.assertIs(dimension["included_in_score"], True)
        self.assertEqual(dimension["effective_weight"], 0.15)
        self.assertEqual(History._evidence_coverage(result["dimensions"])["coverage_percent"], 100)

    def test_all_return_risk_core_gates_remain_required(self):
        for profile in sorted(self.method.RETURN_RISK_PROFILES):
            for metric in ("annualized_return", "max_drawdown", "sharpe_ratio"):
                with self.subTest(profile=profile, metric=metric):
                    metrics = deepcopy(COMPLETE)
                    del metrics["1y"][metric]
                    result = self.method.evaluate(profile, metrics, QUALITY)
                    self.assertEqual(result["status"], "insufficient_evidence")
                    self.assertIsNone(result["total_score"])
                    self.assertEqual(result["missing_data"], [f"core_metric:1y.{metric}"])

    def test_other_category_core_gates_remain_required(self):
        for profile, fixture in (("index_fund", INDEX), ("qdii_index", INDEX),
                                 ("index_enhanced", ENHANCED), ("money_market", MONEY)):
            for metric in self.method.PROFILES[profile]["required_evidence"]:
                with self.subTest(profile=profile, metric=metric):
                    metrics = deepcopy(fixture)
                    for values in metrics.values():
                        values.pop(metric, None)
                    result = self.method.evaluate(profile, metrics, QUALITY)
                    self.assertEqual(result["status"], "insufficient_evidence")
                    self.assertIsNone(result["total_score"])
                    self.assertIn(f"core_metric:{metric}", result["missing_data"])

    def test_true_zero_core_inputs_pass_gate(self):
        metrics = deepcopy(COMPLETE)
        metrics["1y"].update(annualized_return=0.0, max_drawdown=0.0, sharpe_ratio=0.0)
        result = self.method.evaluate("active_equity", metrics, QUALITY)
        self.assertEqual(result["status"], "ok")
        self.assertIsNotNone(result["total_score"])

    def _scoring(self, lookthrough=None):
        return Scoring(data_quality_service=object(), classification_service=Classification(),
                       methodology=self.method, fof_holding_service=lookthrough)

    def test_fof_gate_blocks_despite_complete_numeric_inputs(self):
        for status in ("insufficient_evidence", "sufficient"):
            with self.subTest(status=status):
                lookthrough = SimpleNamespace(get=lambda code, refresh: {
                    "evidence_gate": {"status": status, "missing_items": ["FOF evidence missing"]},
                })
                result = self._scoring(lookthrough).score_from_inputs(
                    {"wind_code": "OFFLINE.FOF"}, {"strategy_family_key": "fof_balanced_allocation"},
                    _panel(COMPLETE), QUALITY,
                )
                if status == "sufficient":
                    self.assertIsNotNone(result["overall_score"])
                else:
                    self.assertEqual(result["status"], "insufficient_evidence")
                    self.assertIsNone(result["overall_score"])
                    self.assertIn("FOF evidence missing", result["missing_data"])

    def test_partial_tenure_history_is_excluded_before_methodology(self):
        panel = _panel(COMPLETE)
        for item in panel:
            if item["metric_window"] == "manager_tenure":
                item["details"] = {"tenure_coverage_status": "partial_since_data_start"}
        result = self._scoring().score_from_inputs(
            {"wind_code": "OFFLINE.TENURE"}, {"strategy_family_key": "active_equity_core"}, panel, QUALITY,
        )
        self.assertIsNone(result["dimension_scores"]["manager_tenure"]["score"])
        self.assertIs(result["dimension_scores"]["manager_tenure"]["included_in_score"], False)
        self.assertEqual(result["dimension_scores"]["manager_tenure"]["effective_weight"], 0.0)
        self.assertEqual(History._evidence_coverage(result["dimension_scores"])["coverage_percent"], 90.0)

    def test_unknown_classification_still_blocks(self):
        result = self._scoring().score_from_inputs({"wind_code": "OFFLINE.UNKNOWN"}, {}, _panel(COMPLETE), QUALITY)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["overall_score"])


class ScoringWindowEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.service = Scoring(data_quality_service=object(), classification_service=Classification())
        self.fund = {
            "wind_code": "OFFLINE.WINDOW", "establishment_date": "2000-01-01",
            "total_asset": 80.0,
            "raw_data": {"info": {"management_fee": 0.5, "custodian_fee": 0.1}},
            "performance_data": {
                "annualized_return_1y": 0.12, "return_1y": 0.11, "annual_return": 0.1,
                "max_drawdown_1y": -0.1, "max_drawdown": -0.3,
                "annualized_volatility_1y": 0.15, "volatility": 0.25,
                "sharpe_ratio": 1.2, "sharpe": 1.1, "calmar_ratio": 1.5,
                "positive_return_ratio": 0.6, "win_rate_1y": 0.7,
                "tracking_difference": -0.003, "excess_return": 0.02,
                "seven_day_annualized_yield": 0.019, "income_per_10000": 0.52,
                "benchmark_annualized_rate": 0.015, "benchmark_yield_spread": 0.004,
            },
            "risk_metrics": {
                "max_drawdown_1y": -0.08, "max_drawdown_2y": -0.2, "max_drawdown": -0.3,
                "annualized_volatility_1y": 0.12, "volatility_1y": 0.13, "volatility": 0.22,
                "tracking_error": 0.005, "information_ratio": 0.8,
            },
        }
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings("ignore", message=r"datetime\.datetime\.utcnow\(\) is deprecated",
                                category=DeprecationWarning, module="offline_scoring_contract")

    def score(self, panel, fund=None, family="active_equity_core", window="1y"):
        return self.service.score_from_inputs(
            self.fund if fund is None else fund, {"strategy_family_key": family},
            panel, QUALITY, evaluation_window=window,
        )

    def test_legacy_performance_and_risk_do_not_create_windowed_facts(self):
        for section in ("performance_data", "performance"):
            with self.subTest(section=section):
                fund = deepcopy(self.fund)
                performance = fund.pop("performance_data")
                fund[section] = performance
                facts = self.service.metric_facts_from_fund(fund)
                self.assertFalse({key: values for key, values in facts.items()
                                  if key != "latest" and values})
                self.assertEqual(set(facts["latest"]), {
                    "expense_ratio", "aum", "seven_day_annualized_yield", "income_per_10000",
                })

    def test_each_legacy_alias_cannot_fill_a_missing_period_metric(self):
        for section in ("performance_data", "risk_metrics"):
            for key, value in self.fund[section].items():
                if key in {"seven_day_annualized_yield", "income_per_10000",
                           "benchmark_annualized_rate", "benchmark_yield_spread"}:
                    continue
                with self.subTest(section=section, field=key):
                    facts = self.service.metric_facts_from_fund({section: {key: value}})
                    self.assertFalse(facts.get("1y"))

    def test_legacy_values_cannot_satisfy_return_risk_core_gates(self):
        for metric in ("annualized_return", "max_drawdown", "sharpe_ratio"):
            with self.subTest(metric=metric):
                metrics = deepcopy(COMPLETE)
                del metrics["1y"][metric]
                result = self.score(_panel(metrics))
                self.assertIsNone(result["overall_score"])
                self.assertEqual(result["status"], "insufficient_evidence")
                self.assertIn(f"core_metric:1y.{metric}", result["missing_data"])

    def test_legacy_values_cannot_satisfy_index_core_gates(self):
        result = self.score([], family="index_broad")
        self.assertIsNone(result["overall_score"])
        self.assertIn("core_metric:tracking_error", result["missing_data"])
        self.assertIn("core_metric:tracking_difference", result["missing_data"])

    def test_legacy_values_cannot_satisfy_enhanced_index_core_gates(self):
        result = self.score([], family="index_enhanced")
        self.assertIsNone(result["overall_score"])
        for metric in ("excess_return", "tracking_error", "information_ratio", "max_drawdown"):
            self.assertIn(f"core_metric:{metric}", result["missing_data"])

    def test_legacy_values_cannot_satisfy_money_market_period_gates(self):
        result = self.score([], family="cash_management")
        self.assertIsNone(result["overall_score"])
        self.assertIn("core_metric:annualized_return", result["missing_data"])
        self.assertIn("core_metric:max_drawdown", result["missing_data"])
        self.assertNotIn("core_metric:seven_day_annualized_yield", result["missing_data"])

    def test_legacy_values_cannot_hide_optional_evidence_gaps(self):
        metrics = {"1y": {key: COMPLETE["1y"][key]
                          for key in ("annualized_return", "max_drawdown", "sharpe_ratio")}}
        result = self.score(_panel(metrics))
        baseline = self.score(_panel(metrics), fund={"wind_code": "OFFLINE.WINDOW"})
        for key in ("overall_score", "dimension_scores", "missing_data", "status"):
            self.assertEqual(result[key], baseline[key])
        self.assertIsNone(result["dimension_scores"]["consistency"]["score"])
        self.assertIn("optional_metric:1y.annualized_volatility", result["missing_data"])

    def test_fund_level_source_label_does_not_certify_individual_windows(self):
        fund = deepcopy(self.fund)
        fund["performance_data"].update(source="metric_snapshot", as_of_date="2026-10-01")
        fund["risk_metrics"].update(source="metric_snapshot", metric_window="1y")
        self.assertIsNone(self.score([], fund=fund)["overall_score"])

    def test_latest_facts_remain_available_without_period_fallback(self):
        facts = self.service.metric_facts_from_fund(self.fund)["latest"]
        self.assertAlmostEqual(facts["expense_ratio"], 0.006)
        self.assertEqual(facts["aum"], 80.0)
        self.assertEqual(facts["seven_day_annualized_yield"], 0.019)
        result = self.score(_panel({"1y": INDEX["1y"]}), family="index_broad")
        baseline = self.score(_panel({"1y": INDEX["1y"], "latest": facts}),
                              fund={"wind_code": "OFFLINE.WINDOW"}, family="index_broad")
        self.assertIsNotNone(result["overall_score"])
        self.assertEqual(result["overall_score"], baseline["overall_score"])

    def test_complete_panel_and_real_zero_values_keep_precedence(self):
        metrics = deepcopy(COMPLETE)
        metrics["1y"].update(annualized_return=0.0, max_drawdown=0.0, sharpe_ratio=0.0,
                             calmar_ratio=0.0, positive_return_ratio=0.0)
        result = self.score(_panel(metrics))
        baseline = self.score(_panel(metrics), fund={"wind_code": "OFFLINE.WINDOW"})
        for key in ("overall_score", "dimension_scores", "missing_data", "status"):
            self.assertEqual(result[key], baseline[key])
        for name in ("annualized_return", "max_drawdown", "sharpe_ratio"):
            self.assertEqual(result["metric_scores"][f"1y.{name}"], 0.0)

    def test_latest_zero_values_remain_facts(self):
        facts = self.service.metric_facts_from_fund({
            "management_fee": 0.0, "custodian_fee": 0.0, "total_asset": 0.0,
            "performance": {"yield_7d": 0.0, "income_10k": 0.0},
        })["latest"]
        self.assertEqual(facts, {"expense_ratio": 0.0, "aum": 0.0,
                                 "seven_day_annualized_yield": 0.0, "income_per_10000": 0.0})

    def test_missing_selected_window_does_not_borrow_one_year_panel(self):
        for window in ("6m", "3y"):
            with self.subTest(window=window):
                result = self.score(_panel({"1y": COMPLETE["1y"]}), window=window)
                self.assertIsNone(result["overall_score"])
                self.assertIn(f"core_metric:{window}.annualized_return", result["missing_data"])


class BenchmarkPanelSelectionTests(unittest.TestCase):
    def setUp(self):
        self.service = Scoring(data_quality_service=object(), classification_service=Classification())
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings("ignore", message=r"datetime\.datetime\.utcnow\(\) is deprecated",
                                category=DeprecationWarning, module="offline_scoring_contract")

    @staticmethod
    def row(name, value, benchmark=None, day="2026-09-30", updated="2026-10-01T00:00:00+00:00", window="1y"):
        return {"metric_name": name, "metric_value": value, "metric_window": window,
                "benchmark_code": benchmark, "as_of_date": day, "updated_at": updated}

    def score(self, rows, benchmark="000300.SH", family="index_broad"):
        context = {"status": "resolved", "strategy_family_key": family,
                   "peer_group_key": "test-group", "peer_group_name": "Test group",
                   "benchmark_mapping": {"benchmark_code": benchmark, "benchmark_name": "Test benchmark"}}
        return self.service.score_from_inputs(
            {"wind_code": "BENCHMARK.TEST"}, {}, rows + _panel({"latest": {"expense_ratio": 0.006, "aum": 45}}),
            QUALITY, context,
        )

    def test_current_benchmark_wins_regardless_of_order_or_other_benchmark_date(self):
        selected = [self.row("tracking_error", 0.006, "000300.SH"),
                    self.row("tracking_difference", -0.004, "000300.SH")]
        other = [self.row("tracking_error", 0.09, "000905.SH", "2026-10-01"),
                 self.row("tracking_difference", -0.07, "000905.SH", "2026-10-01")]
        expected = self.score(selected)
        for rows in (selected + other, other + selected, list(reversed(selected + other))):
            with self.subTest(rows=rows):
                result = self.score(rows)
                self.assertEqual(result["metric_scores"], expected["metric_scores"])
                self.assertEqual(result["overall_score"], expected["overall_score"])
                self.assertEqual(result["as_of_date"], "2026-09-30")

    def test_missing_current_benchmark_does_not_borrow_other_or_unlabelled_metrics(self):
        for benchmark in ("000905.SH", None):
            with self.subTest(benchmark=benchmark):
                result = self.score([self.row("tracking_error", 0.006, benchmark),
                                     self.row("tracking_difference", -0.004, benchmark)])
                self.assertIsNone(result["overall_score"])
                self.assertIn("core_metric:tracking_error", result["missing_data"])

    def test_missing_one_current_metric_does_not_mix_benchmarks(self):
        result = self.score([self.row("tracking_error", 0.006, "000300.SH"),
                             self.row("tracking_difference", -0.004, "000905.SH")])
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result["missing_data"], ["core_metric:tracking_difference"])

    def test_unknown_mapping_with_multiple_bases_is_missing_not_last_row(self):
        for rows in (
            [self.row("tracking_error", 0.006, "000300.SH"), self.row("tracking_difference", -0.004, "000905.SH")],
            [self.row("tracking_error", 0.006), self.row("tracking_difference", -0.004, "000905.SH")],
        ):
            with self.subTest(rows=rows):
                result = self.score(rows, benchmark=None)
                self.assertIsNone(result["overall_score"])
                self.assertIn("core_metric:tracking_error", result["missing_data"])

    def test_unknown_mapping_preserves_single_unambiguous_basis(self):
        for benchmark in (None, "000300.SH"):
            with self.subTest(benchmark=benchmark):
                result = self.score([self.row("tracking_error", 0.006, benchmark),
                                     self.row("tracking_difference", -0.004, benchmark)], benchmark=None)
                self.assertIsNotNone(result["overall_score"])

    def test_absolute_metrics_use_latest_date_across_group_and_benchmark_tags(self):
        older = self.row("annualized_return", 0.9, "OLD", "2026-09-01")
        newer = self.row("annualized_return", 0.07, None, "2026-09-30")
        older["peer_group_key"], newer["peer_group_key"] = "z-old", "a-current"
        for rows in ([newer, older], [older, newer]):
            metrics = self.service._metrics_by_window(rows)
            self.assertEqual(metrics["1y"]["annualized_return"], 0.07)

    def test_latest_update_wins_with_same_as_of_and_timezone_normalization(self):
        older = self.row("annualized_return", 0.9, updated="2026-10-01T09:00:00+08:00")
        newer = self.row("annualized_return", 0.07, updated="2026-10-01T02:00:00+00:00")
        for rows in ([newer, older], [older, newer]):
            self.assertEqual(self.service._metrics_by_window(rows)["1y"]["annualized_return"], 0.07)

    def test_equal_time_conflicting_values_are_missing(self):
        rows = [self.row("tracking_error", value, "000300.SH") for value in (0.006, 0.05)]
        rows.append(self.row("tracking_difference", -0.004, "000300.SH"))
        for ordering in (rows, list(reversed(rows))):
            result = self.score(ordering)
            self.assertIsNone(result["overall_score"])
            self.assertIn("core_metric:tracking_error", result["missing_data"])

    def test_equal_time_identical_values_are_not_ambiguous(self):
        rows = [self.row("tracking_error", 0.0, "000300.SH") for _ in range(2)]
        rows.append(self.row("tracking_difference", 0.0, "000300.SH"))
        result = self.score(rows)
        self.assertIsNotNone(result["overall_score"])
        self.assertEqual(result["metric_scores"]["1y.tracking_error"], 0.0)

    def test_latest_null_or_invalid_value_does_not_revive_older_metric(self):
        for value in (None, float("nan"), float("inf"), True, "invalid"):
            with self.subTest(value=value):
                rows = [self.row("tracking_error", value, "000300.SH"),
                        self.row("tracking_error", 0.006, "000300.SH", day="2026-09-01"),
                        self.row("tracking_difference", -0.004, "000300.SH")]
                self.assertIsNone(self.score(rows)["overall_score"])

    def test_absolute_manager_metrics_are_not_filtered_by_benchmark(self):
        rows = _panel(COMPLETE)
        for row in rows:
            if row["metric_window"] == "manager_tenure":
                row["benchmark_code"] = "LEGACY-NAME"
        result = self.score(rows, family="active_equity_core")
        self.assertIsNotNone(result["dimension_scores"]["manager_tenure"]["score"])

    def test_window_selection_does_not_mix_other_window_benchmarks(self):
        rows = [self.row("tracking_error", 0.006, "000300.SH"),
                self.row("tracking_difference", -0.004, "000300.SH"),
                self.row("tracking_error", 0.08, "000905.SH", window="3y")]
        self.assertIsNotNone(self.score(rows, benchmark=None)["overall_score"])

    def test_selection_does_not_mutate_panel(self):
        rows = [self.row("tracking_error", 0.006, "000300.SH"),
                self.row("tracking_difference", -0.004, "000300.SH")]
        before = deepcopy(rows)
        self.score(rows)
        self.assertEqual(rows, before)


def save_money_benchmark_fixture(benchmark_code="DR007"):
    path = SERVICES.parent / "scripts/sync_fund_ranking_metrics.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"number_or_none", "save_enrichment_metric_facts"}]
    namespace = {"Decimal": Decimal}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    saved = []
    def capture(records):
        saved.extend({**record, "metric_window": record["window"]} for record in records)
        return saved
    namespace["save_enrichment_metric_facts"](
        SimpleNamespace(upsert_metrics=capture), "MONEY.TEST", {
            "benchmark_code": benchmark_code,
            "performance_facts": {
                "seven_day_annualized_yield": 0.019, "income_per_10000": 0.5,
                "benchmark_annualized_rate": 0.015, "benchmark_yield_spread": 0.004,
            },
        }, date(2026, 9, 30),
    )
    return saved


class MoneyBenchmarkWriterTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings("ignore", message=r"datetime\.datetime\.utcnow\(\) is deprecated",
                                category=DeprecationWarning, module="offline_scoring_contract")

    def test_writer_labels_relative_rates_but_not_fund_income(self):
        rows = save_money_benchmark_fixture()
        self.assertEqual(len(rows), 4)
        for row in rows:
            expected = "DR007" if row["metric_name"] in {"benchmark_annualized_rate", "benchmark_yield_spread"} else None
            self.assertEqual(row.get("benchmark_code"), expected, row["metric_name"])

    def test_writer_without_benchmark_does_not_save_unlabelled_relative_rates(self):
        rows = save_money_benchmark_fixture(None)
        self.assertEqual({row["metric_name"] for row in rows}, {"seven_day_annualized_yield", "income_per_10000"})

    def test_generated_benchmark_rates_survive_current_mapping_filter(self):
        service = Scoring(data_quality_service=object(), classification_service=Classification())
        panel = _panel({"1y": MONEY["1y"], "latest": {"aum": 120.0}}) + save_money_benchmark_fixture()
        result = service.score_from_inputs({"wind_code": "MONEY.TEST"}, {}, panel, QUALITY, {
            "status": "resolved", "strategy_family_key": "cash_management", "peer_group_key": "money",
            "peer_group_name": "Money", "benchmark_mapping": {"benchmark_code": "DR007", "benchmark_name": "DR007"},
        })
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metric_scores"]["latest.benchmark_annualized_rate"], 0.015)
        self.assertEqual(result["metric_scores"]["latest.benchmark_yield_spread"], 0.004)


class MoneyBenchmarkFallbackTests(unittest.TestCase):
    def setUp(self):
        self.service = Scoring(data_quality_service=object(), classification_service=Classification())
        self.enterContext(warnings.catch_warnings())
        warnings.filterwarnings("ignore", message=r"datetime\.datetime\.utcnow\(\) is deprecated",
                                category=DeprecationWarning, module="offline_scoring_contract")

    def score(self, relative_rows):
        return self.service.score_from_inputs({
            "wind_code": "MONEY.TEST", "performance_data": {
                "benchmark_annualized_rate": 0.025, "benchmark_yield_spread": -0.006,
                "benchmark_rate_code": "OLD", "source": "metric_snapshot",
            },
        }, {}, _panel({"1y": MONEY["1y"], "latest": {"aum": 120.0, "seven_day_annualized_yield": 0.019}})
            + relative_rows, QUALITY, {
                "status": "resolved", "strategy_family_key": "cash_management", "peer_group_key": "money",
                "peer_group_name": "Money", "benchmark_mapping": {"benchmark_code": "DR007", "benchmark_name": "DR007"},
            })

    def test_legacy_relative_rate_facts_are_not_fallback_evidence(self):
        facts = self.service.metric_facts_from_fund({"performance_data": {
            "benchmark_annualized_rate": 0.025, "benchmark_yield_spread": -0.006,
            "benchmark_rate_code": "DR007", "seven_day_annualized_yield": 0.019,
        }})
        self.assertEqual(facts["latest"], {"seven_day_annualized_yield": 0.019})

    def test_missing_or_wrong_benchmark_snapshot_cannot_be_refilled_from_json(self):
        for rows in ([], save_money_benchmark_fixture("OLD"), save_money_benchmark_fixture(None)):
            with self.subTest(rows=rows):
                result = self.score(rows)
                self.assertEqual(result["status"], "partial")
                self.assertNotIn("latest.benchmark_annualized_rate", result["metric_scores"])
                self.assertNotIn("latest.benchmark_yield_spread", result["metric_scores"])
                self.assertIn("optional_metric:latest.benchmark_annualized_rate", result["missing_data"])

    def test_current_snapshot_not_stale_json_supplies_benchmark_evidence(self):
        result = self.score(save_money_benchmark_fixture())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metric_scores"]["latest.benchmark_annualized_rate"], 0.015)
        self.assertEqual(result["metric_scores"]["latest.benchmark_yield_spread"], 0.004)

    def test_real_zero_benchmark_rate_is_not_replaced_by_json(self):
        rows = save_money_benchmark_fixture()
        for row in rows:
            if row.get("benchmark_code"):
                row["metric_value"] = 0.0
        result = self.score(rows)
        self.assertEqual(result["metric_scores"]["latest.benchmark_annualized_rate"], 0.0)
        self.assertEqual(result["metric_scores"]["latest.benchmark_yield_spread"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
