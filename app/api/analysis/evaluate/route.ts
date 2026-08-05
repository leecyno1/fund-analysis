import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const windCode = String(body.windCode || '').trim().toUpperCase()
    const question = String(body.question || '').trim().slice(0, 1000)
    if (!windCode) return NextResponse.json({ error: '请选择要分析的基金' }, { status: 400 })

    const response = await fetch(
      `${backendApiBaseUrl}/api/reports/fund/${encodeURIComponent(windCode)}/evaluation-analysis`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, include_research: true }),
        cache: 'no-store',
        signal: AbortSignal.timeout(120_000),
      },
    )
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json(
        { error: payload.detail || payload.error || '基金评价分析失败' },
        { status: response.status },
      )
    }
    return NextResponse.json(payload)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '基金评价分析失败' },
      { status: 500 },
    )
  }
}
