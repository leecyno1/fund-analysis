import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const screeningRoute = readFileSync(join(root, 'backend/routes/screening.py'), 'utf8')

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

const screeningStart = screeningRoute.indexOf('async def _do_custom_screening')
const saveStart = screeningRoute.indexOf('@router.post("/save")')
if (screeningStart < 0 || saveStart < 0 || saveStart <= screeningStart) {
  throw new Error('legacy backend screening block not found')
}
const screeningBlock = screeningRoute.slice(screeningStart, saveStart)

assertNotIncludes(screeningBlock, 'get_fund_list', 'legacy screening must not sample provider page')
assertNotIncludes(screeningBlock, 'page_size=200', 'legacy screening must not cap universe at 200')
assertNotIncludes(screeningBlock, 'score_fund(perf, risk, style)', 'legacy screening must not rebuild ad-hoc provider scores')
assertNotIncludes(screeningBlock, 'matched_funds.sort', 'legacy screening must rely on database-side sorting')
assertIncludes(screeningBlock, 'get_fund_repo().list_funds', 'legacy screening database source')
assertIncludes(screeningBlock, 'tradable_only=True', 'legacy screening tradable gate')
assertIncludes(screeningBlock, 'page_size=limit', 'legacy screening exact database page size')
assertIncludes(screeningBlock, '"screening_source": "database_predicate_pushdown"', 'legacy screening source disclosure')
assertIncludes(screeningRoute, 'def _criteria_to_repo_filters', 'legacy screening criteria translator')
assertIncludes(screeningRoute, '"return_3y_min"', 'legacy screening supports 3y return lower bound')
assertIncludes(screeningRoute, '"volatility_1y_max"', 'legacy screening supports volatility bound')
assertIncludes(screeningRoute, '"source": "database_screening_score_v1"', 'legacy screening score source disclosure')

console.log('OK legacy backend screening uses database-backed full-market filters')
