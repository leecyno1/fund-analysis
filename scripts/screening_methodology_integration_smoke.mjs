import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))

function read(relativePath) {
  const fullPath = join(root, relativePath)
  if (!existsSync(fullPath)) throw new Error(`Missing required file: ${relativePath}`)
  return readFileSync(fullPath, 'utf8')
}

function assertIncludes(content, expected, label) {
  if (!content.includes(expected)) throw new Error(`${label} missing text: ${expected}`)
}

function assertNotIncludes(content, forbidden, label) {
  if (content.includes(forbidden)) throw new Error(`${label} should not include: ${forbidden}`)
}

const screeningRoute = read('app/api/screening/route.ts')
const screeningPage = read('app/(dashboard)/screening/page.tsx')

assertIncludes(screeningRoute, 'resolveMethodologyConfigFromData', 'screening API imports methodology repository')
assertIncludes(screeningRoute, 'buildMethodologyContext', 'screening API builds per-fund methodology context')
assertIncludes(screeningRoute, 'const methodologyConfig = await buildMethodologyContext(fund)', 'screening results build methodology config')
assertIncludes(screeningRoute, 'methodologyConfig,', 'screening results attach methodology config')
assertIncludes(screeningRoute, 'availableMethodologyEvidence', 'screening API maps available evidence into methodology tool')
assertIncludes(screeningRoute, 'data.templateKey', 'screening API exposes methodology output data')
assertIncludes(screeningRoute, 'researchTemplateKey', 'screening trace carries research template key')
assertIncludes(screeningRoute, 'methodologyMissingEvidenceFields', 'screening trace carries methodology evidence gaps')
assertIncludes(screeningRoute, '方法论模板只决定研究口径', 'screening API preserves methodology boundary')
assertNotIncludes(screeningRoute, '投委会', 'screening methodology integration must not add governance workflow')
assertNotIncludes(screeningRoute, '购买建议', 'screening methodology integration must not add purchase advice')

assertIncludes(screeningPage, 'methodologyConfig', 'screening page reads methodology config')
assertIncludes(screeningPage, '研究模板', 'screening page shows research template')
assertIncludes(screeningPage, '方法论缺口', 'screening page shows methodology gaps')
assertIncludes(screeningPage, 'methodologyMissingEvidenceFields', 'screening page exports methodology gaps')

console.log('OK screening results are wired to methodology configuration context')
