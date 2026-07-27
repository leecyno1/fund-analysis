import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type BackendManagerDetail = {
  manager_id?: string
  name?: string
  company?: string | null
  edu?: string | null
  education?: string | null
  tenure_years?: number | null
  work_years?: number | null
  fund_count?: number | null
  avg_score?: number | null
  career?: Array<Record<string, unknown>>
  investment_philosophy?: string | null
  funds?: Array<{ wind_code?: string; name?: string; fund_name?: string; type?: string; since?: string | null; start_date?: string | null; end_date?: string | null }>
}

type EnrichedManagerFund = NonNullable<BackendManagerDetail['funds']>[number] & {
  name?: string
  type?: string
}

async function fetchFundNameMap(funds: NonNullable<BackendManagerDetail['funds']> = []) {
  const codes = Array.from(
    new Set(funds.map((fund) => fund.wind_code).filter((code): code is string => Boolean(code))),
  ).slice(0, 40)

  const entries = await Promise.all(
    codes.map(async (code) => {
      try {
        const response = await fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}`, {
          cache: 'no-store',
        })
        if (!response.ok) return null
        const payload = await response.json().catch(() => null)
        if (!payload || typeof payload !== 'object') return null
        return [
          code,
          {
            name: typeof payload.name === 'string' ? payload.name : '',
            type: typeof payload.type === 'string' ? payload.type : '',
          },
        ] as const
      } catch {
        return null
      }
    }),
  )

  return new Map(entries.filter((entry): entry is NonNullable<typeof entry> => Boolean(entry)))
}

function enrichFunds(
  funds: NonNullable<BackendManagerDetail['funds']> = [],
  fundNameMap: Map<string, { name: string; type: string }>,
): EnrichedManagerFund[] {
  return funds.map((fund) => {
    const code = fund.wind_code || ''
    const matched = code ? fundNameMap.get(code) : undefined
    return {
      ...fund,
      name: matched?.name || fund.name || fund.fund_name || code,
      fund_name: matched?.name || fund.fund_name || fund.name || code,
      type: matched?.type || fund.type || '',
    }
  })
}

async function toManagerDetail(manager: BackendManagerDetail) {
  const funds = Array.isArray(manager.funds) ? manager.funds : []
  const enrichedFunds = enrichFunds(funds, await fetchFundNameMap(funds))
  const fundCodes = enrichedFunds.map((fund) => fund.wind_code).filter((code): code is string => Boolean(code))
  const activeFundCodes = enrichedFunds
    .filter((fund) => !fund.end_date)
    .map((fund) => fund.wind_code)
    .filter((code): code is string => Boolean(code))
  return {
    id: manager.manager_id || manager.name || '',
    windCode: manager.manager_id || null,
    name: manager.name || manager.manager_id || '姓名待补',
    company: manager.company || null,
    education: manager.education || manager.edu || null,
    workYears: manager.work_years ?? null,
    managementYears: manager.tenure_years ?? null,
    currentFunds: Array.from(new Set(activeFundCodes)),
    fundCount: manager.fund_count ?? fundCodes.length,
    avgScore: manager.avg_score ?? null,
    funds: enrichedFunds,
    career: manager.career || [],
    investmentPhilosophy: manager.investment_philosophy || '',
    historicalPerformance: {},
    styleAnalysis: {},
    reports: [],
    scores: [],
    aiReports: [],
    source: 'backend.tushare.fund_manager',
  }
}

async function fetchExactManager(id: string) {
  const keyword = id.includes('|') ? id.split('|')[0] : id
  const backendParams = new URLSearchParams({
    page: '1',
    page_size: '100',
  })
  if (keyword) backendParams.set('keyword', keyword)

  const response = await fetch(`${backendApiBaseUrl}/api/managers/?${backendParams.toString()}`, {
    cache: 'no-store',
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || '获取基金经理详情失败')
  }

  const managers = Array.isArray(payload.managers) ? (payload.managers as BackendManagerDetail[]) : []
  return managers.find((manager) => manager.manager_id === id || manager.name === id) || null
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await params
    const manager = await fetchExactManager(id)
    if (!manager) {
      return NextResponse.json({ error: '基金经理不存在或本地数据未同步' }, { status: 404 })
    }

    return NextResponse.json(await toManagerDetail(manager))
  } catch (error) {
    console.error('获取基金经理详情失败:', error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '获取基金经理详情失败' },
      { status: 500 },
    )
  }
}

export async function PUT() {
  return NextResponse.json(
    { error: '基金经理来自本地 Tushare 同步数据，暂不支持前端手工更新。' },
    { status: 405 },
  )
}

export async function DELETE() {
  return NextResponse.json(
    { error: '基金经理来自本地 Tushare 同步数据，暂不支持前端删除。' },
    { status: 405 },
  )
}
