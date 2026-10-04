"""Offline round1 regressions: real calculations, isolated imports, in-memory I/O only."""
import ast
import hashlib
import importlib.util
import logging
import math
import socket
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd


BACKEND = Path(__file__).resolve().parents[1]
SERVICES = BACKEND / "services"


def load_file(name, filename):
    spec = importlib.util.spec_from_file_location(name, SERVICES / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# services.__init__ imports unrelated report/search services; never execute it.
package = ModuleType("services")
package.__path__ = [str(SERVICES)]
factory_module = load_file("services.metric_factory", "metric_factory.py")
ISOLATED_MODULES = {"services": package, "services.metric_factory": factory_module}
with patch.dict(sys.modules, ISOLATED_MODULES):
    rolling_module = load_file("services.rolling_metric_service", "rolling_metric_service.py")
ISOLATED_MODULES["services.rolling_metric_service"] = rolling_module
MetricFactory = factory_module.MetricFactory
RollingMetricService = rolling_module.RollingMetricService
FundNavEvidenceService = load_file(
    "services.fund_nav_evidence_service", "fund_nav_evidence_service.py"
).FundNavEvidenceService


def load_tushare_class():
    # Execute the unchanged real class and its pure helpers, not the SDK imports.
    path = SERVICES / "tushare_service.py"
    source = ast.parse(path.read_text(), filename=str(path))
    selected = {"TushareDataService", "_to_ts_code", "_as_float"}
    nodes = [node for node in source.body if getattr(node, "name", None) in selected]
    annotations = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    tree = ast.fix_missing_locations(ast.Module(body=[annotations, *nodes], type_ignores=[]))
    namespace = {
        "pd": pd, "math": math, "hashlib": hashlib,
        "datetime": datetime, "timedelta": timedelta,
        "logger": logging.getLogger("round1_offline"),
        "MetricFactory": MetricFactory, "FundNavEvidenceService": FundNavEvidenceService,
    }
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace["TushareDataService"]


TushareDataService = load_tushare_class()


def history(count=820):
    start = date(2022, 1, 3)
    return [
        {"date": start + timedelta(days=i), "accum_nav": 1.0 + i * 0.002 + (i % 5) * 0.001}
        for i in range(count)
    ]


def values(records):
    return {row["metric_name"]: float(row["metric_value"]) for row in records}


def tushare_service(frame):
    service = TushareDataService.__new__(TushareDataService)
    service.mock_mode = False
    service.strict_no_mock = True
    service._pro = SimpleNamespace(fund_nav=Mock(side_effect=lambda **kwargs: frame.copy(deep=True)))
    return service


class MetricTruthTests(unittest.TestCase):
    def setUp(self):
        self.modules = patch.dict(sys.modules, ISOLATED_MODULES)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.factory = MetricFactory()

    def save(self, rows, window=None, cutoff=None):
        repos = ModuleType("repositories")
        nav_repo = SimpleNamespace(get_nav_series=Mock(return_value=rows))
        metric_repo = SimpleNamespace(upsert_metrics=Mock(side_effect=lambda records: records))
        repos.get_nav_repo = Mock(return_value=nav_repo)
        repos.get_metric_snapshot_repo = Mock(return_value=metric_repo)
        with patch.dict(sys.modules, {"repositories": repos}):
            result = self.factory.calculate_and_save_fund_metrics(
                "OFFLINE.TEST", as_of_date=cutoff, window=window, source_snapshot_id="fixture",
            )
        nav_repo.get_nav_series.assert_called_once_with(
            "OFFLINE.TEST", end_date=cutoff.isoformat() if cutoff else None,
        )
        metric_repo.upsert_metrics.assert_called_once()
        self.assertEqual(result["saved"], len(metric_repo.upsert_metrics.call_args.args[0]))
        for record in result["metrics"]:
            self.assertEqual(record["source_snapshot_id"], "fixture")
        return result

    def test_supported_saved_windows_match_rolling_values(self):
        rows = history()
        rolling = RollingMetricService(metric_factory=self.factory).calculate_for_nav_series(
            rows, "fund", "OFFLINE.TEST",
        )
        for window, count in {"3m": 63, "6m": 126, "1y": 252, "3y": 756}.items():
            with self.subTest(window=window):
                saved = self.save(rows, window=window)["metrics"]
                actual = values(saved)
                self.assertEqual(actual["observations"], count)
                self.assertAlmostEqual(actual["total_return"], rows[-1]["accum_nav"] / rows[-count]["accum_nav"] - 1)
                self.assertEqual(actual, values([row for row in rolling if row["window"] == window]))
                self.assertTrue(all(row["window"] == window for row in saved))

    def test_window_is_sliced_after_inclusive_as_of_filter_and_sort(self):
        rows = history()
        cutoff = rows[499]["date"]
        expected = self.factory.build_metric_records("fund", "OFFLINE.TEST", cutoff, rows[248:500])
        actual = self.save(list(reversed(rows)), window="1y", cutoff=cutoff)["metrics"]
        self.assertEqual(values(actual)["observations"], 252)
        self.assertEqual(values(actual), values(expected))
        self.assertTrue(all(row["as_of_date"] == cutoff for row in actual))

    def test_short_history_uses_rolling_minimum_not_relabelled_metrics(self):
        for window, count in {"3m": 63, "6m": 126, "1y": 252, "3y": 756}.items():
            minimum = int(count * 0.6)
            for size in (minimum - 1, minimum):
                with self.subTest(window=window, size=size):
                    rows = history(size)
                    actual = self.save(rows, window=window)
                    if size < minimum:
                        self.assertEqual(actual["saved"], 0)
                    else:
                        self.assertEqual(values(actual["metrics"])["observations"], minimum)

    def test_unsupported_explicit_windows_reject_before_repository_access(self):
        for window in ("", "2y", "20d", "1Y", "since_inception"):
            with self.subTest(window=window):
                repos = ModuleType("repositories")
                repos.get_nav_repo = Mock(return_value=SimpleNamespace(get_nav_series=Mock(return_value=[])))
                repos.get_metric_snapshot_repo = Mock()
                with patch.dict(sys.modules, {"repositories": repos}):
                    with self.assertRaisesRegex(ValueError, "window"):
                        self.factory.calculate_and_save_fund_metrics("OFFLINE.TEST", window=window)
                repos.get_nav_repo.assert_not_called()
                repos.get_metric_snapshot_repo.assert_not_called()

    def test_invalid_window_is_a_client_error_at_route_boundary(self):
        from fastapi import HTTPException, Query
        from sqlalchemy.exc import SQLAlchemyError

        path = BACKEND / "routes" / "metrics.py"
        route = next(node for node in ast.parse(path.read_text()).body
                     if isinstance(node, ast.FunctionDef) and node.name == "recalculate_fund_metrics")
        route.decorator_list = []
        tree = ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), route,
        ], type_ignores=[])
        namespace = {"MetricFactory": MetricFactory, "Query": Query,
                     "HTTPException": HTTPException, "SQLAlchemyError": SQLAlchemyError}
        exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
        with self.assertRaises(Exception) as caught:
            namespace["recalculate_fund_metrics"]("OFFLINE.TEST", None, "2y", None)
        self.assertIsInstance(caught.exception, HTTPException)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("window", caught.exception.detail)

    def test_no_window_preserves_full_history_and_latest_date(self):
        rows = history()
        result = self.save(rows)
        self.assertEqual(values(result["metrics"])["observations"], len(rows))
        self.assertTrue(all(row["window"] is None for row in result["metrics"]))
        self.assertTrue(all(row["as_of_date"] == rows[-1]["date"] for row in result["metrics"]))

    def test_invalid_chosen_field_rows_do_not_fall_back_to_other_scales(self):
        for invalid in (None, 0, -1, float("nan"), float("inf"), "bad"):
            with self.subTest(invalid=invalid):
                rows = [
                    {"date": date(2026, 1, 1), "accum_nav": 100, "adj_nav": 10, "nav": 1},
                    {"date": date(2026, 1, 2), "accum_nav": invalid, "adj_nav": 10, "nav": 1},
                    {"date": date(2026, 1, 3), "accum_nav": 100, "adj_nav": 10, "nav": 1},
                ]
                risk = self.factory.calculate_risk_metrics(rows)
                self.assertEqual(risk["max_drawdown"], 0)
                self.assertEqual(risk["annualized_volatility"], 0)
                self.assertEqual(self.factory.calculate_return_metrics(rows)["observations"], 2)

    def test_single_field_fallback_uses_only_finite_positive_values(self):
        fields = ("accum_nav", "adj_nav", "nav", "unit_nav")
        for selected_index, selected in enumerate(fields):
            with self.subTest(selected=selected):
                rows = []
                for i in range(3):
                    row = {"date": date(2026, 1, i + 1)}
                    for j, field in enumerate(fields):
                        row[field] = float("inf") if j < selected_index else 10 ** (3 - j)
                    row[selected] = None if i == 1 else 10 ** (3 - selected_index)
                    rows.append(row)
                result = self.factory.calculate_return_metrics(rows)
                self.assertEqual(result.get("observations"), 2)
                self.assertEqual(result["total_return"], 0)

    def test_future_preferred_field_does_not_change_historical_field_choice(self):
        cutoff = date(2026, 1, 2)
        rows = [{"date": date(2026, 1, 1), "nav": 1}, {"date": cutoff, "nav": 1.1}]
        future = {"date": date(2026, 1, 3), "accum_nav": 100, "nav": 1.2}
        self.assertEqual(
            self.factory._normalize_nav_series(rows + [future], as_of_date=cutoff),
            self.factory._normalize_nav_series(rows, as_of_date=cutoff),
        )

    def test_equal_canonical_input_agrees_across_all_factory_paths(self):
        rows = history(80)
        for i, row in enumerate(rows):
            row["adj_nav"] = 10 + i * 0.01
            row["nav"] = 100 + i * 0.1
            if i in (20, 30, 40):
                row["accum_nav"] = None
        canonical = [{"date": row["date"], "nav": row["accum_nav"]} for row in rows if row["accum_nav"] is not None]
        cutoff = rows[-1]["date"]
        expected = {**self.factory.calculate_return_metrics(canonical), **self.factory.calculate_risk_metrics(canonical)}
        self.assertEqual(self.factory.calculate_return_metrics(rows), self.factory.calculate_return_metrics(canonical))
        self.assertEqual(self.factory.calculate_risk_metrics(rows), self.factory.calculate_risk_metrics(canonical))
        self.assertEqual(values(self.factory.build_metric_records("fund", "OFFLINE.TEST", cutoff, rows)), expected)
        self.assertEqual(values(self.save(rows)["metrics"]), expected)
        rolling = RollingMetricService().calculate_for_nav_series(rows, "fund", "OFFLINE.TEST")
        expected_window = self.factory.build_metric_records("fund", "OFFLINE.TEST", cutoff, canonical[-63:])
        self.assertEqual(values([row for row in rolling if row["window"] == "3m"]), values(expected_window))
        self.assertEqual(values(self.save(rows, window="3m")["metrics"]), values(expected_window))

    def test_benchmark_normalization_does_not_invent_active_risk(self):
        fund = [{"date": date(2026, 1, i + 1), "nav": 1} for i in range(3)]
        benchmark = [
            {"date": row["date"], "accum_nav": None if i == 1 else 100, "nav": 1}
            for i, row in enumerate(fund)
        ]
        result = self.factory.calculate_relative_metrics(fund, benchmark)
        self.assertEqual(result["tracking_error"], 0)
        self.assertEqual(result["excess_return"], 0)

    def test_ingested_canonical_accum_nav_preserves_valid_adjusted_selection(self):
        for factor_derived in (False, True):
            with self.subTest(factor_derived=factor_derived):
                frame = pd.DataFrame([
                    {"nav_date": row["date"].strftime("%Y%m%d"), "unit_nav": row["accum_nav"],
                     "accum_nav": row["accum_nav"] + 0.5, "adj_nav": row["accum_nav"] * 2}
                    for row in history(80)
                ])
                if factor_derived:
                    frame = frame.drop(columns=["adj_nav"])
                service = tushare_service(frame)
                service._pro.fund_adj = Mock(return_value=pd.DataFrame([
                    {"trade_date": day, "adj_factor": 2.0} for day in frame["nav_date"]
                ]))
                rows = service.get_fund_nav("OFFLINE.TEST", "2022-01-01", "2023-01-01")
                self.assertEqual(len(rows), len(frame))
                self.assertTrue(all(row["accum_nav"] == row["adj_nav"] == row["nav"] * 2 for row in rows))
                expected_source = "tushare.fund_adj.adj_factor" if factor_derived else "tushare.fund_nav.adj_nav"
                self.assertTrue(all(row["metric_nav_source"] == expected_source for row in rows))
                canonical = [{"date": row["date"], "nav": row["accum_nav"]} for row in rows]
                self.assertEqual(self.factory.calculate_risk_metrics(rows), self.factory.calculate_risk_metrics(canonical))
                self.assertEqual(values(self.save(rows, window="3m")["metrics"]), values(
                    self.factory.build_metric_records("fund", "OFFLINE.TEST", date(2023, 1, 1), canonical[-63:]),
                ))


