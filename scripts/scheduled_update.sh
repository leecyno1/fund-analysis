#!/usr/bin/env bash
# scripts/scheduled_update.sh
#
# 薄调度器：编排现有 npm/bash/python 同步命令，为 launchd/systemd 定时器提供
# 单一入口。设计要点：
#
#   - 非重入锁：每个任务一把 flock，避免并发写库
#   - 显式日志：logs/scheduled_update/YYYY-MM-DD/<task>.log
#   - 运行记录：logs/scheduled_update/runbook.jsonl（每行一次执行）
#   - 支持 --dry-run（只打印计划）、--only <task>（跑单个）、--list（列任务）、
#     --bucket daily|weekly|quarterly（按节奏批量跑）
#   - 日志脱敏：Token/API Key 不写入日志
#   - 失败告警：非零退出码写入 runbook.jsonl 并保留 stderr 尾部到告警日志
#   - 不做破坏性回滚：上一版有效快照由上游同步脚本保证，本编排器只做记录
#
# 用法示例：
#   bash scripts/scheduled_update.sh --list
#   bash scripts/scheduled_update.sh --dry-run --bucket daily
#   bash scripts/scheduled_update.sh --only funds:backfill-browser-core
#   bash scripts/scheduled_update.sh --bucket weekly

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ------------------------- PATH 补全 -------------------------
# launchd 启动时 PATH 仅 /usr/bin:/bin:/usr/sbin:/sbin，不含 Homebrew 目录，
# 会让所有 npm 任务 exit=127、依赖 psql/pg_dump 的备份任务失败。
for brew_bin in /opt/homebrew/bin /usr/local/bin; do
  if [[ -d "$brew_bin" && ":$PATH:" != *":$brew_bin:"* ]]; then
    PATH="$brew_bin:$PATH"
  fi
done
export PATH

# ------------------------- 环境加载 -------------------------
set -a
for env_file in .env.local .env backend/.env; do
  [[ -f "$env_file" ]] && source "$env_file" || true
done
set +a

LOG_ROOT="${SCHEDULED_UPDATE_LOG_ROOT:-$ROOT_DIR/logs/scheduled_update}"
LOCK_ROOT="${SCHEDULED_UPDATE_LOCK_ROOT:-$ROOT_DIR/.scheduled_update.locks}"
RUNBOOK="$LOG_ROOT/runbook.jsonl"
ALERT_LOG="$LOG_ROOT/alerts.log"
DATE_TAG="$(date +%Y-%m-%d)"
DAY_LOG_DIR="$LOG_ROOT/$DATE_TAG"

mkdir -p "$DAY_LOG_DIR" "$LOCK_ROOT"

# ------------------------- 任务注册表 -------------------------
# 格式：TASK_ID | BUCKET | 命令
#   BUCKET: daily / weekly / quarterly / monthly / adhoc
#   命令：直接放在数组里，用 -- 分隔 npm run 参数
declare -a TASKS=(
  "funds:backfill-browser-core|daily|npm run funds:backfill-browser-core"
  "funds:backfill-peer-evaluation|daily|npm run funds:backfill-peer-evaluation -- --limit 1000"
  "research:sync-ima|daily|npm run research:sync-ima"
  "research:sync-manager-identities|daily|npm run research:sync-manager-identities"
  "managers:snapshot-backlog|daily|.venv/bin/python backend/scripts/sync_fund_manager_tenure.py --snapshot-backlog 3 --throttle 0.5"

  "research:signals-scan|daily|curl -fsS --max-time 300 http://127.0.0.1:8005/api/research-signals/scan"
  "anomalies:scan|daily|curl -fsS --max-time 300 http://127.0.0.1:8005/api/anomalies/scan"
  "watches:scan|daily|curl -fsS --max-time 300 -X POST http://127.0.0.1:8005/api/watches/scan"
  "alerts:scan|daily|curl -fsS --max-time 300 -X POST http://127.0.0.1:8005/api/alerts/scan"

  "evaluation:snapshots|daily|.venv/bin/python backend/scripts/save_evaluation_snapshots.py --limit 150"
  "ops:backup-postgres|daily|bash scripts/backup_postgres.sh"

  "funds:update-universe|weekly|npm run funds:update-universe"
  "funds:sync-manager-universe|weekly|npm run funds:sync-manager-universe"
  "funds:sync-manager-tenure|weekly|npm run funds:sync-manager-tenure"
  "funds:sync-dividends|weekly|npm run funds:sync-dividends -- --limit 300"
  "funds:sync-product-profiles|weekly|npm run funds:sync-product-profiles -- --limit 100"

  "funds:sync-holdings|quarterly|npm run funds:sync-holdings -- --limit 900"
  "funds:sync-bond-holdings|quarterly|npm run funds:sync-bond-holdings -- --limit 100"
  "data:sync-holding-style|quarterly|npm run data:sync-holding-style"

  "research:apply-memo-labels|monthly|npm run research:apply-memo-labels"
  "research:apply-viewpoint-topics|monthly|npm run research:apply-viewpoint-topics"
)

