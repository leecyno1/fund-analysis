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

function assertNotIncludes(content, unexpected, label) {
  if (content.includes(unexpected)) throw new Error(`${label} should not include stale dashboard copy: ${unexpected}`)
}

const dashboard = read('app/(dashboard)/page.tsx')
const acceptance = read('scripts/fund_research_acceptance_smoke.mjs')

for (const expected of [
  '基金研究路径工作台',
  '画像化研究筛选',
  '同类横评',
  '研究清单',
  '材料核验',
  '研究复核作战台',
]) {
  assertIncludes(dashboard, expected, `dashboard uses research platform term ${expected}`)
}

for (const staleCopy of [
  '投资者选基',
  '基金排行榜',
  '基金池',
  '购买研究路径工作台',
  '买前研究作战台',
  '购买候选',
  '可购买',
  '买前',
  '买入',
  '购买',
]) {
  assertNotIncludes(dashboard, staleCopy, 'dashboard research semantics')
}

assertIncludes(acceptance, 'dashboard_research_semantics_smoke.mjs', 'main acceptance includes dashboard research semantics smoke')

console.log('OK dashboard uses canonical fund research semantics without legacy buy/pool/ranking labels')