class TushareRelativeTruthTests(unittest.TestCase):
    def test_no_aligned_benchmark_means_null_relative_metrics_not_zero(self):
        for count, flat in ((300, False), (300, True), (20, False)):
            with self.subTest(count=count, flat=flat):
                frame = pd.DataFrame([
                    {"nav_date": row["date"].strftime("%Y%m%d"), "accum_nav": 1.0 if flat else row["accum_nav"]}
                    for row in history(count)
                ])
                service = tushare_service(frame)
                result = service.get_fund_risk_metrics("OFFLINE.TEST")
                self.assertIn("tracking_error", result)
                self.assertIn("information_ratio", result)
                self.assertIsNone(result["tracking_error"])
                self.assertIsNone(result["information_ratio"])
                self.assertIn("annualized_volatility_1y", result)
                self.assertIn("max_drawdown_2y", result)
                service._pro.fund_nav.assert_called_once()

    def test_mock_and_empty_fallback_do_not_invent_relative_evidence(self):
        for mock_mode in (False, True):
            with self.subTest(mock_mode=mock_mode):
                service = tushare_service(pd.DataFrame())
                service.strict_no_mock = False
                service.mock_mode = mock_mode
                result = service.get_fund_risk_metrics("OFFLINE.TEST")
                self.assertIsNone(result["tracking_error"])
                self.assertIsNone(result["information_ratio"])
                self.assertIsNone(result["beta"])
                self.assertIsNone(result["alpha"])

    def test_alpha_beta_not_fabricated_without_aligned_benchmark(self):
        # 无基金真实基准对齐的 CAPM 输入时，alpha/beta 不得用硬编码市场假设或 1.0 默认值虚构。
        frame = pd.DataFrame([
            {"nav_date": row["date"].strftime("%Y%m%d"), "accum_nav": row["accum_nav"]}
            for row in history(300)
        ])
        service = tushare_service(frame)
        result = service.get_fund_risk_metrics("OFFLINE.TEST")
        self.assertIsNone(result["alpha"])
        self.assertIsNone(result["beta"])
        self.assertIn("alpha", result)
        self.assertIn("beta", result)


