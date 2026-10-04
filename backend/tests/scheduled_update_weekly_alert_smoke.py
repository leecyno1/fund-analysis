"""周任务漏跑检查：只告警、去重，不触发同步任务。"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scheduled_update.sh"
WEEKLY_TASKS = (
    "funds:update-universe",
    "funds:sync-manager-universe",
    "funds:sync-manager-tenure",
    "funds:sync-dividends",
    "funds:sync-product-profiles",
)


def run_check(log_root: Path, *args: str) -> str:
    env = dict(os.environ)
    env["SCHEDULED_UPDATE_LOG_ROOT"] = str(log_root)
    env["SCHEDULED_UPDATE_LOCK_ROOT"] = str(log_root / "locks")
    result = subprocess.run(
        ["bash", str(SCRIPT), *args, "--check-weekly"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        logs = Path(directory)
        alert_log = logs / "alerts.log"

        assert "[alert]" in run_check(logs, "--dry-run")
        assert not alert_log.exists(), "dry-run must not write alerts"

        started = datetime.now().astimezone().isoformat()
        rows = [
            {"task": task, "status": "ok", "start": started}
            for task in WEEKLY_TASKS[:-1]
        ]
        rows.append({"task": WEEKLY_TASKS[-1], "status": "ok", "start": "bad-date"})
        (logs / "runbook.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n"
        )

        assert WEEKLY_TASKS[-1] in run_check(logs)
        assert WEEKLY_TASKS[-1] in run_check(logs)
        assert alert_log.read_text().count("weekly_missed") == 1

        rows[-1]["start"] = started
        (logs / "runbook.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n"
        )
        assert "[ok]" in run_check(logs)
        assert alert_log.read_text().count("weekly_missed") == 1

    print("OK weekly missing, dedup, dry-run and complete cases")


if __name__ == "__main__":
    main()
