import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const dynamic = 'force-dynamic'

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params
    const response = await fetch(
      `${backendApiBaseUrl}/api/funds/${encodeURIComponent(id)}/research-snapshot`,
      { cache: 'no-store', signal: AbortSignal.timeout(120_000) },
    )
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(
      response.ok ? payload : { error: payload.detail || payload.error || '基金研究快照不可用' },
      { status: response.status },
    )
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '基金研究快照不可用' },
      { status: 503 },
    )
  }
}
