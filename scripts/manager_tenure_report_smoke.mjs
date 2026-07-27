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
const reportsRoute = read('backend/routes/reports.py')
const evidenceReport = read('backend/services/evidence_report.py')
const syncBff = read('app/api/sync/wind/route.ts')
const syncPage = read('app/(dashboard)/sync/page.tsx')

assertIncludes(dataSyncRoute, 'from services.manager_tenure_metric_service import ManagerTenureMetricService', 'data sync imports manager tenure metric service')
assertIncludes(dataSyncRoute, 'manager_tenure_start = max(active_begin_dates)', 'data sync uses conservative current team tenure start')
assertIncludes(dataSyncRoute, '_upsert_research_profile_from_sync', 'data sync persists research profile tenure start')
assertIncludes(dataSyncRoute, 'tenure_metrics = ManagerTenureMetricService().calculate_and_save_for_fund(wind_code)', 'data sync calculates manager tenure metrics')
assertIncludes(dataSyncRoute, '"tenure_metrics": tenure_metrics', 'data sync returns manager tenure metric result')

assertIncludes(reportsRoute, '_ensure_manager_tenure_section(report_content, managers, manager_tenure_metrics)', 'fund report appends manager tenure section for all modes')
assertIncludes(reportsRoute, '"manager_tenure_status": "available" if manager_tenure_metrics else "unavailable"', 'fund report stores manager tenure status')
assertIncludes(evidenceReport, 'def build_manager_tenure_report_section', 'deterministic report has manager tenure section builder')
assertIncludes(evidenceReport, '## 现任经理任期切片', 'deterministic report renders manager tenure title')
assertIncludes(evidenceReport, '不能把经理历史代表作或前任经理业绩直接外推', 'manager tenure section blocks misleading attribution')
assertIncludes(syncBff, 'tenureMetrics: payload.tenure_metrics || null', 'sync BFF forwards manager tenure metrics')
assertIncludes(syncPage, '经理任期切片', 'sync page displays manager tenure metric evidence')

console.log('OK manager tenure slice evidence is synced and reported')