# ------------------------- CLI 解析 -------------------------
MODE=""
BUCKET=""
TASK_ID=""
DRY_RUN="0"
FORCE="0"
# daily 权威调度时点（本地 HHMM）：晚间收盘后的正式轮才是权威口径；
# 早于该时点的 RunAtLoad/手工整轮触发会被闸住。测试可用环境变量覆写。
DAILY_FIRE_HM="${DAILY_FIRE_HM:-1815}"

usage() {
  cat <<USAGE
Usage: $0 [--dry-run] [--list | --bucket <name> | --only <task_id>]

  --list                  列出所有已注册任务和其节奏 bucket
  --bucket <name>         执行某个 bucket 内所有任务（daily/weekly/monthly/quarterly）
  --only <task_id>        执行单个任务
  --dry-run               只打印计划，不执行

Environment:
  SCHEDULED_UPDATE_LOG_ROOT   自定义日志目录（默认 logs/scheduled_update/）
  SCHEDULED_UPDATE_LOCK_ROOT  自定义锁目录（默认 .scheduled_update.locks/）
  BACKEND_PYTHON              覆盖 Python 解释器
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)     MODE="list"; shift;;
    --bucket)   MODE="bucket"; BUCKET="${2:-}"; shift 2;;
    --only)     MODE="only"; TASK_ID="${2:-}"; shift 2;;
    --dry-run)  DRY_RUN="1"; shift;;
    --force)    FORCE="1"; shift;;
    -h|--help)  usage; exit 0;;
    *)          echo "未知参数：$1" >&2; usage >&2; exit 2;;
  esac
done

if [[ -z "$MODE" ]]; then
  usage >&2
  exit 2
fi

# ------------------------- 工具函数 -------------------------
scrub_line() {
  # 从命令输出里屏蔽掉常见密钥；只在写日志前做一次
  sed -E \
    -e 's/(TUSHARE_TOKEN[[:space:]]*[:=][[:space:]]*)[^[:space:]"'\'']+/\1***REDACTED***/g' \
    -e 's/(IMA_OPENAPI_APIKEY[[:space:]]*[:=][[:space:]]*)[^[:space:]"'\'']+/\1***REDACTED***/g' \
    -e 's/(api[_-]?key[[:space:]]*[:=][[:space:]]*)[^[:space:]"'\'']+/\1***REDACTED***/gi' \
    -e 's/(password[[:space:]]*[:=][[:space:]]*)[^[:space:]"'\'']+/\1***REDACTED***/gi' \
    -e 's/Bearer[[:space:]]+[A-Za-z0-9._-]+/Bearer ***REDACTED***/g'
}

json_escape() {
  python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read()))'
}

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

lookup_task() {
  local id="$1"
  for row in "${TASKS[@]}"; do
    local rid="${row%%|*}"
    if [[ "$rid" == "$id" ]]; then
      echo "$row"
      return 0
    fi
  done
  return 1
}

acquire_lock() {
  # mkdir 原子非重入锁（macOS 无 flock）；持锁进程已死时视为陈旧锁并接管
  local lock_dir="$1"
  if mkdir "$lock_dir" 2>/dev/null; then
    echo $$ > "$lock_dir/pid"
    return 0
  fi
  local holder_pid
  holder_pid="$(cat "$lock_dir/pid" 2>/dev/null || true)"
  if [[ -n "$holder_pid" ]] && ! kill -0 "$holder_pid" 2>/dev/null; then
    rm -rf "$lock_dir"
    if mkdir "$lock_dir" 2>/dev/null; then
      echo $$ > "$lock_dir/pid"
      return 0
    fi
  fi
  return 1
}

