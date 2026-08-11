import Link from 'next/link'
import { ArrowLeft, CircleAlert } from 'lucide-react'
import { backendApiBaseUrl, toCamelFund, type CamelFund } from '@/lib/backend-api'
import SimpleFundDetailClient, {
  type FundEvaluation,
  type FundNavPoint,
  type FundPeerMetric,
  type FundResearchMemo,
} from './SimpleFundDetailClient'

export const dynamic = 'force-dynamic'

type UnknownRecord = Record<string, unknown>

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as UnknownRecord : {}
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value : value == null ? '' : String(value)
}

function numberOrNull(value: unknown) {
  if (value == null || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.map(textValue).filter(Boolean) : []
}

function dateYearsAgo(years: number) {
  const date = new Date()
  date.setFullYear(date.getFullYear() - years)
  return date.toISOString().slice(0, 10)
}

function normalizeEvaluation(payload: unknown): FundEvaluation {
  const root = asRecord(payload)
  const classification = asRecord(root.classification)
  const peerContext = asRecord(root.peer_context)
  const evaluation = asRecord(root.evaluation)
  const dimensionScores = asRecord(evaluation.dimension_scores)
  const peerPercentiles = asRecord(evaluation.peer_percentiles)
  const dataQuality = asRecord(evaluation.data_quality)
  const status = textValue(root.status) || 'unavailable'
  const sampleStatus = textValue(peerContext.sample_status) || 'unavailable'
  const rawScore = numberOrNull(evaluation.overall_score)
  const score = status === 'insufficient_evidence' || textValue(dataQuality.status) === 'insufficient'
    ? null
    : rawScore

  const peerMetrics: FundPeerMetric[] = Object.entries(peerPercentiles).map(([key, value]) => {
    const metric = asRecord(value)
    return {
      key,
      label: textValue(metric.label) || key,
      value: numberOrNull(metric.value),
      unit: textValue(metric.unit),
      percentile: numberOrNull(metric.percentile),
      rank: numberOrNull(metric.rank),
      peerCount: Number(metric.peer_count || 0),
      sampleStatus: textValue(metric.sample_status),
      metricWindow: textValue(metric.metric_window),
    }
  })

  return {
    status,
    classificationStatus: textValue(classification.status) || 'unclassified',
    peerGroup: textValue(classification.peer_group || peerContext.peer_group),
    peerGroupId: textValue(classification.peer_group_id || peerContext.peer_group_id),
    benchmark: textValue(classification.primary_benchmark || peerContext.primary_benchmark),
    strategyFamily: textValue(classification.strategy_family_name || classification.strategy_family_key),
    activePassive: textValue(classification.active_passive),
    confidence: numberOrNull(classification.confidence),
    sampleStatus,
    validPeerCount: Number(peerContext.valid_metric_peer_count || 0),
    minimumPeerCount: Number(peerContext.minimum_peer_count || 0),
    score,
    grade: score == null ? '' : textValue(evaluation.overall_grade),
    dimensions: Object.entries(dimensionScores).map(([key, value]) => {
      const dimension = asRecord(value)
      return { key, score: numberOrNull(dimension.score), weight: numberOrNull(dimension.weight) }
    }),
    peerMetrics,
    positiveFactors: stringArray(evaluation.positive_factors),
    negativeFactors: stringArray(evaluation.negative_factors),
    missingItems: stringArray(root.missing_items),
    dataQualityStatus: textValue(dataQuality.status),
    dataQualityScore: numberOrNull(dataQuality.score),
  }
}

async function loadFundDetail(code: string) {
  const endDate = new Date().toISOString().slice(0, 10)
  const navParams = new URLSearchParams({ start_date: dateYearsAgo(3), end_date: endDate })
  const [snapshotResult, navResult] = await Promise.allSettled([
    fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}/research-snapshot?window=1y&include_research=true&include_attribution=false`, { cache: 'no-store' }),
    fetch(`${backendApiBaseUrl}/api/funds/${encodeURIComponent(code)}/nav?${navParams.toString()}`, { cache: 'no-store' }),
  ])

  if (snapshotResult.status !== 'fulfilled' || !snapshotResult.value.ok) return null

  const snapshotPayload = asRecord(await snapshotResult.value.json().catch(() => ({})))
  const evaluationPayload = asRecord(snapshotPayload.evaluation)
  const fund = toCamelFund({
    ...asRecord(snapshotPayload.fund),
    managers: snapshotPayload.managers,
    research_profile: snapshotPayload.research_profile,
    rolling_metrics: snapshotPayload.rolling_metrics,
    data_quality: snapshotPayload.data_quality,
    professional_scoring: asRecord(evaluationPayload.evaluation),
  }) as CamelFund
  const navPayload = navResult.status === 'fulfilled' && navResult.value.ok
    ? asRecord(await navResult.value.json().catch(() => ({})))
    : {}
  const memoPayload = asRecord(snapshotPayload.research_memos)

  const nav = (Array.isArray(navPayload.data) ? navPayload.data : [])
    .map((value) => {
      const point = asRecord(value)
      return { date: textValue(point.date), nav: Number(point.nav) }
    })
    .filter((point: FundNavPoint) => point.date && Number.isFinite(point.nav) && point.nav > 0)
    .sort((left: FundNavPoint, right: FundNavPoint) => left.date.localeCompare(right.date))

  const researchMemos: FundResearchMemo[] = (Array.isArray(memoPayload.items) ? memoPayload.items : []).map((value) => {
    const memo = asRecord(value)
    return {
      id: textValue(memo.id),
      title: textValue(memo.title),
      managerName: textValue(memo.manager_name),
      reportDate: textValue(memo.report_date),
      source: textValue(memo.source),
      summary: textValue(memo.summary),
      classifications: stringArray(memo.classifications),
      styleLabels: stringArray(memo.style_labels),
      keyPoints: stringArray(memo.key_points),
    }
  }).filter((memo: FundResearchMemo) => memo.id)

  return { fund, nav, evaluation: normalizeEvaluation(evaluationPayload), researchMemos }
}

export default async function FundDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const data = await loadFundDetail(id)

  if (!data) {
    return (
      <div className="mx-auto max-w-3xl py-12 text-center">
        <CircleAlert className="mx-auto h-7 w-7 text-[#8d6a2f]" />
        <h1 className="mt-4 text-3xl font-bold text-[#18231e]">暂时无法读取这只基金</h1>
        <p className="mt-3 text-sm leading-7 text-[#68746e]">基金代码为 {id}。请确认后端基金数据库已启动，或返回重新搜索。</p>
        <Link href="/discover" className="mt-7 inline-flex h-11 items-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white"><ArrowLeft className="h-4 w-4" />返回找基金</Link>
      </div>
    )
  }

  return <SimpleFundDetailClient {...data} />
}
