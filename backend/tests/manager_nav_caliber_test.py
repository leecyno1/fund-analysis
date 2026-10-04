import ast
from datetime import date
from pathlib import Path
import unittest


def load_service(filename, class_name):
    path = Path(__file__).resolve().parents[1] / "services" / filename
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and (node.module or "").startswith("services.")
    )]
    namespace = {}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace[class_name]


Career = load_service("fund_manager_career_service.py", "FundManagerCareerService")
Comparison = load_service("fund_manager_comparison_service.py", "FundManagerComparisonService")


class ManagerNavCaliberTest(unittest.TestCase):
    def check_points(self, rows, expected):
        with self.subTest(service="career"):
            self.assertEqual({item["date"]: item["nav"] for item in Career._normalize_rows(rows)}, expected)
        with self.subTest(service="comparison"):
            self.assertEqual(Comparison._points(rows), expected)

    def test_missing_accumulated_nav_does_not_use_unit_nav(self):
        self.check_points([
            {"date": "2026-01-01", "accum_nav": 2.0, "unit_nav": 1.0},
            {"date": "2026-01-02", "accum_nav": None, "unit_nav": 1.0},
            {"date": "2026-01-03", "accum_nav": 2.0, "unit_nav": 1.0},
        ], {date(2026, 1, 1): 2.0, date(2026, 1, 3): 2.0})

    def test_single_field_fallback_is_selected_for_the_whole_series(self):
        self.check_points([
            {"date": "2026-01-01", "accum_nav": None, "adj_nav": 2.0, "unit_nav": 1.0},
            {"date": "2026-01-02", "adj_nav": None, "unit_nav": 1.0},
            {"date": "2026-01-03", "adj_nav": 2.2, "unit_nav": 1.1},
        ], {date(2026, 1, 1): 2.0, date(2026, 1, 3): 2.2})

    def test_nonfinite_values_are_not_nav_evidence(self):
        self.check_points([
            {"date": "2026-01-01", "accum_nav": float("inf"), "unit_nav": 1.0},
            {"date": "2026-01-02", "accum_nav": float("nan"), "unit_nav": 1.1},
        ], {date(2026, 1, 1): 1.0, date(2026, 1, 2): 1.1})

    def test_undated_rows_do_not_select_a_nav_caliber(self):
        self.check_points([
            {"date": "invalid", "accum_nav": 2.0},
            {"date": "2026-01-02", "nav": 1.0},
        ], {date(2026, 1, 2): 1.0})

    def test_canonical_nav_keeps_dates_benchmark_and_zero_rejection(self):
        rows = [
            {"trade_date": "2026-01-03", "nav": 1.1, "benchmark_nav": 101},
            {"trade_date": "2026-01-02", "nav": 0},
            {"trade_date": "2026-01-01", "nav": 1.0, "benchmark_nav": 100},
        ]
        self.check_points(rows, {date(2026, 1, 1): 1.0, date(2026, 1, 3): 1.1})
        self.assertEqual([item["benchmark_nav"] for item in Career._normalize_rows(rows)], [100, 101])


if __name__ == "__main__":
    unittest.main()
