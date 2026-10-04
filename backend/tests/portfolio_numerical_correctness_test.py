import ast
from datetime import date, datetime, timedelta
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine


SOURCE = Path(__file__).resolve().parents[1] / "services" / "portfolio_service.py"
tree = ast.parse(SOURCE.read_text())
nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.Assign))]
namespace = {"math": math, "date": date, "datetime": datetime}
module = ast.Module(body=[
    ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
    *nodes,
], type_ignores=[])
exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
PortfolioService = namespace["PortfolioService"]


class MemoryRepo:
    def __init__(self, holdings):
        self.holdings = holdings
        self.writes = []

    def get_portfolio(self, portfolio_id):
        return {"id": portfolio_id, "name": "Offline portfolio"}

    def list_holdings(self, portfolio_id):
        return self.holdings

    def list_targets(self, portfolio_id):
        return []

    def set_weights(self, portfolio_id, items, source):
        self.writes.append(items)
        for item in items:
            next(row for row in self.holdings if row["wind_code"] == item["wind_code"])["weight"] = item["weight"]


class MemoryEngine:
    def __init__(self, rows):
        self.rows = rows
        self.result = []

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        rows = self.rows[params["code"]][-params["limit"]:]
        if "COALESCE" in str(sql):
            self.result = [(day, next((value for value in values if value not in (None, 0)), None)) for day, *values in reversed(rows)]
        else:
            self.result = list(reversed(rows))
        return self

    def fetchall(self):
        return self.result


def make_service(holdings):
    service = PortfolioService(repo=MemoryRepo(holdings), similarity_service=object(), style_repo=object())
    service._with_evaluation_summary = lambda row: row
    service._load_benchmark_series = lambda *args: {}
    service._load_benchmark_metadata = lambda code: {"code": "INDEX", "name": "Same asset"}
    return service


class PortfolioWeightsTest(unittest.TestCase):
    def test_rejects_duplicate_codes_without_writing(self):
        service = make_service([{"wind_code": code, "weight": .25} for code in "ABCD"])
        with self.assertRaisesRegex(ValueError, "重复"):
            service.set_weights("p", [{"wind_code": "A", "weight": .4}, {"wind_code": "A", "weight": .3}, {"wind_code": "B", "weight": .3}])
        self.assertEqual(service.repo.writes, [])

    def test_rejects_omitted_holdings_without_writing(self):
        service = make_service([{"wind_code": code, "weight": .25} for code in "ABCD"])
        with self.assertRaisesRegex(ValueError, "全部持仓"):
            service.set_weights("p", [{"wind_code": code, "weight": weight} for code, weight in zip("ABC", [.4, .3, .3])])
        self.assertEqual(service.repo.writes, [])

    def test_accepted_rounding_is_normalized_to_one(self):
        service = make_service([{"wind_code": code, "weight": None} for code in "ABCD"])
        result = service.set_weights("p", [{"wind_code": code, "weight": .249} for code in "ABCD"])
        self.assertAlmostEqual(sum(row["weight"] for row in result["holdings"]), 1)

    def test_normalization_cannot_raise_a_weight_above_cap(self):
        service = make_service([{"wind_code": code, "weight": None} for code in "ABC"])
        with self.assertRaisesRegex(ValueError, "40%"):
            service.set_weights("p", [{"wind_code": code, "weight": weight} for code, weight in zip("ABC", [.4, .3, .296])])
        self.assertEqual(service.repo.writes, [])

    def test_partial_total_uses_disclosed_equal_basis(self):
        holdings = [{"wind_code": code, "weight": weight} for code, weight in zip("ABC", [.4, .3, .26])]
        self.assertFalse(PortfolioService._weight_summary(holdings)["is_complete"])
        self.assertEqual(PortfolioService._effective_weights(holdings), {code: 1 / 3 for code in "ABC"})

    def test_partial_holdings_are_not_complete_even_if_total_is_one(self):
        holdings = [{"wind_code": code, "weight": weight} for code, weight in zip("ABCD", [.4, .3, .3, None])]
        self.assertFalse(PortfolioService._weight_summary(holdings)["is_complete"])
        self.assertEqual(PortfolioService._effective_weights(holdings), {code: .25 for code in "ABCD"})

    def test_implicit_equal_does_not_bypass_single_fund_limit(self):
        with self.assertRaisesRegex(ValueError, "40%"):
            PortfolioService._effective_weights([{"wind_code": "A"}, {"wind_code": "B"}])

    def test_nonfinite_or_overweight_legacy_values_are_not_complete(self):
        for weights in ([float("nan"), .3, .3], [.6, .2, .2]):
            with self.subTest(weights=weights):
                holdings = [{"wind_code": code, "weight": weight} for code, weight in zip("ABC", weights)]
                summary = PortfolioService._weight_summary(holdings)
                self.assertFalse(summary["is_complete"])
                self.assertTrue(math.isfinite(summary["total_weight"]))
                self.assertEqual(PortfolioService._effective_weights(holdings), {code: 1 / 3 for code in "ABC"})

    def test_valid_custom_weights_are_preserved(self):
        holdings = [{"wind_code": code, "weight": weight} for code, weight in zip("ABC", [.4, .35, .25])]
        self.assertTrue(PortfolioService._weight_summary(holdings)["is_complete"])
        self.assertEqual(PortfolioService._effective_weights(holdings), {row["wind_code"]: row["weight"] for row in holdings})


