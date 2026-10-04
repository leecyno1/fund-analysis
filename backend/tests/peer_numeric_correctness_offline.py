"""Offline peer regressions: execute the complete production class without app imports."""
import ast
from copy import deepcopy
from datetime import date, timedelta
from itertools import permutations
from pathlib import Path
from runpy import run_path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SERVICE_PATH = Path(__file__).resolve().parents[1] / "services" / "peer_comparison_service.py"


def load_peer_service():
    # services.__init__ and repositories import application dependencies. Keep the
    # entire class intact, loading only its standard-library imports and deferring
    # annotations so injected dependencies never require application imports.
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
    safe_imports = {"datetime", "decimal", "statistics", "typing", "itertools"}
    body = ast.parse("from __future__ import annotations").body
    body.extend(
        node for node in tree.body
        if (isinstance(node, ast.ImportFrom) and node.module in safe_imports)
        or (isinstance(node, ast.ClassDef) and node.name == "PeerComparisonService")
    )
    contract = ast.parse((SERVICE_PATH.parent / "scoring_contract.py").read_text())
    body.extend(node for node in contract.body if isinstance(node, ast.FunctionDef) and node.name == "grade_for_score")
    namespace = {
        "__name__": "offline_peer_service",
        "ProfessionalScoringService": run_path(str(Path(__file__).with_name("fund_evaluation_numeric_offline_test.py")))["Scoring"],
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                 str(SERVICE_PATH), "exec"), namespace)
    return namespace["PeerComparisonService"]


PeerComparisonService = load_peer_service()
# This pure standard-library module can run without importing the app package.
FundEvaluationMethodology = run_path(
    str(SERVICE_PATH.parent / "fund_evaluation_methodology.py")
)["FundEvaluationMethodology"]


class PeerRankingTests(unittest.TestCase):
    def setUp(self):
        self.service = PeerComparisonService(
            scoring_service=SimpleNamespace(), classification_service=SimpleNamespace()
        )
        self.options = {
            "higher_is_better": True,
            "metric_name": "return",
            "label": "Return",
            "unit": "percent",
            "metric_window": "1y",
            "required_for_sample": True,
            "source_metric_names": ["annualized_return"],
        }

    def rank_map(self, values, **options):
        return self.service._rank_metric_map(values=values, **{**self.options, **options})

    def rank_one(self, code, values, **options):
        return self.service._rank_metric(target_id=code, values=values,
                                         **{**self.options, **options})

    def test_all_equal_batch_is_neutral_with_shared_first_rank(self):
        values = [(str(index), 7.0) for index in range(5)]
        for higher in (True, False):
            with self.subTest(higher=higher):
                positions = self.rank_map(values, higher_is_better=higher)
                self.assertEqual({(m["rank"], m["percentile"]) for m in positions.values()},
                                 {(1, 50.0)})

    def test_all_equal_single_is_neutral_with_shared_first_rank(self):
        values = [(str(index), 7.0) for index in range(5)]
        for higher in (True, False):
            with self.subTest(higher=higher):
                positions = [self.rank_one(code, values, higher_is_better=higher)
                             for code, _ in values]
                self.assertEqual({(m["rank"], m["percentile"]) for m in positions},
                                 {(1, 50.0)})

    def test_competition_ranks_use_average_tied_position_higher(self):
        values = [("a", 30.0), ("b", 30.0), ("c", 20.0), ("d", 10.0), ("e", 10.0)]
        expected = {"a": (1, 87.5), "b": (1, 87.5), "c": (3, 50.0),
                    "d": (4, 12.5), "e": (4, 12.5)}
        for code, metric in self.rank_map(values).items():
            with self.subTest(code=code):
                self.assertEqual((metric["rank"], metric["percentile"]), expected[code])
                self.assertEqual(self.rank_one(code, values), metric)

    def test_competition_ranks_preserve_lower_is_better(self):
        values = [("a", 30.0), ("b", 30.0), ("c", 20.0), ("d", 10.0), ("e", 10.0)]
        expected = {"a": (4, 12.5), "b": (4, 12.5), "c": (3, 50.0),
                    "d": (1, 87.5), "e": (1, 87.5)}
        for code, metric in self.rank_map(values, higher_is_better=False).items():
            with self.subTest(code=code):
                self.assertEqual((metric["rank"], metric["percentile"]), expected[code])
                self.assertEqual(metric["direction"], "lower")
                self.assertEqual(self.rank_one(code, values, higher_is_better=False), metric)

    def test_tie_results_do_not_depend_on_input_order(self):
        values = [("a", 3.0), ("b", 3.0), ("c", 2.0), ("d", 1.0), ("e", 1.0)]
        for higher in (True, False):
            with self.subTest(higher=higher):
                baseline = self.rank_map(values, higher_is_better=higher)
                for ordering in permutations(values):
                    self.assertEqual(self.rank_map(list(ordering), higher_is_better=higher), baseline)

    def test_single_batch_metadata_and_missing_target_match(self):
        values = [(str(index), float(index)) for index in range(5)] + [("missing", None)]
        for minimum in (5, 6):
            batch = self.rank_map(values, minimum_peer_count=minimum)
            for code, metric in batch.items():
                self.assertEqual(self.rank_one(code, values, minimum_peer_count=minimum), metric)
            absent = self.rank_one("absent", values, minimum_peer_count=minimum)
            self.assertEqual(absent, batch["missing"])
            self.assertEqual(absent["sample_status"],
                             "target_metric_missing" if minimum == 5 else "insufficient_peer_sample")

    def test_untied_ranks_keep_endpoints_and_direction(self):
        values = [(str(index), float(index)) for index in range(5)]
        for higher in (True, False):
            result = self.rank_map(values, higher_is_better=higher)
            for index in range(5):
                expected_rank = 5 - index if higher else index + 1
                self.assertEqual(result[str(index)]["rank"], expected_rank)
                self.assertEqual(result[str(index)]["percentile"], (5 - expected_rank) * 25.0)

    def test_sample_gates_keep_empty_singleton_and_custom_minimum_unranked(self):
        for count, minimum in ((0, None), (1, None), (4, None), (5, 6), (1, 1)):
            with self.subTest(count=count, minimum=minimum):
                values = [(str(index), 1.0) for index in range(count)]
                metric = self.rank_one("0", values, minimum_peer_count=minimum)
                self.assertEqual(metric["sample_status"], "insufficient_peer_sample")
                self.assertEqual(metric["peer_count"], count)
                self.assertIsNone(metric["rank"])
                self.assertIsNone(metric["percentile"])
        sufficient = self.rank_map([("a", 2.0), ("b", 1.0)], minimum_peer_count=1)
        self.assertEqual(sufficient["a"]["minimum_peer_count"], 2)
        self.assertEqual(sufficient["a"]["percentile"], 100.0)

    def test_repeated_entity_does_not_inflate_sample_or_change_positions(self):
        values = [(str(index), float(index)) for index in range(4)]
        duplicate = values + [values[0]]
        self.assertEqual(self.rank_map(duplicate), self.rank_map(values))
        self.assertEqual(self.rank_one("0", duplicate), self.rank_one("0", values))
        sufficient = values + [("4", 4.0)]
        self.assertEqual(self.rank_map(sufficient + [sufficient[0]]), self.rank_map(sufficient))

    def test_ranking_uses_raw_values_not_display_rounding(self):
        values = [(str(index), 1.0 + index * 0.00000001) for index in range(5)]
        result = self.rank_map(values)
        self.assertEqual({metric["value"] for metric in result.values()}, {1.0})
        self.assertEqual([result[str(index)]["rank"] for index in range(5)], [5, 4, 3, 2, 1])

    def test_statistics_table_matches_current_position_for_ties(self):
        for scores in ([70.0] * 5, [70.0, 70.00001, 60.0, 50.0, 50.0], [70.0]):
            with self.subTest(scores=scores):
                values = [(str(index), score) for index, score in enumerate(scores)]
                details = {code: {"overall_score": score} for code, score in values}
                ranking, unscored = self.service._score_ranking(
                    [{"wind_code": code} for code, _ in values], details, {}, [], "1y", "0",
                )
                expected = self.rank_map(values)
                self.assertEqual(unscored, [])
                for row in ranking:
                    current = expected[row["wind_code"]]
                    self.assertEqual((row["rank"], row["percentile"]), (current["rank"], current["percentile"]))


