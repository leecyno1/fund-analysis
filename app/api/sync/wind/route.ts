import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type SyncRequest = {
  type: 'fund' | 'manager' | 'all'
  codes?: string[]
}

type SyncDetail = {
  code?: string
  name?: string
  action: 'updated' | 'skipped' | 'error'
  error?: string
  reason?: string
  managerCount?: number
  managerIds?: string[]
  managerTenureStart?: string | null
  rollingMetrics?: {
    saved?: number
    windows?: string[]
  } | null
  tenureMetrics?: {
    saved?: number
    window?: string
  } | null
  warnings?: string[]
}

async function fetchJson(path: string, init?: RequestInit) {
  const response = await fetch(`${backendApiBaseUrl}${path}`, {
    cache: 'no-store',
    ...init,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `${path} 请求失败`)
  }
  return payload
}

async function assertRealBackendDataSource() {
  const health = await fetchJson('/api/health')
  if (health.mock_mode) {
    const error = new Error('后端当前仍是 Mock 模式，请配置 TUSHARE_TOKEN 并重启后端后再同步真实基金数据。')
    ;(error as Error & { status?: number }).status = 409
    throw error
  }
  return health
}

async function getFundCodes(codes?: string[]) {
  if (codes?.length) return codes
  const payload = await fetchJson('/api/funds?page=1&page_size=10&sort_by=updated_at&sort_order=desc')
  return (payload.funds || [])
    .map((fund: Record<string, unknown>) => String(fund.wind_code || ''))
    .filter(Boolean)
}

async function getManagerIds(codes?: string[]) {
  if (codes?.length) return codes
  const payload = await fetchJson('/api/managers?page=1&page_size=10')
  return (payload.managers || [])
    .map((manager: Record<string, unknown>) => String(manager.manager_id || manager.wind_code || manager.name || ''))
    .filter(Boolean)
}

async function syncFunds(codes?: string[]) {
  const fundCodes = await getFundCodes(codes)
  const summary = { created: 0, updated: 0, errors: 0 }
  const details: SyncDetail[] = []

  for (const code of fundCodes) {
    try {
      const payload = await fetchJson(`/api/data-sync/funds/${encodeURIComponent(code)}`)
      summary.updated += 1
      details.push({
        code,
        action: 'updated',
        managerCount: Number(payload.manager_count || 0),
        managerIds: payload.manager_ids || [],
        managerTenureStart: payload.manager_tenure_start || null,
        rollingMetrics: payload.rolling_metrics || null,
        tenureMetrics: payload.tenure_metrics || null,
        warnings: payload.warnings || [],
      })
    } catch (error) {
      summary.errors += 1
      details.push({
        code,
        action: 'error',
        error: error instanceof Error ? error.message : '未知错误',
      })
    }
  }

  if (fundCodes.length === 0) {
    details.push({ action: 'skipped', reason: '后端暂无可同步基金代码' })
  }

  return { summary, details }
}

async function syncManagers(codes?: string[]) {
  const managerIds = await getManagerIds(codes)
  const summary = { created: 0, updated: 0, errors: 0 }
  const details: SyncDetail[] = []

  for (const managerId of managerIds) {
    try {
      await fetchJson(`/api/data-sync/managers/${encodeURIComponent(managerId)}`)
      summary.updated += 1
      details.push({ name: managerId, action: 'updated' })
    } catch (error) {
      summary.errors += 1
      details.push({
        name: managerId,
        action: 'error',
        error: error instanceof Error ? error.message : '未知错误',
      })
    }
  }

  if (managerIds.length === 0) {
    details.push({ action: 'skipped', reason: '后端暂无可同步基金经理标识' })
  }

  return { summary, details }
}

export async function POST(request: Request) {
  try {
    await assertRealBackendDataSource()
    const body = (await request.json()) as SyncRequest
    const results = {
      funds: { created: 0, updated: 0, errors: 0 },
      managers: { created: 0, updated: 0, errors: 0 },
      details: [] as SyncDetail[],
    }

    if (body.type === 'fund' || body.type === 'all') {
      const fundResult = await syncFunds(body.codes)
      results.funds = fundResult.summary
      results.details.push(...fundResult.details)
    }

    if (body.type === 'manager' || body.type === 'all') {
      const managerResult = await syncManagers(body.codes)
      results.managers = managerResult.summary
      results.details.push(...managerResult.details)
    }

    return NextResponse.json({
      success: results.funds.errors + results.managers.errors === 0,
      message: 'Tushare 数据同步完成',
      results,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error('数据同步失败:', error)
    return NextResponse.json(
      { error: '数据同步失败', details: error instanceof Error ? error.message : '未知错误' },
      { status: (error as Error & { status?: number })?.status || 500 },
    )
  }
}

export async function GET() {
  try {
    const [health, funds, managers] = await Promise.all([
      fetchJson('/api/health'),
      fetchJson('/api/funds?page=1&page_size=1&sort_by=updated_at&sort_order=desc'),
      fetchJson('/api/managers?page=1&page_size=1').catch(() => ({ total: 0, managers: [] })),
    ])

    const latestFund = funds.funds?.[0]
    const latestManager = managers.managers?.[0]

    return NextResponse.json({
      status: health.mock_mode ? 'mock' : 'ready',
      dataSource: health.data_source || 'tushare',
      mockMode: Boolean(health.mock_mode),
      counts: {
        funds: Number(funds.total || 0),
        managers: Number(managers.total || 0),
      },
      lastSync: {
        funds: latestFund?.updated_at || null,
        managers: latestManager?.updated_at || null,
      },
      backendServiceUrl: backendApiBaseUrl,
    })
  } catch (error) {
    console.error('获取同步状态失败:', error)
    return NextResponse.json(
      { error: '获取同步状态失败', details: error instanceof Error ? error.message : '未知错误' },
      { status: 500 },
    )
  }
}
