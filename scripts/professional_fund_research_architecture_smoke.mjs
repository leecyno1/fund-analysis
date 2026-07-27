import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const root = process.cwd()

function read(relativePath) {
  const fullPath = join(root, relativePath)
  if (!existsSync(fullPath)) throw new Error(`Missing required file: ${relativePath}`)
  return readFileSync(fullPath, 'utf8')
}

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) throw new Error(`${label} missing: ${expected}`)
}

function assertNotIncludes(content, forbidden, label) {
  if (content.includes(forbidden)) throw new Error(`${label} must not include: ${forbidden}`)
}

const architecture = read('docs/architecture/professional-fund-research-architecture.md')
const modules = read('lib/research-platform/core-modules.ts')
const dashboardLayout = read('app/(dashboard)/layout.tsx')
const investorSelectionPage = read('app/(dashboard)/investor-selection/page.tsx')
const salesRulesPage = read('app/(dashboard)/sales-rules/page.tsx')
const alertsPage = read('app/(dashboard)/alerts/page.tsx')
const poolsPage = read('app/(dashboard)/pools/page.tsx')
const rankingsPage = read('app/(dashboard)/rankings/page.tsx')
const legacyRedirect = read('app/(dashboard)/legacyResearchRedirect.ts')
const routes = read('lib/research-platform/routes.ts')

for (const phrase of [
  '不覆盖交易、购买或风控',
  '全市场研究库',
  '同类横评',
  '持仓画像',
  '经理与公司研究',
  '研究报告生命周期',
  'OpenBB',
  'QuantStats',
  'FinGPT',
]) {
  assertIncludes(architecture, phrase, `professional architecture documents ${phrase}`)
}

for (const moduleName of [
  'research-universe',
  'fund-profile',
  'peer-comparison',
  'holding-exposure',
  'manager-and-company-research',
  'research-report-lifecycle',
  'evidence-ledger',
  'data-ingestion',
]) {
  assertIncludes(modules, moduleName, `core module registry includes ${moduleName}`)
}

for (const mergedRoute of [
  '/investor-selection',
  '/sales-rules',
  '/alerts',
  '/pools',
  '/rankings',
]) {
  assertIncludes(modules, mergedRoute, `core module registry declares merged route ${mergedRoute}`)
}

for (const obsoleteNav of ['投资者选基', '销售规则', '基金池', '基金复查队列', '基金排行榜']) {
  assertNotIncludes(dashboardLayout, obsoleteNav, 'dashboard navigation removes redundant module label')
}

for (const activeNav of ['全市场研究库', '同类横评', '研究报告', '数据证据', '基金经理']) {
  assertIncludes(dashboardLayout, activeNav, `dashboard navigation keeps canonical label ${activeNav}`)
}

assertIncludes(legacyRedirect, 'redirect(mergedResearchRouteTarget(pathname))', 'legacy redirect helper centralizes page redirect')
assertIncludes(routes, 'mergedResearchRouteTarget', 'routes expose canonical merged page target')

for (const [content, route] of [
  [investorSelectionPage, '/investor-selection'],
  [salesRulesPage, '/sales-rules'],
  [alertsPage, '/alerts'],
  [poolsPage, '/pools'],
  [rankingsPage, '/rankings'],
]) {
  assertIncludes(content, 'redirectToMergedResearchRoute', `merged page uses centralized redirect for ${route}`)
  assertIncludes(content, route, `merged page declares legacy source route ${route}`)
}

console.log('OK professional fund research architecture removes redundant navigation and declares canonical modules')
