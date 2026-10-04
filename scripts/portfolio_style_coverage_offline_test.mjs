import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as icons from 'lucide-react'
import ts from 'typescript'

// Execute the real client, without importing the dashboard or running requests.
const path = new URL('../app/(dashboard)/portfolio/PortfolioClient.tsx', import.meta.url)
const source = ts.createSourceFile(path.pathname, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const client = source.statements.find((statement) => ts.isFunctionDeclaration(statement) && statement.name?.text === 'PortfolioClient')
assert.ok(client, 'Missing production PortfolioClient')
const iconImport = source.statements.find((statement) => ts.isImportDeclaration(statement) && statement.moduleSpecifier.text === 'lucide-react')
const iconBindings = Object.fromEntries(iconImport.importClause.namedBindings.elements.map((item) => [item.name.text, icons[item.name.text]]))
const stateNames = client.body.statements
  .filter(ts.isVariableStatement)
  .flatMap((statement) => [...statement.declarationList.declarations])
  .filter((item) => item.initializer && ts.isCallExpression(item.initializer) && item.initializer.expression.getText(source) === 'useState')
  .map((item) => item.name.elements[0].name.getText(source))
assert.ok(stateNames.includes('detail') && stateNames.includes('analysis'))
const compiled = ts.transpileModule(source.statements
  .filter((statement) => ts.isFunctionDeclaration(statement) || ts.isVariableStatement(statement))
  .map((statement) => statement.getText(source)).join('\n'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React },
  fileName: 'portfolio-client.tsx',
}).outputText