class TushareRiskWindowTests(unittest.TestCase):
    """近一年风险指标必须在一年窗口内独立计算，历史不足不得填 0。"""

    @staticmethod
    def _frame(values, end=None):
        end = end or datetime.now()
        n = len(values)
        return pd.DataFrame([
            {"nav_date": (end - timedelta(days=n - 1 - i)).strftime("%Y%m%d"), "accum_nav": float(v)}
            for i, v in enumerate(values)
        ])

    def test_max_drawdown_1y_uses_one_year_peak_not_two_year_peak(self):
        values = []
        for i in range(730):
            if i <= 100:
                values.append(80 + i * 0.2)            # 早期升至 100（一年窗口外的两年峰值）
            elif i < 365:
                values.append(100 - (i - 100) * 0.075)  # 跌至约 80
            elif i < 500:
                values.append(80 + (i - 365) * 0.11)    # 一年内升至约 95
            elif i < 600:
                values.append(95 - (i - 500) * 0.03)    # 一年内回撤至约 92
            else:
                values.append(92 + (i - 600) * 0.015)
        frame = self._frame(values)
        result = tushare_service(frame).get_fund_risk_metrics("OFFLINE.TEST")

        nav = frame.sort_values("nav_date")
        start_1y = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        nav_1y = nav[nav["nav_date"] >= start_1y]["accum_nav"]
        peak_1y = nav_1y.cummax()
        true_dd_1y = round(float(((nav_1y - peak_1y) / peak_1y).min()), 4)
        peak_2y = nav["accum_nav"].cummax()
        dd_2y = (nav["accum_nav"] - peak_2y) / peak_2y
        two_year_peak_dd = round(float(dd_2y[-252:].min()), 4)

        self.assertEqual(result["max_drawdown_1y"], true_dd_1y)
        self.assertLess(true_dd_1y, 0)
        self.assertNotAlmostEqual(result["max_drawdown_1y"], two_year_peak_dd, places=4)
        self.assertGreater(result["max_drawdown_1y"], two_year_peak_dd)
        self.assertEqual(result["max_drawdown_2y"], round(float(dd_2y.min()), 4))

    def test_insufficient_one_year_history_returns_none_not_zero(self):
        end = datetime.now() - timedelta(days=400)  # 全部数据早于一年窗口
        frame = self._frame([100 - i * 0.1 for i in range(200)], end=end)
        result = tushare_service(frame).get_fund_risk_metrics("OFFLINE.TEST")
        self.assertIsNone(result["max_drawdown_1y"])
        self.assertIsNone(result["annualized_volatility_1y"])
        self.assertIsNone(result["var_95"])
        self.assertIsNotNone(result["max_drawdown_2y"])
        self.assertIsNotNone(result["annualized_volatility_2y"])

    def test_volatility_and_var_use_one_year_window(self):
        values = [100 + (i % 7) * (2.0 if i < 365 else 0.2) for i in range(730)]
        frame = self._frame(values)
        result = tushare_service(frame).get_fund_risk_metrics("OFFLINE.TEST")
        nav = frame.sort_values("nav_date")
        start_1y = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        ret_1y = nav[nav["nav_date"] >= start_1y]["accum_nav"].pct_change(fill_method=None).dropna()
        self.assertEqual(result["annualized_volatility_1y"], round(float(ret_1y.std() * (252 ** 0.5)), 4))
        self.assertEqual(result["var_95"], round(float(ret_1y.quantile(0.05)), 4))
        ret_2y = nav["accum_nav"].pct_change(fill_method=None).dropna()
        self.assertEqual(result["annualized_volatility_2y"], round(float(ret_2y.std() * (252 ** 0.5)), 4))