class PeerBuildFixture:
    """Supply data/configuration at boundaries; all peer algorithms remain real."""

    def __init__(self, windows_by_code, minimum=5, optional_only=False,
                 formal_scores=None, methodology=None, profile_key="offline_profile"):
        self.configs = [
            {"metric_name": "return", "label": "1Y Return", "unit": "percent",
             "higher_is_better": True, "paths": [("selected", "return")],
             "required_for_sample": not optional_only, "valid_range": [-1.0, 1.0]},
            {"metric_name": "risk", "label": "1Y Risk", "unit": "percent",
             "higher_is_better": False, "paths": [("selected", "risk"), ("latest", "risk")],
             "required_for_sample": not optional_only, "transform": "absolute",
             "valid_range": [0.0, 1.0]},
            {"metric_name": "fee", "label": "Fee", "unit": "percent",
             "higher_is_better": False, "paths": [("latest", "fee")],
             "required_for_sample": False},
        ]
        classification = {
            "status": "classified", "peer_group_id": "offline_group",
            "peer_group": "Offline peers", "evaluation_profile_key": profile_key,
            "minimum_peer_count": minimum,
        }
        self.panels = {
            code: [{"metric_window": window, "metric_name": name, "metric_value": value}
                   for window, metrics in windows.items() for name, value in metrics.items()]
            for code, windows in windows_by_code.items()
        }
        self.contexts = [
            {"fund": {"wind_code": code, "name": code, "type": "offline",
                      "establishment_date": "1900-01-01"},
             "profile": {}, "metric_panel": panel,
             "standardized_classification": {"status": "resolved"},
             "classification": dict(classification)}
            for code, panel in self.panels.items()
        ]
        # Formal scores are independent inputs, never inferred from proxy scores.
        self.scorings = {
            code: {"classification": dict(classification),
                   "overall_score": (formal_scores or {}).get(code)}
            for code in windows_by_code
        }
        self.metric_repo = SimpleNamespace(
            get_latest_panels=Mock(side_effect=lambda entity, codes: {
                code: self.panels[code] for code in codes
            }),
            get_latest_panel=Mock(side_effect=AssertionError("unexpected per-fund data read")),
        )
        self.repositories = ModuleType("repositories")
        self.repositories.get_metric_snapshot_repo = lambda: self.metric_repo
        scoring_service = SimpleNamespace(
            methodology=methodology or SimpleNamespace(peer_metric_configs=lambda profile: self.configs),
            score_peer_metrics=lambda profile, metrics: metrics.get("proxy_score"),
            score_fund=Mock(side_effect=AssertionError("formal scoring must not be called")),
        )
        if methodology is not None:
            scoring_service.score_peer_metrics = methodology.score_peer
            scoring_service.score_peer_details = methodology.score_peer_details
        self.service = PeerComparisonService(
            scoring_service=scoring_service,
            classification_service=SimpleNamespace(),
            classification_adapter=SimpleNamespace(
                list_peer_funds=Mock(side_effect=lambda group, **kwargs: [
                    dict(item["fund"]) for item in self.contexts
                ])
            ),
            fund_repo=SimpleNamespace(),
            profile_repo=SimpleNamespace(
                get_profile=Mock(return_value={}), list_profiles=Mock(return_value={})
            ),
        )

    def single(self, code="a", window="1y"):
        context = next(item for item in self.contexts if item["fund"]["wind_code"] == code)
        with patch.dict(sys.modules, {"repositories": self.repositories}):
            return self.service.build_peer_percentiles(code, window=window, target_context=context)

    def batch(self, window="1y"):
        with patch.dict(sys.modules, {"repositories": self.repositories}):
            return self.service.build_peer_percentiles_from_contexts(self.contexts, self.scorings, window=window)

    def statistics(self, code="a", window="1y"):
        context = next(item for item in self.contexts if item["fund"]["wind_code"] == code)
        with patch.dict(sys.modules, {"repositories": self.repositories}):
            return self.service.build_peer_statistics(code, window=window, target_context=context)

    def both(self, code="a", window="1y"):
        return {"single": self.single(code, window), "batch": self.batch(window)[code]}


