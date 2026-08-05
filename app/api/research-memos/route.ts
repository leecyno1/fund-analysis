import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const url = new URL(request.url)
  const backendParams = new URLSearchParams({
    page: url.searchParams.get('page') || '1',
    page_size: url.searchParams.get('limit') || '50',
  })
  for (const key of ['keyword', 'manager_id', 'tags']) {
    const value = url.searchParams.get(key)
    if (value) backendParams.set(key, value)
  }

  try {
    const response = await fetch(`${backendApiBaseUrl}/api/research-reports/?${backendParams.toString()}`, {
      cache: 'no-store',
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail || '调研纪要库不可用')
    return NextResponse.json(payload)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '无法读取调研纪要' },
      { status: 503 },
    )
  }
}
