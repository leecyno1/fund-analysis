import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'
import RecommendationClient, { type RecommendationCoverageGroup, type RecommendationCoverageReport } from './RecommendationClient'

export const dynamic = 'force-dynamic'

async function loadRecommendationUniverse() {
  try {
    const [fundResponse, coverageResponse] = await Promise.all([
      fetch(`${backendApiBaseUrl}/api/fund-browser?page=1&page_size=30`, { cache: 'no-store' }),
      fetch(`${backendApiBaseUrl}/api/funds/recommendation-coverage?limit=100`, { cache: 'no-store' }),
    ])
    if (!fundResponse.ok || !coverageResponse.ok) throw new Error('fund database unavailable')
    const payload = await fundResponse.json()
    const coveragePayload = await coverageResponse.json()
    const coverageGroups: RecommendationCoverageGroup[] = Array.isArray(coveragePayload.groups) ? coveragePayload.groups.map((group: Record<string, unknown>) => ({
      key: String(group.key || ''),
      name: String(group.name || group.key || ''),
      status: String(group.status || 'blocked') as 'ready' | 'partial' | 'blocked',
      minimumPeerCount: Number(group.minimum_peer_count || 0),
      classifiedCount: Number(group.classified_count || 0),
      databaseFundCount: Number(group.database_fund_count || 0),
      evaluationMethodReadyCount: Number(group.evaluation_method_ready_count || 0),
      metricReadyCount: Number(group.metric_ready_count || 0),
      styleReadyCount: Number(group.style_ready_count || 0),
      recommendationReadyCount: Number(group.recommendation_ready_count || 0),
      missingReasonCounts: group.missing_reason_counts && typeof group.missing_reason_counts === 'object'
        ? group.missing_reason_counts as Record<string, number>
        : {},
    })) : []
    const coverage: RecommendationCoverageReport = {
      summary: {
        categoryCount: Number(coveragePayload.summary?.category_count || 0),
        readyCategoryCount: Number(coveragePayload.summary?.ready_category_count || 0),
        classifiedCount: Number(coveragePayload.summary?.classified_count || 0),
        databaseFundCount: Number(coveragePayload.summary?.database_fund_count || 0),
        evaluationMethodReadyCount: Number(coveragePayload.summary?.evaluation_method_ready_count || 0),
        metricReadyCount: Number(coveragePayload.summary?.metric_ready_count || 0),
        styleReadyCount: Number(coveragePayload.summary?.style_ready_count || 0),
        recommendationReadyCount: Number(coveragePayload.summary?.recommendation_ready_count || 0),
      },
      groups: coverageGroups,
      backfillCommand: String(coveragePayload.metric_backfill?.command || 'npm run funds:backfill-peer-evaluation'),
    }
    return {
      funds: (payload.funds || []).map(toCamelFund),
      categories: coverageGroups.filter((group) => group.recommendationReadyCount > 0).map((group) => group.name),
      total: Number(payload.total || 0),
      coverage,
      error: '',
    }
  } catch {
    return {
      funds: [],
      categories: [],
      total: 0,
      coverage: { summary: null, groups: [], backfillCommand: '' } as RecommendationCoverageReport,
      error: '基金数据库暂时无法连接，无法生成候选组。',
    }
  }
}

export default async function RecommendationsPage() {
  const data = await loadRecommendationUniverse()
  return <RecommendationClient initialFunds={data.funds} initialCategories={data.categories} universeTotal={data.total} initialCoverage={data.coverage} initialError={data.error} />
}
