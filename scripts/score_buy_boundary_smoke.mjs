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

function assertNotIncludes(content, unexpected, label) {
  if (content.includes(unexpected)) {
    throw new Error(`${label} must not include buy-signal text: ${unexpected}`)
  }
}

const scoreRoute = read('app/api/scores/route.ts')
const scoringLib = read('lib/scoring.ts')

for (const [label, content] of [
  ['score route', scoreRoute],
  ['scoring lib', scoringLib],
]) {
  assertNotIncludes(content, '具有一定的投资价值', label)
  assertNotIncludes(content, '建议谨慎投资', label)
}

assertIncludes(scoreRoute, 'buyBeforeBoundary', 'score route exposes research boundary metadata')
assertIncludes(scoreRoute, '评分仅用于研究排序', 'score route labels score as research ranking')
assertIncludes(scoreRoute, '必须通过材料核验、R1-R5 适当性、费用、赎回、限购、净值回放和正式研究复核报告门禁', 'score route lists research-review gates')
assertIncludes(scoreRoute, '只用于基金研究排序', 'score route scopes score to research ranking')
assertIncludes(scoreRoute, '仍需完成正式研究证据复核', 'score route summary avoids direct decision copy')
assertIncludes(scoringLib, '只能作为重点研究线索', 'scoring lib high score is research-only')
assertIncludes(scoringLib, '不应直接进入正式研究清单', 'scoring lib low score avoids direct decision wording')

console.log('OK score API and scoring library keep scores as research signals, not buy advice')
