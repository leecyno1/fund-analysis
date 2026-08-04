#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if [[ -z "${DATABASE_URL:-}" ]]; then
  for env_file in "$ROOT_DIR/.env.local" "$ROOT_DIR/.env" "$BACKEND_DIR/.env"; do
    if [[ -f "$env_file" ]] && grep -q '^DATABASE_URL=' "$env_file"; then
      set -a
      # shellcheck disable=SC1090
      source "$env_file" >/dev/null 2>&1
      set +a
      break
    fi
  done
fi

printf '\n== 基金研究引擎：完成度验收 ==\n'
printf '项目目录: %s\n' "$ROOT_DIR"

check_python() {
  local python_bin="$1"
  "$python_bin" - <<'PY' >/dev/null 2>&1
required = ["sqlalchemy", "psycopg2", "pymongo", "tushare"]
for module in required:
    __import__(module)
PY
}

PYTHON_BIN=""
for candidate in "${BACKEND_PYTHON:-}" "/usr/local/bin/python3" "/opt/homebrew/bin/python3" "$(command -v python3 || true)"; do
  if [[ -n "$candidate" && -x "$candidate" ]] && check_python "$candidate"; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo '缺少带后端依赖的 python3，无法执行后端 smoke 测试'
  exit 1
fi
printf '使用 Python: %s\n' "$PYTHON_BIN"

printf '\n[1/5] 检查 DATABASE_URL ...\n'
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo '未检测到 DATABASE_URL，请先配置数据库连接'
  exit 1
fi
printf 'DATABASE_URL 已配置\n'

printf '\n[2/5] 检查 PostgreSQL 连通性 ...\n'
if command -v pg_isready >/dev/null 2>&1; then
  if ! pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; then
    echo 'PostgreSQL 当前不可用，请先启动数据库'
    exit 1
  fi
  echo 'PostgreSQL 连通正常'
else
  echo '未找到 pg_isready，跳过端口探测，继续执行 smoke 测试'
fi

run_py_smoke() {
  local script_path="$1"
  printf '\n>>> 运行 %s\n' "$script_path"
  "$PYTHON_BIN" "$script_path"
}

printf '\n[3/5] 准备幂等验收样本 ...\n'
if command -v psql >/dev/null 2>&1; then
  psql "$DATABASE_URL" -f "$ROOT_DIR/scripts/seed_methodology_config.sql" >/dev/null
  psql "$DATABASE_URL" -f "$ROOT_DIR/scripts/seed_completion_sample.sql" >/dev/null
  psql "$DATABASE_URL" -f "$ROOT_DIR/scripts/seed_research_taxonomy_peer_groups.sql" >/dev/null
  psql "$DATABASE_URL" -f "$ROOT_DIR/scripts/seed_benchmark_attribution.sql" >/dev/null
  "$PYTHON_BIN" "$ROOT_DIR/scripts/seed_rolling_metrics.py"
  echo '验收样本与滚动指标已就绪'
else
  echo '未找到 psql，跳过 SQL 样本导入；后续 DB smoke 可能依赖已有样本'
fi

printf '\n[4/5] 执行 DB-backed smoke tests ...\n'
run_py_smoke "$BACKEND_DIR/tests/fund_pool_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/alert_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/data_snapshot_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/metric_snapshot_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/report_chunk_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/alert_scan_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/alert_scan_enhanced_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/research_profile_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/rolling_metric_service_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/tenure_data_quality_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/professional_scoring_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/fund_classification_service_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/fund_classification_repo_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/standardized_classification_adapter_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/professional_scoring_classification_scope_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/peer_comparison_classification_gate_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/fund_evaluation_service_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/fund_evaluation_route_contract_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/barra_explanatory_scope_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/research_memos_route_import_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/research_memo_service_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/peer_comparison_route_import_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/peer_percentile_service_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/comparison_matrix_service_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/investment_analysis_route_import_smoke.py"
run_py_smoke "$BACKEND_DIR/tests/advanced_investment_service_smoke.py"

printf '\n[5/5] 完成度验收建议 ...\n'
printf '\n>>> 运行基金研究模块边界 smoke\n'
node "$ROOT_DIR/scripts/fund_research_scope_smoke.mjs"

printf '\n>>> 运行高级基金研究前端 smoke\n'
node "$ROOT_DIR/scripts/advanced_analysis_frontend_smoke.mjs"

printf '\n>>> 运行投资者选基前端 smoke\n'
node "$ROOT_DIR/scripts/investor_selection_smoke.mjs"

LOCAL_APP_URL="${LOCAL_APP_URL:-http://127.0.0.1:3001}"
LOCAL_REAL_FLOW_STATUS="skipped"
if curl -fsS "$LOCAL_APP_URL/api/funds?limit=1" >/dev/null 2>&1; then
  printf '\n>>> 运行本地真实买前链路 smoke (%s)\n' "$LOCAL_APP_URL"
  LOCAL_APP_URL="$LOCAL_APP_URL" node "$ROOT_DIR/scripts/local_real_flow_smoke.mjs"
  LOCAL_REAL_FLOW_STATUS="passed"
else
  printf '\n>>> 本地前端服务未检测到，跳过真实页面/API 联调 smoke (%s)\n' "$LOCAL_APP_URL"
fi

if [[ "$LOCAL_REAL_FLOW_STATUS" == "passed" ]]; then
  cat <<'TEXT'
所有 smoke 通过后，核心后端、前端静态边界和本地真实 API 链路已完成自动验收。
如需继续做人工验收，请只补浏览器视觉层：
1. 打开全市场浏览器，确认买前任务分流与销售规则阻断提示
2. 打开基金池，确认已有观察池成员可读可编辑
3. 打开预警中心，确认扫描结果与事件列表可读
4. 打开基金详情/横评页，确认真实数据、同类分位和买前证据展示
TEXT
else
  cat <<'TEXT'
所有 smoke 通过后，核心后端和前端静态边界已完成自动验收。
本地真实 API 链路未运行；如需补齐，请启动前端服务后运行：
  node scripts/local_real_flow_smoke.mjs
TEXT
fi

printf '\n== 验收脚本执行完成 ==\n'
