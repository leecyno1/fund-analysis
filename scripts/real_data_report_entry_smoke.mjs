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

const route = read('app/api/reports/real-data/route.ts')
const syncPage = read('app/(dashboard)/sync/page.tsx')
const backendReports = read('backend/routes/reports.py')

assertIncludes(route, '/api/data-sync/funds/', 'real data report route syncs Tushare data first')
assertIncludes(route, '/api/reports/fund/', 'real data report route generates backend fund report')
assertIncludes(route, '报告已生成但未写入本地 PostgreSQL', 'real data report route enforces local persistence')
assertIncludes(route, 'mock_mode', 'real data report route rejects mock mode')
assertIncludes(route, 'TUSHARE_TOKEN', 'real data report route tells operator why real mode is blocked')
assertIncludes(route, 'MAX_CODES', 'real data report route has batch guard')
assertIncludes(route, 'normalizePurchasePlan(body.purchasePlan)', 'real data report route normalizes purchase plan')
assertIncludes(route, 'normalizePlannedAmount(body.plannedAmount, purchasePlan)', 'real data report route normalizes planned amount')
assertIncludes(route, 'salesRuleNextActionForPlan(purchasePlan)', 'real data report route uses purchase-plan aware sales-rule next action')
assertIncludes(route, '先补齐申购、赎回、起购金额、限购和销售风险等级。', 'real data report lump-sum next action skips SIP-only fields')
assertIncludes(route, 'purchase_plan: options.purchasePlan', 'real data report route forwards purchase plan to backend report generation')
assertIncludes(route, 'planned_amount: String(options.plannedAmount)', 'real data report route forwards planned amount to backend report generation')
assertIncludes(route, 'purchasePlan: metadata.purchasePlan', 'real data report route preserves backend report purchase plan')
assertIncludes(route, 'plannedAmount: Number.isFinite(Number(metadata.plannedAmount))', 'real data report route preserves backend report planned amount')
assertIncludes(route, 'persistReportPurchasePlan(report.id, purchasePlan, plannedAmount)', 'real data report route backfills saved report purchase plan and amount')
assertIncludes(route, "generation_params = COALESCE(generation_params, '{}'::jsonb)", 'real data report route updates saved generation params')
assertIncludes(route, 'client.json({ purchasePlan, plannedAmount })', 'real data report route writes planned amount into saved metadata')
assertIncludes(route, "data_sources = jsonb_set(", 'real data report route updates saved data source summary')
assertIncludes(route, 'getSalesRuleGapsForCodes', 'real data report route checks sales-rule gate after report save')
assertIncludes(route, "getSalesRuleGapsForCodes([windCode], 1, { purchasePlan, plannedAmount })", 'real data report route checks sales-rule gate by purchase plan and amount')
assertIncludes(route, 'purchaseContextParams(purchasePlan, plannedAmount)', 'real data report route builds amount-aware follow-up links')
assertIncludes(route, 'purchasePlan,', 'real data report route exposes purchase plan')
assertIncludes(route, 'plannedAmount,', 'real data report route exposes planned amount')
assertIncludes(route, 'currentSalesRuleGate', 'real data report route returns current sales-rule gate')
assertIncludes(route, 'buyBeforeAction', 'real data report route returns buy-before next action')
assertIncludes(route, '补证后再判断', 'real data report route blocks formal buy-before action when rules missing')

assertIncludes(syncPage, '拉取真实数据并生成报告', 'sync page exposes real data report action')
assertIncludes(syncPage, '/api/reports/real-data', 'sync page calls real data report API')
assertIncludes(syncPage, 'purchasePlan,', 'sync page sends purchase plan into real data report API')
assertIncludes(syncPage, 'plannedAmount: currentPlannedAmount()', 'sync page sends planned amount into real data report API')
assertIncludes(syncPage, '研究口径', 'sync page shows research-plan scope')
assertIncludes(syncPage, '计划金额', 'sync page shows planned amount scope')
assertIncludes(syncPage, 'purchaseContextParams(parsedFundCodes)', 'sync page sales-rule links preserve purchase plan and amount')
assertIncludes(syncPage, '真实数据研究报告结果', 'sync page renders real report result panel')
assertIncludes(syncPage, '打开报告', 'sync page links saved reports')
assertIncludes(syncPage, '查看本地研究报告', 'sync page links report library')
assertIncludes(syncPage, 'real-data-report-sales-rule-gate', 'sync page renders real report sales-rule gate')
assertIncludes(syncPage, 'real-data-report-buy-before-action', 'sync page renders buy-before next action')
assertIncludes(syncPage, '报告已保存，但不能作为正式研究结论', 'sync page keeps hard gate after real report generation')
assertIncludes(syncPage, '研究下一步', 'sync page explains next research action')

assertIncludes(backendReports, 'purchase_plan: str = Query("sip"', 'backend fund report accepts purchase plan')
assertIncludes(backendReports, 'planned_amount: Optional[float] = Query(None', 'backend fund report accepts planned amount')
assertIncludes(backendReports, '"purchasePlan": safe_purchase_plan', 'backend fund report stores purchase plan in generation params')
assertIncludes(backendReports, '"plannedAmount": safe_planned_amount', 'backend fund report stores planned amount in generation params')
assertIncludes(backendReports, '"summary": {', 'backend fund report stores summary context')

console.log('OK real data report entry syncs Tushare data, saves reports, and exposes report links')
