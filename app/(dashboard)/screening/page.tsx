'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { BarChart3, Copy, DollarSign, Download, Filter, GitCompare, Layers3, Save, ShieldCheck, TrendingUp } from 'lucide-react'
import { salesRuleFoundationManualFieldsForPlan } from '@/lib/sales-rule-purchase-plan-copy'
import { canonicalResearchHref, materialEvidenceHref, reviewEventsHref } from '@/lib/research-platform/routes'

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
  purchasePlan?: PurchasePlan
  plannedAmount?: number
  salesRuleComplete?: boolean
}

interface Fund {
  id: string
  windCode: string
  name: string
  type: string
  nav: number | null
  totalAsset: number | null
  establishmentDate: string | null
  performanceData: Record<string, unknown> | null
  riskMetrics: Record<string, unknown> | null
  scores: Array<{ score?: number | string }>
  screeningDecisionTrace?: {
    source: string
    rankInResult: number
    plannedAmountLabel?: string
    researchTemplateKey?: string
    researchTemplateName?: string
    methodologyMissingEvidenceFields?: string[]
    criteriaEvidence: Array<{
      key: string
      label: string
      status: 'matched' | 'missing' | 'outside'
      actual: string
      threshold: string
      source: string
      note: string
    }>
    matchedCriteriaCount: number
    missingCriteriaCount: number
    outsideCriteriaCount: number
    dataGaps: string[]
    summary: string
    nextResearchStep: string
    hardBoundary: string
  }
  methodologyConfig?: {
    researchTemplateKey: string
    researchTemplateName: string
    matchRationale: string
    hardGateDimensions: string[]
    methodologyMissingEvidenceFields: string[]
    readyForFormalReview: boolean
  }
}

type SalesRuleGapStatus = {
  windCode: string
  priority: 'high' | 'medium' | 'low'
  missingItems: string[]
  missingCount: number
  nextAction: string
  ruleSourceUpdatedAt?: string | null
  alertsHref?: string | null
  gateSource?: string | null
}

type RawAlertEvent = {
  fund_id?: string | null
  event_type?: string
  status?: string
  title?: string
  message?: string
  details?: unknown
}

function alertDetails(value: unknown): Record<string, unknown> {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
    } catch {
      return {}
    }
  }
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function alertText(value: unknown) {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return ''
}

function alertFundCode(event: RawAlertEvent) {
  const details = alertDetails(event.details)
  return (
    alertText(details.wind_code) ||
    alertText(details.fund_code) ||
    alertText(event.fund_id)
  ).toUpperCase()
}

type ScreeningTemplate = {
  id: string
  name: string
  description?: string | null
  criteria: ScreeningCriteria
}

type RiskProfile = 'conservative' | 'balanced' | 'aggressive'
type InvestmentHorizon = 'lt1y' | '1to3y' | 'gt3y'
type PurchasePlan = 'lump_sum' | 'sip'

const riskProfileLabel: Record<RiskProfile, string> = {
  conservative: '稳健型',
  balanced: '均衡型',
  aggressive: '进取型',
}

const investmentHorizonLabel: Record<InvestmentHorizon, string> = {
  lt1y: '1年以内',
  '1to3y': '1-3年',
  gt3y: '3年以上',
}

const purchasePlanLabel: Record<PurchasePlan, string> = {
  lump_sum: '一次性配置',
  sip: '定投',
}

function appendReturnTo(href: string, returnTo: string) {
  const separator = href.includes('?') ? '&' : '?'
  return `${href}${separator}returnTo=${encodeURIComponent(returnTo)}`
}

function pickBrowserParam<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  if (typeof globalThis.window === 'undefined') return fallback
  const value = new URLSearchParams(globalThis.window.location.search).get(key) || ''
  return allowed.includes(value as T) ? value as T : fallback
}

function percentInputValue(value?: number) {
  return value == null ? '' : String(Number((value * 100).toFixed(4)))
}

function defaultPlannedAmountForPlan(purchasePlan: PurchasePlan) {
  return purchasePlan === 'lump_sum' ? '10000' : '1000'
}

function normalizePlannedAmountInput(value: string | null | undefined, purchasePlan: PurchasePlan) {
  const amount = Number(value || '')
  return Number.isFinite(amount) && amount > 0 ? String(amount) : defaultPlannedAmountForPlan(purchasePlan)
}

function plannedAmountQueryValue(value: string) {
  const amount = Number(value)
  return Number.isFinite(amount) && amount > 0 ? String(amount) : ''
}

function tsvCell(value: unknown) {
  return String(value ?? '').replace(/\t/g, ' ').replace(/\r?\n/g, ' ').trim()
}

