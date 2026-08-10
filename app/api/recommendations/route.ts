import { NextResponse } from 'next/server'
import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'

type UnknownRecord = Record<string, unknown>

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as UnknownRecord : {}
}

function toRecommendationFund(value: unknown) {
  const candidate = asRecord(value)
  const snapshot = asRecord(candidate.research_snapshot)
  const snapshotEvaluation = asRecord(snapshot.evaluation)
  return toCamelFund({
    ...candidate,
    ...asRecord(snapshot.fund),
    managers: snapshot.managers ?? candidate.managers,
    research_profile: snapshot.research_profile ?? candidate.research_profile,
    rolling_metrics: snapshot.rolling_metrics ?? candidate.rolling_metrics,
    professional_scoring: asRecord(snapshotEvaluation.evaluation),
    recommendation_evidence: snapshot.recommendation_evidence ?? candidate.recommendation_evidence,
  })
}

export async function GET(request: Request) {
  const url = new URL(request.url)
  const category = url.searchParams.get('category')?.trim() || ''
  const style = url.searchParams.get('style')?.trim() || ''
  if (!category) {
    return NextResponse.json({ error: '请先选择基金类别' }, { status: 400 })
  }

  try {
    const backendParams = new URLSearchParams({ peer_group: category, limit: '10' })
    if (style) backendParams.set('style', style)
    const response = await fetch(`${backendApiBaseUrl}/api/funds/recommendation-candidates?${backendParams}`, { cache: 'no-store' })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail?.message || payload.detail || '基金数据库不可用')

    return NextResponse.json({
      data: ((payload.candidates || []) as Record<string, unknown>[]).map(toRecommendationFund),
      category,
      style: style || null,
      peerUniverseCount: Number(payload.peer_universe_count || 0),
      evidenceEligibleCount: Number(payload.evidence_eligible_count || 0),
      styleMatchedCount: Number(payload.style_matched_count || 0),
      excludedCount: Number(payload.excluded_count || 0),
      excludedReasonCounts: asRecord(payload.excluded_reason_counts),
      availableStyles: Array.isArray(payload.available_styles) ? payload.available_styles : [],
      methodologyVersion: String(payload.methodology_version || ''),
      source: String(payload.source || 'full_peer_group_category_evaluation'),
    })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '无法读取同类基金评价' },
      { status: 503 },
    )
  }
}
