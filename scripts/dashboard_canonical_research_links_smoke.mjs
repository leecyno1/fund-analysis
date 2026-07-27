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
  if (content.includes(unexpected)) throw new Error(`${label} should not include stale direct link: ${unexpected}`)
}

const routes = read('lib/research-platform/routes.ts')
const dashboard = read('app/(dashboard)/page.tsx')
const acceptance = read('scripts/fund_research_acceptance_smoke.mjs')

for (const stalePath of ['/investor-selection', '/pools', '/rankings']) {
  assertIncludes(routes, `pathname === '${stalePath}'`, `canonicalResearchHref maps ${stalePath}`)
}

assertIncludes(routes, 'marketResearchHref', 'routes expose canonical full-market research href')
assertIncludes(routes, 'peerComparisonHref', 'routes expose canonical peer comparison href')
assertIncludes(routes, 'researchListHref', 'routes expose canonical research list href')
assertIncludes(routes, 'mergedResearchRouteTarget', 'routes expose merged route target seam')
assertIncludes(routes, 'merged-alerts', 'routes preserve merged alerts source')
assertIncludes(routes, 'merged-sales-rules', 'routes preserve merged sales-rules source')
assertIncludes(dashboard, 'canonicalResearchHref', 'dashboard uses canonical research href mapper')

for (const staleDirectLink of [
  'href="/investor-selection"',
  'href="/pools"',
  'href="/rankings"',
  "href: '/investor-selection",
  "href: '/pools",
  "href: '/rankings",
]) {
  assertNotIncludes(dashboard, staleDirectLink, 'dashboard canonical research links')
}

assertIncludes(acceptance, 'dashboard_canonical_research_links_smoke.mjs', 'main acceptance includes dashboard canonical link smoke')

console.log('OK dashboard routes redundant research entries through canonical research surfaces')