function downloadTsvFile(text: string, fileStem: string) {
  const blob = new Blob([`\ufeff${text}`], { type: 'text/tab-separated-values;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${fileStem}_${new Date().toISOString().slice(0, 10)}.tsv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

const builtInScreeningPresets: Array<{
  name: string
  description: string
  criteria: ScreeningCriteria
}> = [
  {
    name: '稳健低回撤',
    description: '先看一年回撤和规模底线，避开当前数据覆盖不足导致的空筛。',
    criteria: {
      maxdd_1y_max: 0.15,
      totalAsset_min: 20,
    },
  },
  {
    name: '均衡高夏普',
    description: '用夏普和规模做第一层过滤，再进入研究横评和销售规则复核。',
    criteria: {
      sharpe_1y_min: 0.2,
      totalAsset_min: 10,
    },
  },
  {
    name: '进取收益弹性',
    description: '放宽风险边界，适合先找进攻型候选，再严查回撤和经理稳定性。',
    criteria: {
      maxdd_1y_max: 0.35,
      sharpe_1y_min: 0,
      totalAsset_min: 5,
    },
  },
  {
    name: '大规模低波动',
    description: '用规模和一年波动率找核心观察池，适合后续做横向比较。',
    criteria: {
      volatility_1y_max: 0.25,
      totalAsset_min: 30,
    },
  },
]

export default function ScreeningPage() {
  const [criteria, setCriteria] = useState<ScreeningCriteria>({})
  const [results, setResults] = useState<Fund[]>([])
  const [loading, setLoading] = useState(false)
  const [hasScreened, setHasScreened] = useState(false)
  const [templates, setTemplates] = useState<ScreeningTemplate[]>([])
  const [riskProfile, setRiskProfile] = useState<RiskProfile>('balanced')
  const [investmentHorizon, setInvestmentHorizon] = useState<InvestmentHorizon>('1to3y')
  const [purchasePlan, setPurchasePlan] = useState<PurchasePlan>('sip')
  const [plannedAmount, setPlannedAmount] = useState(defaultPlannedAmountForPlan('sip'))
  const foundationManualFields = salesRuleFoundationManualFieldsForPlan(purchasePlan)
  const [compareCodes, setCompareCodes] = useState<string[]>([])
  const [salesRuleGaps, setSalesRuleGaps] = useState<SalesRuleGapStatus[]>([])
  const [salesRuleGapsChecked, setSalesRuleGapsChecked] = useState(false)
  const [savingCandidates, setSavingCandidates] = useState(false)
  const [candidateMessage, setCandidateMessage] = useState('')
  const [candidateError, setCandidateError] = useState('')
  const [savedPoolId, setSavedPoolId] = useState('')
  const [foundationHydrating, setFoundationHydrating] = useState(false)

  useEffect(() => {
    setRiskProfile(pickBrowserParam('profile', ['conservative', 'balanced', 'aggressive'] as const, 'balanced'))
    setInvestmentHorizon(pickBrowserParam('horizon', ['lt1y', '1to3y', 'gt3y'] as const, '1to3y'))
    const urlPurchasePlan = pickBrowserParam('purchasePlan', ['lump_sum', 'sip'] as const, 'sip')
    const urlParams = new URLSearchParams(globalThis.window.location.search)
    setPurchasePlan(urlPurchasePlan)
    setPlannedAmount(normalizePlannedAmountInput(urlParams.get('plannedAmount') || urlParams.get(urlPurchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount'), urlPurchasePlan))
  }, [])

  const currentPlannedAmount = () => Number(plannedAmountQueryValue(plannedAmount) || defaultPlannedAmountForPlan(purchasePlan))
  const plannedAmountParams = () => {
    const amount = plannedAmountQueryValue(plannedAmount) || defaultPlannedAmountForPlan(purchasePlan)
    return {
      plannedAmount: amount,
      [purchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount']: amount,
    }
  }

  const fetchTemplates = useCallback(async () => {
    try {
      const response = await fetch('/api/screening/templates')
      const data = await response.json() as { data?: ScreeningTemplate[] }
      setTemplates(data.data || [])
    } catch (error) {
      console.error('获取模板失败:', error)
    }
  }, [])

  useEffect(() => {
    const timeout = globalThis.setTimeout(() => {
      void fetchTemplates()
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [fetchTemplates])

  const detailContextQuery = useMemo(() => new URLSearchParams({
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams(),
  }).toString(), [investmentHorizon, plannedAmount, purchasePlan, riskProfile])

  const investorSelectionHref = useMemo(() => {
    const params = new URLSearchParams({
      profile: riskProfile,
      horizon: investmentHorizon,
      purchasePlan,
      ...plannedAmountParams(),
      eligibleOnly: 'true',
      minEvidenceGrade: 'B',
    })
    if (criteria.score_min != null) params.set('minScore', String(criteria.score_min))
    return canonicalResearchHref(`/investor-selection?${params.toString()}`)
  }, [criteria.score_min, investmentHorizon, plannedAmount, purchasePlan, riskProfile])
  const rankingsHref = useMemo(() => canonicalResearchHref(`/rankings?${new URLSearchParams({
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams(),
    minEvidenceGrade: 'D',
    eligibleOnly: 'false',
    requireSalesRule: 'false',
  }).toString()}`), [investmentHorizon, plannedAmount, purchasePlan, riskProfile])
  const marketHref = useMemo(() => `/market?${new URLSearchParams({
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams(),
    source: 'screening_condition_health',
  }).toString()}`, [investmentHorizon, plannedAmount, purchasePlan, riskProfile])

  const screeningReturnHref = useMemo(() => `/screening?${new URLSearchParams({
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    plannedAmount: plannedAmountQueryValue(plannedAmount) || defaultPlannedAmountForPlan(purchasePlan),
  }).toString()}`, [investmentHorizon, plannedAmount, purchasePlan, riskProfile])

  const comparisonHref = compareCodes.length >= 2
    ? `/analysis/comparison?${new URLSearchParams({
      codes: compareCodes.join(','),
      profile: riskProfile,
      horizon: investmentHorizon,
      purchasePlan,
      ...plannedAmountParams(),
      autoReplay: '1',
    }).toString()}`
    : '/analysis/comparison'
  const comparisonHrefForCodes = useCallback((codes: string[]) => {
    const normalizedCodes = Array.from(new Set(codes.map((code) => code.trim().toUpperCase()).filter(Boolean)))
    if (normalizedCodes.length < 2) return '/analysis/comparison'
    return `/analysis/comparison?${new URLSearchParams({
      codes: normalizedCodes.join(','),
      profile: riskProfile,
      horizon: investmentHorizon,
      purchasePlan,
      ...plannedAmountParams(),
      autoReplay: '1',
    }).toString()}`
  }, [investmentHorizon, plannedAmount, purchasePlan, riskProfile])
  const salesRulesHref = compareCodes.length
    ? appendReturnTo(materialEvidenceHref(new URLSearchParams({ codes: compareCodes.join(','), purchasePlan, plannedAmount: String(currentPlannedAmount()) })), screeningReturnHref)
    : appendReturnTo(materialEvidenceHref(new URLSearchParams({ purchasePlan, plannedAmount: String(currentPlannedAmount()) })), screeningReturnHref)
  const salesRulesHrefForCodes = useCallback((codes: string[]) => {
    const normalizedCodes = Array.from(new Set(codes.map((code) => code.trim().toUpperCase()).filter(Boolean)))
    const params = new URLSearchParams({ purchasePlan, plannedAmount: String(currentPlannedAmount()) })
    if (normalizedCodes.length) params.set('codes', normalizedCodes.join(','))
    return appendReturnTo(materialEvidenceHref(params), screeningReturnHref)
  }, [plannedAmount, purchasePlan, screeningReturnHref])
  const detailHref = (fund: Fund) => `/funds/${encodeURIComponent(fund.id)}?${detailContextQuery}`
  const resultCodes = useMemo(
    () => Array.from(new Set(results.map((fund) => fund.windCode).filter(Boolean))),
    [results],
  )
  const salesRuleGapByCode = useMemo(() => {
    const gapMap = new Map<string, SalesRuleGapStatus>()
    salesRuleGaps.forEach((gap) => gapMap.set(gap.windCode.toUpperCase(), gap))
    return gapMap
  }, [salesRuleGaps])
  const salesRuleGapSummary = useMemo(() => {
    const sortedGaps = [...salesRuleGaps].sort((left, right) => {
      const priorityWeight = { high: 3, medium: 2, low: 1 }
      return priorityWeight[right.priority] - priorityWeight[left.priority] || right.missingCount - left.missingCount
    })
    const codes = sortedGaps.map((gap) => gap.windCode)
    const reviewAlertBlocked = sortedGaps.some((gap) => Boolean(gap.alertsHref))
    return {
      funds: sortedGaps.length,
      highPriority: sortedGaps.filter((gap) => gap.priority === 'high').length,
      missingItems: sortedGaps.reduce((sum, gap) => sum + gap.missingCount, 0),
      topGaps: sortedGaps.slice(0, 5),
      href: reviewAlertBlocked ? reviewEventsHref({ returnTo: screeningReturnHref }) : salesRulesHrefForCodes(codes),
      reviewAlertBlocked,
    }
  }, [salesRuleGaps, salesRulesHrefForCodes, screeningReturnHref])
  const resultMaturitySummary = useMemo(() => {
    const gapCodes = new Set(salesRuleGaps.map((gap) => gap.windCode.toUpperCase()))
    const readyFunds = results.filter((fund) => !gapCodes.has(fund.windCode.toUpperCase()))
    const blockedFunds = results.filter((fund) => gapCodes.has(fund.windCode.toUpperCase()))
    const readyCodes = readyFunds.map((fund) => fund.windCode).filter(Boolean).slice(0, 6)
    const blockedCodes = blockedFunds.map((fund) => fund.windCode).filter(Boolean).slice(0, 12)
    const reviewAlertBlocked = blockedFunds.some((fund) => Boolean(salesRuleGapByCode.get(fund.windCode.toUpperCase())?.alertsHref))
    return {
      readyCount: readyFunds.length,
      blockedCount: blockedFunds.length,
      readyComparisonHref: readyCodes.length >= 2
        ? `/analysis/comparison?${new URLSearchParams({
          codes: readyCodes.join(','),
          profile: riskProfile,
          horizon: investmentHorizon,
          purchasePlan,
          ...plannedAmountParams(),
          autoReplay: '1',
        }).toString()}`
        : '',
      blockedSalesRulesHref: reviewAlertBlocked ? reviewEventsHref({ returnTo: screeningReturnHref }) : salesRulesHrefForCodes(blockedCodes),
    }
  }, [investmentHorizon, plannedAmount, purchasePlan, results, riskProfile, salesRuleGapByCode, salesRuleGaps, salesRulesHrefForCodes, screeningReturnHref])
  const readyCandidateFunds = useMemo(() => {
    const gapCodes = new Set(salesRuleGaps.map((gap) => gap.windCode.toUpperCase()))
    return results.filter((fund) => !gapCodes.has(fund.windCode.toUpperCase()))
  }, [results, salesRuleGaps])
  const foundationFillableCodes = useMemo(() => {
    return Array.from(new Set(
      salesRuleGaps
        .filter((gap) => gap.missingItems.some((item) =>
          item.includes('销售规则整条待补')
            || item.includes('来源日期')
            || (item.includes('申购状态') && !gap.ruleSourceUpdatedAt),
        ))
        .map((gap) => gap.windCode),
    ))
  }, [salesRuleGaps])
  const screeningPurchaseActionQueue = useMemo(() => {
    return results.slice(0, 12).map((fund) => {
      const salesRuleGap = salesRuleGapByCode.get(fund.windCode.toUpperCase()) || null
      const canCompare = compareCodes.includes(fund.windCode) || compareCodes.length < 6
      const fundDetailHref = detailHref(fund)
      const reviewAlertBlocked = Boolean(salesRuleGap?.alertsHref)
      const fundSalesRulesHref = reviewAlertBlocked ? reviewEventsHref({ returnTo: screeningReturnHref }) : salesRulesHrefForCodes([fund.windCode])
      const screeningTrace = fund.screeningDecisionTrace || null
      const methodologyConfig = fund.methodologyConfig || null
      const topCriteriaEvidence = (screeningTrace?.criteriaEvidence || []).slice(0, 3)
      const status = !salesRuleGapsChecked
        ? 'scanning'
        : salesRuleGap
          ? 'rules_missing'
          : 'ready'
      const label = status === 'scanning'
        ? '规则扫描中'
        : status === 'rules_missing'
          ? reviewAlertBlocked ? '复查队列补证' : '先补销售规则'
          : '可进入研究复核'
      const primaryAction = status === 'rules_missing'
        ? reviewAlertBlocked
          ? '先打开复查队列，处理销售规则/R1-R5过期或待补事件'
          : `补齐 ${salesRuleGap?.missingCount ?? 0} 项销售规则硬缺口`
        : status === 'ready'
          ? '进入详情做净值回放、持仓暴露和研究复核报告'
          : '等待销售规则扫描完成后再决定是否入池'
      const primaryHref = status === 'rules_missing' ? fundSalesRulesHref : fundDetailHref
      const badgeClass = status === 'rules_missing'
        ? 'bg-amber-100 text-amber-800'
        : status === 'ready'
          ? 'bg-emerald-100 text-emerald-800'
          : 'bg-slate-100 text-slate-600'
      return {
        fund,
        salesRuleGap,
        status,
        label,
        primaryAction,
        primaryHref,
        fundDetailHref,
        fundSalesRulesHref,
        screeningTrace,
        methodologyConfig,
        topCriteriaEvidence,
        canCompare,
        badgeClass,
      }
    })
  }, [compareCodes, detailHref, results, salesRuleGapByCode, salesRuleGapsChecked, salesRulesHrefForCodes, screeningReturnHref])
  const screeningPurchaseQueueSummary = useMemo(() => ({
    ready: screeningPurchaseActionQueue.filter((item) => item.status === 'ready').length,
    rulesMissing: screeningPurchaseActionQueue.filter((item) => item.status === 'rules_missing').length,
    reviewAlerts: screeningPurchaseActionQueue.filter((item) => Boolean(item.salesRuleGap?.alertsHref)).length,
    scanning: screeningPurchaseActionQueue.filter((item) => item.status === 'scanning').length,
  }), [screeningPurchaseActionQueue])
  const screeningConditionHealthRows = useMemo(() => {
    const traces = results.map((fund) => fund.screeningDecisionTrace).filter(Boolean) as NonNullable<Fund['screeningDecisionTrace']>[]
    const totalCriteria = traces.reduce((sum, trace) => sum + trace.matchedCriteriaCount + trace.missingCriteriaCount + trace.outsideCriteriaCount, 0)
    const missingCriteria = traces.reduce((sum, trace) => sum + trace.missingCriteriaCount, 0)
    const outsideCriteria = traces.reduce((sum, trace) => sum + trace.outsideCriteriaCount, 0)
    const gapCodes = new Set(salesRuleGaps.map((gap) => gap.windCode.toUpperCase()))
    const rows = [
      {
        key: 'result-size',
        title: '结果规模是否合理',
        status: !hasScreened
          ? '待筛选'
          : results.length === 0
            ? '条件过窄'
            : results.length < 3
              ? '样本偏少'
              : '可继续',
        detail: !hasScreened
          ? '先运行筛选，才能判断条件是否过窄。'
          : results.length === 0
            ? '当前条件没有命中基金，优先放宽收益、回撤、规模或基金类型，再回到研究模型重排。'
            : results.length < 3
              ? `仅命中 ${results.length} 只，难以形成替代横评；建议放宽一项硬条件或扩大基金类型。`
              : `命中 ${results.length} 只，可进入证据检查和横向比较。`,
        actionLabel: results.length >= 3 ? '进入横评' : '放宽筛选',
        actionHref: results.length >= 3 ? comparisonHrefForCodes(results.slice(0, 4).map((fund) => fund.windCode)) : marketHref,
      },
      {
        key: 'criteria-evidence',
        title: '筛选条件证据是否充分',
        status: !traces.length
          ? '待补解释'
          : missingCriteria > 0 || outsideCriteria > 0
            ? '证据待补'
            : '证据较完整',
        detail: !traces.length
          ? '当前结果缺少条件级命中解释，不能证明为什么进入研究样本。'
          : missingCriteria > 0 || outsideCriteria > 0
            ? `条件级证据共 ${totalCriteria} 项，其中待补 ${missingCriteria}、未通过 ${outsideCriteria}；缺证不按中性分处理。`
            : `条件级证据 ${totalCriteria} 项均有可解释结果，可继续做销售规则和研究复核。`,
        actionLabel: missingCriteria > 0 || outsideCriteria > 0 ? '下载证据 TSV' : '复核证据 TSV',
        actionHref: screeningReturnHref,
      },
      {
        key: 'sales-rule',
        title: '销售规则是否阻断',
        status: !salesRuleGapsChecked
          ? '扫描中'
          : salesRuleGaps.length
            ? '规则阻断'
            : '规则未见硬缺口',
        detail: !salesRuleGapsChecked
          ? '正在扫描销售规则和复查队列，扫描完成前不能加入研究清单或生成研究复核报告。'
          : salesRuleGaps.length
            ? `${salesRuleGaps.length} 只基金仍有 ${salesRuleGapSummary.missingItems} 项销售规则/R1-R5/申赎字段缺口；先补证。`
            : '当前结果未检测到销售规则硬缺口，仍需研究复核销售平台实时页面。',
        actionLabel: salesRuleGaps.length ? salesRuleGapSummary.reviewAlertBlocked ? '处理复查队列' : '补规则缺口' : '查销售规则',
        actionHref: salesRuleGaps.length ? salesRuleGapSummary.href : salesRulesHref,
      },
      {
        key: 'next-step',
        title: '下一步是否能形成横评',
        status: resultMaturitySummary.readyCount >= 2
          ? '可横评'
          : resultMaturitySummary.readyCount === 1
            ? '缺替代样本'
            : '先补证',
        detail: resultMaturitySummary.readyCount >= 2
          ? `已有 ${resultMaturitySummary.readyCount} 只规则完整样本，可先做横向比较，再决定观察池和报告留痕。`
          : resultMaturitySummary.readyCount === 1
            ? '只有 1 只规则完整样本，无法证明优劣；放宽条件或补齐被阻断样本后再横评。'
            : '当前没有规则完整样本，先处理销售规则/R1-R5/费用证据缺口。',
        actionLabel: resultMaturitySummary.readyComparisonHref ? '比较规则完整样本' : '去补证',
        actionHref: resultMaturitySummary.readyComparisonHref || resultMaturitySummary.blockedSalesRulesHref || salesRulesHref,
      },
    ]
    return rows
  }, [comparisonHrefForCodes, hasScreened, marketHref, resultMaturitySummary.blockedSalesRulesHref, resultMaturitySummary.readyComparisonHref, resultMaturitySummary.readyCount, results, salesRuleGapSummary.href, salesRuleGapSummary.missingItems, salesRuleGapSummary.reviewAlertBlocked, salesRuleGaps, salesRuleGapsChecked, salesRulesHref, screeningReturnHref])
  const screeningConditionHealthTsv = useMemo(() => {
    const rows = screeningConditionHealthRows.map((row) => [
      row.title,
      row.status,
      row.detail,
      row.actionLabel,
      row.actionHref,
      '筛选诊断只解释条件健康度；销售规则/R1-R5、计划金额、费用、横评和研究复核报告门禁未完成前，不形成正式研究结论。',
    ])
    return [
      ['诊断项', '状态', '解释', '下一步', '入口', '硬边界'],
      ...rows,
    ].map((row) => row.map(tsvCell).join('\t')).join('\n')
  }, [screeningConditionHealthRows])

  const downloadScreeningConditionHealthTsv = () => {
    downloadTsvFile(screeningConditionHealthTsv, `筛选条件健康诊断_${riskProfile}_${investmentHorizon}_${purchasePlan}`)
    setCandidateMessage('已下载筛选条件健康诊断 TSV；用于解释筛选质量，不替代研究证据门禁。')
    setCandidateError('')
  }
  const screeningDecisionTraceTsv = useMemo(() => {
    const rows = results.map((fund, index) => {
      const trace = fund.screeningDecisionTrace
      const salesRuleGap = salesRuleGapByCode.get(fund.windCode.toUpperCase()) || null
      const criteriaEvidence = (trace?.criteriaEvidence || [])
        .map((item) => `${item.label}:${item.actual}/${item.threshold}/${item.status}/source=${item.source}`)
        .join('；')
      return [
        index + 1,
        fund.windCode,
        fund.name,
        fund.type,
        purchasePlanLabel[purchasePlan],
        trace?.plannedAmountLabel || (purchasePlan === 'sip' ? `计划月扣款 ${currentPlannedAmount().toLocaleString('zh-CN')} 元` : `计划配置 ${currentPlannedAmount().toLocaleString('zh-CN')} 元`),
        trace?.summary || '筛选证据待补',
        trace?.matchedCriteriaCount ?? '',
        trace?.missingCriteriaCount ?? '',
        trace?.outsideCriteriaCount ?? '',
        trace?.dataGaps?.join('、') || '无',
        trace?.researchTemplateName || fund.methodologyConfig?.researchTemplateName || '研究模板待识别',
        trace?.methodologyMissingEvidenceFields?.join('、') || fund.methodologyConfig?.methodologyMissingEvidenceFields?.join('、') || '无',
        criteriaEvidence,
        salesRuleGap ? `缺 ${salesRuleGap.missingCount} 项：${salesRuleGap.missingItems.join('、')}` : salesRuleGapsChecked ? '未检测到销售规则硬缺口' : '销售规则扫描中',
        trace?.nextResearchStep || '进入详情页复核研究证据',
        trace?.hardBoundary || '筛选只给出研究对象，仍需正式研究证据复核',
        trace?.source || 'screening-page',
      ]
    })
    return [
      ['排序', '基金代码', '基金名称', '类型', '研究方式', '计划金额', '筛选证据摘要', '命中条件数', '待补条件数', '未通过条件数', '基础数据缺口', '研究模板', '方法论缺口', '条件证据明细', '销售规则状态', '下一步', '硬边界', '证据来源'],
      ...rows,
    ].map((row) => row.map(tsvCell).join('\t')).join('\n')
  }, [purchasePlan, results, salesRuleGapByCode, salesRuleGapsChecked])

  const downloadScreeningDecisionTraceTsv = () => {
    if (!results.length) return
    downloadTsvFile(screeningDecisionTraceTsv, `筛选命中证据台账_${riskProfile}_${investmentHorizon}_${purchasePlan}`)
    setCandidateMessage(`已下载 ${results.length} 条筛选命中证据 TSV；这只是研究留痕，不绕过研究硬门禁。`)
    setCandidateError('')
  }

  const copyScreeningDecisionTraceTsv = async () => {
    if (!results.length) return
    try {
      if (!globalThis.navigator?.clipboard?.writeText) throw new Error('clipboard unavailable')
      await globalThis.navigator.clipboard.writeText(screeningDecisionTraceTsv)
      setCandidateMessage(`已复制 ${results.length} 条筛选命中证据 TSV；后续仍需销售规则、R1-R5、横评和研究复核报告。`)
      setCandidateError('')
    } catch {
      downloadScreeningDecisionTraceTsv()
      setCandidateMessage(`复制受限，已转下载 ${results.length} 条筛选命中证据 TSV。`)
    }
  }

  const loadSalesRuleGapsForCodes = useCallback(async (codes: string[]) => {
    if (!codes.length) {
      setSalesRuleGaps([])
      setSalesRuleGapsChecked(hasScreened)
      return
    }

    setSalesRuleGapsChecked(false)
    const params = new URLSearchParams({
      codes: codes.slice(0, 200).join(','),
      purchasePlan,
      plannedAmount: String(currentPlannedAmount()),
    })
    const [gapResponse, alertsResponse] = await Promise.all([
      fetch(`/api/evidence-coverage/materials/gaps?${params.toString()}`, { cache: 'no-store' }),
      fetch('/api/evidence-coverage/review-events', { cache: 'no-store' }),
    ])
    const data = await gapResponse.json().catch(() => ({}))
    const alertsData = await alertsResponse.json().catch(() => ({}))
    const gapMap = ((gapResponse.ok ? data.gaps || [] : []) as SalesRuleGapStatus[]).reduce((acc, gap) => {
      acc.set(gap.windCode.toUpperCase(), gap)
      return acc
    }, new Map<string, SalesRuleGapStatus>())
    const targetCodes = new Set(codes.map((code) => code.toUpperCase()))
    const activeSalesRuleAlerts = (Array.isArray(alertsData.events) ? alertsData.events as RawAlertEvent[] : [])
      .filter((event) => event.event_type === 'sales_rule_evidence' && event.status !== 'resolved' && targetCodes.has(alertFundCode(event)))
    activeSalesRuleAlerts.forEach((event) => {
      const windCode = alertFundCode(event)
      const existing = gapMap.get(windCode)
      const title = alertText(event.title) || '销售规则/R1-R5证据待补'
      const message = alertText(event.message)
      const alertMissingItem = `复查队列未解决：${title}${message ? `（${message}）` : ''}`
      const missingItems = Array.from(new Set([...(existing?.missingItems || []), alertMissingItem]))
      gapMap.set(windCode, {
        ...(existing || {
          windCode,
          ruleSourceUpdatedAt: null,
        }),
        priority: 'high',
        missingItems,
        missingCount: Math.max(existing?.missingCount || 0, missingItems.length),
        nextAction: '先打开复查队列，处理销售规则/R1-R5过期或待补事件',
        alertsHref: reviewEventsHref({ returnTo: screeningReturnHref }),
        gateSource: 'local.alert_events.sales_rule_evidence',
      })
    })
    setSalesRuleGaps(gapResponse.ok && alertsResponse.ok ? Array.from(gapMap.values()) : [])
    setSalesRuleGapsChecked(true)
    if (!gapResponse.ok) {
      throw new Error(data.error || '读取筛选结果销售规则缺口失败')
    }
    if (!alertsResponse.ok) {
      throw new Error(alertsData.error || alertsData.detail || '读取复查队列失败，不能证明销售规则/R1-R5证据有效。')
    }
  }, [hasScreened, plannedAmount, purchasePlan])

  const runScreening = async (screeningCriteria: ScreeningCriteria) => {
    setLoading(true)
    try {
      const response = await fetch('/api/screening', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...screeningCriteria, purchasePlan, plannedAmount: currentPlannedAmount() })
      })

      const data = await response.json() as { data?: Fund[] }
      setResults(data.data || [])
      setCompareCodes([])
      setSalesRuleGaps([])
      setSalesRuleGapsChecked(false)
      setHasScreened(true)
      setCandidateMessage('')
      setCandidateError('')
    } catch (error) {
      console.error('筛选失败:', error)
      setHasScreened(true)
    } finally {
      setLoading(false)
    }
  }

  const handleScreen = async () => {
    await runScreening(criteria)
  }

  const handleSaveTemplate = async () => {
    const name = prompt('请输入模板名称:')
    if (!name) return

    try {
      await fetch('/api/screening/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: '用户自定义筛选条件',
          criteria
        })
      })

      alert('模板保存成功')
      void fetchTemplates()
    } catch (error) {
      console.error('保存模板失败:', error)
      alert('保存模板失败')
    }
  }

  const handleLoadTemplate = (template: ScreeningTemplate) => {
    setCriteria(template.criteria)
  }

  const applyBuiltInPreset = (preset: typeof builtInScreeningPresets[number]) => {
    setCriteria(preset.criteria)
    void runScreening(preset.criteria)
  }

  const ensureDefaultPool = async () => {
    const poolsResponse = await fetch('/api/market/research-lists', { cache: 'no-store' })
    const poolsPayload = await poolsResponse.json().catch(() => ({}))
    if (!poolsResponse.ok) {
      throw new Error(poolsPayload.detail || poolsPayload.error || '读取默认观察池失败')
    }

    const existingPoolId = poolsPayload.pools?.[0]?.id as string | undefined
    if (existingPoolId) return existingPoolId

    const createResponse = await fetch('/api/market/research-lists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: '默认观察池',
        description: '由基金筛选器自动创建',
        createdBy: 'screening-ui',
        isDefault: true,
      }),
    })
    const createdPayload = await createResponse.json().catch(() => ({}))
    if (!createResponse.ok || !createdPayload.id) {
      throw new Error(createdPayload.detail || createdPayload.error || '创建默认观察池失败')
    }
    return createdPayload.id as string
  }

  const buildCandidateEvidence = (fund: Fund, rank: number) => {
    const scoreValue = Number(fund.scores?.[0]?.score)
    const screeningScore = Number.isFinite(scoreValue) ? Math.round(scoreValue) : null
    const screeningTrace = fund.screeningDecisionTrace || null
    const methodologyConfig = fund.methodologyConfig || null
    const criteriaSummary = Object.entries(criteria)
      .filter(([, value]) => Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== '')
      .map(([key, value]) => `${key}=${Array.isArray(value) ? value.join('/') : value}`)
      .join('；') || '当前筛选条件'
    const fallbackDataGaps = [
      fund.nav == null ? '净值' : '',
      fund.totalAsset == null ? '规模' : '',
      fund.establishmentDate == null ? '成立日期' : '',
      !fund.performanceData ? '业绩指标' : '',
      !fund.riskMetrics ? '风险指标' : '',
    ].filter(Boolean)
    const dataGaps = screeningTrace?.dataGaps?.length ? screeningTrace.dataGaps : fallbackDataGaps
    const nextAction = dataGaps.length
      ? `先补${dataGaps.slice(0, 4).join('、')}，再做横评和研究复核一页纸`
      : '进入横评和详情页研究复核一页纸，复核实时销售平台规则'
    const traceSummary = screeningTrace?.summary ? `；${screeningTrace.summary}` : ''
    const latestConclusion = `筛选留痕：第 ${rank + 1} 名，${screeningScore === null ? '评分待补' : `评分 ${screeningScore}`}，命中「${criteriaSummary}」${traceSummary}；当前页未检测销售规则硬缺口；下一步：${screeningTrace?.nextResearchStep || nextAction}。`
    const plannedAmountLabel = purchasePlan === 'sip'
      ? `计划月扣款 ${currentPlannedAmount().toLocaleString('zh-CN')} 元`
      : `计划配置 ${currentPlannedAmount().toLocaleString('zh-CN')} 元`
    const reason = `筛选器入池：第 ${rank + 1} 名，${screeningScore === null ? '评分待补' : `评分 ${screeningScore}`}，${riskProfileLabel[riskProfile]} · ${investmentHorizonLabel[investmentHorizon]} · ${purchasePlanLabel[purchasePlan]} · ${plannedAmountLabel}`
    const riskNotes = [
      `筛选条件：${criteriaSummary}`,
      screeningTrace?.summary ? `筛选证据：${screeningTrace.summary}` : '',
      methodologyConfig ? `研究模板：${methodologyConfig.researchTemplateName}` : '',
      methodologyConfig?.methodologyMissingEvidenceFields?.length ? `方法论缺口：${methodologyConfig.methodologyMissingEvidenceFields.slice(0, 6).join('、')}` : '',
      dataGaps.length ? `基础数据待补：${dataGaps.join('、')}` : '',
      screeningTrace?.hardBoundary || '筛选命中只代表研究入口，仍需同类横评、销售规则实时复核和研究复核报告。',
    ].filter(Boolean).join('；')

    return {
      reason,
      latestConclusion,
      riskNotes,
      evidence: {
        source: 'screening-page',
        addedAt: new Date().toISOString(),
        investorContext: {
          profile: riskProfile,
          profileLabel: riskProfileLabel[riskProfile],
          horizon: investmentHorizon,
          horizonLabel: investmentHorizonLabel[investmentHorizon],
          purchasePlan,
          purchasePlanLabel: purchasePlanLabel[purchasePlan],
          plannedAmount: currentPlannedAmount(),
          plannedAmountLabel,
        },
        purchaseGate: {
          level: 'watchlist',
          label: '可进入观察池复核',
          evidenceGrade: 'B',
          hardBlocks: [],
          cautionFlags: ['来自筛选器条件命中，仍需做同类横向比较和研究复核报告'],
          mustVerifyBeforeBuy: [
            '复核销售平台实时申购状态、费率、赎回、定投、限购和风险等级',
            '完成至少 2 只同类基金横向对比',
            '生成研究复核一页纸报告后再进入正式研究判断',
          ],
          suitabilityNotes: [`当前画像：${riskProfileLabel[riskProfile]} · ${investmentHorizonLabel[investmentHorizon]} · ${purchasePlanLabel[purchasePlan]} · ${plannedAmountLabel}`],
        },
        buyEvidence: {
          completenessLevel: 'partial',
          requiredMissingCount: dataGaps.length,
          conclusion: latestConclusion,
        },
        screeningDecision: {
          reason,
          latestConclusion,
          nextAction: screeningTrace?.nextResearchStep || nextAction,
          criteriaSummary,
          screeningScore,
          rankInResult: rank + 1,
          dataGaps,
          hardBoundary: '筛选只给出研究对象；销售规则、适当性、横评和研究复核报告未完成前，不进入正式研究候选。',
        },
        screeningDecisionTrace: screeningTrace,
        methodologyConfig,
        screening: {
          criteria,
          criteriaSummary,
          resultCount: results.length,
          rankInResult: rank + 1,
          selectedAt: new Date().toISOString(),
        },
        salesRuleGap: {
          checked: true,
          checkedCode: fund.windCode,
          missingCount: 0,
          missingItems: [],
          nextAction,
        },
      },
    }
  }

  const saveReadyResultsToCandidatePool = async () => {
    if (!salesRuleGapsChecked) {
      setCandidateMessage('')
      setCandidateError('销售规则扫描尚未完成，请等待当前结果完成缺口检查后再入池。')
      return
    }
    if (readyCandidateFunds.length === 0) {
      setCandidateMessage('')
      setCandidateError('当前筛选结果没有规则完整样本，先补销售规则后再加入观察池。')
      return
    }

    try {
      setSavingCandidates(true)
      setCandidateMessage('')
      setCandidateError('')
      const poolId = await ensureDefaultPool()
      const saveResults = await Promise.all(readyCandidateFunds.map(async (fund, rank) => {
        const candidateEvidence = buildCandidateEvidence(fund, rank)
        const response = await fetch(`/api/market/research-lists/${poolId}/members`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fundId: fund.id,
            fundWindCode: fund.windCode,
            status: 'watch',
            purchasePlan,
            plannedAmount: currentPlannedAmount(),
            reason: candidateEvidence.reason,
            latestConclusion: candidateEvidence.latestConclusion,
            riskNotes: candidateEvidence.riskNotes,
            evidence: candidateEvidence.evidence,
            createdBy: 'screening-ui',
          }),
        })
        const payload = await response.json().catch(() => ({}))
        return {
          fundName: fund.name,
          ok: response.ok,
          error: payload.detail || payload.error || null,
        }
      }))

      const successCount = saveResults.filter((result) => result.ok).length
      const failed = saveResults.filter((result) => !result.ok)
      setSavedPoolId(poolId)
      setCandidateMessage(`已把 ${successCount} 只规则完整样本保存到观察池。`)
      if (failed.length) {
        setCandidateError(`另有 ${failed.length} 只入池失败：${failed.slice(0, 3).map((item) => `${item.fundName}${item.error ? `（${item.error}）` : ''}`).join('、')}`)
      }
    } catch (error) {
      console.error('保存筛选结果到观察池失败:', error)
      setCandidateError(error instanceof Error ? error.message : '保存筛选结果到观察池失败')
    } finally {
      setSavingCandidates(false)
    }
  }

  const importTushareFoundationForResults = async () => {
    if (!foundationFillableCodes.length) {
      setCandidateMessage('')
      setCandidateError('当前筛选结果没有可由 Tushare fund_basic 先补的基础状态缺口。')
      return
    }

    try {
      setFoundationHydrating(true)
      setCandidateMessage('')
      setCandidateError('')
      const response = await fetch('/api/evidence-coverage/materials/tushare-foundation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codes: foundationFillableCodes, purchasePlan, plannedAmount: currentPlannedAmount() }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.error || '导入 Tushare 基础申赎状态失败')
      }
      await loadSalesRuleGapsForCodes(resultCodes)
      setCandidateMessage(`已从 Tushare fund_basic 导入 ${data.savedCount || 0} 只基金的基础申赎状态；${foundationManualFields}仍需销售平台核验。`)
      if (data.failedCount) {
        const failedPreview = Array.isArray(data.failed)
          ? data.failed.slice(0, 3).map((item: { windCode?: string; error?: string }) => `${item.windCode || '未知基金'}：${item.error || '原因待查'}`).join('；')
          : ''
        setCandidateError(`另有 ${data.failedCount} 只基础状态导入失败${failedPreview ? `：${failedPreview}` : '。'}`)
      }
    } catch (error) {
      console.error('导入筛选结果 Tushare 基础状态失败:', error)
      setCandidateError(error instanceof Error ? error.message : '导入 Tushare 基础申赎状态失败')
    } finally {
      setFoundationHydrating(false)
    }
  }

  const toggleCompare = (fund: Fund) => {
    setCompareCodes((current) => {
      if (current.includes(fund.windCode)) return current.filter((code) => code !== fund.windCode)
      return [...current, fund.windCode].slice(0, 6)
    })
  }

  useEffect(() => {
    const controller = new AbortController()
    const timeout = globalThis.setTimeout(async () => {
      if (!resultCodes.length) {
        setSalesRuleGaps([])
        setSalesRuleGapsChecked(hasScreened)
        return
      }

      try {
        await loadSalesRuleGapsForCodes(resultCodes)
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error('读取筛选结果销售规则缺口失败:', error)
          setSalesRuleGaps([])
          setSalesRuleGapsChecked(true)
        }
      }
    }, 0)

    return () => {
      controller.abort()
      globalThis.clearTimeout(timeout)
    }
  }, [hasScreened, loadSalesRuleGapsForCodes, resultCodes])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">基金筛选器</h1>
        <p className="mt-1 text-sm text-gray-500">
          根据多维度条件筛选基金，并把结果接入研究画像、横向对比和销售规则复核。
        </p>
      </div>

      <div className="rounded-2xl border border-blue-100 bg-white p-5 shadow">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-lg font-semibold text-gray-900">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              研究画像
            </div>
            <p className="mt-1 text-sm text-gray-500">筛选结果进入详情、对比和报告时会保留这组画像。</p>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="text-xs font-medium text-gray-500">
              风险画像
              <select value={riskProfile} onChange={(event) => setRiskProfile(event.target.value as RiskProfile)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900">
                <option value="conservative">稳健型</option>
                <option value="balanced">均衡型</option>
                <option value="aggressive">进取型</option>
              </select>
            </label>
            <label className="text-xs font-medium text-gray-500">
              持有期
              <select value={investmentHorizon} onChange={(event) => setInvestmentHorizon(event.target.value as InvestmentHorizon)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900">
                <option value="lt1y">1年以内</option>
                <option value="1to3y">1-3年</option>
                <option value="gt3y">3年以上</option>
              </select>
            </label>
            <label className="text-xs font-medium text-gray-500">
              研究方式
              <select
                value={purchasePlan}
                onChange={(event) => {
                  const nextPlan = event.target.value as PurchasePlan
                  setPlannedAmount((current) => current === defaultPlannedAmountForPlan(purchasePlan) ? defaultPlannedAmountForPlan(nextPlan) : current)
                  setPurchasePlan(nextPlan)
                }}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
              >
                <option value="sip">定投</option>
                <option value="lump_sum">一次性配置</option>
              </select>
            </label>
            <label className="text-xs font-medium text-gray-500">
              {purchasePlan === 'sip' ? '计划月扣款' : '计划配置'}（元）
              <input
                type="number"
                min="1"
                value={plannedAmount}
                onChange={(event) => setPlannedAmount(event.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900"
              />
            </label>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          <Link href={investorSelectionHref} className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700">
            用研究模型重算
          </Link>
          <Link href={rankingsHref} className="rounded-lg border border-blue-200 px-4 py-2 font-medium text-blue-700 hover:bg-blue-50">
            看基金排行榜
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 筛选条件 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 业绩指标 */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center mb-4">
              <TrendingUp className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">业绩指标</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  1年收益率 (最小 %)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={percentInputValue(criteria.return_1y_min)}
                  onChange={(e) => setCriteria({ ...criteria, return_1y_min: e.target.value ? Number(e.target.value) / 100 : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  1年收益率 (最大 %)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={percentInputValue(criteria.return_1y_max)}
                  onChange={(e) => setCriteria({ ...criteria, return_1y_max: e.target.value ? Number(e.target.value) / 100 : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  3年收益率 (最小 %)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={percentInputValue(criteria.return_3y_min)}
                  onChange={(e) => setCriteria({ ...criteria, return_3y_min: e.target.value ? Number(e.target.value) / 100 : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  3年收益率 (最大 %)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={percentInputValue(criteria.return_3y_max)}
                  onChange={(e) => setCriteria({ ...criteria, return_3y_max: e.target.value ? Number(e.target.value) / 100 : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* 风险指标 */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center mb-4">
              <BarChart3 className="w-5 h-5 text-red-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">风险指标</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  夏普比率 (最小)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={criteria.sharpe_1y_min ?? ''}
                  onChange={(e) => setCriteria({ ...criteria, sharpe_1y_min: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  最大回撤 (最大 %)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={percentInputValue(criteria.maxdd_1y_max)}
                  onChange={(e) => setCriteria({ ...criteria, maxdd_1y_max: e.target.value ? Number(e.target.value) / 100 : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  波动率 (最大 %)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={percentInputValue(criteria.volatility_1y_max)}
                  onChange={(e) => setCriteria({ ...criteria, volatility_1y_max: e.target.value ? Number(e.target.value) / 100 : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* 其他条件 */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center mb-4">
              <DollarSign className="w-5 h-5 text-green-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">其他条件</h2>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  基金规模 (最小亿元)
                </label>
                <input
                  type="number"
                  value={criteria.totalAsset_min ?? ''}
                  onChange={(e) => setCriteria({ ...criteria, totalAsset_min: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  基金规模 (最大亿元)
                </label>
                <input
                  type="number"
                  value={criteria.totalAsset_max ?? ''}
                  onChange={(e) => setCriteria({ ...criteria, totalAsset_max: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  综合评分 (最小)
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={criteria.score_min ?? ''}
                  onChange={(e) => setCriteria({ ...criteria, score_min: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  综合评分 (最大)
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={criteria.score_max ?? ''}
                  onChange={(e) => setCriteria({ ...criteria, score_max: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-4">
            <button
              onClick={handleScreen}
              disabled={loading}
              className="flex-1 flex items-center justify-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Filter className="w-4 h-4 mr-2" />
              {loading ? '筛选中...' : '开始筛选'}
            </button>
            <button
              onClick={handleSaveTemplate}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Save className="w-4 h-4 inline mr-2" />
              保存模板
            </button>
          </div>
        </div>

        {/* 模板列表 */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">内置策略</h2>
            <p className="mb-3 text-xs leading-5 text-gray-500">
              这些策略按当前本地数据字段设计，点击后会立即筛选；正式研究判断仍以销售规则和横向对比为门禁。
            </p>
            <div className="space-y-2">
              {builtInScreeningPresets.map((preset) => (
                <button
                  key={preset.name}
                  type="button"
                  onClick={() => applyBuiltInPreset(preset)}
                  className="w-full rounded-xl border border-blue-100 bg-blue-50 p-3 text-left transition-colors hover:border-blue-300 hover:bg-blue-100"
                >
                  <div className="text-sm font-semibold text-blue-950">{preset.name}</div>
                  <div className="mt-1 text-xs leading-5 text-blue-800">{preset.description}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">我的筛选模板</h2>
            {templates.length === 0 ? (
              <p className="text-sm text-gray-500">暂无保存的模板</p>
            ) : (
              <div className="space-y-2">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => handleLoadTemplate(template)}
                    className="w-full text-left p-3 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
                  >
                    <p className="text-sm font-medium text-gray-900">{template.name}</p>
                    {template.description && (
                      <p className="text-xs text-gray-500 mt-1">{template.description}</p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 筛选结果 */}
      {results.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-200 p-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                筛选结果 ({results.length} 只基金)
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                勾选 2-6 只进入研究横向对比；销售规则缺口仍需真实补录。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setCompareCodes(results.slice(0, 4).map((fund) => fund.windCode))}
                className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
              >
                <GitCompare className="h-4 w-4" />
                选前4只
              </button>
              {compareCodes.length ? (
                <Link
                  href={salesRulesHref}
                  className="rounded-lg border border-cyan-200 px-3 py-2 text-sm font-medium text-cyan-700 hover:bg-cyan-50"
                >
                  补已选规则
                </Link>
              ) : (
                <span className="cursor-not-allowed rounded-lg bg-cyan-100 px-3 py-2 text-sm font-medium text-cyan-400">
                  补已选规则
                </span>
              )}
              {compareCodes.length >= 2 ? (
                <Link
                  href={comparisonHref}
                  className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                >
                  去对比（{compareCodes.length}）
                </Link>
              ) : (
                <span className="cursor-not-allowed rounded-lg bg-indigo-100 px-3 py-2 text-sm font-medium text-indigo-400">
                  去对比（{compareCodes.length}）
                </span>
              )}
            </div>
          </div>
          {compareCodes.length ? (
            <div className="border-b border-gray-100 px-6 py-3 text-xs text-indigo-700">
              已选：{compareCodes.join(' / ')}
            </div>
          ) : null}
          <div className="border-b border-slate-100 bg-white px-6 py-5" data-testid="screening-condition-health-diagnosis">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-950">筛选条件健康诊断</div>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  先判断本次筛选是样本足够、证据充分、规则可放行，还是条件过窄/缺证/规则阻断；避免把“筛到了”误解成“已有研究结论”。
                </p>
              </div>
              <button
                type="button"
                onClick={downloadScreeningConditionHealthTsv}
                data-testid="screening-condition-health-download"
                className="inline-flex items-center gap-1 rounded-full bg-slate-950 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
              >
                <Download className="h-3.5 w-3.5" />
                下载诊断 TSV
              </button>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-4">
              {screeningConditionHealthRows.map((row) => (
                <div key={row.key} className={`rounded-2xl border p-4 ${
                  row.status.includes('阻断') || row.status.includes('过窄') || row.status === '先补证'
                    ? 'border-rose-100 bg-rose-50 text-rose-950'
                    : row.status.includes('待') || row.status.includes('偏少') || row.status.includes('扫描') || row.status.includes('缺')
                      ? 'border-amber-100 bg-amber-50 text-amber-950'
                      : 'border-emerald-100 bg-emerald-50 text-emerald-950'
                }`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-sm font-semibold">{row.title}</div>
                    <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-semibold">
                      {row.status}
                    </span>
                  </div>
                  <p className="mt-2 min-h-20 text-xs leading-5 opacity-85">{row.detail}</p>
                  {row.actionLabel === '下载证据 TSV' || row.actionLabel === '复核证据 TSV' ? (
                    <button
                      type="button"
                      onClick={downloadScreeningDecisionTraceTsv}
                      className="mt-3 inline-flex rounded-lg bg-white/80 px-3 py-1.5 text-xs font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-white"
                    >
                      {row.actionLabel}
                    </button>
                  ) : (
                    <Link href={row.actionHref} className="mt-3 inline-flex rounded-lg bg-white/80 px-3 py-1.5 text-xs font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-white">
                      {row.actionLabel}
                    </Link>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs leading-5 text-rose-800">
              筛选诊断硬边界：筛选条件健康只说明“这批结果是否值得继续研究”；销售规则/R1-R5、计划金额、费用、横评和研究复核报告门禁未完成前，不形成正式研究结论。
            </div>
          </div>
          <div className="border-b border-slate-100 bg-slate-50 px-6 py-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl bg-white px-4 py-3 ring-1 ring-slate-100">
                <div className="text-xs text-slate-500">筛选命中</div>
                <div className="mt-1 text-2xl font-semibold text-slate-900">{results.length}</div>
              </div>
              <div className="rounded-xl bg-white px-4 py-3 ring-1 ring-emerald-100">
                <div className="text-xs text-emerald-700">规则相对完整</div>
                <div className="mt-1 text-2xl font-semibold text-emerald-800">{resultMaturitySummary.readyCount}</div>
              </div>
              <div className="rounded-xl bg-white px-4 py-3 ring-1 ring-amber-100">
                <div className="text-xs text-amber-700">待补销售规则</div>
                <div className="mt-1 text-2xl font-semibold text-amber-800">{resultMaturitySummary.blockedCount}</div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              {resultMaturitySummary.readyComparisonHref ? (
                <Link href={resultMaturitySummary.readyComparisonHref} className="rounded-lg bg-emerald-600 px-3 py-2 font-medium text-white hover:bg-emerald-700">
                  比较规则完整样本
                </Link>
              ) : null}
              {resultMaturitySummary.blockedCount ? (
                <Link href={resultMaturitySummary.blockedSalesRulesHref} className="rounded-lg border border-amber-200 px-3 py-2 font-medium text-amber-700 hover:bg-amber-50">
                  {salesRuleGapSummary.reviewAlertBlocked ? '处理复查队列' : '补筛选结果缺口'}
                </Link>
              ) : null}
              {foundationFillableCodes.length ? (
                <button
                  type="button"
                  onClick={() => void importTushareFoundationForResults()}
                  disabled={foundationHydrating || !salesRuleGapsChecked}
                  className="rounded-lg border border-cyan-200 px-3 py-2 font-medium text-cyan-700 hover:bg-cyan-50 disabled:cursor-not-allowed disabled:opacity-50"
                  title={`只导入 Tushare fund_basic 的申购/赎回起始状态和来源日期，不会补${foundationManualFields}。`}
                >
                  {foundationHydrating ? '导入基础状态中...' : `先导入基础状态（${foundationFillableCodes.length}）`}
                </button>
              ) : null}
              <Link href={investorSelectionHref} className="rounded-lg border border-blue-200 px-3 py-2 font-medium text-blue-700 hover:bg-blue-50">
                用研究模型重排
              </Link>
              <button
                type="button"
                onClick={() => void saveReadyResultsToCandidatePool()}
                disabled={savingCandidates || !salesRuleGapsChecked || readyCandidateFunds.length === 0}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
              >
                <Layers3 className="h-4 w-4" />
                {savingCandidates
                  ? '保存中...'
                  : !salesRuleGapsChecked
                    ? '规则扫描中'
                    : readyCandidateFunds.length
                      ? `保存规则完整样本（${readyCandidateFunds.length}）`
                      : '暂无可入池样本'}
              </button>
              {savedPoolId ? (
                <Link href={canonicalResearchHref(`/pools?poolId=${encodeURIComponent(savedPoolId)}&status=candidate`)} className="rounded-lg border border-slate-200 px-3 py-2 font-medium text-slate-700 hover:bg-slate-50">
                  打开观察池
                </Link>
              ) : null}
            </div>
            {candidateMessage ? (
              <div className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{candidateMessage}</div>
            ) : null}
            {candidateError ? (
              <div className="mt-3 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm text-rose-700">{candidateError}</div>
            ) : null}
          </div>
          {salesRuleGapSummary.funds ? (
            <div className="border-b border-amber-100 bg-amber-50 px-6 py-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-sm font-semibold text-amber-950">
                    筛选结果销售规则雷达：{salesRuleGapSummary.funds} 只待补 / {salesRuleGapSummary.missingItems} 项，高优先级 {salesRuleGapSummary.highPriority} 只
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {salesRuleGapSummary.topGaps.map((gap) => (
                      <span key={gap.windCode} className="rounded-full bg-white px-2.5 py-1 text-xs text-amber-800 ring-1 ring-amber-100">
                        {gap.windCode} 缺 {gap.missingCount} 项
                      </span>
                    ))}
                  </div>
                  <div className="mt-2 text-xs leading-5 text-amber-800">
                    筛选只负责找出研究对象；销售规则硬缺口未补齐前，不生成正式研究复核报告，不把结果当成研究候选。
                  </div>
                </div>
                <Link href={salesRuleGapSummary.href} className="rounded-lg bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-700">
                  补全部缺口
                </Link>
              </div>
            </div>
          ) : null}
          <div className="border-b border-slate-100 bg-white px-6 py-5" data-testid="screening-purchase-action-queue">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">筛选结果研究行动队列</div>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  筛选只给出研究对象；这里把前 12 只拆成可执行下一步：补规则、进详情、加入横评或保存到观察池。
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-emerald-100 px-2.5 py-1 font-semibold text-emerald-700">可研究 {screeningPurchaseQueueSummary.ready}</span>
                <span className="rounded-full bg-amber-100 px-2.5 py-1 font-semibold text-amber-700">待补规则 {screeningPurchaseQueueSummary.rulesMissing}</span>
                {screeningPurchaseQueueSummary.reviewAlerts ? (
                  <span className="rounded-full bg-rose-100 px-2.5 py-1 font-semibold text-rose-700">复查队列 {screeningPurchaseQueueSummary.reviewAlerts}</span>
                ) : null}
                {screeningPurchaseQueueSummary.scanning ? (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">扫描中 {screeningPurchaseQueueSummary.scanning}</span>
                ) : null}
                <button
                  type="button"
                  onClick={copyScreeningDecisionTraceTsv}
                  disabled={!results.length}
                  data-testid="screening-copy-decision-trace-tsv"
                  className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 font-semibold text-blue-700 ring-1 ring-blue-100 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                  title="复制当前筛选结果的命中证据、销售规则状态和下一步；只作研究留痕。"
                >
                  <Copy className="h-3.5 w-3.5" />
                  复制证据 TSV
                </button>
                <button
                  type="button"
                  onClick={downloadScreeningDecisionTraceTsv}
                  disabled={!results.length}
                  data-testid="screening-download-decision-trace-tsv"
                  className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Download className="h-3.5 w-3.5" />
                  下载证据 TSV
                </button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {screeningPurchaseActionQueue.map((item) => (
                <div key={item.fund.windCode} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="font-semibold text-slate-950">{item.fund.name}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.fund.windCode} · {item.fund.type}</div>
                    </div>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.badgeClass}`}>
                      {item.label}
                    </span>
                  </div>
                  <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-100">
                    下一步：{item.primaryAction}
                  </div>
                  {item.screeningTrace ? (
                    <div className="mt-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900" data-testid="screening-decision-trace-card">
                      <div className="font-semibold">筛选命中证据：{item.screeningTrace.summary}</div>
                      <div className="mt-1 text-blue-800">
                        研究模板：{item.screeningTrace.researchTemplateName || item.methodologyConfig?.researchTemplateName || '待识别'}
                      </div>
                      {(item.screeningTrace.methodologyMissingEvidenceFields?.length || item.methodologyConfig?.methodologyMissingEvidenceFields?.length) ? (
                        <div className="mt-1 text-amber-800">
                          方法论缺口：{(item.screeningTrace.methodologyMissingEvidenceFields || item.methodologyConfig?.methodologyMissingEvidenceFields || []).slice(0, 5).join('、')}
                        </div>
                      ) : null}
                      {item.topCriteriaEvidence.length ? (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {item.topCriteriaEvidence.map((criterion) => (
                            <span key={criterion.key} title={`${criterion.source}：${criterion.note}`} className={`rounded-full px-2 py-0.5 font-medium ${
                              criterion.status === 'matched'
                                ? 'bg-emerald-100 text-emerald-800'
                                : criterion.status === 'missing'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-rose-100 text-rose-800'
                            }`}>
                              {criterion.label} {criterion.actual} / {criterion.threshold}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {item.salesRuleGap ? (
                    <div className="mt-2 text-xs leading-5 text-amber-700">
                      缺口：{item.salesRuleGap.missingItems.slice(0, 4).join('、')}
                    </div>
                  ) : null}
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
                    <Link href={item.primaryHref} className="rounded-lg bg-slate-900 px-3 py-1.5 text-white hover:bg-slate-800">
                      {item.salesRuleGap?.alertsHref ? '开复查队列' : item.status === 'rules_missing' ? '补规则' : '基金诊断'}
                    </Link>
                    <Link href={item.fundDetailHref} className="rounded-lg border border-blue-200 px-3 py-1.5 text-blue-700 hover:bg-blue-50">
                      看详情
                    </Link>
                    <button
                      type="button"
                      onClick={() => toggleCompare(item.fund)}
                      disabled={!item.canCompare && !compareCodes.includes(item.fund.windCode)}
                      className="rounded-lg border border-indigo-200 px-3 py-1.5 text-indigo-700 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {compareCodes.includes(item.fund.windCode) ? '移出横评' : '加入横评'}
                    </button>
                    <Link href={item.fundSalesRulesHref} className="rounded-lg border border-amber-200 px-3 py-1.5 text-amber-700 hover:bg-amber-50">
                      {item.salesRuleGap?.alertsHref ? '开复查队列' : '查规则'}
                    </Link>
                  </div>
                </div>
              ))}
            </div>
            {results.length > screeningPurchaseActionQueue.length ? (
              <div className="mt-3 text-xs text-slate-500">已展示前 {screeningPurchaseActionQueue.length} 只；完整列表见下方表格。</div>
            ) : null}
            <div className="mt-3 rounded-xl border border-rose-100 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">
              销售规则硬缺口或复查队列未清零前，不生成正式研究复核报告，不把筛选结果当成研究候选。
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">基金代码</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">基金名称</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">最新净值</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">规模(亿)</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {results.map((fund) => {
                  const salesRuleGap = salesRuleGapByCode.get(fund.windCode.toUpperCase()) || null
                  return (
                  <tr key={fund.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{fund.windCode}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="font-medium">{fund.name}</div>
                      {salesRuleGap ? (
                        <div className="mt-1 text-xs text-amber-700">
                          销售规则缺 {salesRuleGap.missingCount} 项：{salesRuleGap.missingItems.slice(0, 3).join('、')}
                        </div>
                      ) : (
                        <div className="mt-1 text-xs text-emerald-700">未检测到销售规则硬缺口</div>
                      )}
                      {fund.screeningDecisionTrace ? (
                        <div className="mt-1 text-xs text-blue-700" title={fund.screeningDecisionTrace.source}>
                          筛选证据：{fund.screeningDecisionTrace.summary}
                        </div>
                      ) : null}
                      {(fund.screeningDecisionTrace?.researchTemplateName || fund.methodologyConfig?.researchTemplateName) ? (
                        <div className="mt-1 text-xs text-indigo-700">
                          研究模板：{fund.screeningDecisionTrace?.researchTemplateName || fund.methodologyConfig?.researchTemplateName}
                          {(fund.screeningDecisionTrace?.methodologyMissingEvidenceFields?.length || fund.methodologyConfig?.methodologyMissingEvidenceFields?.length)
                            ? `；方法论缺口：${(fund.screeningDecisionTrace?.methodologyMissingEvidenceFields || fund.methodologyConfig?.methodologyMissingEvidenceFields || []).slice(0, 4).join('、')}`
                            : ''}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{fund.type}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {fund.nav ? Number(fund.nav).toFixed(4) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {fund.totalAsset ? (Number(fund.totalAsset) / 100000000).toFixed(2) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <div className="flex flex-wrap gap-3">
                        <Link
                          href={detailHref(fund)}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          查看详情
                        </Link>
                        <Link href={salesRuleGap?.alertsHref || salesRulesHrefForCodes([fund.windCode])} className="text-cyan-700 hover:text-cyan-900">
                          {salesRuleGap?.alertsHref ? '开复查队列' : salesRuleGap ? '补规则' : '查规则'}
                        </Link>
                        <button
                          type="button"
                          onClick={() => toggleCompare(fund)}
                          disabled={!compareCodes.includes(fund.windCode) && compareCodes.length >= 6}
                          className="text-indigo-700 hover:text-indigo-900 disabled:cursor-not-allowed disabled:text-gray-400"
                        >
                          {compareCodes.includes(fund.windCode) ? '移出对比' : '加入对比'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {hasScreened && !loading && results.length === 0 ? (
        <div className="rounded-2xl border border-amber-100 bg-white p-8 text-center shadow">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
            <Filter className="h-6 w-6 text-amber-600" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900">当前筛选条件没有命中基金</h2>
          <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-gray-500">
            这通常不是“没有基金可研究”，而是条件过窄或基础字段缺失。建议先放宽收益/回撤/规模条件，再用研究模型做风险画像、证据等级和销售规则门禁。
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3 text-sm">
            <button
              type="button"
              onClick={() => {
                setCriteria({})
                setResults([])
                setCompareCodes([])
                setSalesRuleGaps([])
                setHasScreened(false)
              }}
              className="rounded-lg border border-slate-200 px-4 py-2 font-medium text-slate-700 hover:bg-slate-50"
            >
              清空条件重筛
            </button>
            <Link href={investorSelectionHref} className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700">
              去研究选基
            </Link>
            <Link href="/market" className="rounded-lg border border-blue-200 px-4 py-2 font-medium text-blue-700 hover:bg-blue-50">
              去全市场浏览器
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  )
}
