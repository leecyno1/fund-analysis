import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

// Transpile the real client module (type-only import is erased) and capture its exports.
const path = new URL('../lib/fund-research/market/market-workbench.ts', import.meta.url)
const js = ts.transpileModule(readFileSync(path, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const module = { exports: {} }
new Function('exports', 'module', 'require', js)(module.exports, module, () => ({}))
const { getReturn1y, getMaxDrawdown1y, getSharpe1y } = module.exports

// Shape mirrors the live backend fund record after toCamelFund (inner keys stay snake_case,
// rollingMetrics is window-keyed).
const fund = {
  performanceData: { return_1y: 0.12, annualized_return_1y: 0.11, sharpe_ratio: 1.3, total_return: 0.12 },
  riskMetrics: { max_drawdown_1y: -0.08, max_drawdown: -0.2, volatility_1y: 0.15 },
  rollingMetrics: { '1y': { sharpe_ratio: 1.25, annualized_return: 0.11, max_drawdown: -0.08, total_return: 0.12 } },
}

test('getSharpe1y reads the real backend sharpe key', () => {
  assert.equal(getSharpe1y(fund), 1.3)
})

test('getSharpe1y falls back to rolling 1y window', () => {
  const only = { performanceData: {}, riskMetrics: {}, rollingMetrics: { '1y': { sharpe_ratio: 0.9 } } }
  assert.equal(getSharpe1y(only), 0.9)
})

test('getSharpe1y is null when genuinely absent', () => {
  assert.equal(getSharpe1y({ performanceData: {}, riskMetrics: {}, rollingMetrics: {} }), null)
})

test('getReturn1y reads 1y return', () => {
  assert.equal(getReturn1y(fund), 0.12)
})

test('getMaxDrawdown1y reads the 1y drawdown not the full-window one', () => {
  assert.equal(getMaxDrawdown1y(fund), -0.08)
})
