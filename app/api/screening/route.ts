import { NextResponse } from 'next/server'
import { backendApiBaseUrl, toCamelFund } from '@/lib/backend-api'
import { resolveMethodologyConfigFromData } from '@/lib/research-platform/methodology-mapping-repository'

interface ScreeningCriteria {
  fundTypes?: string[]
  return_1y_min?: number
  return_1y_max?: number
  return_3y_min?: number
  return_3y_max?: number
  sharpe_1y_min?: number
  maxdd_1y_max?: number
  volatility_1y_max?: number
  totalAsset_min?: number
  totalAsset_max?: number
  establishmentDate_min?: string
  establishmentDate_max?: string
  score_min?: number
  score_max?: number
  purchasePlan?: 'lump_sum' | 'sip'
  plannedAmount?: number
  salesRuleComplete?: boolean
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  page?: number
  limit?: number
}

type ScreeningFund = ReturnType<typeof toCamelFund>
type CriterionEvidenceStatus = 'matched' | 'missing' | 'outside'
type ScreeningCriterionEvidence = {
  key: string
  label: string
  status: CriterionEvidenceStatus
  actual: string
  threshold: string
  source: string
  note: string
}

const sortByMap: Record<string, string> = {
  createdAt: 'updated_at',
  updatedAt: 'updated_at',
  name: 'name',
  windCode: 'wind_code',
  nav: 'nav',
  totalAsset: 'total_asset',
  establishmentDate: 'establishment_date',
  return: 'return',
  risk: 'risk',
  sharpe: 'sharpe',
  screeningScore: 'screening_score',
  score: 'screening_score',
}