filter_bucket() {
  local bucket="$1"
  local out=()
  for row in "${TASKS[@]}"; do
    local rest="${row#*|}"
    local rbucket="${rest%%|*}"
    if [[ "$rbucket" == "$bucket" ]]; then
      out+=("$row")
    fi
  done
  printf "%s\n" "${out[@]}"
}

list_tasks() {
  printf "%-40s %-10s %s\n" "TASK_ID" "BUCKET" "COMMAND"
  printf "%-40s %-10s %s\n" "----------------------------------------" "----------" "-------"
  for row in "${TASKS[@]}"; do
    local id="${row%%|*}"; local rest="${row#*|}"
    local bucket="${rest%%|*}"; local cmd="${rest#*|}"
    printf "%-40s %-10s %s\n" "$id" "$bucket" "$cmd"
  done
}

# ------------------------- 单任务执行 -------------------------
daily_fire_epoch() {
  # 当日 DAILY_FIRE_HM（本地）的 epoch 秒。解析失败取极大值：宁可重跑也不误跳。
  local today epoch
  today="$(date +%Y-%m-%d)"
  epoch="$(date -j -f "%Y-%m-%d %H:%M" "${today} ${DAILY_FIRE_HM:0:2}:${DAILY_FIRE_HM:2:2}" +%s 2>/dev/null || true)"
  echo "${epoch:-9999999999}"
}

_ok_since_daily_fire() {
  # 当日权威时点（默认 18:15 本地）之后已有该任务的 ok 记录 → 返回 0。
  # 语义：晚间正式调度是权威口径；早于时点的 ok（晨间 RunAtLoad 或手工提前跑）
  # 不计入去重，保证当晚正式轮照常执行、当日收盘数据不丢。
  local id="$1" boundary
  boundary="$(daily_fire_epoch)"
  [[ -f "$RUNBOOK" ]] || return 1
  python3 - "$RUNBOOK" "$id" "$boundary" <<'PY' 2>/dev/null
import json, sys
from datetime import datetime
path, task_id, boundary = sys.argv[1], sys.argv[2], float(sys.argv[3])
try:
    with open(path) as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("task") != task_id or row.get("status") != "ok":
                continue
            start = str(row.get("start") or "")
            if not start:
                continue
            try:
                ts = datetime.fromisoformat(start.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
            if ts >= boundary:
                sys.exit(0)
except OSError:
    pass
sys.exit(1)
PY
}

run_task() {
  local row="$1"
  local id="${row%%|*}"; local rest="${row#*|}"
  local bucket="${rest%%|*}"; local cmd="${rest#*|}"

  local task_log="$DAY_LOG_DIR/${id//[:\/ ]/_}.log"
  local lock_dir="$LOCK_ROOT/${id//[:\/ ]/_}.lockdir"
  local start_ts end_ts start_iso end_iso duration exit_code=0

  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ "$bucket" == "daily" && "$FORCE" != "1" ]] && _ok_since_daily_fire "$id"; then
      printf "[dry-run] %-40s %s\n" "$id" "skipped_today（当日权威时点后已成功，补跑保护）"
    else
      printf "[dry-run] %-40s %s\n" "$id" "$cmd"
    fi
    return 0
  fi

  # 当日权威时点后已成功：跳过补跑（runbook 记 skipped_today，不改写既有 ok 记录）。
  # --force 绕过；weekly 不做去重（RunAtLoad=false，仅周日调度或手工触发）。
  if [[ "$bucket" == "daily" && "$FORCE" != "1" ]] && _ok_since_daily_fire "$id"; then
    echo "[skip] $id 当日权威时点后已成功，跳过补跑。" | tee -a "$task_log"
    _write_runbook "$id" "$bucket" "$cmd" "skipped_today" 0 "$(now_iso)" "$(now_iso)" 0 "already ok since daily fire time"
    return 0
  fi

  # mkdir 原子非重入锁：同一任务并发只允许一个
  if ! acquire_lock "$lock_dir"; then
    echo "[skip] $id 已在运行（锁未释放），跳过。" | tee -a "$ALERT_LOG"
    _write_runbook "$id" "$bucket" "$cmd" "skipped_locked" 0 "$(now_iso)" "$(now_iso)" 0 "lock busy"
    return 0
  fi

  start_iso="$(now_iso)"
  start_ts="$(date +%s)"
  echo "===== $id start $start_iso =====" | tee -a "$task_log"
  echo "cmd: $cmd" | tee -a "$task_log"

  # 执行；stdout/stderr 一并流入日志，且做脱敏
  if bash -c "$cmd" 2>&1 | scrub_line | tee -a "$task_log"; then
    exit_code=0
  else
    exit_code="${PIPESTATUS[0]:-1}"
  fi

  end_ts="$(date +%s)"
  end_iso="$(now_iso)"
  duration=$(( end_ts - start_ts ))
  echo "===== $id end $end_iso exit=$exit_code duration=${duration}s =====" | tee -a "$task_log"

  local status="ok"
  if [[ "$exit_code" -ne 0 ]]; then
    status="failed"
    {
      echo "[$(now_iso)] $id failed (exit=$exit_code, log=$task_log)"
      tail -n 30 "$task_log" | sed 's/^/    /'
    } >> "$ALERT_LOG"
  fi

  _write_runbook "$id" "$bucket" "$cmd" "$status" "$exit_code" "$start_iso" "$end_iso" "$duration" "$task_log"
  rm -rf "$lock_dir"
  return "$exit_code"
}