def coverage_fixture(return_codes="abcde", risk_codes="abcdf", **options):
    codes = sorted(set(return_codes) | set(risk_codes))
    return PeerBuildFixture({
        code: {"1y": {"return": 0.1 if code in return_codes else None,
                       "risk": 0.2 if code in risk_codes else None}}
        for code in codes
    }, **options)


class PeerIntersectionTests(unittest.TestCase):
    def test_valid_count_is_actual_intersection_not_minimum_marginal_count(self):
        for path, result in coverage_fixture().both().items():
            with self.subTest(path=path):
                self.assertEqual(result["metric_coverage"]["return"], 5)
                self.assertEqual(result["metric_coverage"]["risk"], 5)
                self.assertEqual(result["valid_metric_peer_count"], 4)
                for name in ("return", "risk"):
                    self.assertEqual(result["metrics"][name]["sample_status"], "sufficient")
                    self.assertEqual(result["metrics"][name]["percentile"], 50.0)

    def test_intersection_shortage_blocks_overall_sufficient(self):
        for path, result in coverage_fixture().both().items():
            with self.subTest(path=path):
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")

    def test_intersection_shortage_reports_actionable_complete_peer_gap(self):
        for path, result in coverage_fixture().both().items():
            with self.subTest(path=path):
                gap = result["peer_metric_gap"]
                self.assertEqual(gap["required_more_funds"], 1)
                self.assertEqual(gap["next_action"], "sync_peer_nav_and_rolling_metrics")
                self.assertEqual(set(gap["suggested_sync_codes"]), {"e", "f"})
                complete_gap = next(item for item in gap["blocking_metrics"]
                                    if item["metric_name"] == "complete_required_metrics")
                self.assertEqual(complete_gap["peer_count"], 4)
                self.assertEqual(complete_gap["missing_count"], 1)
                suggestions = {item["wind_code"]: item["missing_metrics"]
                               for item in gap["suggested_sync_funds"]}
                self.assertEqual(suggestions, {"e": ["risk"], "f": ["return"]})

    def test_complete_peer_gap_uses_classification_threshold_and_filtered_inputs(self):
        fixtures = [
            (coverage_fixture("abcdef", "abcdeg", minimum=6), 1),
            (coverage_fixture("abcde", "fghij"), 5),
            (coverage_fixture("abc", "abcd"), 2),
        ]
        for fixture, shortage in fixtures:
            for path, result in fixture.both().items():
                with self.subTest(path=path, shortage=shortage):
                    gap = result["peer_metric_gap"]
                    self.assertEqual(gap["required_more_funds"], shortage)
                    self.assertEqual(gap["next_action"], "sync_peer_nav_and_rolling_metrics")

    def test_complete_peer_gap_ignores_optional_metric_shortage(self):
        for fixture in (coverage_fixture("abcdef", "abcdeg"),
                        coverage_fixture(optional_only=True)):
            for path, result in fixture.both().items():
                with self.subTest(path=path):
                    gap = result["peer_metric_gap"]
                    self.assertEqual(gap["required_more_funds"], 0)
                    self.assertEqual(gap["blocking_metrics"], [])
                    self.assertEqual(gap["suggested_sync_codes"], [])
                    self.assertEqual(gap["next_action"], "none")

    def test_disjoint_required_samples_have_zero_valid_peers(self):
        for path, result in coverage_fixture("abcde", "fghij").both().items():
            with self.subTest(path=path):
                self.assertEqual(result["metric_coverage"]["return"], 5)
                self.assertEqual(result["metric_coverage"]["risk"], 5)
                self.assertEqual(result["valid_metric_peer_count"], 0)
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")

    def test_intersection_at_minimum_is_sufficient_despite_optional_missing(self):
        for path, result in coverage_fixture("abcdef", "abcdeg").both().items():
            with self.subTest(path=path):
                self.assertEqual(result["valid_metric_peer_count"], 5)
                self.assertEqual(result["sample_status"], "sufficient")
                self.assertEqual(result["metric_coverage"]["return"], 6)
                self.assertEqual(result["metric_coverage"]["risk"], 6)
                self.assertEqual(result["metric_coverage"]["fee"], 0)
                self.assertEqual(result["metric_coverage"]["professional_score"], 0)

    def test_no_required_metrics_is_unavailable_with_zero_valid_peers(self):
        fixture = coverage_fixture("abcde", "abcde", optional_only=True)
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["valid_metric_peer_count"], 0)
                self.assertEqual(result["sample_status"], "unavailable")

    def test_intersection_uses_range_transform_fallback_and_history_filtered_values(self):
        windows = {code: {"1y": {"return": 0.1, "risk": -0.2}} for code in "abcdefg"}
        windows["a"]["1y"]["return"] = 0.0
        windows["b"]["1y"]["return"] = 2.0
        windows["c"]["1y"]["risk"] = -2.0
        windows["f"] = {"1y": {"return": 0.1}, "latest": {"risk": -0.2}}
        windows["g"]["1y"]["risk"] = 0.0
        fixture = PeerBuildFixture(windows)
        fixture.contexts[3]["fund"]["establishment_date"] = "9999-12-31"
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["metric_coverage"]["return"], 5)
                self.assertEqual(result["metric_coverage"]["risk"], 5)
                self.assertEqual(result["valid_metric_peer_count"], 4)
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")
                self.assertEqual(result["metrics"]["risk"]["value"], 0.2)

    def test_repeated_contexts_do_not_inflate_entity_counts(self):
        fixture = coverage_fixture("abcd", "abcd")
        fixture.contexts.append(deepcopy(fixture.contexts[0]))
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["peer_count"], 4)
                self.assertEqual(result["classified_peer_count"], 4)
                self.assertEqual(result["valid_metric_peer_count"], 4)
                self.assertEqual(result["metric_coverage"]["return"], 4)
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")

    def test_target_missing_is_preserved_when_intersection_is_sufficient(self):
        fixture = coverage_fixture("bcdef", "abcdef")
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["valid_metric_peer_count"], 5)
                self.assertEqual(result["sample_status"], "target_metric_missing")
                self.assertIsNone(result["metrics"]["return"]["percentile"])

    def test_classification_specific_minimum_applies_to_intersection(self):
        fixture = coverage_fixture("abcdef", "abcdeg", minimum=6)
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["minimum_valid_peer_count"], 6)
                self.assertEqual(result["valid_metric_peer_count"], 5)
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")
                self.assertEqual(result["metrics"]["return"]["sample_status"], "sufficient")

    def test_single_batch_and_reordered_builds_match_for_identical_metric_inputs(self):
        fixture = PeerBuildFixture({
            code: {"1y": {"return": value, "risk": value, "proxy_score": value * 100},
                   "latest": {"fee": 0.01}}
            for code, value in zip("abcde", (0.3, 0.3, 0.2, 0.1, 0.1))
        }, formal_scores=dict(zip("abcde", (10, 20, 30, 40, 50))))
        batch = fixture.batch()
        singles = {code: fixture.single(code) for code in batch}
        fixture.contexts.reverse()
        self.assertEqual(fixture.batch(), batch)
        for code in batch:
            with self.subTest(code=code):
                self.assertEqual(fixture.single(code), singles[code])
                for name in ("return", "risk", "fee"):
                    self.assertEqual(singles[code]["metrics"][name], batch[code]["metrics"][name])
                for name in ("valid_metric_peer_count", "sample_status", "metric_coverage"):
                    self.assertEqual(singles[code][name], batch[code][name])
                self.assertEqual(singles[code]["metrics"]["professional_score"],
                                 batch[code]["metrics"]["professional_score"])
                self.assertEqual(singles[code]["professional_score_source"],
                                 "category_specific_peer_metric_proxy")
                self.assertEqual(batch[code]["professional_score_source"],
                                 "category_specific_peer_metric_proxy")