function setNumberParam(params: URLSearchParams, key: string, value: unknown) {
  if (value === undefined || value === null || value === '') return
  const numberValue = Number(value)
  if (Number.isFinite(numberValue)) params.set(key, String(numberValue))
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function numberMetric(...sources: Array<Record<string, unknown>>) {
  return (keys: string[]) => {
    for (const source of sources) {
      for (const key of keys) {
        const value = source[key]
        const parsed = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
        if (Number.isFinite(parsed)) return parsed
      }
    }
    return null
  }
}

function latestScore(fund: ScreeningFund) {
  const screeningScore = Number(fund.screeningScore)
  if (Number.isFinite(screeningScore)) return screeningScore

  const professionalScore = asRecord(fund.professionalScoring).overall_score
  const parsedProfessionalScore = typeof professionalScore === 'number' ? professionalScore : typeof professionalScore === 'string' ? Number(professionalScore) : NaN
  if (Number.isFinite(parsedProfessionalScore)) return parsedProfessionalScore

  const scores = Array.isArray(fund.scores) ? fund.scores : []
  const values = scores
    .map((score) => asRecord(score).score)
    .map((score) => typeof score === 'number' ? score : typeof score === 'string' ? Number(score) : NaN)
    .filter(Number.isFinite)
  if (values.length === 0) return null
  return values.reduce((sum, score) => sum + score, 0) / values.length
}

function passesRange(value: number | null, min?: number, max?: number) {
  if (min === undefined && max === undefined) return true
  if (value === null) return false
  if (min !== undefined && value < min) return false
  if (max !== undefined && value > max) return false
  return true
}

function formatNumber(value: number | null, options: Intl.NumberFormatOptions = {}) {
  if (value === null || !Number.isFinite(value)) return '待补'
  return new Intl.NumberFormat('zh-CN', options).format(value)
}

function formatPercent(value: number | null) {
  if (value === null || !Number.isFinite(value)) return '待补'
  return `${(value * 100).toFixed(2)}%`
}

function formatMoneyYi(value: number | null) {
  if (value === null || !Number.isFinite(value)) return '待补'
  return `${(value / 100000000).toFixed(2)} 亿`
}

function rangeThreshold(min?: number, max?: number, formatter: (value: number | null) => string = formatNumber) {
  if (min !== undefined && max !== undefined) return `${formatter(min)} ~ ${formatter(max)}`
  if (min !== undefined) return `≥ ${formatter(min)}`
  if (max !== undefined) return `≤ ${formatter(max)}`
  return '未设置'
}

function criterionStatus(value: number | null, min?: number, max?: number): CriterionEvidenceStatus {
  if (min === undefined && max === undefined) return 'matched'
  if (value === null) return 'missing'
  return passesRange(value, min, max) ? 'matched' : 'outside'
}

function availableMethodologyEvidence(fund: ScreeningFund) {
  const researchProfile = asRecord(fund.researchProfile)
  const benchmark = asRecord(fund.benchmark)
  const peerPercentiles = asRecord(fund.peerPercentiles)
  return Array.from(new Set([
    fund.type ? 'asset_class' : '',
    fund.type ? 'strategy_type' : '',
    fund.totalAsset != null ? 'aum' : '',
    fund.holdingCount ? 'top_holdings' : '',
    fund.holdingCount ? 'holding_count' : '',
    fund.holdingCount ? 'constituents' : '',
    fund.performanceData ? 'excess_return' : '',
    fund.performanceData ? 'tracking_difference' : '',
    fund.riskMetrics ? 'tracking_error' : '',
    benchmark.primaryBenchmark || researchProfile.primaryBenchmark ? 'benchmark_mapping' : '',
    benchmark.primaryBenchmark || researchProfile.primaryBenchmark ? 'index_benchmark' : '',
    peerPercentiles || researchProfile.peerGroup ? 'peer_group_policy' : '',
    peerPercentiles || researchProfile.peerGroup ? 'same_index_peers' : '',
    Array.isArray(fund.managers) && fund.managers.length ? 'tenure_slice' : '',
    Array.isArray(fund.managers) && fund.managers.length ? 'representative_fund' : '',
    researchProfile.styleLabel ? 'style_exposure' : '',
    researchProfile.strategyTags ? 'style_tags' : '',
  ].filter(Boolean)))
}

async function buildMethodologyContext(fund: ScreeningFund) {
  const researchProfile = asRecord(fund.researchProfile)
  const data = await resolveMethodologyConfigFromData({
    fundType: fund.type,
    assetClass: String(fund.type || ''),
    activePassive: String(researchProfile.activePassive || researchProfile.active_passive || ''),
    strategyFamilyKey: String(researchProfile.strategyFamilyKey || researchProfile.strategy_family_key || fund.type || ''),
    availableEvidence: availableMethodologyEvidence(fund),
  })
  return {
    researchTemplateKey: data.templateKey,
    researchTemplateName: data.templateName,
    matchRationale: data.matchRationale,
    hardGateDimensions: data.hardGateDimensions,
    methodologyMissingEvidenceFields: data.missingEvidenceFields,
    readyForFormalReview: Boolean(data.readyForFormalReview),
    hardBlocks: data.readyForFormalReview ? [] : [`${data.templateName} 方法论硬门槛证据待补`],
    gaps: data.missingEvidenceFields,
    evidence: [],
    policy: data.policy,
  }
}

function buildScreeningDecisionTrace(
  fund: ScreeningFund,
  criteria: ScreeningCriteria,
  context: { rank: number; purchasePlan: 'lump_sum' | 'sip'; plannedAmount: number | null; methodologyConfig: Awaited<ReturnType<typeof buildMethodologyContext>> },
) {
  const performance = asRecord(fund.performanceData)
  const risk = asRecord(fund.riskMetrics)
  const rollingMetrics = asRecord(fund.rollingMetrics)
  const oneYearRolling = asRecord(rollingMetrics['1y'])
  const metric = numberMetric(performance, risk, oneYearRolling)
  const return1y = metric(['return_1y', 'annual_return', 'annualized_return', 'total_return'])
  const return3y = metric(['return_3y', 'annual_return_3y', 'annualized_return_3y'])
  const sharpe1y = metric(['sharpe_1y', 'sharpe', 'sharpe_ratio'])
  const maxDrawdown = metric(['maxdd_1y', 'max_drawdown_1y', 'max_drawdown'])
  const volatility = metric(['volatility_1y', 'volatility'])
  const score = latestScore(fund)
  const totalAsset = typeof fund.totalAsset === 'number' ? fund.totalAsset : Number.isFinite(Number(fund.totalAsset)) ? Number(fund.totalAsset) : null

  const criteriaEvidence: ScreeningCriterionEvidence[] = [
    criteria.fundTypes?.length ? {
      key: 'fundTypes',
      label: '基金类型',
      status: criteria.fundTypes.includes(String(fund.type || '')) ? 'matched' as const : 'outside' as const,
      actual: String(fund.type || '待补'),
      threshold: criteria.fundTypes.join(' / '),
      source: 'funds.type',
      note: '类型只用于研究样本分层，不替代同类横评。',
    } : null,
    criteria.totalAsset_min !== undefined || criteria.totalAsset_max !== undefined ? {
      key: 'totalAsset',
      label: '基金规模',
      status: criterionStatus(totalAsset, criteria.totalAsset_min == null ? undefined : criteria.totalAsset_min * 100000000, criteria.totalAsset_max == null ? undefined : criteria.totalAsset_max * 100000000),
      actual: formatMoneyYi(totalAsset),
      threshold: rangeThreshold(criteria.totalAsset_min, criteria.totalAsset_max, (value) => `${formatNumber(value, { maximumFractionDigits: 2 })} 亿`),
      source: 'funds.total_asset',
      note: '规模用于过滤流动性和策略容量风险。',
    } : null,
    criteria.return_1y_min !== undefined || criteria.return_1y_max !== undefined ? {
      key: 'return1y',
      label: '近一年收益',
      status: criterionStatus(return1y, criteria.return_1y_min, criteria.return_1y_max),
      actual: formatPercent(return1y),
      threshold: rangeThreshold(criteria.return_1y_min, criteria.return_1y_max, formatPercent),
      source: return1y === null ? 'performance_data/rolling_metrics 缺失' : 'performance_data/rolling_metrics',
      note: '收益命中只能说明进入研究样本，不能直接形成研究结论。',
    } : null,
    criteria.return_3y_min !== undefined || criteria.return_3y_max !== undefined ? {
      key: 'return3y',
      label: '近三年收益',
      status: criterionStatus(return3y, criteria.return_3y_min, criteria.return_3y_max),
      actual: formatPercent(return3y),
      threshold: rangeThreshold(criteria.return_3y_min, criteria.return_3y_max, formatPercent),
      source: return3y === null ? 'performance_data/rolling_metrics 缺失' : 'performance_data/rolling_metrics',
      note: '三年收益需结合经理任期和风格暴露复核。',
    } : null,
    criteria.sharpe_1y_min !== undefined ? {
      key: 'sharpe1y',
      label: '一年夏普',
      status: criterionStatus(sharpe1y, criteria.sharpe_1y_min, undefined),
      actual: formatNumber(sharpe1y, { maximumFractionDigits: 3 }),
      threshold: rangeThreshold(criteria.sharpe_1y_min, undefined, (value) => formatNumber(value, { maximumFractionDigits: 3 })),
      source: sharpe1y === null ? 'risk_metrics/rolling_metrics 缺失' : 'risk_metrics/rolling_metrics',
      note: '夏普只衡量风险调整后收益，仍需回撤压力测试。',
    } : null,
    criteria.maxdd_1y_max !== undefined ? {
      key: 'maxDrawdown1y',
      label: '一年最大回撤',
      status: maxDrawdown === null ? 'missing' as const : Math.abs(maxDrawdown) <= Math.abs(criteria.maxdd_1y_max) ? 'matched' as const : 'outside' as const,
      actual: formatPercent(maxDrawdown),
      threshold: `绝对值 ≤ ${formatPercent(Math.abs(criteria.maxdd_1y_max))}`,
      source: maxDrawdown === null ? 'risk_metrics/rolling_metrics 缺失' : 'risk_metrics/rolling_metrics',
      note: '回撤约束是研究复核预算入口，不代表未来回撤上限。',
    } : null,
    criteria.volatility_1y_max !== undefined ? {
      key: 'volatility1y',
      label: '一年波动率',
      status: criterionStatus(volatility, undefined, criteria.volatility_1y_max),
      actual: formatPercent(volatility),
      threshold: rangeThreshold(undefined, criteria.volatility_1y_max, formatPercent),
      source: volatility === null ? 'risk_metrics/rolling_metrics 缺失' : 'risk_metrics/rolling_metrics',
      note: '波动率用于持有体验初筛，仍需净值回放验证。',
    } : null,
    criteria.score_min !== undefined || criteria.score_max !== undefined ? {
      key: 'screeningScore',
      label: '初筛分',
      status: criterionStatus(score, criteria.score_min, criteria.score_max),
      actual: score === null ? '待补' : `${Math.round(score)} 分`,
      threshold: rangeThreshold(criteria.score_min, criteria.score_max, (value) => `${formatNumber(value, { maximumFractionDigits: 0 })} 分`),
      source: score === null ? 'screening_score/professional_score 缺失' : 'database_screening_score_v1',
      note: '分数只用于排序和解释，不能绕过销售规则与研究复核报告门禁。',
    } : null,
  ].filter((item): item is ScreeningCriterionEvidence => item !== null)

  const dataGaps = [
    fund.nav == null ? '净值' : '',
    totalAsset === null ? '规模' : '',
    !fund.establishmentDate ? '成立日期' : '',
    !fund.performanceData ? '业绩指标' : '',
    !fund.riskMetrics ? '风险指标' : '',
  ].filter(Boolean)
  const missingCriteria = criteriaEvidence.filter((item) => item.status === 'missing')
  const outsideCriteria = criteriaEvidence.filter((item) => item.status === 'outside')
  const matchedCriteria = criteriaEvidence.filter((item) => item.status === 'matched')
  const amountLabel = context.plannedAmount
    ? context.purchasePlan === 'sip'
      ? `计划月扣款 ${context.plannedAmount.toLocaleString('zh-CN')} 元`
      : `计划配置 ${context.plannedAmount.toLocaleString('zh-CN')} 元`
    : '计划金额待补'

  return {
    source: 'screening_api.database_predicate_pushdown_trace_v1',
    rankInResult: context.rank,
    purchasePlan: context.purchasePlan,
    plannedAmount: context.plannedAmount,
    plannedAmountLabel: amountLabel,
    researchTemplateKey: context.methodologyConfig.researchTemplateKey,
    researchTemplateName: context.methodologyConfig.researchTemplateName,
    methodologyMissingEvidenceFields: context.methodologyConfig.methodologyMissingEvidenceFields,
    criteriaEvidence,
    matchedCriteriaCount: matchedCriteria.length,
    missingCriteriaCount: missingCriteria.length,
    outsideCriteriaCount: outsideCriteria.length,
    dataGaps,
    summary: criteriaEvidence.length
      ? `命中 ${matchedCriteria.length}/${criteriaEvidence.length} 项筛选条件；${dataGaps.length ? `基础证据待补 ${dataGaps.join('、')}` : '基础字段可进入下一步复核'}。`
      : `未设置硬筛选条件；按数据库排序返回第 ${context.rank} 名，需继续做研究证据复核。`,
    nextResearchStep: dataGaps.length
      ? `先补${dataGaps.slice(0, 4).join('、')}，再按${context.methodologyConfig.researchTemplateName}做同类横评和研究复核报告。`
      : `进入基金详情，按${context.methodologyConfig.researchTemplateName}复核核心证据；不得把筛选命中直接当成研究结论。`,
    hardBoundary: '筛选解释只证明为什么进入研究样本；方法论模板只决定研究口径；销售规则、R1-R5、费用、限购、赎回、净值回放和正式研究复核报告未清零前，不输出研究结论。',
  }
}

function passesScreening(fund: ScreeningFund, criteria: ScreeningCriteria) {
  const performance = asRecord(fund.performanceData)
  const risk = asRecord(fund.riskMetrics)
  const rollingMetrics = asRecord(fund.rollingMetrics)
  const oneYearRolling = asRecord(rollingMetrics['1y'])
  const metric = numberMetric(performance, risk, oneYearRolling)
  const return1y = metric(['return_1y', 'annual_return', 'annualized_return', 'total_return'])
  const return3y = metric(['return_3y', 'annual_return_3y', 'annualized_return_3y'])
  const sharpe1y = metric(['sharpe_1y', 'sharpe', 'sharpe_ratio'])
  const maxDrawdown = metric(['maxdd_1y', 'max_drawdown_1y', 'max_drawdown'])
  const volatility = metric(['volatility_1y', 'volatility'])
  const score = latestScore(fund)

  return [
    passesRange(return1y, criteria.return_1y_min, criteria.return_1y_max),
    passesRange(return3y, criteria.return_3y_min, criteria.return_3y_max),
    passesRange(sharpe1y, criteria.sharpe_1y_min, undefined),
    criteria.maxdd_1y_max === undefined || (maxDrawdown !== null && Math.abs(maxDrawdown) <= Math.abs(criteria.maxdd_1y_max)),
    criteria.volatility_1y_max === undefined || (volatility !== null && volatility <= criteria.volatility_1y_max),
    passesRange(score, criteria.score_min, criteria.score_max),
  ].every(Boolean)
}

export async function POST(request: Request) {
  try {
    const criteria = await request.json() as ScreeningCriteria
    const page = Math.max(1, Number(criteria.page || 1))
    const limit = Math.max(1, Math.min(100, Number(criteria.limit || 20)))
    const purchasePlan = criteria.purchasePlan === 'lump_sum' ? 'lump_sum' : 'sip'
    const plannedAmount = Number(criteria.plannedAmount)
    const safePlannedAmount = Number.isFinite(plannedAmount) && plannedAmount > 0 ? plannedAmount : null
    const backendParams = new URLSearchParams({
      page: String(page),
      page_size: String(limit),
      sort_by: sortByMap[criteria.sortBy || 'updatedAt'] || 'updated_at',
      sort_order: criteria.sortOrder || 'desc',
      tradable_only: 'true',
      purchase_plan: purchasePlan,
    })
    if (safePlannedAmount !== null) backendParams.set('planned_amount', String(safePlannedAmount))
    if (criteria.fundTypes?.length === 1) backendParams.set('fund_type', criteria.fundTypes[0])
    setNumberParam(backendParams, 'asset_min', criteria.totalAsset_min)
    setNumberParam(backendParams, 'asset_max', criteria.totalAsset_max)
    if (criteria.establishmentDate_min) backendParams.set('established_from', criteria.establishmentDate_min)
    if (criteria.establishmentDate_max) backendParams.set('established_to', criteria.establishmentDate_max)
    setNumberParam(backendParams, 'return_1y_min', criteria.return_1y_min)
    setNumberParam(backendParams, 'return_1y_max', criteria.return_1y_max)
    setNumberParam(backendParams, 'return_3y_min', criteria.return_3y_min)
    setNumberParam(backendParams, 'return_3y_max', criteria.return_3y_max)
    setNumberParam(backendParams, 'max_drawdown_1y_max', criteria.maxdd_1y_max)
    setNumberParam(backendParams, 'volatility_1y_max', criteria.volatility_1y_max)
    setNumberParam(backendParams, 'sharpe_1y_min', criteria.sharpe_1y_min)
    setNumberParam(backendParams, 'screening_score_min', criteria.score_min)
    setNumberParam(backendParams, 'screening_score_max', criteria.score_max)
    if (criteria.salesRuleComplete === true) backendParams.set('sales_rule_complete', 'true')

    const response = await fetch(`${backendApiBaseUrl}/api/funds?${backendParams.toString()}`, {
      cache: 'no-store',
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      return NextResponse.json(
        { error: payload.detail || payload.error || '筛选失败' },
        { status: response.status },
      )
    }

    const fetchedFunds = ((payload.funds || []) as Record<string, unknown>[]).map(toCamelFund)
    const typeFilteredFunds = criteria.fundTypes && criteria.fundTypes.length > 1
      ? fetchedFunds.filter((fund) => criteria.fundTypes?.includes(fund.type))
      : fetchedFunds
    const filteredFunds = typeFilteredFunds.filter((fund) => passesScreening(fund, criteria))
    const results = await Promise.all(filteredFunds.slice(0, limit).map(async (fund, index) => {
      const methodologyConfig = await buildMethodologyContext(fund)
      return {
        ...fund,
        methodologyConfig,
        screeningDecisionTrace: buildScreeningDecisionTrace(fund, criteria, {
        rank: index + 1,
        purchasePlan,
        plannedAmount: safePlannedAmount,
          methodologyConfig,
        }),
      }
    }))
    const total = criteria.fundTypes && criteria.fundTypes.length > 1
      ? filteredFunds.length
      : Number(payload.total || filteredFunds.length)

    return NextResponse.json({
      data: results,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.max(1, Math.ceil(total / limit)),
      },
      criteria: {
        ...criteria,
        purchasePlan,
        plannedAmount: safePlannedAmount,
      },
      source: payload.source || 'backend.funds',
      screeningSource: 'database_predicate_pushdown',
      backendQuery: backendParams.toString(),
    })
  } catch (error) {
    console.error('筛选失败:', error)
    return NextResponse.json(
      { error: '筛选失败', details: error instanceof Error ? error.message : '未知错误' },
      { status: 500 },
    )
  }
}