_write_runbook() {
  # 参数：id bucket cmd status exit_code start end duration extra
  local id="$1" bucket="$2" cmd="$3" status="$4" ec="$5" s="$6" e="$7" dur="$8" extra="$9"
  local id_j cmd_j extra_j
  id_j="$(printf '%s' "$id" | json_escape)"
  cmd_j="$(printf '%s' "$cmd" | json_escape)"
  extra_j="$(printf '%s' "$extra" | json_escape)"
  printf '{"ts":"%s","task":%s,"bucket":"%s","cmd":%s,"status":"%s","exit_code":%s,"start":"%s","end":"%s","duration_seconds":%s,"log":%s}\n' \
    "$(now_iso)" "$id_j" "$bucket" "$cmd_j" "$status" "$ec" "$s" "$e" "$dur" "$extra_j" \
    >> "$RUNBOOK"
}

# ------------------------- 主流程 -------------------------
case "$MODE" in
  list)
    list_tasks
    ;;

  only)
    if [[ -z "$TASK_ID" ]]; then
      echo "--only 需要任务 ID" >&2; exit 2
    fi
    if row="$(lookup_task "$TASK_ID")"; then
      run_task "$row"
    else
      echo "未知任务：$TASK_ID" >&2
      echo "可用任务：" >&2
      list_tasks >&2
      exit 2
    fi
    ;;

  bucket)
    if [[ -z "$BUCKET" ]]; then
      echo "--bucket 需要名称" >&2; exit 2
    fi
    # 权威时点闸：daily 的权威调度是每日 18:15（收盘后）。早于该时点的整轮触发
    # （RunAtLoad 晨间登录、手工提前跑）直接退出，避免预跑结果让晚间正式轮被去重
    # 跳过而丢当日收盘数据。--force 绕过；--only 单任务不受限。
    if [[ "$BUCKET" == "daily" && "$FORCE" != "1" ]]; then
      now_hm="$(date +%H%M)"
      if [[ "$now_hm" < "$DAILY_FIRE_HM" ]]; then
        echo "[gate] 当前 ${now_hm} 早于 daily 权威时点 ${DAILY_FIRE_HM}，本次整轮触发不执行；晚间正式调度会跑。"
        mkdir -p "$DAY_LOG_DIR" 2>/dev/null || true
        echo "[$(now_iso)] gated before ${DAILY_FIRE_HM} (now=${now_hm})" >> "$DAY_LOG_DIR/runatload-gate.log" 2>/dev/null || true
        exit 0
      fi
    fi
    rows=()
    while IFS= read -r row; do
      [[ -n "$row" ]] && rows+=("$row")
    done < <(filter_bucket "$BUCKET")
    if [[ "${#rows[@]}" -eq 0 ]]; then
      echo "bucket '$BUCKET' 下没有任务。" >&2; exit 2
    fi
    fail_count=0
    for row in "${rows[@]}"; do
      if ! run_task "$row"; then
        fail_count=$(( fail_count + 1 ))
        # 单任务失败不阻塞后续任务，只累积计数
      fi
    done
    if [[ "$fail_count" -gt 0 ]]; then
      echo "bucket '$BUCKET' 完成，$fail_count 个任务失败。见 $ALERT_LOG" >&2
      exit 1
    fi
    ;;

  *)
    usage >&2; exit 2;;
esac
