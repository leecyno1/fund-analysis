"""data_health._runbook_path 必须锚定项目根，不随 cwd 漂移（生产 launchd 下 cwd=backend/）。纯离线。"""
import __future__
import ast
import os
from pathlib import Path
import tempfile
import unittest


ROUTE = Path(__file__).resolve().parents[1] / "routes" / "data_health.py"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_runbook_path():
    tree = ast.parse(ROUTE.read_text(encoding="utf-8"), filename=str(ROUTE))
    body = ast.parse("from __future__ import annotations").body
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_runbook_path":
            node.decorator_list = []
            body.append(node)
    namespace = {"os": os, "Path": Path, "__file__": str(ROUTE)}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(ROUTE), "exec", flags=__future__.annotations.compiler_flag,
        ),
        namespace,
    )
    return namespace["_runbook_path"]


runbook_path = _load_runbook_path()


class RunbookPathTest(unittest.TestCase):
    def test_anchored_to_repo_root_not_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            os.chdir(tmp)
            try:
                resolved = runbook_path()
            finally:
                os.chdir(original)
        self.assertEqual(resolved, REPO_ROOT / "logs" / "scheduled_update" / "runbook.jsonl")

    def test_points_at_the_real_runbook_that_scheduler_writes(self):
        # 生产后端 cwd=backend/，修复前会指向 backend/logs（不存在）而漏读真实 runbook。
        self.assertTrue(runbook_path().exists(), runbook_path())

    def test_env_override_is_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SCHEDULED_UPDATE_LOG_ROOT"] = tmp
            try:
                self.assertEqual(runbook_path(), Path(tmp) / "runbook.jsonl")
            finally:
                del os.environ["SCHEDULED_UPDATE_LOG_ROOT"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