class PortfolioReturnsTest(unittest.TestCase):
    def setUp(self):
        self.days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(72)]
        self.rows = {code: [(day, 1.0 if i == 0 else 1.1, .5, .5) for i, day in enumerate(self.days)] for code in "ABC"}
        self.service = make_service([{"wind_code": code, "weight": 1 / 3} for code in "ABC"])
        namespace["get_engine"] = lambda: MemoryEngine(self.rows)

    def test_first_loss_counts_in_maximum_drawdown(self):
        metrics = PortfolioService._performance_metrics([-.1] + [0] * 60, self.days[:62])
        self.assertAlmostEqual(metrics["max_drawdown"], -.1)

    def test_drawdown_recovers_and_restarts_from_new_peak(self):
        metrics = PortfolioService._performance_metrics([-.1, 1 / 9, .2, -.25], self.days[:5])
        self.assertAlmostEqual(metrics["max_drawdown"], -.25)

    def test_loader_returns_nav_and_never_switches_scale_on_missing_day(self):
        self.rows["A"][1] = (self.days[1], None, .5, .5)
        values = self.service._load_nav_series(["A"], 365)["A"]
        self.assertNotIn(self.days[1], values)
        self.assertEqual(values[self.days[0]], 1.0)
        self.assertEqual(values[self.days[2]], 1.1)

    def test_loader_uses_single_fallback_column(self):
        for unit_available in (True, False):
            with self.subTest(unit_available=unit_available):
                self.rows["A"] = [
                    (self.days[0], None, 1.0 if unit_available else None, 100.0),
                    (self.days[1], None, 1.1 if unit_available else None, 200.0),
                ]
                expected = [1.0, 1.1] if unit_available else [100.0, 200.0]
                self.assertEqual(list(self.service._load_nav_series(["A"], 365)["A"].values()), expected)

    def test_all_funds_same_nav_have_same_cumulative_return(self):
        result = self.service.backtest("p")
        self.assertAlmostEqual(result["metrics"]["cumulative_return"], .1)
        self.assertEqual(result["curve"][0], {"date": self.days[0], "value": 1.0})

    def test_missing_nav_day_aligns_endpoints_before_returns(self):
        self.rows["B"].pop(1)
        self.service._load_benchmark_series = lambda *args: {day: 1.0 if i == 0 else 1.1 for i, day in enumerate(self.days)}
        result = self.service.backtest("p")
        self.assertAlmostEqual(result["metrics"]["cumulative_return"], .1)
        self.assertAlmostEqual(result["benchmark"]["excess_return"], 0)
        self.assertEqual(result["benchmark"]["metrics"]["sample_days"], result["metrics"]["sample_days"])

    def test_benchmark_missing_common_endpoint_does_not_claim_excess_return(self):
        self.service._load_benchmark_series = lambda code, *args: {
            day: 1.1 for day in (self.days[1:] if code == "EXPLICIT" else self.days)
        }
        result = self.service.backtest("p", benchmark_wind_code="EXPLICIT")
        self.assertEqual(result["benchmark"]["status"], "insufficient")
        self.assertNotIn("excess_return", result["benchmark"])
        self.assertEqual(result["benchmark"]["source"], "EXPLICIT")

    def test_correlation_uses_same_endpoint_returns(self):
        for code in "ABC":
            value = 1.0
            rows = []
            for i, day in enumerate(self.days):
                value *= 1 + (.03 if i % 2 else -.01)
                rows.append((day, value, value, value))
            self.rows[code] = rows
        self.rows["B"].pop(20)
        result = self.service._correlation_matrix(["A", "B"], {"A": .5, "B": .5})
        self.assertAlmostEqual(result["pairs"][0]["correlation"], 1.0)
        self.assertEqual(result["pairs"][0]["overlap_days"], 70)

    def test_insufficient_common_intervals_are_rejected(self):
        self.rows = {code: rows[:60] for code, rows in self.rows.items()}
        self.assertEqual(self.service.backtest("p")["status"], "insufficient_sample")


class PortfolioMonitorTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        self.engine_patch = patch.dict(namespace, get_engine=lambda: self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        with self.engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE peer_groups (id TEXT, key TEXT, name TEXT)")
            conn.exec_driver_sql("CREATE TABLE fund_evaluation_snapshots (wind_code TEXT, peer_group_id TEXT, created_at TEXT)")
            conn.exec_driver_sql("CREATE TABLE holding_style_snapshots (wind_code TEXT, peer_group_key TEXT, quarter TEXT)")
            conn.exec_driver_sql("INSERT INTO peer_groups VALUES ('11111111-1111-1111-1111-111111111111', 'equity', '权益'), ('bond-id', 'bond', '债券')")
            conn.exec_driver_sql("INSERT INTO fund_evaluation_snapshots VALUES ('A', '11111111-1111-1111-1111-111111111111', '2026-09-30'), ('B', 'bond-id', '2026-09-30')")
            conn.exec_driver_sql("INSERT INTO holding_style_snapshots VALUES ('C', 'bond', '2026Q2')")
        self.service = make_service([{"wind_code": code, "weight": weight} for code, weight in zip("ABC", [.4, .3, .3])])
        self.targets = [{"peer_group_key": "equity", "target_weight": .4}, {"peer_group_key": "bond", "target_weight": .6}]
        self.service.repo.list_targets = lambda _: self.targets
        module = ModuleType("services.holding_style_drift_service")
        module.HoldingStyleDriftService = lambda: SimpleNamespace(get=lambda _: {"status": "unavailable"})
        modules = patch.dict(sys.modules, {"services.holding_style_drift_service": module})
        modules.start()
        self.addCleanup(modules.stop)

    def test_snapshot_ids_and_style_keys_match_target_keys_without_false_rebalance(self):
        result = self.service.monitor("p")
        self.assertFalse(result["rebalance_needed"])
        rows = {row["peer_group_key"]: row for row in result["target_deviations"]}
        self.assertEqual(set(rows), {"equity", "bond"})
        self.assertEqual(rows["equity"]["actual_weight"], .4)
        self.assertEqual(rows["bond"]["actual_weight"], .6)
        self.assertTrue(all(row["deviation"] == 0 for row in rows.values()))

    def test_uuid_targets_prefilled_by_monitor_resolve_to_canonical_keys(self):
        self.targets[0]["peer_group_key"] = "11111111-1111-1111-1111-111111111111"
        result = self.service.monitor("p")
        self.assertFalse(result["rebalance_needed"])
        self.assertEqual(result["target_deviations"][0]["peer_group_key"], "equity")

    def test_latest_unresolved_snapshot_falls_back_to_style_key_not_older_group(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO fund_evaluation_snapshots VALUES ('B', 'deleted-group', '2026-10-01')")
            conn.exec_driver_sql("INSERT INTO holding_style_snapshots VALUES ('B', 'equity', '2026Q3')")
        self.assertEqual(self.service._holding_peer_group("B"), "equity")

    def test_latest_null_classification_falls_back_to_style_without_reviving_old_group(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO fund_evaluation_snapshots VALUES ('B', NULL, '2026-10-01')")
            conn.exec_driver_sql("INSERT INTO holding_style_snapshots VALUES ('B', 'equity', '2026Q3')")
        self.targets[0]["target_weight"] = .7
        self.targets[1]["target_weight"] = .3
        result = self.service.monitor("p")
        self.assertFalse(result["rebalance_needed"])
        self.assertEqual([row["actual_weight"] for row in result["target_deviations"]], [.7, .3])

    def test_latest_null_style_group_does_not_revive_older_style_group(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO holding_style_snapshots VALUES ('C', NULL, '2026Q3')")
        self.assertEqual(self.service._holding_peer_group("C"), "unclassified")

    def test_missing_groups_stay_unclassified_and_no_targets_do_not_trigger_rebalance(self):
        self.assertEqual(self.service._holding_peer_group("missing"), "unclassified")
        self.targets.clear()
        result = self.service.monitor("p")
        self.assertFalse(result["rebalance_needed"])
        self.assertEqual({row["peer_group_key"] for row in result["target_deviations"]}, {"equity", "bond"})
        self.assertTrue(all(row["target_weight"] is None and row["deviation"] is None for row in result["target_deviations"]))

    def test_real_deviation_remains_visible(self):
        self.targets[0]["target_weight"] = .6
        self.targets[1]["target_weight"] = .4
        result = self.service.monitor("p")
        self.assertTrue(result["rebalance_needed"])
        self.assertEqual([row["deviation"] for row in result["target_deviations"]], [-.2, .2])

    def test_target_aliases_for_same_group_are_aggregated_before_deviation(self):
        self.targets[0]["target_weight"] = .2
        self.targets.append({"peer_group_key": "11111111-1111-1111-1111-111111111111", "target_weight": .2})
        result = self.service.monitor("p")
        self.assertFalse(result["rebalance_needed"])
        self.assertEqual(len(result["target_deviations"]), 2)
        self.assertEqual(result["target_deviations"][0]["target_weight"], .4)

    def test_group_key_lookup_prefers_key_and_never_casts_user_input_to_uuid(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO peer_groups VALUES ('other-id', '11111111-1111-1111-1111-111111111111', '字面key')")
        self.assertEqual(self.service._peer_group_key("11111111-1111-1111-1111-111111111111"), "11111111-1111-1111-1111-111111111111")
        self.assertIsNone(self.service._peer_group_key("not-a-uuid"))

    def test_evaluation_foreign_id_is_not_reinterpreted_as_another_groups_key(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO peer_groups VALUES ('other-id', '11111111-1111-1111-1111-111111111111', '字面key')")
        self.assertEqual(self.service._holding_peer_group("A"), "equity")


class PortfolioStyleCoverageTest(unittest.TestCase):
    def setUp(self):
        self.weights = {"A": .4, "B": .3, "C": .3}
        self.snapshots = {
            "A": {"descriptors": [
                {"factor": "BETA", "label": "Beta", "unit": "multiple", "exposure": 2., "fund_nav_coverage": .5},
                {"factor": "MOMENTUM", "label": "Momentum", "unit": "ratio", "exposure": -.2, "fund_nav_coverage": .25},
            ]},
            "B": {"descriptors": [
                {"factor": "BETA", "label": "Beta", "unit": "multiple", "exposure": 1., "fund_nav_coverage": .2},
            ]},
            "C": {"descriptors": []},
        }
        self.service = make_service([])
        self.service.style_repo = SimpleNamespace(get_latest_map=lambda _: self.snapshots)

    def aggregate(self):
        return self.service._style_aggregate(list(self.weights), self.weights)

    def test_factor_contributions_use_fund_nav_coverage_not_full_fund_weight(self):
        result = self.aggregate()
        factors = {row["factor"]: row for row in result["factors"]}
        self.assertAlmostEqual(factors["BETA"]["weighted_exposure"], .46)
        self.assertAlmostEqual(factors["BETA"]["covered_exposure"], .46 / .26, places=6)
        self.assertAlmostEqual(factors["MOMENTUM"]["weighted_exposure"], -.02)
        self.assertAlmostEqual(factors["MOMENTUM"]["covered_exposure"], -.2)

    def test_each_factor_discloses_own_coverage_and_unknown_weight(self):
        result = self.aggregate()
        factors = {row["factor"]: row for row in result["factors"]}
        self.assertEqual(result["snapshot_coverage"], 1.)
        self.assertEqual(factors["BETA"]["coverage"], .26)
        self.assertEqual(factors["BETA"]["unknown_weight"], .74)
        self.assertEqual(factors["MOMENTUM"]["coverage"], .1)
        self.assertEqual(factors["MOMENTUM"]["unknown_weight"], .9)
        self.assertNotIn("coverage", result)
        self.assertIn("不等于", result["coverage_note"])

    def test_missing_or_invalid_nav_coverage_cannot_be_assumed_from_descriptor_coverage(self):
        for coverage in (None, 0, -1., 1.1, float("nan"), float("inf"), True):
            with self.subTest(coverage=coverage):
                self.snapshots = {"A": {"holdings_disclosed_weight": .8, "descriptors": [
                    {"factor": "BETA", "exposure": 2., "descriptor_coverage": 1., "fund_nav_coverage": coverage},
                ]}}
                result = self.aggregate()
                self.assertEqual(result["status"], "insufficient")
                self.assertEqual(result["factors"], [])
                self.assertIn("reason", result)

    def test_nonfinite_exposure_does_not_claim_factor_coverage(self):
        for exposure in (None, float("nan"), float("inf"), True):
            with self.subTest(exposure=exposure):
                self.snapshots = {"A": {"descriptors": [
                    {"factor": "BETA", "exposure": exposure, "fund_nav_coverage": .5},
                ]}}
                result = self.aggregate()
                self.assertEqual(result["factors"], [])
                self.assertEqual(result["status"], "insufficient")

    def test_zero_exposure_is_known_evidence_not_missing(self):
        self.snapshots = {"A": {"descriptors": [
            {"factor": "BETA", "exposure": 0., "fund_nav_coverage": .5},
        ]}}
        result = self.aggregate()
        factor = result["factors"][0]
        self.assertEqual(factor["weighted_exposure"], 0.)
        self.assertEqual(factor["covered_exposure"], 0.)
        self.assertEqual(factor["coverage"], .2)
        self.assertEqual(factor["unknown_weight"], .8)

    def test_full_coverage_preserves_weighted_average(self):
        self.snapshots = {code: {"descriptors": [{"factor": "BETA", "exposure": exposure, "fund_nav_coverage": 1.}]}
                          for code, exposure in zip("ABC", [2., 1., 0.])}
        factor = self.aggregate()["factors"][0]
        self.assertEqual(factor["weighted_exposure"], 1.1)
        self.assertEqual(factor["covered_exposure"], 1.1)
        self.assertEqual(factor["coverage"], 1.)
        self.assertEqual(factor["unknown_weight"], 0.)

    def test_no_snapshots_remains_insufficient(self):
        self.snapshots = {}
        result = self.aggregate()
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["snapshot_coverage"], 0.)
        self.assertEqual(result["factors"], [])


class PortfolioFrequencyAndUnknownWeightTest(unittest.TestCase):
    """C1 年化按日历跨度而非假设日频；C3 零方差相关不冒充 0；C5 未知权重不伪造全额申购。"""

    def test_annualization_uses_calendar_span_for_monthly_nav(self):
        dates = [(date(2023, 1, 1) + timedelta(days=30 * i)).isoformat() for i in range(37)]
        per_interval = 1.2 ** (1 / 36) - 1
        metrics = PortfolioService._performance_metrics([per_interval] * 36, dates)
        span_years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
        expected_annualized = 1.2 ** (1 / span_years) - 1
        self.assertAlmostEqual(metrics["cumulative_return"], 0.2, places=4)
        self.assertAlmostEqual(metrics["annualized_return"], expected_annualized, places=4)
        self.assertLess(metrics["annualized_return"], 0.15)

    def test_volatility_scales_by_observed_frequency_not_252(self):
        dates = [(date(2023, 1, 1) + timedelta(days=30 * i)).isoformat() for i in range(25)]
        returns = [0.02, -0.01] * 12
        metrics = PortfolioService._performance_metrics(returns, dates)
        span_years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
        periods_per_year = len(returns) / span_years
        mean = sum(returns) / len(returns)
        variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
        self.assertAlmostEqual(metrics["annualized_volatility"], math.sqrt(variance) * math.sqrt(periods_per_year), places=5)
        self.assertLess(metrics["annualized_volatility"], math.sqrt(variance) * math.sqrt(252))

    def test_zero_variance_correlation_is_undefined_not_zero(self):
        self.assertIsNone(PortfolioService._pearson([0.0, 0.0, 0.0], [0.1, 0.2, 0.3]))
        self.assertIsNone(PortfolioService._pearson([0.1, 0.2, 0.3], [0.0, 0.0, 0.0]))

    def test_flat_nav_pair_is_not_reported_as_zero_correlation(self):
        days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(80)]
        rows = {
            "A": [(day, 1.0 + 0.01 * i, 1.0 + 0.01 * i, 1.0 + 0.01 * i) for i, day in enumerate(days)],
            "B": [(day, 1.0, 1.0, 1.0) for day in days],
        }
        service = make_service([{"wind_code": code, "weight": 0.5} for code in "AB"])
        namespace["get_engine"] = lambda: MemoryEngine(rows)
        pair = service._correlation_matrix(["A", "B"], {"A": 0.5, "B": 0.5})["pairs"][0]
        self.assertIsNone(pair["correlation"])
        self.assertNotEqual(pair["status"], "ok")

    def test_unknown_current_weight_does_not_fabricate_full_purchase(self):
        service = make_service([
            {"wind_code": "A", "weight": 0.4},
            {"wind_code": "B", "weight": 0.3},
            {"wind_code": "C", "weight": 0.3},
        ])
        service._latest_nav_map = lambda codes: {
            code: {"nav": 1.0, "name": f"Fund {code}", "nav_date": "2026-01-01"} for code in "ABC"
        }
        result = service.trade_list(
            "p",
            [{"wind_code": "A", "weight": None}, {"wind_code": "B", "weight": 0.3}, {"wind_code": "C", "weight": 0.3}],
            total_amount=10000,
        )
        rows = {row["wind_code"]: row for row in result["items"]}
        self.assertNotIn("B", rows)
        self.assertNotIn("C", rows)
        unknown = rows.get("A")
        self.assertTrue(unknown is None or unknown["amount"] is None)
        if unknown is not None:
            self.assertIsNone(unknown["current_weight"])
            self.assertNotEqual(unknown.get("action"), "申购")


if __name__ == "__main__":
    unittest.main()
