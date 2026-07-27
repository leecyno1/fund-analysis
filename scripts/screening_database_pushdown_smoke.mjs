import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const screeningRoute = readFileSync(join(root, 'app/api/screening/route.ts'), 'utf8')
const fundRoute = readFileSync(join(root, 'backend/routes/funds.py'), 'utf8')
const fundRepo = readFileSync(join(root, 'backend/repositories/fund_repo.py'), 'utf8')

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

assertIncludes(screeningRoute, "page_size: String(limit)", 'screening BFF uses exact page size after DB pushdown')
assertNotIncludes(screeningRoute, 'Math.max(limit * 5, limit)', 'screening BFF must not sample a larger page then filter locally')
assertIncludes(screeningRoute, "tradable_only: 'true'", 'screening BFF excludes non-tradable funds by default')
assertIncludes(screeningRoute, "const purchasePlan = criteria.purchasePlan === 'lump_sum' ? 'lump_sum' : 'sip'", 'screening BFF normalizes purchase plan')
assertIncludes(screeningRoute, 'const safePlannedAmount = Number.isFinite(plannedAmount) && plannedAmount > 0 ? plannedAmount : null', 'screening BFF normalizes planned amount')
assertIncludes(screeningRoute, 'purchase_plan: purchasePlan', 'screening BFF pushes purchase plan into backend sales-rule gate')
assertIncludes(screeningRoute, "backendParams.set('planned_amount', String(safePlannedAmount))", 'screening BFF pushes planned amount into backend sales-rule gate')
assertIncludes(screeningRoute, "if (criteria.salesRuleComplete === true) backendParams.set('sales_rule_complete', 'true')", 'screening BFF can push strict sales-rule completeness')
assertIncludes(screeningRoute, 'const screeningScore = Number(fund.screeningScore)', 'screening BFF local score check recognizes database screening score')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'return_1y_min'", 'screening return lower bound pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'return_1y_max'", 'screening return upper bound pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'return_3y_min'", 'screening 3y return lower bound pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'return_3y_max'", 'screening 3y return upper bound pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'max_drawdown_1y_max'", 'screening drawdown pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'volatility_1y_max'", 'screening volatility pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'sharpe_1y_min'", 'screening sharpe pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'screening_score_min'", 'screening score lower bound pushdown')
assertIncludes(screeningRoute, "setNumberParam(backendParams, 'screening_score_max'", 'screening score upper bound pushdown')
assertIncludes(screeningRoute, "screeningSource: 'database_predicate_pushdown'", 'screening source disclosure')
assertIncludes(screeningRoute, 'backendQuery: backendParams.toString()', 'screening backend query disclosure')
assertIncludes(screeningRoute, 'plannedAmount: safePlannedAmount', 'screening BFF returns planned amount context')

for (const name of [
  'return_1y_max',
  'return_3y_min',
  'return_3y_max',
  'volatility_1y_max',
  'screening_score_max',
]) {
  assertIncludes(fundRoute, `${name}: Optional[float] = Query`, `fund API accepts ${name}`)
  assertIncludes(fundRepo, `${name}: Optional[float] = None`, `fund repo accepts ${name}`)
  assertIncludes(fundRepo, `params["${name}"] = ${name}`, `fund repo binds ${name}`)
}

assertIncludes(fundRepo, 'return_3y_raw', 'fund repo uses 3y return expression')
assertIncludes(fundRepo, 'volatility_1y_raw', 'fund repo uses volatility expression')
assertIncludes(fundRepo, 'screening_score_expr}) <= :screening_score_max', 'fund repo score upper bound SQL')

console.log('OK screening pushes investor filters into database-backed full-market query')
