import { readFileSync } from 'node:fs'

const baseUrl = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:3000'

async function fetchJson(path) {
  const response = await fetch(new URL(path, baseUrl), { cache: 'no-store' })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}: ${JSON.stringify(payload)}`)
  return payload
}

const discoverPage = readFileSync('app/(dashboard)/discover/FundDiscoverClient.tsx', 'utf8')
const simpleFundView = readFileSync('lib/simple-fund-view.ts', 'utf8')
const simpleFundDetailPage = readFileSync('app/(dashboard)/funds/[id]/page.tsx', 'utf8')
const simpleComparePage = readFileSync('app/(dashboard)/compare/page.tsx', 'utf8')
for (const required of [
  "professionalPeerGroupId(fund)",
  "这只基金尚未完成专业分类",
  "比较已锁定",
  "params.set('peerGroup', nextPeerGroup)",
]) {
  if (!discoverPage.includes(required)) throw new Error(`fund browser missing peer-group guard: ${required}`)
}

for (const [label, source] of [
  ['fund browser', simpleFundView],
  ['fund detail', simpleFundDetailPage],
  ['fund comparison', simpleComparePage],
]) {
  if (!source.includes("'insufficient'")) {
    throw new Error(`${label} must hide scores when data quality is insufficient`)
  }
}

const categories = await fetchJson('/api/fund-browser?peerGroup=%E6%8C%87%E6%95%B0-%E6%B2%AA%E6%B7%B1300&limit=30')
if (categories.source !== 'standardized_peer_group_universe') {
  throw new Error(`fund browser must disclose standardized peer-group source: ${JSON.stringify(categories)}`)
}
if (!Array.isArray(categories.data) || categories.data.length < 2) {
  throw new Error(`expected at least two HS300 peers: ${JSON.stringify(categories)}`)
}
for (const fund of categories.data) {
  if (fund.researchProfile?.peerGroup !== '指数-沪深300' || fund.researchProfile?.peerGroupId !== 'peer-index-hs300') {
    throw new Error(`cross-category fund leaked into HS300 browser: ${JSON.stringify(fund)}`)
  }
}

const search = await fetchJson('/api/fund-browser?peerGroup=%E8%B4%A7%E5%B8%81-%E7%8E%B0%E9%87%91%E7%AE%A1%E7%90%86&search=000330.OF&limit=30')
if (search.pagination?.total !== 1 || search.data?.[0]?.windCode !== '000330.OF') {
  throw new Error(`full peer-group keyword search failed: ${JSON.stringify(search)}`)
}
if (search.data[0].researchProfile?.peerGroupId !== 'peer-money-cash-management') {
  throw new Error(`money-market peer-group identity missing: ${JSON.stringify(search.data[0])}`)
}

console.log('OK fund browser filters, searches, and compares only within standardized peer groups')
