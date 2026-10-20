import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const dynamic = 'force-dynamic'

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params
    const { searchParams } = new URL(request.url)
    const quarters = searchParams.get('quarters') || '4'
    const refresh = searchParams.get('refresh') || 'false'
    const backendUrl = new URL(
      `/api/funds/${encodeURIComponent(id)}/attribution-conclusion`,
      backendApiBaseUrl,
    )
    backendUrl.searchParams.set('quarters', quarters)
    backendUrl.searchParams.set('refresh', refresh)
    const response = await fetch(backendUrl, {
      cache: 'no-store',
      signal: AbortSignal.timeout(120_000),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json(
        { error: payload.detail || payload.error || '归因结论暂时不可用' },
        { status: response.status },
      )
    }
    return NextResponse.json(payload)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '归因结论暂时不可用' },
      { status: 503 },
    )
  }
}
