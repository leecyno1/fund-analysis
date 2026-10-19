"""研究问题清单：把异常转成待查问题并挂接相关纪要/报告。纯离线。"""
import __future__
import ast
from pathlib import Path
import unittest


SRC = Path(__file__).resolve().parents[1] / "services" / "fund_research_questions_service.py"


def _load():
    tree = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    body = ast.parse("from __future__ import annotations").body
    wanted = {"build_research_questions", "_question_for", "_question_text", "_fmt_pct", "_fmt_ratio", "_fmt_yi", "_fmt_plain_pct"}
    wanted_const = {"MAX_EVIDENCE_PER_QUESTION", "_ACTION_LABELS"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            node.decorator_list = []
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in wanted_const for t in node.targets
        ):
            body.append(node)
    ns = {}
    exec(
        compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                str(SRC), "exec", flags=__future__.annotations.compiler_flag),
        ns,
    )
    return ns["build_research_questions"]


build = _load()


REPORTS = [
    {"report_id": "r1", "title": "杨恒访谈", "report_date": "2026-10-01", "manager_name": "杨恒"},
    {"report_id": "r2", "title": "组合季报复盘", "report_date": "2026-09-01", "manager_name": "张三"},
]


def _anomalies():
    return [
        {"type": "scale_anomaly", "wind_code": "000001.OF", "description": "规模较 2026-08-12 变动 +990.0%（2.52 → 27.45 亿元）", "change_pct": 990.0, "aum_prev": 2.52, "aum_now": 27.45, "prev_date": "2026-08-12", "as_of_date": "2026-10-14"},
        {"type": "drawdown_anomaly", "wind_code": "000001.OF", "description": "近3月回撤 -42.4% 已达近3年的 100%", "dd_3m": -0.424, "ratio_pct": 100.0},
        {"type": "concentration_change", "wind_code": "000001.OF", "description": "前十大集中度变动 -50.6pct", "change_pct": -50.6, "prev_rows": 15, "latest_rows": 15},
        {"type": "manager_change", "wind_code": "000001.OF", "description": "经理变更：杨恒 离任（2026-10-16）", "manager_name": "杨恒", "change_type": "manager_removed", "changed_at": "2026-10-16"},
    ]


class ResearchQuestionsTest(unittest.TestCase):
    def test_each_anomaly_becomes_question_with_evidence(self):
        out = build(_anomalies(), REPORTS, "000001.OF")
        self.assertEqual(out["status"], "available")
        self.assertEqual(out["question_count"], 4)
        types = [q["anomaly_type"] for q in out["questions"]]
        self.assertEqual(types, ["scale_anomaly", "drawdown_anomaly", "concentration_change", "manager_change"])
        for question in out["questions"]:
            self.assertTrue(question["question"])
            self.assertLessEqual(len(question["evidence"]), 3)

    def test_manager_change_prefers_matching_manager_report(self):
        out = build(_anomalies(), REPORTS, "000001.OF")
        manager_q = next(q for q in out["questions"] if q["anomaly_type"] == "manager_change")
        self.assertEqual(manager_q["evidence"][0]["report_id"], "r1")
        self.assertIsNone(manager_q["evidence_gap"])

    def test_missing_manager_report_sets_evidence_gap(self):
        reports = [r for r in REPORTS if r["manager_name"] != "杨恒"]
        out = build(_anomalies(), reports, "000001.OF")
        manager_q = next(q for q in out["questions"] if q["anomaly_type"] == "manager_change")
        self.assertEqual(manager_q["evidence"], [])
        self.assertIn("杨恒", manager_q["evidence_gap"])

    def test_no_reports_sets_gap_on_every_question(self):
        out = build(_anomalies(), [], "000001.OF")
        for question in out["questions"]:
            self.assertEqual(question["evidence"], [])
            self.assertTrue(question["evidence_gap"])

    def test_no_anomalies_returns_no_anomalies(self):
        out = build([], REPORTS, "000001.OF")
        self.assertEqual(out["status"], "no_anomalies")
        self.assertEqual(out["question_count"], 0)
        self.assertEqual(out["questions"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