def proxy_fixture(scores=(90, 70, 50, 30, 10), **options):
    """Real category proxy calculations; supplied formal scores run the other way."""
    def facts(score):
        return {
            "annualized_return": -0.10 + 0.35 * score / 100,
            "max_drawdown": -0.35 + 0.32 * score / 100,
            "sharpe_ratio": 2.0 * score / 100,
        }

    codes = "abcdefg"[:len(scores)]
    return PeerBuildFixture(
        {code: {"1y": facts(score), "3y": facts(100 - score),
                "latest": {"expense_ratio": 0.01, "aum": 10.0}}
         for code, score in zip(codes, scores)},
        formal_scores={code: (index + 1) * 10 for index, code in enumerate(codes)},
        methodology=FundEvaluationMethodology(), profile_key="active_equity", **options,
    )


class PeerProxyConsistencyTests(unittest.TestCase):
    def assert_paths_match(self, fixture, code, window, batch):
        single = fixture.single(code, window)
        statistics = fixture.statistics(code, window)
        metric = batch[code]["metrics"]["professional_score"]
        self.assertEqual(single["metrics"]["professional_score"], metric)
        self.assertEqual(statistics["current"], {
            "score": metric["value"],
            **{name: metric[name] for name in ("rank", "percentile", "peer_count", "sample_status")},
        })
        self.assertEqual(statistics["scored_peer_count"], metric["peer_count"])
        self.assertEqual(statistics["classified_peer_count"], batch[code]["peer_count"])
        row = next((item for item in statistics["ranking"] if item["wind_code"] == code), None)
        if metric["value"] is None:
            self.assertIsNone(row)
        else:
            self.assertEqual((row["score"], row["rank"], row["percentile"]),
                             (metric["value"], metric["rank"], metric["percentile"]))
        return metric

    def test_reverse_formal_order_does_not_change_same_window_peer_positions(self):
        fixture = proxy_fixture()
        codes = list("abcde")
        formal_order = sorted(codes, key=lambda code: fixture.scorings[code]["overall_score"], reverse=True)
        single_order = sorted(codes, key=lambda code: fixture.single(code)["metrics"]["professional_score"]["value"],
                              reverse=True)
        self.assertEqual(single_order, list(reversed(formal_order)))
        batch = fixture.batch()
        for index, code in enumerate(codes):
            with self.subTest(code=code):
                metric = self.assert_paths_match(fixture, code, "1y", batch)
                self.assertEqual((metric["value"], metric["rank"], metric["percentile"]),
                                 (90 - index * 20, index + 1, 100 - index * 25))

    def test_window_switch_changes_proxy_positions_without_changing_formal_scores(self):
        fixture = proxy_fixture()
        before = deepcopy(fixture.scorings)
        for window, expected in (("1y", (90.0, 1, 100.0)), ("3y", (10.0, 5, 0.0))):
            with self.subTest(window=window):
                batch = fixture.batch(window)
                for code in batch:
                    self.assert_paths_match(fixture, code, window, batch)
                metric = batch["a"]["metrics"]["professional_score"]
                self.assertEqual((metric["value"], metric["rank"], metric["percentile"]), expected)
                self.assertEqual(metric["metric_window"], window)
        self.assertEqual(fixture.scorings, before)

    def test_high_formal_score_cannot_rescue_insufficient_window_history(self):
        fixture = proxy_fixture((90, 70, 50, 30, 10, 20))
        fixture.contexts[0]["fund"]["establishment_date"] = (date.today() - timedelta(days=730)).isoformat()
        fixture.scorings["a"]["overall_score"] = 100.0
        short_batch = fixture.batch("1y")
        self.assertIsNotNone(fixture.single("a", "1y")["metrics"]["professional_score"]["value"])
        for window, batch in (("1y", short_batch), ("3y", fixture.batch("3y"))):
            with self.subTest(window=window):
                metric = self.assert_paths_match(fixture, "a", window, batch)
                if window == "1y":
                    self.assertEqual(metric["value"], 90.0)
                else:
                    self.assertIsNone(metric["value"])
                    self.assertIsNone(metric["percentile"])
                    self.assertEqual(metric["sample_status"], "target_metric_missing")
                    self.assertEqual(metric["peer_count"], 5)
        self.assertEqual(fixture.statistics("a", "3y")["unscored"][0]["reason"], "insufficient_history")

    def test_high_formal_score_cannot_rescue_missing_proxy_evidence(self):
        fixture = proxy_fixture((90, 70, 50, 30, 10, 20))
        # One usable quantitative metric is below the real methodology's proxy gate.
        fixture.panels["a"][:] = [row for row in fixture.panels["a"]
                                 if row["metric_window"] != "1y" or row["metric_name"] == "annualized_return"]
        fixture.scorings["a"]["overall_score"] = 100.0
        batch = fixture.batch()
        for code in batch:
            with self.subTest(code=code):
                metric = self.assert_paths_match(fixture, code, "1y", batch)
                self.assertEqual(metric["peer_count"], 5)
                if code == "a":
                    self.assertIsNone(metric["value"])
                    self.assertIsNone(metric["rank"])
                    self.assertEqual(metric["sample_status"], "target_metric_missing")
        self.assertEqual(fixture.statistics()["unscored"][0]["reason"], "missing_required_metrics")

    def test_formal_scores_cannot_inflate_proxy_sample_above_minimum(self):
        fixture = proxy_fixture()
        fixture.panels["a"].clear()
        batch = fixture.batch()
        for code in batch:
            with self.subTest(code=code):
                metric = self.assert_paths_match(fixture, code, "1y", batch)
                self.assertEqual(metric["peer_count"], 4)
                self.assertEqual(metric["sample_status"], "insufficient_peer_sample")
                self.assertIsNone(metric["rank"])
                self.assertIsNone(metric["percentile"])

    def test_equal_proxies_share_positions_despite_distinct_formal_scores(self):
        for scores, expected in (
            ((70, 70, 50, 30, 30), ((1, 87.5), (1, 87.5), (3, 50.0), (4, 12.5), (4, 12.5))),
            ((50,) * 5, ((1, 50.0),) * 5),
        ):
            fixture = proxy_fixture(scores)
            batch = fixture.batch()
            fixture.contexts.reverse()
            self.assertEqual(fixture.batch(), batch)
            for code, position in zip("abcde", expected):
                with self.subTest(scores=scores, code=code):
                    metric = self.assert_paths_match(fixture, code, "1y", batch)
                    self.assertEqual((metric["rank"], metric["percentile"]), position)

    def test_proxy_source_metadata_agrees_across_all_three_paths(self):
        fixture = proxy_fixture()
        source = "category_specific_peer_metric_proxy"
        for window in ("1y", "3y"):
            with self.subTest(window=window):
                single, batch, statistics = fixture.single(window=window), fixture.batch(window)["a"], fixture.statistics(window=window)
                for result in (single, batch):
                    self.assertEqual(result["professional_score_source"], source)
                    self.assertEqual(result["metrics"]["professional_score"]["source_metric_names"], [source])
                    self.assertEqual(result["metric_window"], statistics["metric_window"])
                    self.assertEqual(result["peer_methodology_version"], statistics["methodology_version"])
                self.assertEqual(statistics["score_basis"], source)

    def test_batch_uses_preloaded_panels_without_data_reads_or_formal_rescoring(self):
        fixture = proxy_fixture((90, 70, 50, 30, 10, 20))
        fixture.panels["f"].clear()
        with patch.object(fixture.service, "_peer_universe", side_effect=AssertionError("unexpected universe read")), \
             patch.object(fixture.service, "_metric_map", wraps=fixture.service._metric_map) as metric_map:
            batch = fixture.batch()
        fixture.metric_repo.get_latest_panels.assert_not_called()
        fixture.metric_repo.get_latest_panel.assert_not_called()
        fixture.service._classification_adapter.list_peer_funds.assert_not_called()
        fixture.service._profile_repo_adapter.get_profile.assert_not_called()
        fixture.service._profile_repo_adapter.list_profiles.assert_not_called()
        fixture.service.scoring_service.score_fund.assert_not_called()
        metric_map.assert_called_once()
        self.assertEqual(metric_map.call_args.args[2], fixture.panels)
        self.assertEqual(batch["a"]["metrics"]["professional_score"]["value"], 90.0)
        self.assertIsNone(batch["f"]["metrics"]["professional_score"]["value"])

    def test_batch_preserves_formal_inputs_and_uses_their_classification(self):
        fixture = proxy_fixture()
        for index, context in enumerate(fixture.contexts):
            code = context["fund"]["wind_code"]
            context["classification"] = {"peer_group_id": "wrong", "evaluation_profile_key": "wrong"}
            fixture.scorings[code].update({
                "dimension_scores": {"manager_tenure": {"score": 80 + index}},
                "data_quality": {"score": 95, "issues": ["offline"]},
            })
            fixture.scorings[code]["classification"]["peer_group_id"] = "left" if index < 2 else "right"
            fixture.scorings[code]["classification"]["minimum_peer_count"] = 2
        original = deepcopy(fixture.scorings)
        contexts_before = deepcopy(fixture.contexts)
        for window in ("1y", "3y"):
            batch = fixture.batch(window)
            self.assertEqual(fixture.scorings, original)
            self.assertEqual(fixture.contexts, contexts_before)
            for index, code in enumerate("abcde"):
                with self.subTest(window=window, code=code):
                    self.assertEqual(batch[code]["classification"], original[code]["classification"])
                    self.assertEqual(batch[code]["peer_metric_profile"], "active_equity")
                    self.assertEqual(batch[code]["peer_count"], 2 if index < 2 else 3)
            self.assertEqual(batch["a"]["metrics"]["professional_score"]["value"], 90 if window == "1y" else 10)


