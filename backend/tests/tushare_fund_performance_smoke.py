import math
import os
import sys
import unittest
from datetime import date, timedelta
from statistics import stdev
from unittest.mock import Mock

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tushare_service import TushareDataService


NAV_VALUES = [
    1.0000, 1.0200, 0.9900, 1.0150, 1.0050, 0.9800, 1.0100, 1.0300,
    1.0000, 0.9700, 1.0050, 1.0250, 0.9950, 1.0150, 1.0400, 1.0100,
    0.9850, 1.0200, 1.0350, 1.0050, 0.9750, 1.0150, 1.0300, 1.0500,
    1.0200, 1.0000, 1.0250, 1.0450, 1.0150, 1.0350,
]


class FakePro:
    def fund_nav(self, **kwargs):
        start = date.today() - timedelta(days=len(NAV_VALUES) - 1)
        return pd.DataFrame([
            {
                "ts_code": "000001.OF",
                "nav_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
                "unit_nav": value,
                "accum_nav": value,
                "adj_nav": value,
            }
            for offset, value in enumerate(NAV_VALUES)
        ])


def expected_sortino() -> float:
    daily_returns = [
        NAV_VALUES[index] / NAV_VALUES[index - 1] - 1
        for index in range(1, len(NAV_VALUES))
    ]
    annual_excess_return = (sum(daily_returns) / len(daily_returns)) * 252 - 0.02
    downside_shortfalls = [min(value - 0.02 / 252, 0.0) for value in daily_returns]
    second_moment = sum(value**2 for value in downside_shortfalls) / len(daily_returns)
    downside_deviation = math.sqrt(second_moment * 252)
    return annual_excess_return / downside_deviation


def main() -> int:
    service = TushareDataService.__new__(TushareDataService)
    service.mock_mode = False
    service.strict_no_mock = True
    service._pro = FakePro()

    performance = service.get_fund_performance("000001.OF")
    sortino = performance.get("sortino")
    sharpe = performance.get("sharpe_ratio")

    real_sortino = expected_sortino()
    if sortino is None or abs(sortino - real_sortino) > 1e-4:
        raise AssertionError(
            f"sortino must be derived from downside deviation, expected {real_sortino}, got {sortino}"
        )
    if abs(sortino - round(sharpe * 1.2, 4)) < 1e-9:
        raise AssertionError(f"sortino must not be fabricated as sharpe*1.2: {sortino}")

    print("OK Tushare fund performance derives sortino from downside deviation")
    return 0


class FramePro:
    def __init__(self, rows, factors=None):
        self.rows = rows
        self.factors = factors or []
        self.adj_calls = []

    def fund_nav(self, **kwargs):
        return pd.DataFrame(self.rows)

    def fund_adj(self, **kwargs):
        self.adj_calls.append(kwargs)
        return pd.DataFrame(self.factors)


def nav_rows(count=20):
    start = date.today() - timedelta(days=count - 1)
    return [
        {
            "nav_date": (start + timedelta(days=index)).strftime("%Y%m%d"),
            "unit_nav": 1.5 + index * 0.001,
            "accum_nav": 2.0 + index * 0.002,
            "adj_nav": 10.0 + index * 0.01,
        }
        for index in range(count)
    ]


def frame_service(rows, factors=None):
    service = TushareDataService.__new__(TushareDataService)
    service.mock_mode = False
    service.strict_no_mock = True
    service._pro = FramePro(rows, factors)
    service._mock_performance = Mock(side_effect=AssertionError("Unexpected mock performance"))
    return service


