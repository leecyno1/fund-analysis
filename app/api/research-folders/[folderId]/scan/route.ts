import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export async function POST(_request: Request, { params }: { params: Promise<{ folderId: string }> }) {
  const { folderId } = await params
  try {
    const response = await fetch(`${backendApiBaseUrl}/api/research-folders/${encodeURIComponent(folderId)}/scan`, {
      method: 'POST',
      cache: 'no-store',
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(response.ok ? payload : { error: payload.detail || '扫描失败' }, { status: response.status })
  } catch {
    return NextResponse.json({ error: '扫描服务暂时不可用' }, { status: 503 })
  }
}
