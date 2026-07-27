import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))

function assertFile(relativePath) {
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

const factorRoute = assertFile('app/api/investment-analysis/fund/[windCode]/factor-lens/route.ts')
assertIncludes(factorRoute, '/api/investment-analysis/fund/', 'factor lens BFF')

const attributionRoute = assertFile('app/api/investment-analysis/fund/[windCode]/attribution/route.ts')
assertIncludes(attributionRoute, '/api/investment-analysis/fund/', 'attribution BFF')

const advancedPage = assertFile('app/(dashboard)/analysis/advanced/page.tsx')
assertIncludes(advancedPage, '高级基金研究', 'advanced analysis page')
assertIncludes(advancedPage, '因子镜头', 'advanced analysis page')
assertIncludes(advancedPage, '主动归因', 'advanced analysis page')

const analysisHub = assertFile('app/(dashboard)/analysis/page.tsx')
assertIncludes(analysisHub, '/analysis/advanced', 'analysis hub advanced entry')

console.log('OK advanced fund research frontend BFF and page entry')
