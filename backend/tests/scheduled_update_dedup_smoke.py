"""调度补偿的权威时点语义：时点前整轮触发被闸住；时点后 ok 才计入去重；--force 绕过两者。

场景（全部用 DAILY_FIRE_HM 注入时点、dry-run 执行，零副作用）：
1. 闸：时点设为当天 23:59 → 当前时刻必然早于时点 → 整轮触发打印 gate 提示、无任务行。
2. 去重：时点设为当天 00:00 → 当天任意时刻的 ok 记录都晚于时点 → 全部标 skipped_today。
   （依赖当天 runbook 已有 ok 记录；无记录时退化为"至少展示正常命令行"并提示场景不可测。）
3. force：时点 23:59 + --force → 闸与去重都被绕过，展示真实命令。
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO, "scripts", "scheduled_update.sh")


def _run(*args, fire=None):
    env = dict(os.environ)
    if fire is not None:
        env["DAILY_FIRE_HM"] = fire
    return subprocess.run(
        ["bash", SCRIPT, *args],
        capture_output=True, text=True, cwd=REPO, timeout=120, env=env,
    )


def main() -> int:
    # 场景 1：时点前的整轮触发必须被闸住（晨间 RunAtLoad 语义）
    gated = _run("--bucket", "daily", "--dry-run", fire="2359")
    if gated.returncode != 0:
        print(f"gate run failed: {gated.stdout[-300:]} {gated.stderr[-300:]}")
        return 1
    if "[gate]" not in gated.stdout or "[dry-run]" in gated.stdout:
        print(f"Expected gate notice without task lines before fire time, got:\n{gated.stdout[-500:]}")
        return 1

    # 场景 2：时点后的 ok 计入去重（当天已有 ok 记录时全部 skipped_today）
    dedup = _run("--bucket", "daily", "--dry-run", fire="0000")
    if dedup.returncode != 0:
        print(f"dedup run failed: {dedup.stdout[-300:]}")
        return 1
    if "skipped_today" in dedup.stdout:
        if "[dry-run]" not in dedup.stdout or "npm run" in dedup.stdout:
            print(f"Expected all tasks marked skipped_today, got:\n{dedup.stdout[-500:]}")
            return 1
    else:
        # 当天 runbook 尚无 ok 记录：至少应展示正常命令行（未误闸、未误跳）
        if "[gate]" in dedup.stdout or "npm run" not in dedup.stdout:
            print(f"No ok records today; expected plain command listing, got:\n{dedup.stdout[-500:]}")
            return 1
        print("no ok records recorded today; dedup path untestable now (gate/force verified)")

    # 场景 3：--force 同时绕过闸与去重
    forced = _run("--bucket", "daily", "--dry-run", "--force", fire="2359")
    if forced.returncode != 0:
        print(f"force run failed: {forced.stdout[-300:]}")
        return 1
    if "[gate]" in forced.stdout or "skipped_today" in forced.stdout or "npm run" not in forced.stdout:
        print(f"Expected force to bypass gate and dedup, got:\n{forced.stdout[-500:]}")
        return 1

    # 场景 4：--only 单任务不受闸限制（手工定向运维入口）
    only = _run("--only", "alerts:scan", "--dry-run", fire="2359")
    if "[dry-run]" not in only.stdout or "[gate]" in only.stdout:
        print(f"Expected --only to bypass the gate, got:\n{only.stdout[-300:]}")
        return 1

    print("OK fire-time gate, since-fire dedup, force bypass and --only exemption all behave correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
