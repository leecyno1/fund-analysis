import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'
import FundDiscoverClient from './FundDiscoverClient'

export const dynamic = 'force-dynamic'

async function loadFunds() {
  try {
    const response = await fetch(`${backendApiBaseUrl}/api/funds?page=1&page_size=30&sort_by=updated_at&sort_order=desc`, {
      cache: 'no-store',
    })
    if (!response.ok) throw new Error('fund database unavailable')
    const payload = await response.json()
    return {
      funds: (payload.funds || []).map(toCamelFund),
      total: Number(payload.total || 0),
      source: String(payload.source || 'database'),
      error: '',
    }
  } catch {
    return {
      funds: [],
      total: 0,
      source: 'unavailable',
      error: '基金数据库暂时无法连接，请先启动后端服务。',
    }
  }
}

export default async function DiscoverPage() {
  const data = await loadFunds()
  return <FundDiscoverClient initialFunds={data.funds} initialTotal={data.total} initialSource={data.source} initialError={data.error} />
}