class LegacyFundFactPeerTests(unittest.TestCase):
    def fixture(self, with_panels=False):
        scoring = run_path(str(Path(__file__).with_name("fund_evaluation_numeric_offline_test.py")))["Scoring"]
        fixture = PeerBuildFixture({
            code: {"1y": {"tracking_error": 0.005, "tracking_difference": 0.0}} if with_panels else {}
            for code in "abcde"
        }, methodology=FundEvaluationMethodology(), profile_key="index_fund")
        fixture.service.scoring_service = scoring(
            data_quality_service=object(), classification_service=SimpleNamespace(),
        )
        for context in fixture.contexts:
            context["fund"].update({
                "total_asset": 80.0,
                "management_fee": 0.005, "custodian_fee": 0.001,
                "performance_data": {"tracking_difference": -0.003, "excess_return": 0.02},
                "risk_metrics": {"tracking_error": 0.004},
            })
        return fixture

    def test_legacy_only_peers_cannot_create_one_year_sample_or_proxy(self):
        fixture = self.fixture()
        for window in ("1y", "6m", "3y"):
            for path, result in fixture.both(window=window).items():
                with self.subTest(path=path, window=window):
                    self.assertEqual(result["valid_metric_peer_count"], 0)
                    self.assertEqual(result["sample_status"], "insufficient_peer_sample")
                    metric = result["metrics"]["professional_score"]
                    self.assertIsNone(metric["value"])
                    self.assertIsNone(metric["percentile"])

    def test_legacy_only_peers_remain_unscored_in_statistics(self):
        statistics = self.fixture().statistics()
        self.assertEqual(statistics["ranking"], [])
        self.assertEqual({item["wind_code"] for item in statistics["unscored"]}, set("abcde"))

    def test_legacy_facts_cannot_inflate_four_snapshot_peers_to_five(self):
        fixture = self.fixture(with_panels=True)
        fixture.panels["a"].clear()
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["valid_metric_peer_count"], 4)
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")
                metric = result["metrics"]["professional_score"]
                self.assertEqual(metric["peer_count"], 4)
                self.assertIsNone(metric["value"])
                self.assertIsNone(metric["rank"])

    def test_windowed_panels_with_latest_fee_facts_still_rank(self):
        fixture = self.fixture(with_panels=True)
        expected = fixture.service.scoring_service.score_peer_metrics("index_fund", {
            "tracking_error": 0.005, "tracking_difference": 0.0, "expense_ratio": 0.006, "aum": 80.0,
        })
        before = deepcopy(fixture.contexts)
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["valid_metric_peer_count"], 5)
                self.assertEqual(result["sample_status"], "sufficient")
                metric = result["metrics"]["professional_score"]
                self.assertEqual(metric["value"], expected)
                self.assertEqual((metric["rank"], metric["percentile"]), (1, 50.0))
        self.assertEqual(fixture.contexts, before)


