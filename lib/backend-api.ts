export const backendApiBaseUrl =
  process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://127.0.0.1:8005'

type BackendRecord = Record<string, unknown>

export type CamelFund = {
  id: string
  windCode: string
  name: string
  type: string
  nav: number | null
  navDate: string | null
  totalAsset: number | null
  establishmentDate: string | null
  performanceData: Record<string, unknown>
    riskMetrics: Record<string, unknown>
    evidenceCoverageScore?: number | null
    managerIds: string[]
  scores: Array<Record<string, unknown>>
  aiReports: Array<Record<string, unknown>>
  [key: string]: unknown
}

function asRecord(value: unknown): BackendRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as BackendRecord : null
}

function asText(value: unknown, fallback = '') {
  if (value == null) return fallback
  return typeof value === 'string' ? value : String(value)
}

function asNumberOrNull(value: unknown) {
  if (value == null || value === '') return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function asStringArray(value: unknown) {
  return Array.isArray(value) ? value.map((item) => asText(item)).filter(Boolean) : []
}

function asRecordArray(value: unknown) {
  return Array.isArray(value) ? value.map((item) => asRecord(item)).filter((item): item is BackendRecord => Boolean(item)) : []
}

export function toCamelFund(fund: BackendRecord): CamelFund {
  const windCode = asText(fund.wind_code ?? fund.windCode)
  const researchProfile = asRecord(fund.research_profile ?? fund.researchProfile)
  const trust = asRecord(fund.trust)

  return {
    id: asText(fund.id ?? windCode),
    windCode,
    name: asText(fund.name),
    type: asText(fund.type),
    managerIds: asStringArray(fund.manager_ids ?? fund.managerIds),
    managers: (Array.isArray(fund.managers) ? fund.managers : []).map((manager) => {
      const managerRecord = asRecord(manager) || {}
      return ({
        managerId: asText(managerRecord.manager_id ?? managerRecord.managerId ?? managerRecord.wind_code ?? managerRecord.windCode),
        windCode: asText(managerRecord.wind_code ?? managerRecord.windCode ?? managerRecord.manager_id ?? managerRecord.managerId),
        name: asText(managerRecord.name),
        company: asText(managerRecord.company),
        education: asText(managerRecord.education),
        workYears: asNumberOrNull(managerRecord.work_years ?? managerRecord.workYears),
        managementYears: asNumberOrNull(managerRecord.management_years ?? managerRecord.managementYears),
        currentFunds: asStringArray(managerRecord.current_funds ?? managerRecord.currentFunds),
        beginDate: managerRecord.begin_date == null && managerRecord.beginDate == null ? null : asText(managerRecord.begin_date ?? managerRecord.beginDate),
        endDate: managerRecord.end_date == null && managerRecord.endDate == null ? null : asText(managerRecord.end_date ?? managerRecord.endDate),
        source: asText(managerRecord.source, 'tushare.fund_manager'),
      })
    }),
    nav: asNumberOrNull(fund.nav),
    navDate: fund.nav_date == null && fund.navDate == null ? null : asText(fund.nav_date ?? fund.navDate),
    totalAsset: asNumberOrNull(fund.total_asset ?? fund.totalAsset),
    establishmentDate: fund.establishment_date == null && fund.establishmentDate == null ? null : asText(fund.establishment_date ?? fund.establishmentDate),
    operationStatus: fund.operation_status ?? fund.operationStatus ?? null,
    salesStatus: fund.sales_status ?? fund.salesStatus ?? null,
    feeInfo: fund.fee_info ?? fund.feeInfo ?? null,
    salesRule: fund.sales_rule ?? fund.salesRule ?? null,
    benchmark: fund.benchmark ?? null,
    peerPercentiles: fund.peer_percentiles ?? fund.peerPercentiles ?? null,
    performanceData: asRecord(fund.performance_data ?? fund.performance ?? fund.performanceData) || {},
    riskMetrics: asRecord(fund.risk_metrics ?? fund.riskMetrics) || {},
    screeningScore: fund.screening_score ?? fund.screeningScore ?? null,
    evidenceCoverageScore: asNumberOrNull(fund.evidence_coverage_score ?? fund.evidenceCoverageScore),
    marketResearchChecklist: fund.market_research_checklist ?? fund.marketResearchChecklist ?? null,
    holdingCount: asNumberOrNull(fund.holding_count ?? fund.holdingCount),
    updatedAt: fund.updated_at ?? fund.updatedAt ?? null,
    researchProfile: researchProfile
      ? {
          primaryBenchmark: researchProfile.primary_benchmark ?? researchProfile.primaryBenchmark ?? '',
          secondaryBenchmark: researchProfile.secondary_benchmark ?? researchProfile.secondaryBenchmark ?? null,
          peerGroup: researchProfile.peer_group ?? researchProfile.peerGroup ?? '',
          styleLabel: researchProfile.style_label ?? researchProfile.styleLabel ?? '',
          strategyTags: researchProfile.strategy_tags ?? researchProfile.strategyTags ?? [],
          managerTenureStart: researchProfile.manager_tenure_start ?? researchProfile.managerTenureStart ?? null,
          capacityNotes: researchProfile.capacity_notes ?? researchProfile.capacityNotes ?? null,
          dataQualityNotes: researchProfile.data_quality_notes ?? researchProfile.dataQualityNotes ?? null,
          evidence: researchProfile.evidence ?? null,
        }
      : null,
    rollingMetrics: fund.rolling_metrics ?? fund.rollingMetrics ?? {},
    dataQuality: fund.data_quality ?? fund.dataQuality ?? null,
    professionalScoring: fund.professional_scoring ?? fund.professionalScoring ?? null,
    scores: asRecordArray(fund.scores),
    aiReports: asRecordArray(fund.ai_reports ?? fund.aiReports),
    trust: trust
      ? {
          dataAsOf: trust.data_as_of ?? trust.dataAsOf ?? null,
          syncedAt: trust.synced_at ?? trust.syncedAt ?? null,
          scoreAsOf: trust.score_as_of ?? trust.scoreAsOf ?? null,
          scoreCount: trust.score_count ?? trust.scoreCount ?? 0,
          reportCount: trust.report_count ?? trust.reportCount ?? 0,
          dataQualityStatus: trust.data_quality_status ?? trust.dataQualityStatus ?? 'unknown',
          dataQualityScore: trust.data_quality_score ?? trust.dataQualityScore ?? 0,
          dataQualityIssues: trust.data_quality_issues ?? trust.dataQualityIssues ?? [],
        }
      : undefined,
  }
}

export function toSnakePool(pool: Record<string, unknown>) {
  return {
    ...pool,
    is_default: pool.is_default ?? pool.isDefault,
    created_at: pool.created_at ?? pool.createdAt,
    updated_at: pool.updated_at ?? pool.updatedAt,
  }
}

export function toSnakePoolMember(member: Record<string, unknown>) {
  return {
    ...member,
    pool_id: member.pool_id ?? member.poolId,
    fund_id: member.fund_id ?? member.fundId,
    latest_conclusion: member.latest_conclusion ?? member.latestConclusion,
    next_review_date: member.next_review_date ?? member.nextReviewDate,
    risk_notes: member.risk_notes ?? member.riskNotes,
    created_at: member.created_at ?? member.createdAt,
    updated_at: member.updated_at ?? member.updatedAt,
  }
}
