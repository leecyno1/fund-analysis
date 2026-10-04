"""A5：滚动指标投影必须经 select_metric_panel 消解多基准歧义，不得 last-wins。纯离线。

只抽取两个投影纯函数，注入真实 ProfessionalScoringService（含已验证的 select_metric_panel）。
"""
import __future__
import ast
from pathlib import Path
from runpy import run_path
import unittest


BACKEND = Path(__file__).resolve().parents[1]
Scoring = run_path(str(Path(__file__).with_name("fund_evaluation_numeric_offline_test.py")))["Scoring"]


def _extract(path, wanted):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    body = ast.parse("from __future__ import annotations").body
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            node.decorator_list = []
            body.append(node)
    namespace = {"ProfessionalScoringService": Scoring}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(path), "exec", flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    return namespace


rolling_panel = _extract(BACKEND / "routes" / "funds.py", {"_rolling_metric_panel"})["_rolling_metric_panel"]
project_rolling = _extract(
    BACKEND / "services" / "fund_research_snapshot_service.py", {"project_rolling_metrics"}
)["project_rolling_metrics"]


def _row(name, window, value, benchmark=None, as_of="2026-09-30", updated="2026-09-30T00:00:00"):
    return {
        "metric_name": name, "metric_window": window, "metric_value": value,
        "benchmark_code": benchmark, "as_of_date": as_of, "updated_at": updated,
    }


class RollingMetricPanelBenchmarkTest(unittest.TestCase):
    def test_expected_benchmark_selects_its_own_excess_return(self):
        panel = [
            _row("excess_return", "1y", 0.05, benchmark="IDX_A"),
            _row("excess_return", "1y", 0.09, benchmark="IDX_B"),
        ]
        result = rolling_panel(panel, benchmark_code="IDX_A")
        self.assertEqual(result["1y"]["excess_return"], 0.05)
        self.assertEqual(result["1y"]["benchmark_code"], "IDX_A")

    def test_ambiguous_benchmark_without_expected_is_dropped_not_last_wins(self):
        panel = [
            _row("excess_return", "1y", 0.05, benchmark="IDX_A"),
            _row("excess_return", "1y", 0.09, benchmark="IDX_B"),
        ]
        self.assertNotIn("excess_return", rolling_panel(panel).get("1y", {}))

    def test_single_benchmark_relative_metric_is_preserved(self):
        result = rolling_panel([_row("excess_return", "1y", 0.05, benchmark="IDX_A")])
        self.assertEqual(result["1y"]["excess_return"], 0.05)

    def test_latest_as_of_wins_for_absolute_metric(self):
        panel = [
            _row("sharpe_ratio", "1y", 1.2, as_of="2026-09-30", updated="2026-09-30T00:00:00"),
            _row("sharpe_ratio", "1y", 0.8, as_of="2026-06-30", updated="2026-06-30T00:00:00"),
        ]
        result = rolling_panel(panel)
        self.assertEqual(result["1y"]["sharpe_ratio"], 1.2)
        self.assertEqual(result["1y"]["as_of_date"], "2026-09-30")


class ProjectRollingMetricsBenchmarkTest(unittest.TestCase):
    def test_expected_benchmark_selects_its_own_information_ratio(self):
        panel = [
            _row("information_ratio", "1y", 0.3, benchmark="IDX_A"),
            _row("information_ratio", "1y", 0.9, benchmark="IDX_B"),
        ]
        self.assertEqual(project_rolling(panel, benchmark_code="IDX_A")["1y"]["information_ratio"], 0.3)

    def test_ambiguous_benchmark_without_expected_is_dropped(self):
        panel = [
            _row("information_ratio", "1y", 0.3, benchmark="IDX_A"),
            _row("information_ratio", "1y", 0.9, benchmark="IDX_B"),
        ]
        self.assertNotIn("information_ratio", project_rolling(panel).get("1y", {}))

    def test_single_benchmark_relative_metric_is_preserved(self):
        result = project_rolling([_row("excess_return", "1y", 0.04, benchmark="IDX_A")])
        self.assertEqual(result["1y"]["excess_return"], 0.04)


if __name__ == "__main__":
    unittest.main(verbosity=2)