class PeerBenchmarkSelectionTests(unittest.TestCase):
    def fixture(self):
        fixture = PeerBuildFixture({code: {"latest": {"expense_ratio": 0.006, "aum": 45.0}}
                                    for code in "abcde"},
                                   methodology=FundEvaluationMethodology(), profile_key="index_fund")
        for index, context in enumerate(fixture.contexts):
            code = context["fund"]["wind_code"]
            expected = "000300.SH" if index % 2 == 0 else "000905.SH"
            context["fund"]["benchmark_code"] = expected
            context["classification"]["benchmark_code"] = expected
            fixture.scorings[code]["classification"]["benchmark_code"] = expected
            for benchmark in (expected, "OTHER"):
                fixture.panels[code].extend([
                    {"metric_window": "1y", "metric_name": name, "metric_value": value,
                     "benchmark_code": benchmark, "as_of_date": "2026-09-30"}
                    for name, value in (
                        ("tracking_error", 0.006 + index * 0.001 if benchmark == expected else 0.09),
                        ("tracking_difference", -0.004 if benchmark == expected else -0.07),
                    )
                ])
        return fixture

    def test_three_paths_use_each_funds_own_benchmark_and_ignore_panel_order(self):
        fixture = self.fixture()
        before = deepcopy(fixture.contexts)
        for reverse in (False, True):
            if reverse:
                for rows in fixture.panels.values():
                    rows.reverse()
            batch = fixture.batch()
            for index, code in enumerate("abcde"):
                with self.subTest(reverse=reverse, code=code):
                    single = fixture.single(code)
                    statistics = fixture.statistics(code)
                    expected = fixture.service.scoring_service.score_peer_metrics("index_fund", {
                        "tracking_error": 0.006 + index * 0.001, "tracking_difference": -0.004,
                        "expense_ratio": 0.006, "aum": 45.0,
                    })
                    self.assertEqual(batch[code]["metrics"]["professional_score"]["value"], expected)
                    self.assertEqual(single["metrics"], batch[code]["metrics"])
                    self.assertEqual(statistics["current"]["score"], expected)
                    self.assertEqual(statistics["current"]["rank"], index + 1)
        for rows in fixture.panels.values():
            rows.reverse()
        self.assertEqual(fixture.contexts, before)

    def test_batch_uses_preloaded_classification_instead_of_stale_fund_code(self):
        fixture = self.fixture()
        for context in fixture.contexts:
            context["fund"]["benchmark_code"] = "OTHER"
        result = fixture.batch()["a"]
        self.assertEqual(result["metrics"]["tracking_error"]["value"], 0.006)
        fixture.metric_repo.get_latest_panels.assert_not_called()
        fixture.service._classification_adapter.list_peer_funds.assert_not_called()

    def test_target_classification_is_retained_when_target_already_in_peer_rows(self):
        fixture = self.fixture()
        fixture.contexts[0]["fund"]["benchmark_code"] = "OTHER"
        target, peers, _ = fixture.service._peer_universe("a", fixture.contexts[0])
        target_row = next(fund for fund in peers if fund["wind_code"] == "a")
        self.assertEqual(target_row.get("classification"), target["classification"])
        self.assertEqual(fixture.single()["metrics"]["tracking_error"]["value"], 0.006)
        self.assertEqual(fixture.statistics()["current"]["score"], fixture.batch()["a"]["metrics"]["professional_score"]["value"])

    def test_missing_current_benchmark_does_not_inflate_sample(self):
        fixture = self.fixture()
        fixture.panels["a"][:] = [row for row in fixture.panels["a"] if row.get("benchmark_code") != "000300.SH"]
        for path, result in fixture.both().items():
            with self.subTest(path=path):
                self.assertEqual(result["valid_metric_peer_count"], 4)
                self.assertIsNone(result["metrics"]["tracking_error"]["value"])
                self.assertIsNone(result["metrics"]["professional_score"]["value"])
                self.assertEqual(result["sample_status"], "insufficient_peer_sample")

    def test_unknown_multiple_benchmarks_stay_unscored_across_paths(self):
        fixture = self.fixture()
        for context in fixture.contexts:
            code = context["fund"]["wind_code"]
            context["fund"].pop("benchmark_code")
            context["classification"].pop("benchmark_code")
            fixture.scorings[code]["classification"].pop("benchmark_code")
        for result in fixture.both().values():
            self.assertEqual(result["valid_metric_peer_count"], 0)
            self.assertIsNone(result["metrics"]["professional_score"]["value"])
        self.assertEqual(fixture.statistics()["scored_peer_count"], 0)

    def test_absolute_values_use_date_not_peer_group_alphabetical_order(self):
        fixture = self.fixture()
        rows = [{"metric_window": "1y", "metric_name": "annualized_return", "metric_value": value,
                 "peer_group_key": group, "as_of_date": day}
                for value, group, day in ((0.07, "a-current", "2026-09-30"), (0.9, "z-old", "2026-09-01"))]
        self.assertEqual(fixture.service._metrics_by_window(rows)["1y"]["annualized_return"], 0.07)

    def test_peer_query_includes_effective_entity_benchmark_without_extra_queries(self):
        path = SERVICE_PATH.parents[1] / "repositories/fund_classification_repo.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FundClassificationRepo")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "list_peer_funds")
        namespace = {"__name__": "offline_peer_query", "active_fund_sql": lambda alias: "TRUE",
                     "_row_to_dict": lambda row: dict(row._mapping)}
        module = ast.Module(body=ast.parse("from __future__ import annotations").body + [method], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
        queries = []
        class Connection:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, sql, parameters):
                queries.append((str(sql), parameters))
                return SimpleNamespace(fetchall=lambda: [])
        repo = SimpleNamespace(_schema_ready=lambda: True, engine=SimpleNamespace(connect=Connection))
        namespace["list_peer_funds"](repo, "test-group", "a")
        self.assertEqual(len(queries), 1)
        sql, parameters = queries[0]
        self.assertIn("benchmark.benchmark_code", sql)
        self.assertIn("bm.entity_id = fe.id", sql)
        self.assertIn("bm.status = 'active'", sql)
        self.assertIn("bm.effective_from <= CURRENT_DATE", sql)
        self.assertIn("bm.effective_to >= CURRENT_DATE", sql)
        self.assertIn("(bm.peer_group_id = pg.id) DESC NULLS LAST", sql)
        self.assertLess(sql.index("bm.updated_at DESC"), sql.index("bm.effective_from DESC"))
        self.assertEqual(parameters["target_wind_code"], "a")