function renderStyle(analysis) {
  let stateIndex = 0
  const seeded = {
    detail: {
      id: 'offline', name: '离线组合', objective: null, status: 'active', targets: [], holdings: [],
      weight_summary: { holding_count: 0, weighted_count: 0, total_weight: 0, is_complete: false },
    },
    analysis,
  }
  const bindings = {
    React, ...iconBindings,
    // Seed only completed detail/analysis state; SSR preserves hooks and never runs effects.
    useState: (initial) => {
      const name = stateNames[stateIndex++]
      return React.useState(Object.hasOwn(seeded, name) ? seeded[name] : initial)
    },
    useEffect: React.useEffect,
    useCallback: React.useCallback,
    fetch: () => { throw new Error('Offline regression must not fetch') },
  }
  const loadedModule = { exports: {} }
  new Function('module', 'exports', ...Object.keys(bindings), compiled)(
    loadedModule, loadedModule.exports, ...Object.values(bindings),
  )
  const html = renderToStaticMarkup(React.createElement(loadedModule.exports.default))
  const section = html.match(/<h4\b[^>]*>风格暴露聚合[\s\S]*?(?=<h4\b[^>]*>净值收益率相关性)/)?.[0]
  assert.ok(section, 'The production style section must be rendered')
  return section.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

const quarterBasis = '各持仓最新已披露季度（可能不完全一致）'
const coverageNote = '有风格快照的持仓权重为 100.0%，不等于因子净值覆盖；未知部分不按零暴露计入。'
const positive = {
  factor: 'value', label: '价值', unit: null,
  weighted_exposure: 0.308642, covered_exposure: 1.234568, coverage: 0.25, unknown_weight: 0.75,
}
function payload(factors = [positive], overrides = {}) {
  return { style_aggregate: {
    status: 'available', reason: null, quarter_basis: quarterBasis,
    snapshot_coverage: 1, coverage_note: coverageNote, factors, ...overrides,
  } }
}

for (const { name, factor, expected } of [
  {
    name: 'positive partial coverage', factor: positive,
    expected: '价值 已覆盖部分均值 1.235 已知贡献 0.309 NAV覆盖 25.0% 未知权重 75.0%',
  },
  {
    name: 'negative partial coverage',
    factor: { ...positive, weighted_exposure: -0.308642, covered_exposure: -1.234568 },
    expected: '价值 已覆盖部分均值 -1.235 已知贡献 -0.309 NAV覆盖 25.0% 未知权重 75.0%',
  },
  {
    name: 'zero exposure is valid evidence',
    factor: { ...positive, weighted_exposure: 0, covered_exposure: 0 },
    expected: '价值 已覆盖部分均值 0.000 已知贡献 0.000 NAV覆盖 25.0% 未知权重 75.0%',
  },
  {
    name: 'full coverage has no unknown weight',
    factor: { ...positive, weighted_exposure: 1.234568, coverage: 1, unknown_weight: 0 },
    expected: '价值 已覆盖部分均值 1.235 已知贡献 1.235 NAV覆盖 100.0% 未知权重 0.0%',
  },
]) {
  test(name, () => {
    const text = renderStyle(payload([factor]))
    assert.ok(text.includes(expected), `Expected ${expected}\nActual: ${text}`)
    assert.doesNotMatch(text, /暂无风格快照|NaN|Infinity|undefined/)
  })
}

test('each factor displays its own NAV coverage and unknown weight', () => {
  const text = renderStyle(payload([
    positive,
    { factor: 'growth', label: '成长', unit: null, weighted_exposure: -0.4, covered_exposure: -0.5, coverage: 0.8, unknown_weight: 0.2 },
  ]))
  assert.match(text, /价值 已覆盖部分均值 1\.235 已知贡献 0\.309 NAV覆盖 25\.0% 未知权重 75\.0%/)
  assert.match(text, /成长 已覆盖部分均值 -0\.500 已知贡献 -0\.400 NAV覆盖 80\.0% 未知权重 20\.0%/)
})

test('100% snapshot weight is never presented as 100% NAV coverage', () => {
  const text = renderStyle(payload())
  assert.match(text, /NAV覆盖 25\.0%/)
  assert.doesNotMatch(text, /NAV覆盖 100\.0%|覆盖 100\.0% 权重的持仓|未覆盖部分为残差/)
  assert.ok(text.includes(coverageNote), 'Display the supplied note instead of the old hardcoded explanation')
})

test('quarter basis is preserved verbatim, including inconsistent-quarter warnings', () => {
  for (const quarter of [quarterBasis, '2025Q4 / 2026Q1（季度不一致）']) {
    const text = renderStyle(payload([positive], { quarter_basis: quarter }))
    assert.ok(text.includes(quarter), `Missing quarter basis: ${quarter}`)
  }
})

test('no valid factors keeps the insufficient reason, quarter and coverage note without invented metrics', () => {
  const reason = '缺少有效风格描述子或逐因子净值覆盖，暂不能聚合风格暴露。'
  const text = renderStyle(payload([], { status: 'insufficient', reason }))
  assert.ok(text.includes(reason))
  assert.ok(text.includes(quarterBasis))
  assert.ok(text.includes(coverageNote))
  assert.doesNotMatch(text, /已覆盖部分均值|已知贡献|NAV覆盖|未知权重|NaN|Infinity/)
})

test('empty analysis and an empty portfolio do not invent coverage', () => {
  for (const analysis of [null, {}, { style_aggregate: null }, { style_aggregate: { status: 'insufficient', reason: '组合暂无持仓。' } }]) {
    const text = renderStyle(analysis)
    assert.match(text, /暂无风格快照可聚合。|组合暂无持仓。/)
    assert.doesNotMatch(text, /已覆盖部分均值|已知贡献|NAV覆盖|未知权重|\d+(?:\.\d+)?%|NaN|Infinity|undefined/)
  }
})

test('Analysis declares the new coverage contract rather than legacy aggregate coverage', () => {
  const analysisType = source.statements.find((statement) => ts.isTypeAliasDeclaration(statement) && statement.name.text === 'Analysis')
  const aggregateType = analysisType.type.members.find((member) => member.name.getText(source) === 'style_aggregate').type
  const names = aggregateType.members.map((member) => member.name.getText(source))
  assert.ok(!names.includes('coverage'), 'Legacy aggregate coverage must be removed')
  for (const name of ['status', 'reason', 'quarter_basis', 'snapshot_coverage', 'coverage_note', 'factors']) {
    assert.ok(names.includes(name), `Missing aggregate field: ${name}`)
  }
  const factorType = aggregateType.members.find((member) => member.name.getText(source) === 'factors').type.typeArguments[0]
  const factorNames = factorType.members.map((member) => member.name.getText(source))
  for (const name of ['factor', 'label', 'unit', 'weighted_exposure', 'covered_exposure', 'coverage', 'unknown_weight']) {
    assert.ok(factorNames.includes(name), `Missing factor field: ${name}`)
  }
})