class TusharePerformanceWindowTests(unittest.TestCase):
    """get_fund_performance 的近一年字段必须用一年窗口，历史不足不得填 0，calmar 保留符号。"""

    @staticmethod
    def _frame(values, end=None):
        end = end or datetime.now()
        n = len(values)
        return pd.DataFrame([
            {"nav_date": (end - timedelta(days=n - 1 - i)).strftime("%Y%m%d"),
             "adj_nav": float(v), "accum_nav": float(v)}
            for i, v in enumerate(values)
        ])

    def _one_year_slice(self, frame):
        start_1y = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        nav = frame.sort_values("nav_date")
        return nav[nav["nav_date"] >= start_1y]

    def test_win_rate_1y_uses_one_year_window_not_full_sample(self):
        values = [100.0]
        for i in range(1, 1095):
            values.append(values[-1] * (0.999 if i % 4 else 1.002) if i < 730
                          else values[-1] * (1.002 if i % 4 else 0.999))
        frame = self._frame(values)
        result = tushare_service(frame).get_fund_performance("OFFLINE.TEST")
        nav_1y = self._one_year_slice(frame)["adj_nav"]
        ret_1y = nav_1y.pct_change(fill_method=None).dropna()
        expected = round(float((ret_1y > 0).sum()) / len(ret_1y), 4)
        full = frame.sort_values("nav_date")["adj_nav"].pct_change(fill_method=None).dropna()
        full_win = round(float((full > 0).sum()) / len(full), 4)
        self.assertEqual(result["win_rate_1y"], expected)
        self.assertNotAlmostEqual(result["win_rate_1y"], full_win, places=4)

    def test_calmar_is_signed_and_uses_one_year_drawdown(self):
        values = []
        for i in range(730):
            if i <= 200:
                values.append(100 + i * (40 / 200))         # 升至 140（一年窗口外的峰值）
            elif i < 365:
                values.append(140 - (i - 200) * (20 / 165))  #  older year 回落至约 120
            else:
                values.append(120 - (i - 365) * (10 / 365))  # 近一年 120→110，负收益
        frame = self._frame(values)
        result = tushare_service(frame).get_fund_performance("OFFLINE.TEST")
        nav_1y = self._one_year_slice(frame)["adj_nav"]
        ret_1y = float(nav_1y.iloc[-1]) / float(nav_1y.iloc[0]) - 1
        peak_1y = nav_1y.cummax()
        max_dd_1y = float(((nav_1y - peak_1y) / peak_1y).min())
        expected_calmar = round(ret_1y / abs(max_dd_1y), 4)
        full = frame.sort_values("nav_date")["adj_nav"]
        max_dd_3y = float(((full - full.cummax()) / full.cummax()).min())
        buggy_abs_calmar = round(abs(ret_1y / max_dd_3y), 4)
        self.assertEqual(result["calmar_ratio"], expected_calmar)
        self.assertLess(result["calmar_ratio"], 0)
        self.assertNotAlmostEqual(result["calmar_ratio"], buggy_abs_calmar, places=4)

    def test_insufficient_one_year_history_returns_none_not_zero(self):
        end = datetime.now() - timedelta(days=400)
        frame = self._frame([100 + i * 0.05 for i in range(200)], end=end)
        result = tushare_service(frame).get_fund_performance("OFFLINE.TEST")
        self.assertIsNone(result["annualized_return_1y"])
        self.assertIsNone(result["win_rate_1y"])
        self.assertIsNone(result["calmar_ratio"])
        self.assertIsNotNone(result["annualized_return_3y"])
        self.assertIsNotNone(result["max_drawdown"])


if __name__ == "__main__":
    with (
        patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")),
        patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")),
    ):
        unittest.main(verbosity=2)