class RecommendationBenchmarkQueryTests(unittest.TestCase):
    def test_recommendation_rows_use_current_entity_mapping_not_group_default(self):
        path = SERVICE_PATH.parents[1] / "repositories/fund_classification_repo.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FundClassificationRepo")
        namespace = {"__name__": "offline_recommendation_query", "active_fund_sql": lambda alias: "TRUE",
                     "_row_to_dict": lambda row: dict(row._mapping), "date": date}
        constants = [node for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id.startswith("FOF_LOOKTHROUGH_")
                             for target in node.targets)]
        module = ast.Module(body=ast.parse("from __future__ import annotations").body + constants + [cls], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
        queries = []
        class Connection:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, sql, parameters):
                queries.append((str(sql), parameters))
                return SimpleNamespace(fetchall=lambda: [])
        repo = namespace["FundClassificationRepo"](engine=SimpleNamespace(connect=Connection))
        repo._schema_ready = lambda: True
        repo.list_recommendation_funds("test-group")
        self.assertEqual(len(queries), 1)
        sql = queries[0][0]
        self.assertIn("benchmark.benchmark_code", sql)
        self.assertIn("benchmark.benchmark_name", sql)
        self.assertNotIn("pg.benchmark_code", sql)
        self.assertNotIn("pg.benchmark_name", sql)
        self.assertIn("bm.entity_id = fe.id", sql)
        self.assertIn("bm.status = 'active'", sql)
        self.assertIn("bm.effective_from <= CURRENT_DATE", sql)
        self.assertIn("bm.effective_to >= CURRENT_DATE", sql)
        self.assertIn("(bm.peer_group_id = pg.id) DESC NULLS LAST", sql)
        self.assertLess(sql.index("bm.updated_at DESC"), sql.index("bm.effective_from DESC"))


