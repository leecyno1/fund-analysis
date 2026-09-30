"""当日已成功任务的补跑去重：RunAtLoad 补偿依赖此语义，正常日子登录不重复消耗配额。"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO, "scripts", "scheduled_update.sh")


def _run(*args):
    return subprocess.run(
        ["bash", SCRIPT, *args],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )


def _today_ok_count(task_id):
    # 复刻 runbook 判定：当日（本地日期）同名任务 status=ok 的条数
    import json
    import datetime
    today = datetime.date.today().isoformat()
    count = 0
    with open(os.path.join(REPO, "logs", "scheduled_update", "runbook.jsonl")) as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("task") == task_id and row.get("status") == "ok" and str(row.get("ts", ""))[:10] == today:
                count += 1
    return count


def main() -> int:
    # dry-run 模式下，当日已 ok 的任务必须被标记为 skipped_today（补跑保护）
    result = _run("--bucket", "daily", "--dry-run")
    if result.returncode != 0:
        print(f"dry-run failed: {result.stdout[-500:]} {result.stderr[-500:]}")
        return 1
    out = result.stdout

    if "skipped_today" not in out:
        # 当日确有 ok 任务（本冒烟在调度运行过的一天执行）时应出现 skipped_today
        probe = _today_ok_count("alerts:scan")
        if probe > 0:
            print(f"Expected skipped_today markers for already-ok tasks today, got:\n{out[-800:]}")
            return 1
        print("no ok tasks recorded today; dedup path untestable now, run after a scheduled day")
        return 0

    # 出现 skipped_today 时，必须同时保留 dry-run 输出中未跑任务的正常展示
    if "[dry-run]" not in out:
        print(f"Expected dry-run listing for fresh tasks, got:\n{out[-500:]}")
        return 1

    print("OK same-day already-ok tasks are deduplicated on rerun (skipped_today)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
