import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))

function read(relativePath) {
  const fullPath = join(root, relativePath)
  if (!existsSync(fullPath)) {
    throw new Error(`Missing required file: ${relativePath}`)
  }
  return readFileSync(fullPath, 'utf8')
}

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) {
    throw new Error(`${label} missing text: ${expected}`)
  }
}

const dataSyncRoute = read('backend/routes/data_sync.py')
const rollingMetricService = read('backend/services/rolling_metric_service.py')
const metricFactory = read('backend/services/metric_factory.py')
const tushareService = read('backend/services/tushare_service.py')
const rankingMetricScript = read('backend/scripts/sync_fund_ranking_metrics.py')
const rankingMetricShell = read('scripts/update_fund_ranking_metrics.sh')
const packageJson = read('package.json')
const syncBff = read('app/api/sync/wind/route.ts')
const syncPage = read('app/(dashboard)/sync/page.tsx')

assertIncludes(dataSyncRoute, 'from services.rolling_metric_service import RollingMetricService', 'data sync imports rolling metric calculator')
assertIncludes(dataSyncRoute, 'rolling_metrics = RollingMetricService().calculate_and_save_for_fund(wind_code)', 'data sync recalculates rolling metrics after NAV sync')
assertIncludes(dataSyncRoute, '"rolling_metrics": rolling_metrics', 'data sync returns rolling metric result')
assertIncludes(dataSyncRoute, '净值已同步，但滚动指标样本不足', 'data sync warns when NAV cannot support metrics')
assertIncludes(rollingMetricService, 'min_observation_ratio: float = 0.6', 'rolling metric service has observation threshold')
assertIncludes(rollingMetricService, 'metric_repo.upsert_metric', 'rolling metric service persists MetricSnapshot')
assertIncludes(metricFactory, 'item.get("adj_nav") or item.get("accum_nav")', 'metric factory prefers adjusted or accumulated NAV for return metrics')
assertIncludes(tushareService, '"adj_nav": adjusted_nav', 'Tushare NAV sync keeps adjusted NAV evidence')
assertIncludes(tushareService, '"total_netasset": _as_float(row.get("total_netasset"))', 'Tushare NAV sync keeps asset evidence when available')
assertIncludes(rankingMetricScript, '同步基金筛选榜单所需的真实净值与滚动指标', 'ranking metric sync script documents research-only scope')
assertIncludes(rankingMetricScript, 'build_fund_metric_payload', 'ranking metric sync writes performance and risk JSON for screener sorting')
assertIncludes(rankingMetricScript, 'wind_code LIKE', 'ranking metric sync defaults to public fund codes with fund_nav coverage')
assertIncludes(rankingMetricShell, 'sync_fund_ranking_metrics.py', 'ranking metric shell invokes Python sync')
assertIncludes(packageJson, 'funds:update-ranking-metrics', 'package exposes ranking metric sync command')
assertIncludes(syncBff, 'rollingMetrics: payload.rolling_metrics || null', 'sync BFF forwards rolling metric result')
assertIncludes(syncPage, '滚动指标补证', 'sync page displays rolling metric evidence result')
assertIncludes(syncPage, 'detail.rollingMetrics.windows.join', 'sync page displays rolling metric windows')

console.log('OK real data sync persists rolling metrics for peer percentile evidence')