class ConsistentPerformanceNavTests(unittest.TestCase):
    def assert_performance(self, actual, rows, column):
        values = [float(row[column]) for row in rows]
        returns = [current / previous - 1 for previous, current in zip(values, values[1:])]
        mean_return = sum(returns) / len(returns)
        volatility = stdev(returns) * math.sqrt(252)
        downside = math.sqrt(sum(min(value - 0.02 / 252, 0) ** 2 for value in returns) / len(returns) * 252)
        total_return = values[-1] / values[0] - 1
        years = (date.today() - date.fromisoformat(rows[0]["nav_date"])).days / 365
        expected = {
            "annualized_return_1y": round(total_return, 4),
            "annualized_return_3y": round((1 + total_return) ** (1 / max(years, 0.1)) - 1, 4),
            "max_drawdown": 0.0,
            "sharpe_ratio": round(mean_return * 252 / volatility, 4) if volatility else 0,
            "volatility": round(volatility, 4),
            "sortino": round((mean_return * 252 - 0.02) / downside, 4) if downside else 0,
            "calmar_ratio": 0,
            "win_rate_1y": round(sum(value > 0 for value in returns) / len(returns), 4),
        }
        for key, value in expected.items():
            self.assertAlmostEqual(actual[key], value, places=4, msg=key)

    def test_adjusted_gaps_never_borrow_accumulated_nav(self):
        for gap in (0, 10, 19):
            with self.subTest(gap=gap):
                rows = nav_rows()
                rows[gap]["adj_nav"] = None
                service = frame_service(rows)
                actual = service.get_fund_performance("UNIT.TEST")
                self.assert_performance(actual, [row for index, row in enumerate(rows) if index != gap], "adj_nav")
                self.assertEqual(service._pro.adj_calls, [])

    def test_accumulated_gap_never_borrows_unit_nav(self):
        rows = nav_rows()
        for row in rows:
            row.pop("adj_nav")
        rows[10]["accum_nav"] = None
        service = frame_service(rows)
        actual = service.get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows[:10] + rows[11:], "accum_nav")
        self.assertEqual(len(service._pro.adj_calls), 1)

    def test_sparse_adjusted_column_falls_back_as_a_whole(self):
        rows = nav_rows()
        for row in rows[11:]:
            row["adj_nav"] = None
        actual = frame_service(rows).get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows, "accum_nav")

    def test_sixty_percent_adjusted_coverage_keeps_priority(self):
        rows = nav_rows()
        for row in rows[12:]:
            row["adj_nav"] = None
        actual = frame_service(rows).get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows[:12], "adj_nav")

    def test_sparse_accumulated_column_falls_back_as_a_whole(self):
        rows = nav_rows()
        for index, row in enumerate(rows):
            row.pop("adj_nav")
            if index >= 11:
                row["accum_nav"] = None
        actual = frame_service(rows).get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows, "unit_nav")

    def test_selected_column_must_itself_have_ten_usable_rows(self):
        rows = nav_rows(10)
        rows[5]["adj_nav"] = None
        actual = frame_service(rows).get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows, "accum_nav")

    def test_invalid_adjusted_value_is_not_an_observation(self):
        for invalid in (0, -1, "invalid", float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                rows = nav_rows()
                rows[10]["adj_nav"] = invalid
                actual = frame_service(rows).get_fund_performance("UNIT.TEST")
                self.assert_performance(actual, rows[:10] + rows[11:], "adj_nav")

    def test_invalid_values_do_not_satisfy_column_coverage(self):
        rows = nav_rows()
        for row in rows[5:]:
            row["adj_nav"] = 0
        actual = frame_service(rows).get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows, "accum_nav")

    def test_columns_cannot_pool_rows_to_satisfy_sample_gate(self):
        rows = nav_rows()
        for index, row in enumerate(rows):
            row["adj_nav"] = row["adj_nav"] if index < 6 else None
            row["accum_nav"] = row["accum_nav"] if 6 <= index < 13 else None
            row["unit_nav"] = row["unit_nav"] if index >= 13 else None
        service = frame_service(rows)
        with self.assertLogs("services.tushare_service", level="ERROR"):
            with self.assertRaisesRegex(RuntimeError, "consistent NAV column"):
                service.get_fund_performance("UNIT.TEST")
        service._mock_performance.assert_not_called()

    def test_partial_adjustment_factors_never_borrow_accumulated_nav(self):
        rows = nav_rows()
        for row in rows:
            row.pop("adj_nav")
        selected = [row for index, row in enumerate(rows) if index != 10]
        factors = [{"trade_date": row["nav_date"], "adj_factor": 3.0} for row in selected]
        actual = frame_service(rows, factors).get_fund_performance("UNIT.TEST")
        expected_rows = [{**row, "adj_nav": row["unit_nav"] * 3.0} for row in selected]
        self.assert_performance(actual, expected_rows, "adj_nav")

    def test_sparse_adjustment_factors_fall_back_as_a_whole(self):
        rows = nav_rows()
        for row in rows:
            row.pop("adj_nav")
        factors = [{"trade_date": row["nav_date"], "adj_factor": 3.0} for row in rows[:5]]
        actual = frame_service(rows, factors).get_fund_performance("UNIT.TEST")
        self.assert_performance(actual, rows, "accum_nav")

    def test_money_market_adjusted_gap_keeps_real_yield_evidence(self):
        rows = nav_rows()
        for index, row in enumerate(rows):
            row.update(unit_nav=1.0, accum_nav=None, adj_nav=13940.0 + index * 0.4)
        rows[10]["adj_nav"] = None
        actual = frame_service(rows).get_fund_performance("UNIT.TEST")
        self.assertEqual(actual["max_drawdown"], 0.0)
        expected_yield = ((13940.0 + 19 * 0.4) / (13940.0 + 12 * 0.4)) ** (365 / 7) - 1
        self.assertAlmostEqual(actual["seven_day_annualized_yield"], expected_yield, places=8)
        self.assertEqual(actual["seven_day_yield_source"], "derived:tushare.fund_nav.adj_nav")


if __name__ == "__main__":
    main()
    unittest.main()
