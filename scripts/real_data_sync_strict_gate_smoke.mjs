import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const registry = readFileSync(join(root, 'backend/service_registry.py'), 'utf8')
const tushare = readFileSync(join(root, 'backend/services/tushare_service.py'), 'utf8')
const dataSync = readFileSync(join(root, 'backend/routes/data_sync.py'), 'utf8')
const syncBff = readFileSync(join(root, 'app/api/sync/wind/route.ts'), 'utf8')
const syncPage = readFileSync(join(root, 'app/(dashboard)/sync/page.tsx'), 'utf8')

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) {
    throw new Error(`${label} missing text: ${expected}`)
  }
}

function assertNotIncludes(content, expected, label) {
  if (content.includes(expected)) {
    throw new Error(`${label} must not include text: ${expected}`)
  }
}

assertIncludes(registry, 'def get_strict_tushare_service()', 'service registry strict tushare provider')
assertIncludes(registry, 'TushareDataService(strict_no_mock=True)', 'service registry strict tushare construction')
assertIncludes(tushare, 'if strict_no_mock and mock_mode:', 'tushare strict constructor gate')
assertIncludes(tushare, 'Tushare strict_no_mock requires real data source', 'tushare strict error message')
assertIncludes(tushare, 'TUSHARE_TOKEN missing', 'tushare strict token diagnosis')
assertIncludes(dataSync, 'from service_registry import get_strict_tushare_service', 'data sync imports strict tushare provider')
assertIncludes(dataSync, 'data_svc = get_strict_tushare_service()', 'data sync uses strict real data provider')
assertNotIncludes(dataSync, 'get_data_service()', 'data sync must not use mock-capable provider')
assertIncludes(syncBff, 'assertRealBackendDataSource', 'sync BFF has real data guard')
assertIncludes(syncBff, "fetchJson('/api/health')", 'sync BFF checks backend health before sync')
assertIncludes(syncBff, '后端当前仍是 Mock 模式，请配置 TUSHARE_TOKEN', 'sync BFF explains mock-mode block')
assertIncludes(syncBff, 'status = 409', 'sync BFF returns conflict for mock-mode sync')
assertIncludes(syncPage, "throw new Error(result.details || result.error || '同步失败')", 'sync page surfaces backend sync failure detail')
assertIncludes(syncPage, "error instanceof Error ? error.message : '未知错误'", 'sync page renders real sync error detail')
assertIncludes(syncPage, 'realDataReportGateSummary', 'sync page summarizes real-data report buy-before gate')
assertIncludes(syncPage, 'real-data-report-buy-before-summary', 'sync page renders real-data buy-before summary')
assertIncludes(syncPage, '真实报告研究门禁汇总', 'sync page labels real-data research summary')
assertIncludes(syncPage, '同步和报告保存不等于正式研究结论', 'sync page preserves report-vs-research boundary')
assertIncludes(syncPage, '批量补规则（{realDataReportGateSummary.blockedCodes.length}）', 'sync page links blocked real reports to sales-rule remediation')

console.log('OK real-data sync path requires strict Tushare and cannot fall back to mock')
