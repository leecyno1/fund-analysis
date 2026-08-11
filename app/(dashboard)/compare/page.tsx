import Link from 'next/link'
import { ArrowLeft, CircleAlert } from 'lucide-react'
import { backendApiBaseUrl, toCamelFund, type CamelFund } from '@/lib/backend-api'
import SimpleComparisonClient, { type ComparisonFund } from './SimpleComparisonClient'

export const dynamic = 'force-dynamic'

type EvaluationPayload = {
  status?: string
  classification?: {
    status?: string
    peer_group?: string
    peer_group_id?: string
    primary_benchmark?: string
  }
  peer_context?: {
    sample_status?: string
    valid_metric_peer_count?: number
    minimum_peer_count?: number
  }
  evaluation?: {
    overall_score?: number | null
    overall_grade?: string | null
    metric_scores?: Record<string, number | string | null>
  }
}

type NavPoint = {
  date: string
  nav: number
}

function parseCodes(value?: string | string[]) {
  const raw = Array.isArray(value) ? value.join(',') : value || ''
  return Array.from(new Set(raw.split(',').map((code) => code.trim().toUpperCase()).filter(Boolean))).slice(0, 6)
}

function dateYearsAgo(years: number) {
  const date = new Date()
  date.setFullYear(date.getFullYear() - years)
  return date.toISOString().slice(0, 10)
}

async function loadComparisonFund(code: string): Promise<ComparisonFund | null> {
  const endDate = new Date().toISOString().slice(0, 10)
  const [detailResponse, evaluationResponse, navResponse] = await Promise.all([
    fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}`, { cache: 'no-store' }),
    fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}/evaluation?window=1y`, { cache: 'no-store' }),
    fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}/nav?${new URLSearchParams({ start_date: dateYearsAgo(3), end_date: endDate })}`, { cache: 'no-store' }),
  ])
  if (!detailResponse.ok) return null

  const detailPayload = await detailResponse.json().catch(() => ({}))
  const fund = toCamelFund((detailPayload.fund || detailPayload) as Record<string, unknown>) as CamelFund
  const evaluation = evaluationResponse.ok
    ? await evaluationResponse.json().catch(() => ({})) as EvaluationPayload
    : {}
  const metricScores = evaluation.evaluation?.metric_scores || {}
  const rollingMetrics = { ...((fund.rollingMetrics || {}) as Record<string, Record<string, unknown>>) }
  for (const [path, value] of Object.entries(metricScores)) {
    const separator = path.indexOf('.')
    if (separator <= 0 || value == null) continue
    const metricWindow = path.slice(0, separator)
    const metricName = path.slice(separator + 1)
    rollingMetrics[metricWindow] = {
      ...(rollingMetrics[metricWindow] || {}),
      [metricName]: value,
    }
  }
  fund.rollingMetrics = rollingMetrics
  if (fund.totalAsset == null && metricScores['latest.aum'] != null) {
    fund.totalAsset = Number(metricScores['latest.aum'])
  }
  const navPayload = navResponse.ok ? await navResponse.json().catch(() => ({})) : {}
  const nav = (Array.isArray(navPayload.data) ? navPayload.data : [])
    .map((item: Record<string, unknown>) => ({ date: String(item.date || ''), nav: Number(item.nav) }))
    .filter((item: NavPoint) => item.date && Number.isFinite(item.nav) && item.nav > 0)

  return {
    fund,
    nav,
    classification: {
      status: String(evaluation.classification?.status || 'unclassified'),
      peerGroup: String(evaluation.classification?.peer_group || ''),
      peerGroupId: String(evaluation.classification?.peer_group_id || ''),
      benchmark: String(evaluation.classification?.primary_benchmark || ''),
    },
    evaluation: {
      status: String(evaluation.status || 'unavailable'),
      sampleStatus: String(evaluation.peer_context?.sample_status || 'unavailable'),
      validPeerCount: Number(evaluation.peer_context?.valid_metric_peer_count || 0),
      minimumPeerCount: Number(evaluation.peer_context?.minimum_peer_count || 0),
      score: evaluation.evaluation?.overall_score == null ? null : Number(evaluation.evaluation.overall_score),
      grade: String(evaluation.evaluation?.overall_grade || ''),
    },
  }
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ codes?: string | string[] }> }) {
  const codes = parseCodes((await searchParams).codes)
  const loaded = await Promise.all(codes.map(loadComparisonFund))
  const funds = loaded.filter((item): item is ComparisonFund => Boolean(item))

  if (funds.length < 2) {
    return (
      <div className="mx-auto max-w-3xl py-12 text-center">
        <CircleAlert className="mx-auto h-7 w-7 text-[#8d6a2f]" />
        <h1 className="mt-4 text-3xl font-bold text-[#18231e]">请先选择至少两只基金</h1>
        <p className="mt-3 text-sm leading-7 text-[#68746e]">在基金浏览器中勾选 2 至 6 只同类基金，再查看净值和风险指标。</p>
        <Link href="/discover" className="mt-7 inline-flex h-11 items-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white">
          <ArrowLeft className="h-4 w-4" />返回找基金
        </Link>
      </div>
    )
  }

  return <SimpleComparisonClient funds={funds} />
}
