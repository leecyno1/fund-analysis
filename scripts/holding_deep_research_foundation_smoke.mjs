import { readFileSync, existsSync } from 'node:fs'
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
  if (content.includes(forbidden)) throw new Error(`${label} should not include: ${forbidden}`)
}

const schema = read('prisma/schema.prisma')
const migration = read('prisma/migrations/20260614000100_holding_deep_research/migration.sql')
const tool = read('lib/research-platform/tools/holding-deep-research.ts')
const registry = read('lib/research-platform/tools/registry.ts')
const index = read('lib/research-platform/tools/index.ts')

for (const modelName of ['model HoldingLookthroughSnapshot', 'model HoldingSimilarity']) {
  assertIncludes(schema, modelName, `schema includes ${modelName}`)
}

for (const tableName of ['holding_lookthrough_snapshots', 'holding_similarities']) {
  assertIncludes(migration, `CREATE TABLE "${tableName}"`, `migration creates ${tableName}`)
}

for (const field of [
  'topTenWeight',
  'topThreeWeight',
  'topIndustryWeight',
  'industryBuckets',
  'themeTags',
  'styleTags',
  'marketCapBuckets',
  'turnoverEstimate',
  'heavyPositionChanges',
  'overlapWeight',
  'jaccardScore',
  'commonHoldings',
  'similarity',
]) {
  assertIncludes(tool, field, `holding deep research tool covers ${field}`)
}

assertIncludes(tool, '持仓穿透', 'tool names holding look-through')
assertIncludes(tool, '行业/主题/风格标签', 'tool names industry/theme/style tags')
assertIncludes(tool, '集中度', 'tool names concentration')
assertIncludes(tool, '换手', 'tool names turnover')
assertIncludes(tool, '重仓变化', 'tool names heavy position changes')
assertIncludes(tool, '基金间持仓相似度', 'tool names fund holding similarity')
assertIncludes(tool, '不能输出行业、主题、风格或相似度结论', 'tool blocks conclusions when holdings are missing')
assertIncludes(tool, '不构成配置、交易或组合建议', 'tool keeps similarity in research-only scope')
assertIncludes(tool, 'FUND_RESEARCH_GUARDRAILS.noTradingDirective', 'tool keeps research-only guardrail')
assertNotIncludes(tool, '购买建议', 'tool must not output purchase advice')

assertIncludes(registry, 'holdingDeepResearchTool', 'tool registry includes holding deep research')
assertIncludes(index, 'HoldingDeepResearchOutput', 'tool index exports holding deep research types')

console.log('OK holding look-through and similarity foundation is modeled, tooled, and registered')
