import { readFileSync } from 'node:fs'

const apiRoute = readFileSync('app/api/recommendations/route.ts', 'utf8')
const client = readFileSync('app/(dashboard)/recommendations/RecommendationClient.tsx', 'utf8')
const backendRoute = readFileSync('backend/routes/funds.py', 'utf8')

function requireText(source, text, message) {
  if (!source.includes(text)) throw new Error(`${message}: ${text}`)
}

requireText(backendRoute, '@router.get("/recommendation-candidates")', 'backend candidate-group endpoint is missing')
requireText(backendRoute, 'FundRecommendationService().build_candidate_group', 'backend endpoint must use the candidate-group service')
requireText(apiRoute, '/api/funds/recommendation-candidates', 'Next API must call the full peer-group candidate endpoint')
requireText(apiRoute, "backendParams.set('style', style)", 'Next API must pass style filtering to the backend')
requireText(client, 'recommendationEvidence(fund)', 'candidate cards must render backend recommendation evidence')
requireText(client, '主要风险', 'candidate cards must show risks')
requireText(client, '数据截至', 'candidate cards must disclose the evidence date')
requireText(client, 'void loadCandidates(category, nextStyle)', 'style changes must refresh the full peer candidate group')

for (const forbidden of [
  'MAX_EVALUATED_FUNDS',
  'Promise.all(matchingFunds.map',
  '.sort((left, right) => right.score - left.score)',
]) {
  if (apiRoute.includes(forbidden) || client.includes(forbidden)) {
    throw new Error(`recommendation flow still performs truncated or client-side selection: ${forbidden}`)
  }
}

const baseUrl = process.env.FRONTEND_BASE_URL
if (baseUrl) {
  const response = await fetch(new URL('/api/recommendations?category=%E6%8C%87%E6%95%B0-%E6%B2%AA%E6%B7%B1300', baseUrl), { cache: 'no-store' })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(`recommendation API returned HTTP ${response.status}: ${JSON.stringify(payload)}`)
  if (payload.source !== 'full_peer_group_category_evaluation') {
    throw new Error(`recommendation source is not full peer-group evaluation: ${JSON.stringify(payload)}`)
  }
  if (!Array.isArray(payload.data) || payload.data.length > 10) {
    throw new Error(`recommendation endpoint must return at most ten candidates: ${JSON.stringify(payload)}`)
  }
  if (payload.data.some((fund) => fund.researchProfile?.peerGroup !== '指数-沪深300')) {
    throw new Error(`cross-category fund leaked into recommendations: ${JSON.stringify(payload)}`)
  }
  for (const fund of payload.data) {
    const evidence = fund.recommendationEvidence || {}
    if (!evidence.reasons?.length || !evidence.risks?.length || !evidence.dataAsOf) {
      throw new Error(`candidate evidence is incomplete: ${JSON.stringify(fund)}`)
    }
  }
}

console.log('OK recommendation flow uses full peer-group evaluation and renders evidence-backed candidate groups')
