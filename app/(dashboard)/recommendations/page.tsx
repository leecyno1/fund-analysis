import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'
import RecommendationClient from './RecommendationClient'

export const dynamic = 'force-dynamic'

async function loadRecommendationUniverse() {
  try {
    const [fundResponse, categoryResponse] = await Promise.all([
      fetch(`${backendApiBaseUrl}/api/fund-browser?page=1&page_size=30`, { cache: 'no-store' }),
      fetch(`${backendApiBaseUrl}/api/funds/recommendation-categories?limit=100`, { cache: 'no-store' }),
    ])
    if (!fundResponse.ok || !categoryResponse.ok) throw new Error('fund database unavailable')
    const payload = await fundResponse.json()
    const categoryPayload = await categoryResponse.json()
    return {
      funds: (payload.funds || []).map(toCamelFund),
      categories: (categoryPayload.categories || []).map((item: { name?: string }) => String(item.name || '')).filter(Boolean),
      total: Number(payload.total || 0),
      error: '',
    }
  } catch {
    return { funds: [], categories: [], total: 0, error: '基金数据库暂时无法连接，无法生成候选组。' }
  }
}

export default async function RecommendationsPage() {
  const data = await loadRecommendationUniverse()
  return <RecommendationClient initialFunds={data.funds} initialCategories={data.categories} universeTotal={data.total} initialError={data.error} />
}
