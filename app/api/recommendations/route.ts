import { NextResponse } from 'next/server'
import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'

const MAX_EVALUATED_FUNDS = 30

function peerGroupOf(fund: Record<string, unknown>) {
  const profile = fund.research_profile && typeof fund.research_profile === 'object'
    ? fund.research_profile as Record<string, unknown>
    : {}
  return String(profile.peer_group || fund.type || '').trim()
}

export async function GET(request: Request) {
  const category = new URL(request.url).searchParams.get('category')?.trim() || ''
  if (!category) {
    return NextResponse.json({ error: '请先选择基金类别' }, { status: 400 })
  }

  try {
    const response = await fetch(
      `${backendApiBaseUrl}/api/funds/recommendation-universe?${new URLSearchParams({ peer_group: category, limit: String(MAX_EVALUATED_FUNDS) })}`,
      { cache: 'no-store' },
    )
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail?.message || payload.detail || '基金数据库不可用')

    const matchingFunds = ((payload.funds || []) as Record<string, unknown>[])
      .filter((fund) => peerGroupOf(fund) === category)
      .slice(0, MAX_EVALUATED_FUNDS)

    const evaluated = await Promise.all(matchingFunds.map(async (fund) => {
      const code = String(fund.wind_code || '')
      if (!code) return null
      try {
        const evaluationResponse = await fetch(
          `${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}/evaluation?window=1y`,
          { cache: 'no-store', signal: AbortSignal.timeout(12_000) },
        )
        const evaluation = await evaluationResponse.json().catch(() => ({}))
        if (!evaluationResponse.ok) return null
        const professionalScoring = evaluation.evaluation || {}
        if (
          evaluation.status !== 'ok'
          || evaluation.peer_context?.sample_status !== 'sufficient'
          || evaluation.peer_context?.peer_group !== category
          || professionalScoring.overall_score == null
        ) return null
        return toCamelFund({
          ...fund,
          professional_scoring: {
            ...professionalScoring,
            status: evaluation.status,
            calculation_method: professionalScoring.calculation_method,
          },
          peer_percentiles: {
            metrics: professionalScoring.peer_percentiles || {},
            peer_context: evaluation.peer_context || {},
          },
        })
      } catch {
        return null
      }
    }))

    return NextResponse.json({
      data: evaluated.filter(Boolean),
      category,
      evaluated: matchingFunds.length,
      available: evaluated.filter(Boolean).length,
      truncated: matchingFunds.length >= MAX_EVALUATED_FUNDS,
      source: 'category_gated_professional_evaluation',
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '无法读取同类基金评价' },
      { status: 503 },
    )
  }
}
