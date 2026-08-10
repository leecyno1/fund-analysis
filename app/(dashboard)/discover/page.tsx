import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'
import FundDiscoverClient from './FundDiscoverClient'

export const dynamic = 'force-dynamic'

async function loadFunds() {
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
      categories: (categoryPayload.categories || []).map((item: Record<string, unknown>) => ({
        id: String(item.id || item.key || item.name || ''),
        name: String(item.name || ''),
        count: Number(item.fund_count || 0),
      })).filter((item: { id: string; name: string }) => item.id && item.name),
      total: Number(payload.total || 0),
      source: String(payload.source || 'fund_database'),
      error: '',
    }
  } catch {
    return {
      funds: [],
      categories: [],
      total: 0,
      source: 'unavailable',
      error: '基金数据库暂时无法连接，请先启动后端服务。',
    }
  }
}

export default async function DiscoverPage() {
  const data = await loadFunds()
  return <FundDiscoverClient initialFunds={data.funds} initialCategories={data.categories} initialTotal={data.total} initialSource={data.source} initialError={data.error} />
}