class MoneyBenchmarkPeerTests(unittest.TestCase):
    def fixture(self, benchmark_code):
        scoring = run_path(str(Path(__file__).with_name("fund_evaluation_numeric_offline_test.py")))
        fixture = PeerBuildFixture({code: {"1y": scoring["MONEY"]["1y"], "latest": {"aum": 120.0}}
                                    for code in "abcde"},
                                   methodology=FundEvaluationMethodology(), profile_key="money_market")
        fixture.service.scoring_service = scoring["Scoring"](
            data_quality_service=object(), classification_service=SimpleNamespace(),
        )
        for context in fixture.contexts:
            code = context["fund"]["wind_code"]
            fixture.panels[code].extend(scoring["save_money_benchmark_fixture"](benchmark_code))
            context["fund"].update({
                "benchmark_code": "DR007",
                "performance_data": {"benchmark_annualized_rate": 0.025, "benchmark_yield_spread": -0.006},
            })
            context["classification"]["benchmark_code"] = "DR007"
            fixture.scorings[code]["classification"]["benchmark_code"] = "DR007"
        return fixture

    def test_missing_current_rate_does_not_rank_stale_json_spread(self):
        for benchmark_code in (None, "OLD"):
            fixture = self.fixture(benchmark_code)
            for path, result in fixture.both().items():
                with self.subTest(benchmark=benchmark_code, path=path):
                    metric = result["metrics"]["benchmark_yield_spread"]
                    self.assertIsNone(metric["value"])
                    self.assertIsNone(metric["percentile"])
                    self.assertEqual(metric["peer_count"], 0)
                    self.assertEqual(result["sample_status"], "sufficient")

    def test_writer_generated_current_spread_remains_ranked(self):
        fixture = self.fixture("DR007")
        for result in fixture.both().values():
            metric = result["metrics"]["benchmark_yield_spread"]
            self.assertEqual(metric["value"], 0.004)
            self.assertEqual(metric["peer_count"], 5)
            self.assertEqual(metric["percentile"], 50.0)


class MatrixRowBestCodeTests(unittest.TestCase):
    """A1：对比矩阵 best_code 不得混百分位与原始值尺度，且须尊重指标方向。"""

    def setUp(self):
        self.service = PeerComparisonService(
            scoring_service=SimpleNamespace(), classification_service=SimpleNamespace()
        )

    def _best(self, config, funds):
        return self.service._matrix_row(config, funds, "1y")["best_code"]

    def test_lower_is_better_raw_fallback_picks_minimum(self):
        config = {"metric_name": "volatility", "label": "波动", "unit": "percent", "higher_is_better": False}
        funds = [
            {"wind_code": "A", "metrics": {"volatility": 0.20}, "peer_percentiles": {}},
            {"wind_code": "B", "metrics": {"volatility": 0.10}, "peer_percentiles": {}},
        ]
        self.assertEqual(self._best(config, funds), "B")

    def test_percentile_and_raw_are_not_mixed_in_one_ranking(self):
        config = {"metric_name": "sharpe", "label": "夏普", "unit": "number", "higher_is_better": True}
        funds = [
            {"wind_code": "A", "metrics": {}, "peer_percentiles": {"sharpe": {"percentile": 30}}},
            {"wind_code": "B", "metrics": {}, "peer_percentiles": {"sharpe": {"percentile": 80}}},
            {"wind_code": "C", "metrics": {"sharpe": 99.0}, "peer_percentiles": {}},
        ]
        self.assertEqual(self._best(config, funds), "B")

    def test_higher_is_better_raw_fallback_picks_maximum(self):
        config = {"metric_name": "sharpe", "label": "夏普", "unit": "number", "higher_is_better": True}
        funds = [
            {"wind_code": "A", "metrics": {"sharpe": 0.5}, "peer_percentiles": {}},
            {"wind_code": "B", "metrics": {"sharpe": 1.2}, "peer_percentiles": {}},
        ]
        self.assertEqual(self._best(config, funds), "B")

    def test_no_evidence_yields_no_best_code(self):
        config = {"metric_name": "sharpe", "label": "夏普", "unit": "number", "higher_is_better": True}
        self.assertIsNone(self._best(config, [{"wind_code": "A", "metrics": {}, "peer_percentiles": {}}]))

    def test_best_code_is_order_independent_on_percentile_ties(self):
        config = {"metric_name": "sharpe", "label": "夏普", "unit": "number", "higher_is_better": True}
        tied = [
            {"wind_code": "A", "metrics": {}, "peer_percentiles": {"sharpe": {"percentile": 80}}},
            {"wind_code": "B", "metrics": {}, "peer_percentiles": {"sharpe": {"percentile": 80}}},
        ]
        self.assertEqual(self._best(config, tied), self._best(config, list(reversed(tied))))

    def test_best_code_is_order_independent_on_raw_ties(self):
        config = {"metric_name": "max_drawdown", "label": "回撤", "unit": "percent", "higher_is_better": False}
        tied = [
            {"wind_code": "A", "metrics": {"max_drawdown": -0.10}, "peer_percentiles": {}},
            {"wind_code": "B", "metrics": {"max_drawdown": -0.10}, "peer_percentiles": {}},
        ]
        self.assertEqual(self._best(config, tied), self._best(config, list(reversed(tied))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
