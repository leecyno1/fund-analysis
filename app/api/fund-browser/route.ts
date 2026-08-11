import { NextResponse } from 'next/server'
import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const url = new URL(request.url)
  const keyword = url.searchParams.get('search')?.trim() || ''
  const peerGroup = url.searchParams.get('peerGroup')?.trim() || ''
  const page = Math.max(1, Number(url.searchParams.get('page') || 1))
  const limit = Math.max(1, Math.min(Number(url.searchParams.get('limit') || url.searchParams.get('page_size') || 30), 100))

  try {
    const backendUrl = new URL('/api/fund-browser', backendApiBaseUrl)
    backendUrl.searchParams.set('page', String(page))
    backendUrl.searchParams.set('page_size', String(limit))
    if (peerGroup) backendUrl.searchParams.set('peer_group', peerGroup)
    if (keyword) backendUrl.searchParams.set('keyword', keyword)

    const response = await fetch(backendUrl, { cache: 'no-store' })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail?.message || payload.detail || '基金数据库不可用')

    const sourceFunds = (Array.isArray(payload.funds) ? payload.funds : []) as Record<string, unknown>[]

    return NextResponse.json({
      data: sourceFunds.slice(0, limit).map(toCamelFund),
      pagination: {
        page,
        limit,
        total: Number(payload.total || sourceFunds.length),
      },
      peerGroup,
      source: String(payload.source || 'fund_database'),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '基金浏览器暂时不可用' },
      { status: 503 },
    )
  }
}
