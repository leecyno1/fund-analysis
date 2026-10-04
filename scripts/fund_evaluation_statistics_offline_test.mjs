import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

// Execute the production declarations without loading the dashboard or making requests.
function extractDeclarations(relativePath, names) {
  const path = new URL(relativePath, import.meta.url)
  const source = ts.createSourceFile(path.pathname, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  return names.map((name) => {
    const declaration = source.statements.find((statement) => (
      ts.isFunctionDeclaration(statement) && statement.name?.text === name
    ) || (
      ts.isVariableStatement(statement) && statement.declarationList.declarations.some((item) => item.name.getText(source) === name)
    ))
    assert.ok(declaration, `Missing production declaration: ${name}`)
    return declaration.getText(source)
  }).join('\n')
}

const source = [
  extractDeclarations('../lib/simple-fund-view.ts', ['asRecord', 'numberValue']),
  extractDeclarations('../app/(dashboard)/funds/[id]/SimpleFundDetailClient.tsx', [
    'dimensionLabels', 'normalizeEvaluationStatistics', 'EvaluationStatisticsPanel',
  ]),
  'export { normalizeEvaluationStatistics, EvaluationStatisticsPanel }',
].join('\n')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React },
  fileName: 'evaluation-statistics.tsx',
}).outputText

function loadPanel(statistics = null) {
  const loadedModule = { exports: {} }
  const bindings = {
    React,
    // Seed the completed request state; preserve real React hooks. SSR never runs effects.
    useState: (initial) => React.useState(typeof initial === 'boolean' ? initial : {
      key: '000001.OF:1y', data: statistics, error: '',
    }),
    useEffect: React.useEffect,
    Link: ({ children, ...props }) => React.createElement('a', props, children),
    BarChart3: () => null,
    fetch: () => { throw new Error('Offline regression must not fetch') },
  }
  new Function('module', 'exports', ...Object.keys(bindings), compiled)(
    loadedModule, loadedModule.exports, ...Object.values(bindings),
  )
  return loadedModule.exports
}

const { normalizeEvaluationStatistics } = loadPanel()
const peer = {
  wind_code: '000001.OF',
  name: '单一样本基金',
  fund_type: '债券型',
  rank: null,
  percentile: null,
  score: 76.4,
  grade: 'B',
  is_current: true,
  dimension_scores: { return: 0, risk: 85 },
  data_coverage: { available_metric_count: 4, required_metric_count: 4, coverage_rate: 100 },
}

function payload(ranking = [peer], overrides = {}) {
  return {
    status: 'insufficient',
    metric_window: '1y',
    peer_group: '测试同类组',
    classified_peer_count: 1,
    scored_peer_count: 1,
    minimum_peer_count: 5,
    coverage_rate: 100,
    ranking,
    current: { score: 76.4, rank: null, percentile: null, peer_count: 1 },
    ...overrides,
  }
}

function renderStatistics(input) {
  const statistics = normalizeEvaluationStatistics(input)
  const { EvaluationStatisticsPanel } = loadPanel(statistics)
  const html = renderToStaticMarkup(React.createElement(EvaluationStatisticsPanel, {
    fundCode: '000001.OF', window: '1y', windowLabel: '近 1 年',
  }))
  const text = (markup) => markup.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
  const cells = [...html.matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)].map(([, markup]) => text(markup))
  return { html, text: text(html), cells }
}

test('normalization retains the scored peer below the five-peer minimum', () => {
  const statistics = normalizeEvaluationStatistics(payload())
  assert.equal(statistics.ranking.length, 1, 'A scored peer must not disappear when rank is unavailable')
  const row = statistics.ranking[0]
  assert.equal(row.windCode, peer.wind_code)
  assert.equal(row.rank, null)
  assert.equal(row.percentile, null)
  assert.equal(row.score, 76.4)
  assert.deepEqual(row.dimensionScores, [{ key: 'return', score: 0 }, { key: 'risk', score: 85 }])
  assert.equal(statistics.scoredPeerCount, 1)
  assert.equal(statistics.minimumPeerCount, 5)
})

test('missing and non-finite positions stay unavailable; only missing fund codes are filtered', () => {
  for (const position of [null, undefined, '', 'not-a-number', Infinity, NaN]) {
    const statistics = normalizeEvaluationStatistics(payload([
      { ...peer, wind_code: undefined, windCode: '000002.OF', rank: position, percentile: position },
      { ...peer, wind_code: '', rank: 1, percentile: 100 },
    ]))
    assert.equal(statistics.ranking.length, 1)
    assert.equal(statistics.ranking[0].windCode, '000002.OF')
    assert.equal(statistics.ranking[0].rank, null)
    assert.equal(statistics.ranking[0].percentile, null)
  }
})

test('insufficient-sample rendering keeps the score row and marks both positions unavailable', () => {
  const rendered = renderStatistics(payload())
  assert.equal(rendered.cells.length, 6, 'The scored peer must remain visible in the table')
  assert.equal(rendered.cells[0], '暂不可用')
  assert.match(rendered.cells[1], /单一样本基金.*000001\.OF.*当前基金/)
  assert.equal(rendered.cells[2], '76.4 B 百分位 暂不可用')
  assert.match(rendered.cells[3], /收益能力 0/)
  assert.match(rendered.text, /有效样本 1 只，最低需要 5 只/)
  assert.match(rendered.text, /已评分 1 只/)
  assert.doesNotMatch(rendered.text, /百分位 0%|当前窗口还没有可排序的同类评分/)
  assert.match(rendered.html, /href="\/funds\/000001\.OF"/)
})

test('an unavailable percentile does not render as zero even when rank exists', () => {
  const rendered = renderStatistics(payload([{ ...peer, rank: 1 }]))
  assert.equal(rendered.cells[0], '1')
  assert.equal(rendered.cells[2], '76.4 B 百分位 暂不可用')
  assert.doesNotMatch(rendered.text, /百分位 0%/)
})

test('true zero percentile and scores remain numeric in normalization and rendering', () => {
  const input = payload([{ ...peer, rank: 5, percentile: 0, score: 0 }], {
    status: 'sufficient', scored_peer_count: 5, classified_peer_count: 5,
  })
  const row = normalizeEvaluationStatistics(input).ranking[0]
  assert.equal(row.rank, 5)
  assert.equal(row.percentile, 0)
  assert.equal(row.score, 0)
  const rendered = renderStatistics(input)
  assert.equal(rendered.cells[0], '5')
  assert.equal(rendered.cells[2], '0.0 B 百分位 0%')
  assert.match(rendered.cells[3], /收益能力 0/)
  assert.doesNotMatch(rendered.cells.join(' '), /暂不可用/)
})

test('ordinary numeric-string ranks and percentiles keep their existing formatting', () => {
  const input = payload([{ ...peer, rank: '2', percentile: '75.5', score: '81.25' }])
  const row = normalizeEvaluationStatistics(input).ranking[0]
  assert.equal(row.rank, 2)
  assert.equal(row.percentile, 75.5)
  assert.equal(row.score, 81.25)
  const rendered = renderStatistics(input)
  assert.equal(rendered.cells[0], '2')
  assert.equal(rendered.cells[2], '81.3 B 百分位 76%')
})
