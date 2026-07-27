import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const brinson = readFileSync(join(root, 'backend/lib/brinson/attribution.py'), 'utf8')
const brinsonRoute = readFileSync(join(root, 'backend/routes/brinson.py'), 'utf8')
const barra = readFileSync(join(root, 'backend/lib/barra/factor_calculation.py'), 'utf8')
const investmentService = readFileSync(join(root, 'backend/services/investment_analysis_service.py'), 'utf8')
const advancedPage = readFileSync(join(root, 'app/(dashboard)/analysis/advanced/page.tsx'), 'utf8')

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

for (const [label, content] of [
  ['brinson attribution', brinson],
  ['barra factor calculation', barra],
]) {
  assertNotIncludes(content, 'import random', label)
  assertNotIncludes(content, 'random.uniform', label)
  assertNotIncludes(content, '_mock_', label)
}

assertNotIncludes(brinson, '_estimate_stock_return', 'brinson must not hash stock codes into fake returns')
assertNotIncludes(brinson, '_estimate_industry_returns', 'brinson must not invent industry returns')
assertNotIncludes(brinson, '_estimate_industry_return', 'brinson must not hard-code benchmark industry returns')
assertIncludes(brinson, 'status": "insufficient_evidence"', 'brinson missing evidence status')
assertIncludes(brinson, '持仓明细缺失，不能计算 Brinson 行业配置/选择效应', 'brinson holding evidence gate')
assertIncludes(brinson, '行业收益率序列缺失，不能输出可验证的 Brinson 归因', 'brinson industry return evidence gate')
assertIncludes(brinson, '行业缺少基准行业收益，不能输出可验证的配置效应', 'brinson benchmark industry return evidence gate')
assertNotIncludes(brinsonRoute, 'benchmark_return = 0.05', 'brinson route must not hard-code benchmark return')
assertIncludes(brinsonRoute, '基准区间收益缺失，不能输出可验证的 Brinson 归因', 'brinson route benchmark evidence gate')

assertNotIncludes(barra, '默认波动率暴露', 'barra must not default residual volatility exposure')
assertIncludes(barra, 'status": "insufficient_evidence"', 'barra missing evidence status')
assertIncludes(barra, 'Barra 风格因子数据缺失', 'barra missing factor evidence')
assertIncludes(barra, 'Barra 风格因子 {factor} 缺失，未用启发式估算', 'barra no heuristic style factor')

assertNotIncludes(investmentService, 'synthetic_75pct_beta', 'advanced attribution must not synthesize benchmark')
assertNotIncludes(investmentService, 'value * 0.75', 'advanced attribution must not scale fund returns into benchmark')
assertIncludes(investmentService, 'insufficient_benchmark_evidence', 'advanced attribution missing benchmark source')
assertIncludes(investmentService, '补齐可验证基准或同类收益序列后再运行主动归因。', 'advanced attribution missing benchmark recommendation')
assertIncludes(investmentService, '净值收益序列少于 60 个观测，因子镜头不输出正式评分', 'factor lens short sample gate')

assertIncludes(advancedPage, '因子镜头证据不足', 'advanced page factor evidence warning')
assertIncludes(advancedPage, '主动归因证据不足', 'advanced page attribution evidence warning')
assertIncludes(advancedPage, '暂不输出主动归因结论', 'advanced page attribution missing evidence card')

console.log('OK advanced factor/attribution analysis refuses mock or synthetic evidence')
