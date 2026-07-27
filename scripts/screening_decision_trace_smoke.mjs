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

const screeningRoute = read('app/api/screening/route.ts')
const screeningPage = read('app/(dashboard)/screening/page.tsx')

assertIncludes(screeningRoute, 'buildScreeningDecisionTrace', 'screening API builds per-fund decision trace')
assertIncludes(screeningRoute, 'screening_api.database_predicate_pushdown_trace_v1', 'screening trace discloses database-backed source')
assertIncludes(screeningRoute, 'criteriaEvidence', 'screening trace carries criterion-level evidence')
assertIncludes(screeningRoute, 'hardBoundary', 'screening trace preserves buy-before boundary')
assertIncludes(screeningRoute, 'screeningDecisionTrace: buildScreeningDecisionTrace', 'screening API attaches trace to each result')

assertIncludes(screeningPage, 'screeningDecisionTrace', 'screening page reads decision trace')
assertIncludes(screeningPage, 'screening-decision-trace-card', 'screening action queue displays trace card')
assertIncludes(screeningPage, '筛选命中证据', 'screening page labels why a fund matched')
assertIncludes(screeningPage, 'screeningDecisionTrace: screeningTrace', 'screening pool evidence stores trace')
assertIncludes(screeningPage, 'screeningDecisionTraceTsv', 'screening page builds decision trace TSV')
assertIncludes(screeningPage, '条件证据明细', 'screening TSV exports criterion evidence details')
assertIncludes(screeningPage, 'screening-copy-decision-trace-tsv', 'screening page can copy trace ledger TSV')
assertIncludes(screeningPage, 'screening-download-decision-trace-tsv', 'screening page can download trace ledger TSV')
assertIncludes(screeningPage, 'screeningConditionHealthRows', 'screening page builds condition health diagnosis rows')
assertIncludes(screeningPage, 'screeningConditionHealthTsv', 'screening page builds condition health TSV')
assertIncludes(screeningPage, 'downloadScreeningConditionHealthTsv', 'screening page downloads condition health TSV')
assertIncludes(screeningPage, 'screening-condition-health-diagnosis', 'screening page renders condition health diagnosis')
assertIncludes(screeningPage, 'screening-condition-health-download', 'screening page exposes condition health TSV download')
assertIncludes(screeningPage, '筛选条件健康诊断', 'screening page condition health diagnosis title')
assertIncludes(screeningPage, '结果规模是否合理', 'screening condition health checks result size')
assertIncludes(screeningPage, '筛选条件证据是否充分', 'screening condition health checks evidence')
assertIncludes(screeningPage, '销售规则是否阻断', 'screening condition health checks sales-rule blockers')
assertIncludes(screeningPage, '下一步是否能形成横评', 'screening condition health checks comparison readiness')
assertIncludes(screeningPage, '筛选诊断硬边界', 'screening condition health visible hard boundary')
assertIncludes(screeningPage, '筛选条件健康只说明“这批结果是否值得继续研究”', 'screening condition health keeps scope narrow')
assertIncludes(screeningPage, '销售规则/R1-R5、计划金额、费用、横评和研究复核报告门禁未完成前，不形成正式研究结论', 'screening condition health blocks premature formal conclusion')
assertIncludes(screeningRoute, '筛选解释只证明为什么进入研究样本', 'screening keeps explanation separate from purchase advice')
assertIncludes(screeningPage, '销售规则硬缺口或复查队列未清零前，不生成正式研究复核报告', 'screening page keeps visible hard gate guardrail')

console.log('OK screening results include criterion-level decision traces and preserve research-review boundary')
