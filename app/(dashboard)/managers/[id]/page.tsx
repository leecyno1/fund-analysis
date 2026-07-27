'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { AlertCircle, ArrowLeft, Briefcase, Building, Copy, Download, GraduationCap, ShieldCheck, TrendingUp, User } from 'lucide-react'
import { materialEvidenceHref, reviewEventsHref } from '@/lib/research-platform/routes'

type RiskProfile = 'conservative' | 'balanced' | 'aggressive'
type InvestmentHorizon = 'lt1y' | '1to3y' | 'gt3y'
type PurchasePlan = 'lump_sum' | 'sip'

type ManagerFund = {
  wind_code?: string
  name?: string
  fund_name?: string
  type?: string
  since?: string | null
  start_date?: string | null
  end_date?: string | null
}

type ManagerReport = {
  id: string
  title?: string
  reportDate?: string
  summary?: string
}

type ManagerScore = {
  id: string
  dimension?: string
  score?: number | string
  calculationMethod?: string
}

type ManagerAiReport = {
  id?: string
  reportType?: string
  createdAt?: string
}

type SalesRuleGap = {
  windCode: string
  priority: 'high' | 'medium' | 'low'
  missingItems: string[]
  missingCount: number
  nextAction: string
  alertsHref?: string | null
  gateSource?: string | null
}

type SalesRuleGapsPayload = {
  gaps: SalesRuleGap[]
  gapCount: number
  summary?: {
    high?: number
    medium?: number
    low?: number
  }
}

type RawAlertEvent = {
  event_type?: string
  status?: string
  fund_id?: string | null
  fund_code?: string | null
  fundCode?: string | null
  target_id?: string | null
  targetId?: string | null
  title?: string | null
  message?: string | null
  details?: unknown
  metadata?: unknown
}

type ManagerCounterEvidenceStatus = 'pass' | 'warn' | 'block'

interface Manager {
  id: string
  windCode: string | null
  name: string
  company: string | null
  education: string | null
  workYears: number | null
  managementYears: number | null
  currentFunds: string[]
  fundCount?: number
  avgScore?: number | null
  funds?: ManagerFund[]
  investmentPhilosophy?: string
  historicalPerformance: Record<string, unknown>
  styleAnalysis: Record<string, unknown>
  reports: ManagerReport[]
  scores: ManagerScore[]
  aiReports: ManagerAiReport[]
}

const riskProfileLabels: Record<RiskProfile, string> = {
  conservative: '稳健型',
  balanced: '均衡型',
  aggressive: '进取型',
}

const horizonLabels: Record<InvestmentHorizon, string> = {
  lt1y: '1 年以内',
  '1to3y': '1-3 年',
  gt3y: '3 年以上',
}

const purchasePlanLabels: Record<PurchasePlan, string> = {
  lump_sum: '一次性配置假设',
  sip: '定投假设',
}

function pickParam<T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return value && allowed.includes(value as T) ? (value as T) : fallback
}

function getBrowserParam(name: string) {
  if (typeof window === 'undefined') return null
  return new URLSearchParams(window.location.search).get(name)
}

function appendReturnTo(href: string, returnTo: string) {
  const separator = href.includes('?') ? '&' : '?'
  return `${href}${separator}returnTo=${encodeURIComponent(returnTo)}`
}

function safeReturnPath(returnTo: string | null | undefined, fallback = '/managers') {
  return returnTo?.startsWith('/') && !returnTo.startsWith('//') ? returnTo : fallback
}

function formatFundDate(value?: string | null) {
  if (!value) return '缺失'
  if (/^\d{8}$/.test(value)) {
    return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`
  }
  return value
}

function formatOptionalDate(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString()
}

function decodeRouteParam(value?: string) {
  if (!value) return ''
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function safeFileStem(value: string) {
  return value.replace(/[\\/:*?"<>|\s]+/gu, '_').replace(/_+/gu, '_').replace(/^_|_$/gu, '').slice(0, 80) || 'manager_fund_queue'
}

function tsvCell(value: unknown) {
  return String(value ?? '').replace(/\t|\r?\n/gu, ' ')
}

function managerCounterEvidenceClass(status: ManagerCounterEvidenceStatus) {
  if (status === 'pass') return 'border-emerald-100 bg-emerald-50 text-emerald-950'
  if (status === 'warn') return 'border-amber-100 bg-amber-50 text-amber-950'
  return 'border-rose-100 bg-rose-50 text-rose-950'
}

function managerCounterEvidenceBadgeClass(status: ManagerCounterEvidenceStatus) {
  if (status === 'pass') return 'bg-emerald-100 text-emerald-800'
  if (status === 'warn') return 'bg-amber-100 text-amber-800'
  return 'bg-rose-100 text-rose-800'
}

function managerCounterEvidenceStatusLabel(status: ManagerCounterEvidenceStatus) {
  if (status === 'pass') return '暂未触发'
  if (status === 'warn') return '需要复核'
  return '阻断优先'
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function stringValue(value: unknown) {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return ''
}

function alertFundCode(event: RawAlertEvent) {
  const details = asRecord(event.details)
  const metadata = asRecord(event.metadata)
  return [
    event.fund_code,
    event.fundCode,
    event.fund_id,
    event.target_id,
    event.targetId,
    details.wind_code,
    details.fund_code,
    metadata.windCode,
    metadata.wind_code,
    metadata.fundCode,
    metadata.fund_code,
  ].map(stringValue).find(Boolean)?.toUpperCase() || ''
}

function getBrowserPurchasePlan() {
  return pickParam(getBrowserParam('purchasePlan'), ['lump_sum', 'sip'] as const, 'sip')
}

function defaultPlannedAmountForPlan(purchasePlan: PurchasePlan) {
  return purchasePlan === 'lump_sum' ? '10000' : '1000'
}

function normalizePlannedAmountInput(value: string | null | undefined, purchasePlan: PurchasePlan) {
  const amount = Number(value || '')
  return Number.isFinite(amount) && amount > 0 ? String(Math.round(amount)) : defaultPlannedAmountForPlan(purchasePlan)
}

function getBrowserPlannedAmountForPlan(purchasePlan: PurchasePlan) {
  return getBrowserParam('plannedAmount') || getBrowserParam(purchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount')
}

function plannedAmountSearchParams(purchasePlan: PurchasePlan, plannedAmount: string) {
  const amount = normalizePlannedAmountInput(plannedAmount, purchasePlan)
  return {
    plannedAmount: amount,
    [purchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount']: amount,
  }
}

export default function ManagerDetailPage() {
  const params = useParams()
  const rawManagerId = Array.isArray(params.id) ? params.id[0] : params.id
  const managerId = decodeRouteParam(rawManagerId)
  const [manager, setManager] = useState<Manager | null>(null)
  const [loading, setLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [salesRuleGapPayload, setSalesRuleGapPayload] = useState<SalesRuleGapsPayload | null>(null)
  const [salesRuleGapLoading, setSalesRuleGapLoading] = useState(false)
  const [salesRuleGapError, setSalesRuleGapError] = useState<string | null>(null)
  const [riskProfile, setRiskProfile] = useState<RiskProfile>(() => pickParam(getBrowserParam('profile'), ['conservative', 'balanced', 'aggressive'] as const, 'balanced'))
  const [investmentHorizon, setInvestmentHorizon] = useState<InvestmentHorizon>(() => pickParam(getBrowserParam('horizon'), ['lt1y', '1to3y', 'gt3y'] as const, '1to3y'))
  const [purchasePlan, setPurchasePlan] = useState<PurchasePlan>(() => getBrowserPurchasePlan())
  const [plannedAmount, setPlannedAmount] = useState(() => {
    const initialPurchasePlan = getBrowserPurchasePlan()
    return normalizePlannedAmountInput(getBrowserPlannedAmountForPlan(initialPurchasePlan), initialPurchasePlan)
  })
  const [sourceReturnHref, setSourceReturnHref] = useState(() => safeReturnPath(getBrowserParam('returnTo')))
  const [managerEvidenceCopyStatus, setManagerEvidenceCopyStatus] = useState<'idle' | 'copied' | 'fallback'>('idle')
  const [managerQueueCopyStatus, setManagerQueueCopyStatus] = useState<'idle' | 'copied' | 'fallback'>('idle')
  const plannedAmountParams = useMemo(
    () => plannedAmountSearchParams(purchasePlan, plannedAmount),
    [plannedAmount, purchasePlan],
  )
  const normalizedPlannedAmount = plannedAmountParams.plannedAmount
  const investorContextQuery = useMemo(() => new URLSearchParams({
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams,
  }).toString(), [investmentHorizon, plannedAmountParams, purchasePlan, riskProfile])
  const managerBaseHref = useMemo(
    () => `/managers/${encodeURIComponent(managerId)}?${investorContextQuery}`,
    [investorContextQuery, managerId],
  )
  const currentManagerHref = useMemo(
    () => appendReturnTo(managerBaseHref, sourceReturnHref),
    [managerBaseHref, sourceReturnHref],
  )

  const fetchManagerDetail = useCallback(async () => {
    if (!managerId) return
    setLoading(true)
    setErrorMessage(null)
    try {
      const response = await fetch(`/api/managers/${encodeURIComponent(managerId)}`)
      const data = await response.json().catch(() => ({}))
      if (response.ok) {
        setManager(data)
      } else {
        setManager(null)
        setErrorMessage(data.error || '基金经理不存在')
      }
    } catch (error) {
      console.error('获取基金经理详情失败:', error)
      setManager(null)
      setErrorMessage(error instanceof Error ? error.message : '获取基金经理详情失败')
    } finally {
      setLoading(false)
    }
  }, [managerId])

  useEffect(() => {
    if (!managerId) return
    const timeout = globalThis.setTimeout(() => {
      void fetchManagerDetail()
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [fetchManagerDetail, managerId])

  useEffect(() => {
    const timeout = globalThis.setTimeout(() => {
      const nextPurchasePlan = getBrowserPurchasePlan()
      setPurchasePlan(nextPurchasePlan)
      setPlannedAmount(normalizePlannedAmountInput(getBrowserPlannedAmountForPlan(nextPurchasePlan), nextPurchasePlan))
      setSourceReturnHref(safeReturnPath(getBrowserParam('returnTo')))
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [managerId])

  const managerSalesRuleCodes = useMemo(() => {
    if (!manager?.funds?.length) return []
    return Array.from(
      new Set(manager.funds.map((fund) => fund.wind_code).filter((code): code is string => Boolean(code))),
    ).slice(0, 30)
  }, [manager])

  useEffect(() => {
    const controller = new AbortController()
    const timeout = globalThis.setTimeout(async () => {
      if (!managerSalesRuleCodes.length) {
        setSalesRuleGapPayload(null)
        setSalesRuleGapError(null)
        return
      }
      try {
        setSalesRuleGapLoading(true)
        setSalesRuleGapError(null)
        const params = new URLSearchParams({
          codes: managerSalesRuleCodes.join(','),
          limit: String(managerSalesRuleCodes.length),
          purchasePlan,
          ...plannedAmountParams,
        })
        const [response, alertsResponse] = await Promise.all([
          fetch(`/api/evidence-coverage/materials/gaps?${params.toString()}`, {
            cache: 'no-store',
            signal: controller.signal,
          }),
          fetch('/api/evidence-coverage/review-events', {
            cache: 'no-store',
            signal: controller.signal,
          }),
        ])
        const payload = await response.json().catch(() => ({}))
        const alertsPayload = await alertsResponse.json().catch(() => ({}))
        if (!response.ok || !alertsResponse.ok) {
          throw new Error(!response.ok
            ? payload.error || payload.detail || '读取经理名下基金销售规则缺口失败'
            : alertsPayload.error || alertsPayload.detail || '读取复查队列失败，不能证明经理名下基金销售规则/R1-R5证据有效')
        }
        const targetCodes = new Set(managerSalesRuleCodes.map((code) => code.toUpperCase()))
        const gapMap = new Map<string, SalesRuleGap>((Array.isArray(payload.gaps) ? payload.gaps as SalesRuleGap[] : [])
          .map((gap) => [gap.windCode.toUpperCase(), gap]))
        const activeSalesRuleReviewAlerts = (Array.isArray(alertsPayload.events) ? alertsPayload.events as RawAlertEvent[] : [])
          .filter((event) => event.event_type === 'sales_rule_evidence' && event.status !== 'resolved' && targetCodes.has(alertFundCode(event)))
        activeSalesRuleReviewAlerts.forEach((event) => {
          const windCode = alertFundCode(event)
          const existing = gapMap.get(windCode)
          const title = stringValue(event.title) || '销售规则/R1-R5证据待补'
          const message = stringValue(event.message)
          const missingItem = `复查队列未解决：${title}${message ? `（${message}）` : ''}`
          const missingItems = Array.from(new Set([...(existing?.missingItems || []), missingItem]))
          gapMap.set(windCode, {
            ...(existing || {
              windCode,
              priority: 'high',
              nextAction: '先处理复查队列，再恢复经理名下基金研究路径',
            }),
            priority: 'high',
            missingItems,
            missingCount: Math.max(existing?.missingCount || 0, missingItems.length),
            nextAction: '先处理复查队列，再恢复经理名下基金研究路径',
            alertsHref: reviewEventsHref({ returnTo: currentManagerHref }),
            gateSource: 'local.alert_events.sales_rule_evidence',
          })
        })
        setSalesRuleGapPayload({
          ...payload,
          gaps: Array.from(gapMap.values()),
          gapCount: gapMap.size,
          source: activeSalesRuleReviewAlerts.length
            ? `${payload.source || 'local.sales_rule_gaps'}+local.alert_events.sales_rule_evidence`
            : payload.source,
        })
      } catch (error) {
        if (!controller.signal.aborted) {
          setSalesRuleGapPayload({
            gaps: managerSalesRuleCodes.map((windCode) => ({
              windCode,
              priority: 'high',
              missingItems: ['复查队列读取失败：不能证明经理名下基金销售规则/R1-R5证据有效'],
              missingCount: 1,
              nextAction: '先打开复查队列，确认销售规则/R1-R5证据事件状态后再恢复经理评价研究路径',
              alertsHref: reviewEventsHref({ returnTo: currentManagerHref }),
              gateSource: 'local.alert_events.sales_rule_evidence',
            })),
            gapCount: managerSalesRuleCodes.length,
            summary: { high: managerSalesRuleCodes.length, medium: 0, low: 0 },
          })
          setSalesRuleGapError(error instanceof Error ? error.message : '读取经理名下基金销售规则缺口失败')
        }
      } finally {
        if (!controller.signal.aborted) setSalesRuleGapLoading(false)
      }
    }, 0)

    return () => {
      controller.abort()
      globalThis.clearTimeout(timeout)
    }
  }, [currentManagerHref, managerSalesRuleCodes, plannedAmountParams, purchasePlan])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (!manager) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <div className="text-gray-500 mb-4">{errorMessage || '基金经理不存在'}</div>
        <Link href={sourceReturnHref} className="text-blue-600 hover:text-blue-800" data-testid="manager-detail-return-link">
          返回列表
        </Link>
      </div>
    )
  }

  const allFundRows = manager.funds || []
  const uniqueFundCodes = Array.from(
    new Set(allFundRows.map((fund) => fund.wind_code).filter((code): code is string => Boolean(code))),
  )
  const activeFundCodes = Array.from(
    new Set(allFundRows.filter((fund) => !fund.end_date).map((fund) => fund.wind_code).filter((code): code is string => Boolean(code))),
  )
  const salesRuleCodes = managerSalesRuleCodes
  const activeFundRows = allFundRows.filter((fund) => !fund.end_date)
  const historicalFundRows = allFundRows.filter((fund) => fund.end_date)
  const managerSalesRuleGaps = salesRuleGapPayload?.gaps || []
  const managerSalesRuleGapMap = new Map(managerSalesRuleGaps.map((gap) => [gap.windCode.toUpperCase(), gap]))
  const rawCompareCodes = (activeFundCodes.length >= 2 ? activeFundCodes : uniqueFundCodes).slice(0, 8)
  const compareCodes = (salesRuleGapPayload
    ? rawCompareCodes.filter((code) => !managerSalesRuleGapMap.has(code.toUpperCase()))
    : rawCompareCodes
  ).slice(0, 8)
  const salesRuleBlockedCompareCount = rawCompareCodes.filter((code) => managerSalesRuleGapMap.has(code.toUpperCase())).length
  const managerSalesRuleGapSummary = {
    gapCount: managerSalesRuleGaps.length,
    highPriority: managerSalesRuleGaps.filter((gap) => gap.priority === 'high').length,
    missingItems: managerSalesRuleGaps.reduce((sum, gap) => sum + gap.missingCount, 0),
    reviewAlerts: managerSalesRuleGaps.filter((gap) => Boolean(gap.alertsHref)).length,
  }
  const managerTenureStatus = manager.managementYears == null
    ? '任期证据待补'
    : manager.managementYears >= 5
      ? '长期任期样本'
      : manager.managementYears >= 2
        ? '任期可观察'
        : '任期偏短'
  const managerWorkflowNextAction = managerSalesRuleGapSummary.gapCount > 0
    ? managerSalesRuleGapSummary.reviewAlerts
      ? `该经理名下 ${managerSalesRuleGapSummary.reviewAlerts} 只基金复查队列未清零；先处理复查队列，再做横向比较和研究复核报告。`
      : `该经理名下 ${managerSalesRuleGapSummary.gapCount} 只基金仍有销售规则硬缺口，共缺 ${managerSalesRuleGapSummary.missingItems} 项；先补规则，再做横向比较和研究复核报告。`
    : compareCodes.length >= 2
    ? '优先比较该经理未见离任基金，再逐只进入研究诊断；不要只凭经理名气直接筛入研究样本。'
    : compareCodes.length === 1
      ? '当前仅有 1 只可比较基金，应进入单基金研究诊断并补销售规则。'
      : '当前缺少可落地基金代码，应先补齐 Tushare 任职基金数据。'
  const managerTenureYears = manager.managementYears == null ? null : Number(manager.managementYears)
  const managerPurchaseLensRawScore = Math.round(
    (managerTenureYears == null ? 8 : managerTenureYears >= 5 ? 28 : managerTenureYears >= 2 ? 22 : 12)
    + (activeFundRows.length >= 3 ? 18 : activeFundRows.length >= 1 ? 12 : 0)
    + (managerSalesRuleGapSummary.gapCount === 0 && salesRuleGapPayload ? 28 : managerSalesRuleGapSummary.gapCount > 0 ? 8 : 14)
    + (compareCodes.length >= 2 ? 16 : compareCodes.length === 1 ? 8 : 0)
    + (manager.company ? 5 : 0)
    + (manager.education ? 5 : 0),
  )
  const managerPurchaseLensScore = managerSalesRuleGapSummary.gapCount > 0
    ? Math.min(managerPurchaseLensRawScore, 58)
    : activeFundRows.length === 0
      ? Math.min(managerPurchaseLensRawScore, 45)
      : Math.min(100, managerPurchaseLensRawScore)
  const managerPurchaseLensLabel = managerSalesRuleGapSummary.gapCount > 0
    ? managerSalesRuleGapSummary.reviewAlerts ? '先处理复查队列' : '先补规则再评价'
    : activeFundRows.length === 0
      ? '缺少基金研究入口'
      : managerPurchaseLensScore >= 75
        ? '可作为优先经理入口'
        : managerPurchaseLensScore >= 60
          ? '可观察后横评'
          : '先补经理/基金证据'
  const managerPurchaseLensClass = managerSalesRuleGapSummary.gapCount > 0
    ? 'border-amber-100 bg-amber-50 text-amber-900'
    : activeFundRows.length === 0
      ? 'border-slate-100 bg-slate-50 text-slate-800'
      : managerPurchaseLensScore >= 75
        ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
        : managerPurchaseLensScore >= 60
          ? 'border-blue-100 bg-blue-50 text-blue-900'
          : 'border-slate-100 bg-slate-50 text-slate-800'
  const managerPurchaseLensReasons = [
    managerTenureYears == null ? '管理年限待补，经理稳定性证据不足' : `管理年限 ${managerTenureYears.toFixed(1)} 年，${managerTenureStatus}`,
    activeFundRows.length ? `当前未见离任基金 ${activeFundRows.length} 只，可落到具体基金诊断` : '当前缺少未见离任基金，不能作为研究入口',
    compareCodes.length >= 2 ? `可带入 ${compareCodes.length} 只基金做同经理横向比较` : '同经理可比样本不足，需进入单基金诊断',
    salesRuleBlockedCompareCount > 0 ? `已从默认横评剔除 ${salesRuleBlockedCompareCount} 只销售规则/复查队列待补基金` : '',
    managerSalesRuleGapSummary.gapCount > 0
      ? managerSalesRuleGapSummary.reviewAlerts
        ? `名下基金复查队列 ${managerSalesRuleGapSummary.reviewAlerts} 只未清零，处理前不形成正式研究结论`
        : `名下基金销售规则仍缺 ${managerSalesRuleGapSummary.missingItems} 项，补齐前不形成正式研究结论`
      : salesRuleGapPayload
        ? '当前名下基金未检测到销售规则硬缺口'
        : '销售规则扫描待完成',
    manager.company ? `公司：${manager.company}` : '公司信息待补',
  ]
  const managerEvidenceConclusion = managerSalesRuleGapSummary.gapCount > 0
    ? '暂不支持正式研究结论'
    : activeFundRows.length === 0
      ? '仅可作为履历观察'
      : compareCodes.length >= 2 && managerPurchaseLensScore >= 60
        ? '可进入名下基金横评'
        : '先做单基金诊断'
  const managerEvidencePrimaryAction = managerSalesRuleGapSummary.gapCount > 0
    ? managerSalesRuleGapSummary.reviewAlerts
      ? `处理 ${managerSalesRuleGapSummary.reviewAlerts} 只名下基金复查队列事件`
      : `补齐 ${managerSalesRuleGapSummary.gapCount} 只名下基金销售规则硬缺口`
    : compareCodes.length >= 2
      ? `比较 ${compareCodes.length} 只名下基金的研究证据`
      : activeFundCodes[0]
        ? `诊断 ${activeFundCodes[0]} 的研究证据`
        : '补齐本地 Tushare 任职基金数据'
  const managerEvidenceReverseTriggers = managerSalesRuleGapSummary.gapCount > 0
    ? [
      managerSalesRuleGapSummary.reviewAlerts ? '名下基金销售规则/R1-R5复查事件全部处理完成' : '名下基金风险等级、限购金额、申购状态、来源日期等硬缺口全部补齐',
      '至少 1 只未见离任基金完成销售规则、净值回放和同类比较',
      '经理入口评价落到具体基金后，再生成研究复核报告',
    ]
    : activeFundRows.length === 0
      ? [
        '本地 Tushare 任职记录同步出未见离任基金',
        '可落地基金代码能进入单基金研究诊断',
        '经理资料从履历观察升级为基金研究入口证据',
      ]
      : [
        '名下基金新增销售规则硬缺口时，降级为补规则状态',
        '同经理横评出现费用、回撤或业绩一致性明显劣势时，移出优先入口',
        '任期或任职基金数据被最新同步修正时，重新计算经理入口证据',
      ]
  const managerAnalysisHref = appendReturnTo(`/analysis/manager?managerId=${encodeURIComponent(manager.id)}&${investorContextQuery}`, currentManagerHref)
  const comparisonQuery = new URLSearchParams({
    codes: compareCodes.join(','),
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams,
    autoReplay: '1',
    returnTo: currentManagerHref,
  }).toString()
  const comparisonHref = `/analysis/comparison?${comparisonQuery}`
  const comparisonHrefForCodes = (codes: string[]) => `/analysis/comparison?${new URLSearchParams({
    codes: codes.join(','),
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams,
    autoReplay: '1',
    returnTo: currentManagerHref,
  }).toString()}`
  const fundDetailHrefForCode = (fundCode: string) => appendReturnTo(
    `/funds/${encodeURIComponent(fundCode)}?${investorContextQuery}`,
    currentManagerHref,
  )
  const salesRulesParams = new URLSearchParams()
  if (salesRuleCodes.length > 0) salesRulesParams.set('codes', salesRuleCodes.join(','))
  salesRulesParams.set('purchasePlan', purchasePlan)
  Object.entries(plannedAmountParams).forEach(([key, value]) => salesRulesParams.set(key, value))
  salesRulesParams.set('returnTo', currentManagerHref)
  const salesRulesHref = materialEvidenceHref(salesRulesParams)
  const managerSalesRuleActionHref = managerSalesRuleGapSummary.reviewAlerts
    ? reviewEventsHref({ returnTo: currentManagerHref })
    : salesRulesHref
  const managerPurchaseLensActionHref = managerSalesRuleGapSummary.gapCount > 0
    ? managerSalesRuleActionHref
    : compareCodes.length >= 2
      ? comparisonHref
      : activeFundCodes[0]
        ? fundDetailHrefForCode(activeFundCodes[0])
        : '/sync'
  const managerPurchaseLensActionLabel = managerSalesRuleGapSummary.gapCount > 0
    ? managerSalesRuleGapSummary.reviewAlerts ? '打开复查队列' : '先补名下基金规则'
    : compareCodes.length >= 2
      ? '比较名下基金'
      : activeFundCodes[0]
        ? '进入单基金诊断'
        : '先同步任职数据'
  const managerFundPurchaseQueue = allFundRows.map((fund, index) => {
    const fundCode = fund.wind_code || ''
    const normalizedCode = fundCode.toUpperCase()
    const salesRuleGap = fundCode ? managerSalesRuleGapMap.get(normalizedCode) || null : null
    const isActive = !fund.end_date
    const fundName = fund.name || fund.fund_name || fundCode || `基金 ${index + 1}`
    const fundHref = fundCode
      ? fundDetailHrefForCode(fundCode)
      : appendReturnTo('/funds', currentManagerHref)
    const baseSalesRuleHref = fundCode
      ? materialEvidenceHref(new URLSearchParams({ codes: fundCode, purchasePlan, ...plannedAmountParams, returnTo: currentManagerHref }))
      : salesRulesHref
    const salesRuleHref = salesRuleGap?.alertsHref ? appendReturnTo(salesRuleGap.alertsHref, currentManagerHref) : baseSalesRuleHref
    const status = !fundCode
      ? 'code_missing'
      : !isActive
        ? 'history_only'
        : salesRuleGap
          ? 'rules_missing'
          : salesRuleGapPayload
            ? 'ready_for_diagnosis'
            : 'rules_pending'
    const label = status === 'code_missing'
      ? '代码待补'
      : status === 'history_only'
        ? '历史任职观察'
        : status === 'rules_missing'
          ? salesRuleGap?.alertsHref ? '先处理复查队列' : '先补销售规则'
          : status === 'ready_for_diagnosis'
            ? '进入研究诊断'
            : '规则扫描中'
    const className = status === 'rules_missing'
      ? 'bg-rose-50 text-rose-700 ring-1 ring-rose-100'
      : status === 'ready_for_diagnosis'
        ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100'
        : status === 'history_only'
          ? 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'
          : 'bg-amber-50 text-amber-700 ring-1 ring-amber-100'
    const nextAction = status === 'rules_missing'
      ? salesRuleGap?.alertsHref ? `处理 ${salesRuleGap?.missingCount ?? 0} 项复查队列事件` : `补齐 ${salesRuleGap?.missingCount ?? 0} 项销售规则硬缺口`
      : status === 'ready_for_diagnosis'
        ? '进入单基金详情页，核查净值回放、持仓暴露和同类比较'
        : status === 'history_only'
          ? '仅作为经理履历样本，不进入研究样本'
          : status === 'code_missing'
            ? '先同步任职基金代码'
            : '等待销售规则缺口扫描完成'
    const primaryHref = status === 'rules_missing' ? salesRuleHref : fundHref
    const primaryLabel = status === 'rules_missing'
      ? salesRuleGap?.alertsHref ? '开复查队列' : '补规则'
      : status === 'ready_for_diagnosis'
        ? '诊断基金'
        : status === 'history_only'
          ? '查看履历基金'
          : '查看基金'
    const inDefaultComparison = Boolean(fundCode && compareCodes.includes(normalizedCode))
    const defaultCompareRole = inDefaultComparison
      ? '默认纳入经理横评'
      : !fundCode
        ? '不纳入横评：代码待补'
        : !isActive
          ? '不纳入横评：历史任职'
          : salesRuleGap
            ? '已剔除：销售规则/复查队列待补'
            : salesRuleGapPayload
              ? '不纳入横评：可比名额或样本不足'
              : '待销售规则扫描后决定'
    return {
      key: `${fundCode || fundName}-${index}`,
      fundCode,
      fundName,
      type: fund.type || '',
      startDate: formatFundDate(fund.start_date || fund.since),
      endDate: formatFundDate(fund.end_date),
      status,
      label,
      className,
      nextAction,
      salesRuleGap,
      fundHref,
      salesRuleHref,
      primaryHref,
      primaryLabel,
      inDefaultComparison,
      defaultCompareRole,
    }
  })
  const activePurchaseQueue = managerFundPurchaseQueue.filter((item) => item.status !== 'history_only')
  const purchaseQueueSummary = {
    ready: managerFundPurchaseQueue.filter((item) => item.status === 'ready_for_diagnosis').length,
    rulesMissing: managerFundPurchaseQueue.filter((item) => item.status === 'rules_missing').length,
    historyOnly: managerFundPurchaseQueue.filter((item) => item.status === 'history_only').length,
    pending: managerFundPurchaseQueue.filter((item) => item.status === 'rules_pending' || item.status === 'code_missing').length,
  }
  const managerFundGateMatrix = managerFundPurchaseQueue.slice(0, 8).map((item) => {
    const managerLens = item.status === 'history_only'
      ? '履历证据'
      : activeFundRows.length === 0
        ? '缺基金入口'
        : managerPurchaseLensLabel
    const hasReviewAlert = Boolean(item.salesRuleGap?.alertsHref)
    const fundGate = item.status === 'rules_missing'
      ? hasReviewAlert ? '复查队列未解决' : '基金门禁阻断'
      : item.status === 'ready_for_diagnosis'
        ? '基金可诊断'
        : item.status === 'history_only'
          ? '不进研究路径'
          : '门禁待扫描'
    const investabilityRole = item.status === 'ready_for_diagnosis'
      ? '横评/详情候选'
      : item.status === 'rules_missing'
        ? hasReviewAlert ? '复查队列样本' : '补规则样本'
        : item.status === 'history_only'
          ? '经理履历样本'
          : '补代码/待扫描'
    const boundary = item.status === 'ready_for_diagnosis'
      ? '经理评价通过入口筛选后，仍需单基金净值回放、持仓暴露和同类比较。'
      : item.status === 'rules_missing'
        ? hasReviewAlert
          ? `复查队列仍有 ${item.salesRuleGap?.missingCount ?? 0} 项未解决，经理入口分不能覆盖过期/待核销售规则证据。`
          : `销售规则缺 ${item.salesRuleGap?.missingCount ?? 0} 项，经理入口分不能覆盖基金硬缺口。`
        : item.status === 'history_only'
          ? '历史任职仅证明经理履历，不作为今天的研究复核对象。'
          : '基金代码或销售规则扫描未完成，不能形成研究判断。'
    return {
      ...item,
      managerLens,
      fundGate,
      investabilityRole,
      boundary,
    }
  })
  const managerFundPurchaseQueueTsv = [
    ['基金代码', '基金名称', '基金类型', '任职开始', '任职结束', '研究状态', '默认横评处理', '销售规则缺口数', '缺口字段', '下一动作', '基金详情入口', '销售规则入口'].join('\t'),
    ...managerFundPurchaseQueue.map((item) => [
      item.fundCode || '',
      item.fundName,
      item.type || '',
      item.startDate,
      item.endDate,
      item.label,
      item.defaultCompareRole,
      item.salesRuleGap?.missingCount ?? 0,
      item.salesRuleGap?.missingItems.join('、') || '',
      item.nextAction,
      item.fundHref,
      item.salesRuleHref,
    ].map(tsvCell).join('\t')),
    ['说明', '经理评价只能作为选基入口，正式研究必须落到逐只基金的销售规则、净值回放、持仓暴露和同类横评；默认横评只纳入销售规则未阻断样本。', '', '', '', '', '', '', '', '', '', ''].join('\t'),
  ].join('\n')
  const downloadManagerFundPurchaseQueue = () => {
    const blob = new Blob([`\uFEFF${managerFundPurchaseQueueTsv}`], { type: 'text/tab-separated-values;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${safeFileStem(`${manager.name}_名下基金研究队列`)}_${new Date().toISOString().slice(0, 10)}.tsv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  const copyManagerFundPurchaseQueue = async () => {
    try {
      let copied = false
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(managerFundPurchaseQueueTsv)
          copied = true
        } catch {
          copied = false
        }
      }
      if (!copied) {
        const textArea = document.createElement('textarea')
        textArea.value = managerFundPurchaseQueueTsv
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        copied = document.execCommand('copy')
        textArea.remove()
      }
      if (!copied) throw new Error('copy failed')
      setManagerQueueCopyStatus('copied')
      globalThis.setTimeout(() => setManagerQueueCopyStatus('idle'), 1800)
    } catch {
      downloadManagerFundPurchaseQueue()
      setManagerQueueCopyStatus('fallback')
      globalThis.setTimeout(() => setManagerQueueCopyStatus('idle'), 1800)
    }
  }
  const fundTypeBuckets = allFundRows.reduce<Record<string, number>>((acc, fund) => {
    const type = fund.type || '类型待补'
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {})
  const activeTypeBuckets = activeFundRows.reduce<Record<string, number>>((acc, fund) => {
    const type = fund.type || '类型待补'
    acc[type] = (acc[type] || 0) + 1
    return acc
  }, {})
  const dominantType = Object.entries(activeTypeBuckets).sort((left, right) => right[1] - left[1])[0]
    || Object.entries(fundTypeBuckets).sort((left, right) => right[1] - left[1])[0]
    || null
  const activeTypeCount = Object.keys(activeTypeBuckets).length
  const careerTypeCount = Object.keys(fundTypeBuckets).length
  const activeConcentrationRatio = activeFundRows.length && dominantType
    ? dominantType[1] / activeFundRows.length
    : 0
  const careerContinuityRatio = allFundRows.length
    ? activeFundRows.length / allFundRows.length
    : 0
  const managerStyleStabilityScore = Math.round(Math.min(100,
    (managerTenureYears == null ? 10 : managerTenureYears >= 5 ? 30 : managerTenureYears >= 2 ? 22 : 12)
    + (activeConcentrationRatio >= 0.75 ? 24 : activeConcentrationRatio >= 0.5 ? 18 : activeFundRows.length ? 10 : 0)
    + (careerTypeCount <= 2 && allFundRows.length > 0 ? 18 : careerTypeCount <= 4 ? 12 : 6)
    + (careerContinuityRatio >= 0.7 ? 14 : careerContinuityRatio >= 0.4 ? 9 : activeFundRows.length ? 5 : 0)
    + (managerSalesRuleGapSummary.gapCount === 0 && salesRuleGapPayload ? 14 : managerSalesRuleGapSummary.gapCount > 0 ? 4 : 8),
  ))
  const managerStyleStabilityLabel = managerSalesRuleGapSummary.gapCount > 0
    ? '风格证据待规则确认'
    : activeFundRows.length === 0
      ? '仅履历观察'
      : managerStyleStabilityScore >= 78
        ? '能力圈较稳定'
        : managerStyleStabilityScore >= 62
          ? '能力圈可观察'
          : '风格一致性待核'
  const managerStyleStabilityClass = managerSalesRuleGapSummary.gapCount > 0
    ? 'border-amber-100 bg-amber-50 text-amber-900'
    : activeFundRows.length === 0
      ? 'border-slate-100 bg-slate-50 text-slate-800'
      : managerStyleStabilityScore >= 78
        ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
        : managerStyleStabilityScore >= 62
          ? 'border-blue-100 bg-blue-50 text-blue-900'
          : 'border-rose-100 bg-rose-50 text-rose-900'
  const managerStyleSignals = [
    dominantType ? `主能力圈：${dominantType[0]}（${dominantType[1]} 只${activeFundRows.length ? '未见离任/在管样本' : '任职样本'}）` : '主能力圈待补',
    activeFundRows.length ? `在管类型覆盖 ${activeTypeCount || 0} 类，集中度 ${(activeConcentrationRatio * 100).toFixed(0)}%` : '缺少未见离任基金，不能验证当前能力圈',
    `历史任职类型覆盖 ${careerTypeCount || 0} 类，样本 ${allFundRows.length} 条`,
    `在管连续性 ${(careerContinuityRatio * 100).toFixed(0)}%，历史离任样本 ${historicalFundRows.length} 条`,
    managerTenureYears == null ? '管理年限待补' : `管理年限 ${managerTenureYears.toFixed(1)} 年`,
  ]
  const managerStyleWarnings = [
    managerSalesRuleGapSummary.gapCount > 0
      ? managerSalesRuleGapSummary.reviewAlerts
        ? `名下基金仍有 ${managerSalesRuleGapSummary.reviewAlerts} 只复查队列未清零，风格稳定不能替代研究门禁`
        : `名下基金仍有 ${managerSalesRuleGapSummary.gapCount} 只销售规则硬缺口，风格稳定不能替代研究门禁`
      : '',
    activeTypeCount >= 4 ? '在管基金类型跨度较大，需警惕经理能力圈漂移' : '',
    careerTypeCount >= 5 ? '历史任职类型较分散，不能只按经理名气筛选基金' : '',
    activeFundRows.length === 1 ? '当前只有 1 只未见离任基金，风格判断样本偏薄' : '',
    managerTenureYears !== null && managerTenureYears < 2 ? '管理年限偏短，稳定性证据不足' : '',
  ].filter(Boolean)
  const managerStyleNextActions = [
    managerSalesRuleGapSummary.gapCount > 0
      ? managerSalesRuleGapSummary.reviewAlerts
        ? '先处理名下基金复查队列，再确认是否可进入正式研究'
        : '先补名下基金销售规则，再确认是否可进入正式研究'
      : '',
    compareCodes.length >= 2 ? '把同经理基金放入横向比较，验证收益、回撤、费用和持有回放是否同向' : '',
    dominantType ? `优先在 ${dominantType[0]} 能力圈内找替代样本，避免跨类型误比` : '',
    activeFundCodes[0] ? '进入单基金研究复核页，核查持仓暴露是否支持经理风格判断' : '',
  ].filter(Boolean)
  const managerProductBuckets = Object.entries(activeTypeBuckets)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN'))
    .map(([type, count]) => {
      const funds = activeFundRows.filter((fund) => (fund.type || '类型待补') === type)
      const codes = funds.map((fund) => fund.wind_code).filter((code): code is string => Boolean(code))
      const gapFunds = codes.filter((code) => managerSalesRuleGapMap.has(code.toUpperCase()))
      const reviewAlertFunds = codes.filter((code) => Boolean(managerSalesRuleGapMap.get(code.toUpperCase())?.alertsHref))
      const comparisonCodes = codes.slice(0, 6)
      const href = comparisonCodes.length >= 2
        ? comparisonHrefForCodes(comparisonCodes)
        : comparisonCodes[0]
          ? fundDetailHrefForCode(comparisonCodes[0])
          : managerSalesRuleActionHref
      const actionLabel = gapFunds.length
        ? reviewAlertFunds.length ? '处理复查队列' : '先补规则'
        : comparisonCodes.length >= 2
          ? '同类横评'
          : comparisonCodes.length === 1
            ? '单基金诊断'
            : '补代码'
      const risk = gapFunds.length
        ? reviewAlertFunds.length
          ? `${reviewAlertFunds.length} 只复查队列未清零，不能作为研究分工结论`
          : `${gapFunds.length} 只销售规则未清，不能作为研究分工结论`
        : comparisonCodes.length >= 2
          ? '可在同经理同类型内比较费后回放、回撤和证据完整度'
          : comparisonCodes.length === 1
            ? '样本只有 1 只，经理分工只能落到单基金诊断'
            : '缺少可落地基金代码'
      return {
        type,
        count,
        codes,
        gapCount: gapFunds.length,
        reviewAlertCount: reviewAlertFunds.length,
        representative: funds[0]?.name || funds[0]?.fund_name || codes[0] || '基金待补',
        href: gapFunds.length
          ? reviewAlertFunds.length ? managerSalesRuleActionHref : salesRulesHref
          : href,
        actionLabel,
        risk,
      }
    })
  const managerProductWorkloadLabel = activeFundRows.length >= 8
    ? '一拖多负荷较高'
    : activeFundRows.length >= 4
      ? '多产品并行'
      : activeFundRows.length >= 1
        ? '产品负荷可观察'
        : '无在管产品入口'
  const managerProductWorkloadWarning = activeFundRows.length >= 8
    ? '名下在管基金数量较多，研究复核需要确认目标基金是否为经理主要精力覆盖产品。'
    : activeTypeCount >= 3
      ? '在管类型跨度较大，需先确认每只基金的定位，不要把经理整体能力直接外推。'
      : managerProductBuckets.length
        ? '当前可按产品分工进入逐只基金诊断。'
        : '缺少在管基金，经理页只能作为履历资料。'
  const managerCounterEvidenceItems = [
    {
      key: 'sales-rule',
      title: '名下基金门禁反证',
      status: managerSalesRuleGapSummary.gapCount > 0 ? 'block' as const : salesRuleGapPayload ? 'pass' as const : 'warn' as const,
      challenge: managerSalesRuleGapSummary.gapCount > 0
        ? managerSalesRuleGapSummary.reviewAlerts
          ? `仍有 ${managerSalesRuleGapSummary.reviewAlerts} 只基金复查队列未清零，经理入口分不能证明基金可进入研究路径。`
          : `仍有 ${managerSalesRuleGapSummary.gapCount} 只基金销售规则硬缺口，共缺 ${managerSalesRuleGapSummary.missingItems} 项。`
        : salesRuleGapPayload
          ? '当前名下基金未检测到销售规则硬缺口，但仍需销售平台实时复核。'
          : '销售规则扫描尚未完成，不能证明名下基金可进入正式研究候选。',
      evidence: [
        `扫描基金 ${salesRuleCodes.length} 只`,
        `硬缺口 ${managerSalesRuleGapSummary.gapCount} 只`,
        `高优先级 ${managerSalesRuleGapSummary.highPriority} 只`,
      ],
      action: managerSalesRuleGapSummary.gapCount > 0
        ? managerSalesRuleGapSummary.reviewAlerts ? '先处理复查队列' : '先补销售规则'
        : '进入逐基金诊断',
      href: managerSalesRuleGapSummary.gapCount > 0 ? managerSalesRuleActionHref : managerPurchaseLensActionHref,
    },
    {
      key: 'concentration',
      title: '能力圈漂移反证',
      status: activeTypeCount >= 4 || careerTypeCount >= 5 ? 'warn' as const : activeFundRows.length === 0 ? 'block' as const : 'pass' as const,
      challenge: activeFundRows.length === 0
        ? '缺少未见离任基金，无法证明当前能力圈仍可落地。'
        : activeTypeCount >= 4 || careerTypeCount >= 5
          ? '在管或历史任职类型较分散，不能把经理历史标签直接外推到目标基金。'
          : '当前产品类型集中度暂未触发明显能力圈漂移反证。',
      evidence: [
        `在管类型 ${activeTypeCount} 类`,
        `历史类型 ${careerTypeCount} 类`,
        dominantType ? `主类型 ${dominantType[0]} ${dominantType[1]} 只` : '主类型待补',
      ],
      action: dominantType ? `优先在 ${dominantType[0]} 内横评` : '先补任职基金类型',
      href: compareCodes.length >= 2 ? comparisonHref : managerPurchaseLensActionHref,
    },
    {
      key: 'workload',
      title: '一拖多精力反证',
      status: activeFundRows.length >= 8 ? 'warn' as const : activeFundRows.length === 0 ? 'block' as const : 'pass' as const,
      challenge: activeFundRows.length >= 8
        ? '在管基金数量较多，需要证明目标基金不是边缘产品。'
        : activeFundRows.length === 0
          ? '没有可落到研究路径的在管基金。'
          : '当前在管数量暂未触发明显一拖多反证。',
      evidence: [
        `在管 ${activeFundRows.length} 只`,
        `历史任职 ${historicalFundRows.length} 条`,
        `产品分工 ${managerProductBuckets.length} 组`,
      ],
      action: '按产品分工逐只诊断',
      href: managerPurchaseLensActionHref,
    },
    {
      key: 'tenure',
      title: '任期归因反证',
      status: managerTenureYears === null ? 'warn' as const : managerTenureYears < 2 ? 'warn' as const : 'pass' as const,
      challenge: managerTenureYears === null
        ? '管理年限待补，不能证明历史业绩归属于现任经理。'
        : managerTenureYears < 2
          ? '任期偏短，不能把基金长期历史收益直接归因给当前经理。'
          : '任期样本暂可观察，但仍需逐只基金回放验证。',
      evidence: [
        `管理年限 ${managerTenureYears === null ? '待补' : `${managerTenureYears.toFixed(1)} 年`}`,
        `未见离任基金 ${activeFundRows.length} 只`,
        `可横评样本 ${compareCodes.length} 只`,
      ],
      action: compareCodes.length >= 2 ? '横评同经理基金' : '进入单基金任期核查',
      href: compareCodes.length >= 2 ? comparisonHref : managerPurchaseLensActionHref,
    },
  ]
  const managerCounterEvidenceBlockCount = managerCounterEvidenceItems.filter((item) => item.status === 'block').length
  const managerCounterEvidenceWarnCount = managerCounterEvidenceItems.filter((item) => item.status === 'warn').length
  const managerCounterEvidencePassCount = managerCounterEvidenceItems.filter((item) => item.status === 'pass').length
  const managerCounterEvidenceVerdict = managerCounterEvidenceBlockCount > 0
    ? '先处理反证阻断'
    : managerCounterEvidenceWarnCount > 0
      ? '先补反证再横评'
      : '反证暂未触发'
  const managerCounterEvidenceSummary = managerCounterEvidenceBlockCount > 0
    ? '经理名气、任期或历史产品不能覆盖当前阻断；先处理复查队列、销售规则或可落地基金入口。'
    : managerCounterEvidenceWarnCount > 0
      ? '经理入口可以继续研究，但必须补能力圈、任期或一拖多反证后再做同类横评。'
      : '当前未触发主要反证，但仍必须落到逐只基金的销售规则、回放、持仓和报告门禁。'
  const managerBuyBeforeEvidenceTsv = [
    ['证据组', '对象', '状态/结论', '关键证据', '下一动作', '入口', '硬边界'].join('\t'),
    [
      '经理研究证据总览',
      `${manager.name}${manager.company ? ` / ${manager.company}` : ''}`,
      managerEvidenceConclusion,
      `经理入口分 ${managerPurchaseLensScore}；${managerPurchaseLensReasons.join('；')}`,
      managerEvidencePrimaryAction,
      currentManagerHref,
      '经理评价只服务于基金筛选、基金分析和基金经理评价；只沉淀研究证据，不输出执行建议。',
    ].map(tsvCell).join('\t'),
    [
      '投资口径',
      manager.name,
      `${riskProfileLabels[riskProfile]} / ${horizonLabels[investmentHorizon]} / ${purchasePlanLabels[purchasePlan]}`,
      `plannedAmount=${Number(normalizedPlannedAmount).toLocaleString('zh-CN')} 元；来源=本地 Tushare 任职记录 + 销售规则缺口扫描`,
      '所有动作必须带计划金额重新核查',
      currentManagerHref,
      '计划金额是研究门禁口径，不能省略或换成默认中性判断。',
    ].map(tsvCell).join('\t'),
    [
      '销售规则/R1-R5 门禁',
      `${salesRuleCodes.length} 只名下基金`,
      managerSalesRuleGapSummary.gapCount > 0
        ? managerSalesRuleGapSummary.reviewAlerts
          ? `阻断：${managerSalesRuleGapSummary.reviewAlerts} 只复查队列未清零`
          : `阻断：${managerSalesRuleGapSummary.gapCount} 只待补`
        : salesRuleGapPayload ? '当前未检出硬缺口' : '扫描待完成',
      `缺口项 ${managerSalesRuleGapSummary.missingItems}；高优先级 ${managerSalesRuleGapSummary.highPriority}`,
      managerSalesRuleGapSummary.gapCount > 0
        ? managerSalesRuleGapSummary.reviewAlerts ? '先处理复查队列' : '先进入销售规则补证台'
        : '进入逐只基金详情继续研究诊断',
      managerSalesRuleActionHref,
      '任一基金销售规则、R1-R5、申购状态、费率、限购或来源日期缺失，经理分不能抵消。',
    ].map(tsvCell).join('\t'),
    [
      '风格稳定性与能力圈',
      manager.name,
      `${managerStyleStabilityLabel} / ${managerStyleStabilityScore} 分`,
      [...managerStyleSignals, ...managerStyleWarnings].join('；') || '风格证据待补',
      managerStyleNextActions.join('；') || '先补经理和名下基金证据',
      compareCodes.length >= 2 ? comparisonHref : managerPurchaseLensActionHref,
      '风格稳定只能缩小研究范围，不能绕过具体基金销售规则、费用、净值回放和持仓证据。',
    ].map(tsvCell).join('\t'),
    [
      '产品分工/一拖多',
      manager.name,
      managerProductWorkloadLabel,
      `${managerProductWorkloadWarning} 在管 ${activeFundRows.length} 只；类型 ${activeTypeCount} 类；历史任职 ${historicalFundRows.length} 条`,
      managerProductBuckets.length ? '按产品类型拆分到逐只基金' : '先补在管基金入口',
      managerPurchaseLensActionHref,
      '经理评价不能把所有名下基金混成一个研究结论。',
    ].map(tsvCell).join('\t'),
    ...managerCounterEvidenceItems.map((item) => [
      '经理反证核查清单',
      item.title,
      managerCounterEvidenceStatusLabel(item.status),
      [item.challenge, ...item.evidence].join('；'),
      item.action,
      item.href,
      '反证未解除前，不能因明星经理、长任期或历史代表作把名下基金放入正式研究样本。',
    ].map(tsvCell).join('\t')),
    ...managerFundGateMatrix.map((item) => [
      '逐基金隔离矩阵',
      `${item.fundCode || '代码缺失'} ${item.fundName}`,
      `${item.managerLens} / ${item.fundGate} / ${item.investabilityRole}`,
      item.boundary,
      item.nextAction,
      item.primaryHref,
      '逐只基金硬缺口优先级高于经理入口分；历史任职只保留为履历证据。',
    ].map(tsvCell).join('\t')),
    [
      '正式结论边界',
      manager.name,
      managerSalesRuleGapSummary.gapCount > 0 ? '不能进入正式研究结论' : '只能作为研究入口证据',
      managerEvidenceReverseTriggers.join('；'),
      managerSalesRuleGapSummary.reviewAlerts ? '先处理复查队列，再进入单基金一页纸或同类横评' : '进入单基金一页纸、同类横评或补证台',
      managerPurchaseLensActionHref,
      '经理证据不能保存为正式研究复核报告或研究样本依据，必须落到具体基金报告门禁。',
    ].map(tsvCell).join('\t'),
  ].join('\n')
  const downloadManagerBuyBeforeEvidence = () => {
    const blob = new Blob([`\uFEFF${managerBuyBeforeEvidenceTsv}`], { type: 'text/tab-separated-values;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${safeFileStem(`${manager.name}_经理研究证据`)}_${new Date().toISOString().slice(0, 10)}.tsv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }
  const copyManagerBuyBeforeEvidence = async () => {
    try {
      let copied = false
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(managerBuyBeforeEvidenceTsv)
          copied = true
        } catch {
          copied = false
        }
      }
      if (!copied) {
        const textArea = document.createElement('textarea')
        textArea.value = managerBuyBeforeEvidenceTsv
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.focus()
        textArea.select()
        copied = document.execCommand('copy')
        textArea.remove()
      }
      if (!copied) throw new Error('copy failed')
      setManagerEvidenceCopyStatus('copied')
      globalThis.setTimeout(() => setManagerEvidenceCopyStatus('idle'), 1800)
    } catch {
      downloadManagerBuyBeforeEvidence()
      setManagerEvidenceCopyStatus('fallback')
      globalThis.setTimeout(() => setManagerEvidenceCopyStatus('idle'), 1800)
    }
  }

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <Link
        href={sourceReturnHref}
        className="inline-flex items-center text-gray-600 hover:text-gray-900"
        data-testid="manager-detail-return-link"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        返回列表
      </Link>

      {/* 基金经理基本信息 */}
      {errorMessage ? (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4" />
          {errorMessage}
        </div>
      ) : null}

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
              <User className="w-8 h-8 text-blue-600" />
            </div>
            <div className="ml-4">
              <h1 className="text-2xl font-bold text-gray-900">{manager.name}</h1>
              {manager.company && (
                <p className="text-sm text-gray-500">{manager.company}</p>
              )}
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">管理基金数</p>
            <p className="text-lg font-semibold text-gray-900">
              {manager.fundCount ?? uniqueFundCodes.length} 条任职记录
            </p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <Building className="w-6 h-6 text-blue-600" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-gray-500">所属公司</p>
              <p className="text-lg font-semibold text-gray-900">
                {manager.company || '-'}
              </p>
            </div>
          </div>

          <div className="flex items-start">
            <div className="flex-shrink-0">
              <GraduationCap className="w-6 h-6 text-green-600" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-gray-500">学历</p>
              <p className="text-lg font-semibold text-gray-900">
                {manager.education || '-'}
              </p>
            </div>
          </div>

          <div className="flex items-start">
            <div className="flex-shrink-0">
              <Briefcase className="w-6 h-6 text-purple-600" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-gray-500">从业年限</p>
              <p className="text-lg font-semibold text-gray-900">
                {manager.workYears ? `${manager.workYears} 年` : '-'}
              </p>
            </div>
          </div>

          <div className="flex items-start">
            <div className="flex-shrink-0">
              <TrendingUp className="w-6 h-6 text-orange-600" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-gray-500">管理年限</p>
              <p className="text-lg font-semibold text-gray-900">
                {manager.managementYears ? `${Number(manager.managementYears).toFixed(1)} 年` : '-'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg bg-white p-6 shadow">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">研究复核场景</h2>
            <p className="mt-1 text-sm text-gray-500">
              当前：{riskProfileLabels[riskProfile]} · {horizonLabels[investmentHorizon]} · {purchasePlanLabels[purchasePlan]} · 计划金额 {Number(normalizedPlannedAmount).toLocaleString('zh-CN')} 元
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4 lg:w-[720px]">
            <label className="text-xs font-medium text-slate-600">
              研究画像
              <select value={riskProfile} onChange={(event) => setRiskProfile(event.target.value as RiskProfile)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900">
                <option value="conservative">稳健型</option>
                <option value="balanced">均衡型</option>
                <option value="aggressive">进取型</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              持有期
              <select value={investmentHorizon} onChange={(event) => setInvestmentHorizon(event.target.value as InvestmentHorizon)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900">
                <option value="lt1y">1 年以内</option>
                <option value="1to3y">1-3 年</option>
                <option value="gt3y">3 年以上</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              研究方式假设
              <select value={purchasePlan} onChange={(event) => setPurchasePlan(event.target.value as PurchasePlan)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900">
                <option value="sip">{purchasePlanLabels.sip}</option>
                <option value="lump_sum">{purchasePlanLabels.lump_sum}</option>
              </select>
            </label>
            <label className="text-xs font-medium text-slate-600">
              研究金额口径（元）
              <input
                type="number"
                min={1}
                step={1}
                value={plannedAmount}
                onChange={(event) => setPlannedAmount(event.target.value)}
                onBlur={() => setPlannedAmount(normalizePlannedAmountInput(plannedAmount, purchasePlan))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
              />
            </label>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          <Link href={managerAnalysisHref} className="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700">
            生成经理研究报告
          </Link>
          <Link
            href={comparisonHref}
            title={salesRuleBlockedCompareCount > 0 ? '默认只带入销售规则未阻断样本；待补样本先处理销售规则/R1-R5。' : undefined}
            className={`rounded-lg px-4 py-2 font-medium ${compareCodes.length >= 2 ? 'bg-blue-600 text-white hover:bg-blue-700' : 'pointer-events-none bg-slate-100 text-slate-400'}`}
          >
            对比规则完整基金
          </Link>
          <Link href={managerSalesRuleActionHref} className="rounded-lg border border-amber-300 px-4 py-2 font-medium text-amber-700 hover:bg-amber-50">
            {managerSalesRuleGapSummary.reviewAlerts ? '处理复查队列' : '批量补销售规则'}
          </Link>
        </div>
      </div>

      <div className={`rounded-2xl border p-6 shadow ${managerPurchaseLensClass}`} data-testid="manager-purchase-lens">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold ring-1 ring-black/5">
              <ShieldCheck className="h-4 w-4" />
              经理入口研究评级
            </div>
            <div className="mt-4 flex flex-wrap items-end gap-4">
              <div>
                <div className="text-4xl font-bold">{managerPurchaseLensScore}</div>
                <div className="mt-1 text-xs opacity-75">经理入口分</div>
              </div>
              <div>
                <div className="text-xl font-semibold">{managerPurchaseLensLabel}</div>
                <p className="mt-2 text-sm leading-6 opacity-80">
                  经理只能作为选基入口；最终仍必须落到名下具体基金的销售规则、净值回放、同类比较和研究复核报告。
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {managerPurchaseLensReasons.map((reason) => (
                <div key={reason} className="rounded-xl bg-white/70 px-3 py-2 text-xs leading-5 ring-1 ring-black/5">
                  {reason}
                </div>
              ))}
            </div>
          </div>
          <div className="flex shrink-0 flex-col gap-2">
            <Link href={managerPurchaseLensActionHref} className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-slate-50">
              {managerPurchaseLensActionLabel}
            </Link>
            <Link href={managerAnalysisHref} className="rounded-lg bg-white/60 px-4 py-2 text-sm font-semibold text-slate-800 ring-1 ring-black/5 hover:bg-white">
              生成经理研究报告
            </Link>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow" data-testid="manager-buy-before-evidence-card">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
              <ShieldCheck className="h-4 w-4" />
              经理研究证据卡
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                <div className="text-xs text-slate-500">证据结论</div>
                <div className="mt-1 text-lg font-semibold text-slate-950">{managerEvidenceConclusion}</div>
              </div>
              <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                <div className="text-xs text-blue-700">主动作</div>
                <div className="mt-1 text-sm font-semibold leading-6 text-blue-950">{managerEvidencePrimaryAction}</div>
              </div>
              <div className="rounded-xl border border-amber-100 bg-amber-50 p-4">
                <div className="text-xs text-amber-700">硬门禁</div>
                <div className="mt-1 text-sm font-semibold leading-6 text-amber-950">
                  {managerSalesRuleGapSummary.gapCount > 0 ? '销售规则缺口未清，不进入正式研究结论' : '经理证据必须继续落到具体基金'}
                </div>
              </div>
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-100 p-4">
                <h3 className="text-sm font-semibold text-slate-900">当前判断依据</h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {managerPurchaseLensReasons.map((reason) => (
                    <li key={reason}>• {reason}</li>
                  ))}
                </ul>
              </div>
              <div className="rounded-xl border border-slate-100 p-4">
                <h3 className="text-sm font-semibold text-slate-900">结论反转条件</h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {managerEvidenceReverseTriggers.map((trigger) => (
                    <li key={trigger}>• {trigger}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-medium leading-6 text-rose-800">
              研究边界：基金经理评价只服务于基金筛选、基金分析和经理评价，不能替代具体基金的销售规则门禁与研究复核报告。
            </div>
          </div>
          <div className="flex shrink-0 flex-col gap-2">
            <Link href={managerPurchaseLensActionHref} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">
              {managerPurchaseLensActionLabel}
            </Link>
            <Link href={managerSalesRuleActionHref} className="rounded-lg border border-amber-200 px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50">
              {managerSalesRuleGapSummary.reviewAlerts ? '处理复查队列' : '补销售规则'}
            </Link>
            <button
              type="button"
              onClick={copyManagerBuyBeforeEvidence}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              data-testid="manager-buy-before-evidence-copy"
            >
              <Copy className="h-4 w-4" />
              {managerEvidenceCopyStatus === 'copied' ? '已复制 TSV' : managerEvidenceCopyStatus === 'fallback' ? '已转下载 TSV' : '复制证据 TSV'}
            </button>
            <button
              type="button"
              onClick={downloadManagerBuyBeforeEvidence}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              data-testid="manager-buy-before-evidence-download"
            >
              <Download className="h-4 w-4" />
              下载证据 TSV
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-rose-100 bg-rose-50 p-6 shadow" data-testid="manager-counter-evidence-checklist">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-rose-800 ring-1 ring-rose-100">
              <AlertCircle className="h-4 w-4" />
              经理反证核查清单
            </div>
            <h2 className="mt-4 text-xl font-semibold text-rose-950">先证明“不能只信经理光环”</h2>
            <p className="mt-2 text-sm leading-6 text-rose-900">
              {managerCounterEvidenceSummary} 这张卡专门检查明星经理、长期任期、能力圈标签和一拖多产品是否会误导研究选择。
            </p>
          </div>
          <div className="grid shrink-0 grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-xl bg-white px-3 py-2 text-emerald-900 ring-1 ring-emerald-100">
              <div className="text-emerald-600">暂未触发</div>
              <div className="mt-1 text-lg font-semibold">{managerCounterEvidencePassCount}</div>
            </div>
            <div className="rounded-xl bg-white px-3 py-2 text-amber-900 ring-1 ring-amber-100">
              <div className="text-amber-600">待复核</div>
              <div className="mt-1 text-lg font-semibold">{managerCounterEvidenceWarnCount}</div>
            </div>
            <div className="rounded-xl bg-white px-3 py-2 text-rose-900 ring-1 ring-rose-100">
              <div className="text-rose-600">阻断</div>
              <div className="mt-1 text-lg font-semibold">{managerCounterEvidenceBlockCount}</div>
            </div>
          </div>
        </div>
        <div className="mt-4 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-rose-900 ring-1 ring-rose-100">
          当前反证结论：{managerCounterEvidenceVerdict}
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {managerCounterEvidenceItems.map((item) => (
            <div key={item.key} className={`rounded-2xl border p-4 ${managerCounterEvidenceClass(item.status)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold">{item.title}</div>
                  <div className="mt-1 text-xs leading-5 opacity-80">{item.challenge}</div>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${managerCounterEvidenceBadgeClass(item.status)}`}>
                  {managerCounterEvidenceStatusLabel(item.status)}
                </span>
              </div>
              <div className="mt-3 space-y-1 text-xs leading-5 opacity-80">
                {item.evidence.map((evidence) => (
                  <div key={evidence}>• {evidence}</div>
                ))}
              </div>
              <Link href={item.href} className="mt-3 inline-flex rounded-lg bg-white/80 px-3 py-2 text-xs font-semibold ring-1 ring-white/80 hover:bg-white">
                {item.action}
              </Link>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-xl border border-rose-200 bg-white px-4 py-3 text-sm font-medium leading-6 text-rose-800">
          硬边界：反证未解除前，不能因明星经理、长任期或历史代表作把名下基金放入正式研究样本；经理评价必须回到逐只基金门禁。
        </div>
      </div>

      <div className={`rounded-2xl border p-6 shadow ${managerStyleStabilityClass}`} data-testid="manager-style-stability-card">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold ring-1 ring-black/5">
              <TrendingUp className="h-4 w-4" />
              经理风格稳定性与能力圈
            </div>
            <div className="mt-4 flex flex-wrap items-end gap-4">
              <div>
                <div className="text-4xl font-bold">{managerStyleStabilityScore}</div>
                <div className="mt-1 text-xs opacity-75">风格稳定分</div>
              </div>
              <div>
                <div className="text-xl font-semibold">{managerStyleStabilityLabel}</div>
                <p className="mt-2 text-sm leading-6 opacity-80">
                  用名下基金类型分布、在管连续性、任期和销售规则门禁判断经理能力圈；它只帮助缩小研究范围，不替代具体基金研究核查。
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <div className="rounded-2xl bg-white/70 p-4 ring-1 ring-black/5">
                <div className="text-sm font-semibold">能力圈证据</div>
                <div className="mt-3 space-y-2 text-xs leading-5">
                  {managerStyleSignals.slice(0, 5).map((signal) => (
                    <div key={signal} className="rounded-xl bg-white/80 px-3 py-2 ring-1 ring-black/5">{signal}</div>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl bg-white/70 p-4 ring-1 ring-black/5">
                <div className="text-sm font-semibold">风格漂移警报</div>
                <div className="mt-3 space-y-2 text-xs leading-5">
                  {managerStyleWarnings.length ? managerStyleWarnings.slice(0, 5).map((warning) => (
                    <div key={warning} className="rounded-xl bg-white/80 px-3 py-2 ring-1 ring-black/5">{warning}</div>
                  )) : (
                    <div className="rounded-xl bg-white/80 px-3 py-2 ring-1 ring-black/5">当前未识别明显风格漂移警报，仍需落到具体基金验证。</div>
                  )}
                </div>
              </div>
              <div className="rounded-2xl bg-white/70 p-4 ring-1 ring-black/5">
                <div className="text-sm font-semibold">下一步研究动作</div>
                <div className="mt-3 space-y-2 text-xs leading-5">
                  {managerStyleNextActions.slice(0, 5).map((action) => (
                    <div key={action} className="rounded-xl bg-white/80 px-3 py-2 ring-1 ring-black/5">{action}</div>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm font-medium leading-6 text-rose-800">
              硬门禁：经理能力圈稳定，也不能绕过名下具体基金的销售规则、风险等级、费用和研究复核报告。
            </div>
          </div>
          <div className="flex shrink-0 flex-col gap-2">
            {compareCodes.length >= 2 ? (
              <Link href={comparisonHref} className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-slate-50">
                横评能力圈基金
              </Link>
            ) : null}
            <Link href={managerSalesRuleActionHref} className="rounded-lg bg-white/70 px-4 py-2 text-sm font-semibold text-amber-800 ring-1 ring-black/5 hover:bg-white">
              {managerSalesRuleGapSummary.reviewAlerts ? '打开复查队列' : '核查销售规则'}
            </Link>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-6 shadow" data-testid="manager-product-workload-card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-indigo-800 ring-1 ring-indigo-100">
              <Briefcase className="h-4 w-4" />
              经理产品分工与一拖多负荷
            </div>
            <h2 className="mt-4 text-xl font-semibold text-indigo-950">{managerProductWorkloadLabel}</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-indigo-900">
              {managerProductWorkloadWarning} 经理评价不能把所有名下基金混成一个结论；必须按产品类型、销售规则和目标基金逐只拆开。
            </p>
          </div>
          <div className="grid shrink-0 grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-xl bg-white px-3 py-2 text-indigo-900 ring-1 ring-indigo-100">
              <div className="text-indigo-600">在管基金</div>
              <div className="mt-1 text-lg font-semibold">{activeFundRows.length}</div>
            </div>
            <div className="rounded-xl bg-white px-3 py-2 text-indigo-900 ring-1 ring-indigo-100">
              <div className="text-indigo-600">产品类型</div>
              <div className="mt-1 text-lg font-semibold">{activeTypeCount}</div>
            </div>
            <div className="rounded-xl bg-white px-3 py-2 text-indigo-900 ring-1 ring-indigo-100">
              <div className="text-indigo-600">{managerSalesRuleGapSummary.reviewAlerts ? '复查未清' : '待补规则'}</div>
              <div className="mt-1 text-lg font-semibold">{managerSalesRuleGapSummary.gapCount}</div>
            </div>
          </div>
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-3">
          {managerProductBuckets.slice(0, 6).map((bucket) => (
            <div key={bucket.type} className="rounded-2xl bg-white p-4 text-sm text-indigo-950 ring-1 ring-indigo-100">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold">{bucket.type}</div>
                  <div className="mt-1 text-xs text-indigo-600">代表基金：{bucket.representative}</div>
                </div>
                <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 ring-1 ring-indigo-100">
                  {bucket.count} 只
                </span>
              </div>
              <p className="mt-3 min-h-10 text-xs leading-5 text-indigo-800">{bucket.risk}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {bucket.codes.slice(0, 4).map((code) => (
                  <span key={code} className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">{code}</span>
                ))}
                {bucket.codes.length > 4 ? (
                  <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-500">+{bucket.codes.length - 4}</span>
                ) : null}
              </div>
              <Link href={bucket.href} className="mt-4 inline-flex rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700">
                {bucket.actionLabel}
              </Link>
            </div>
          ))}
          {managerProductBuckets.length === 0 ? (
            <div className="rounded-2xl bg-white p-4 text-sm leading-6 text-indigo-900 ring-1 ring-indigo-100">
              当前没有未见离任基金可拆分，经理评价只能作为履历观察，不能进入研究选择。
            </div>
          ) : null}
        </div>
          <div className="mt-4 rounded-xl border border-rose-100 bg-white px-4 py-3 text-sm font-medium leading-6 text-rose-800">
          硬门禁：任一产品分工仍有销售规则硬缺口时，只能作为经理研究观察；当前计划金额 {Number(normalizedPlannedAmount).toLocaleString('zh-CN')} 元不能保存为正式研究复核报告或研究样本依据。
        </div>
      </div>

      <div className="rounded-2xl border border-cyan-100 bg-cyan-50 p-6 shadow" data-testid="manager-fund-gate-separation-matrix">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-cyan-800 ring-1 ring-cyan-100">
              <ShieldCheck className="h-4 w-4" />
              经理评价与基金门禁隔离矩阵
            </div>
            <h2 className="mt-4 text-xl font-semibold text-cyan-950">经理能力不等于基金研究结论</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-cyan-900">
              先看经理入口，再落到逐只基金，再过销售规则/R1-R5、费用、净值回放和持仓证据；任何基金硬缺口都会压过经理入口分。
            </p>
          </div>
          <div className="grid shrink-0 grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-xl bg-white px-3 py-2 text-cyan-900 ring-1 ring-cyan-100">
              <div className="text-cyan-600">矩阵样本</div>
              <div className="mt-1 text-lg font-semibold">{managerFundGateMatrix.length}</div>
            </div>
            <div className="rounded-xl bg-white px-3 py-2 text-cyan-900 ring-1 ring-cyan-100">
              <div className="text-cyan-600">基金可诊断</div>
              <div className="mt-1 text-lg font-semibold">{purchaseQueueSummary.ready}</div>
            </div>
            <div className="rounded-xl bg-white px-3 py-2 text-cyan-900 ring-1 ring-cyan-100">
              <div className="text-cyan-600">规则阻断</div>
              <div className="mt-1 text-lg font-semibold">{purchaseQueueSummary.rulesMissing}</div>
            </div>
          </div>
        </div>
        <div className="mt-5 grid gap-3 lg:grid-cols-2">
          {managerFundGateMatrix.map((item) => (
            <div key={`gate-matrix-${item.key}`} className="rounded-2xl bg-white p-4 text-sm text-slate-800 ring-1 ring-cyan-100">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-slate-950">{item.fundName}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.fundCode || '代码缺失'}{item.type ? ` · ${item.type}` : ''}</div>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.className}`}>
                  {item.investabilityRole}
                </span>
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                <div className="rounded-xl bg-cyan-50 px-3 py-2">
                  <div className="text-[11px] font-semibold text-cyan-700">经理入口</div>
                  <div className="mt-1 text-xs leading-5 text-cyan-950">{item.managerLens}</div>
                </div>
                <div className="rounded-xl bg-slate-50 px-3 py-2">
                  <div className="text-[11px] font-semibold text-slate-500">基金门禁</div>
                  <div className="mt-1 text-xs leading-5 text-slate-950">{item.fundGate}</div>
                </div>
                <div className="rounded-xl bg-amber-50 px-3 py-2">
                  <div className="text-[11px] font-semibold text-amber-700">下一动作</div>
                  <div className="mt-1 text-xs leading-5 text-amber-950">{item.primaryLabel}</div>
                </div>
              </div>
              <div className="mt-3 rounded-xl border border-cyan-100 bg-cyan-50 px-3 py-2 text-xs leading-5 text-cyan-900">
                {item.boundary}
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
                <Link href={item.primaryHref} className="rounded-lg bg-cyan-700 px-3 py-2 text-white hover:bg-cyan-800">
                  {item.primaryLabel}
                </Link>
                {item.fundCode ? (
                  <Link href={item.salesRuleHref} className="rounded-lg bg-white px-3 py-2 text-amber-700 ring-1 ring-amber-100 hover:bg-amber-50">
                    查销售规则
                  </Link>
                ) : null}
              </div>
            </div>
          ))}
          {managerFundGateMatrix.length === 0 ? (
            <div className="rounded-2xl bg-white p-4 text-sm leading-6 text-cyan-900 ring-1 ring-cyan-100">
              当前缺少可映射基金，经理评价只能停留在履历层，不能进入基金研究选择。
            </div>
          ) : null}
        </div>
        <div className="mt-4 rounded-xl border border-rose-100 bg-white px-4 py-3 text-sm font-medium leading-6 text-rose-800">
          隔离边界：经理入口分、风格稳定分、一拖多负荷只能帮助缩小研究范围；不能抵消逐只基金销售规则、R1-R5 和研究证据缺口。
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">经理维度研究路径</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              经理评价只作为入口，最终仍要落到具体基金的销售规则、净值回放、持仓和同类比较。
            </p>
          </div>
          <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
            {riskProfileLabels[riskProfile]} · {horizonLabels[investmentHorizon]} · {purchasePlanLabels[purchasePlan]}
          </span>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">
            <div className="text-xs text-emerald-700">未见离任基金</div>
            <div className="mt-1 text-2xl font-semibold">{activeFundRows.length}</div>
            <div className="mt-1 text-xs">优先进入研究诊断和横向比较</div>
          </div>
          <div className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
            <div className="text-xs text-blue-700">可比较代码</div>
            <div className="mt-1 text-2xl font-semibold">{compareCodes.length}</div>
            <div className="mt-1 text-xs">最多带入 8 只做横评</div>
          </div>
          <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
            <div className="text-xs text-amber-700">任期判断</div>
            <div className="mt-1 text-lg font-semibold">{managerTenureStatus}</div>
            <div className="mt-1 text-xs">管理年限 {manager.managementYears == null ? '待补' : `${Number(manager.managementYears).toFixed(1)} 年`}</div>
          </div>
          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-900">
            <div className="text-xs text-slate-500">历史任职记录</div>
            <div className="mt-1 text-2xl font-semibold">{historicalFundRows.length}</div>
            <div className="mt-1 text-xs">用于观察履历，不直接作为研究对象</div>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-rose-100 bg-rose-50 p-4 text-sm text-rose-900">
            <div className="text-xs text-rose-700">经理名下销售规则硬缺口</div>
            <div className="mt-1 text-2xl font-semibold">{salesRuleGapLoading ? '扫描中' : managerSalesRuleGapSummary.gapCount}</div>
            <div className="mt-1 text-xs">共缺 {managerSalesRuleGapSummary.missingItems} 项，研究复核报告和样本入池会受影响</div>
          </div>
          <div className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-900">
            <div className="text-xs text-amber-700">高优先级规则缺口</div>
            <div className="mt-1 text-2xl font-semibold">{salesRuleGapLoading ? '-' : managerSalesRuleGapSummary.highPriority}</div>
            <div className="mt-1 text-xs">优先补风险等级、限购金额和来源日期</div>
          </div>
          <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
            <div className="text-xs text-blue-700">{managerSalesRuleGapSummary.reviewAlerts ? '复查入口' : '补证入口'}</div>
            <div className="mt-1 text-sm font-semibold">
              {managerSalesRuleGapSummary.reviewAlerts
                ? `${managerSalesRuleGapSummary.reviewAlerts} 只基金需先处理复查队列`
                : salesRuleCodes.length ? `${salesRuleCodes.length} 只基金带入补证台` : '暂无可补代码'}
            </div>
            <Link href={managerSalesRuleActionHref} className="mt-2 inline-flex text-xs font-medium text-blue-700 hover:text-blue-900">
              {managerSalesRuleGapSummary.reviewAlerts ? '打开复查队列 →' : '打开销售规则补证台 →'}
            </Link>
          </div>
        </div>
        {salesRuleGapError ? (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {salesRuleGapError}
          </div>
        ) : null}

        <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900">
          {managerWorkflowNextAction}
        </div>
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          {compareCodes.length >= 2 ? (
            <Link href={comparisonHref} className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800">
              横向比较在管基金
            </Link>
          ) : null}
          {activeFundCodes[0] ? (
            <Link href={fundDetailHrefForCode(activeFundCodes[0])} className="rounded-lg border border-blue-200 px-4 py-2 font-medium text-blue-700 hover:bg-blue-50">
              进入首只基金诊断
            </Link>
          ) : null}
          <Link href={managerSalesRuleActionHref} className="rounded-lg border border-amber-200 px-4 py-2 font-medium text-amber-700 hover:bg-amber-50">
            {managerSalesRuleGapSummary.reviewAlerts ? '处理在管基金复查队列' : '补齐在管基金销售规则'}
          </Link>
          <Link href={managerAnalysisHref} className="rounded-lg border border-emerald-200 px-4 py-2 font-medium text-emerald-700 hover:bg-emerald-50">
            生成经理报告
          </Link>
        </div>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4" data-testid="manager-fund-purchase-queue">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-950">名下基金研究队列</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                把经理评价拆到逐只基金：先清销售规则硬缺口，再进入基金详情诊断；历史任职只保留为履历证据。
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-emerald-100 px-2.5 py-1 font-semibold text-emerald-700">可诊断 {purchaseQueueSummary.ready}</span>
              <span className="rounded-full bg-rose-100 px-2.5 py-1 font-semibold text-rose-700">
                {managerSalesRuleGapSummary.reviewAlerts ? '复查未清' : '待补规则'} {purchaseQueueSummary.rulesMissing}
              </span>
              <span className="rounded-full bg-slate-200 px-2.5 py-1 font-semibold text-slate-700">历史观察 {purchaseQueueSummary.historyOnly}</span>
              <button
                type="button"
                onClick={copyManagerFundPurchaseQueue}
                className="inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                data-testid="manager-fund-purchase-queue-copy"
              >
                <Copy className="h-3.5 w-3.5" />
                {managerQueueCopyStatus === 'copied' ? '已复制 TSV' : managerQueueCopyStatus === 'fallback' ? '已转下载 TSV' : '复制队列 TSV'}
              </button>
              <button
                type="button"
                onClick={downloadManagerFundPurchaseQueue}
                className="inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
                data-testid="manager-fund-purchase-queue-download"
              >
                <Download className="h-3.5 w-3.5" />
                下载队列 TSV
              </button>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold text-slate-500">
                  <th className="px-3 py-2">基金</th>
                  <th className="px-3 py-2">任职区间</th>
                  <th className="px-3 py-2">研究状态</th>
                  <th className="px-3 py-2">下一动作</th>
                  <th className="px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {managerFundPurchaseQueue.slice(0, 12).map((item) => (
                  <tr key={item.key}>
                    <td className="px-3 py-3">
                      <div className="font-semibold text-slate-950">{item.fundName}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.fundCode || '代码缺失'}{item.type ? ` · ${item.type}` : ''}</div>
                    </td>
                    <td className="px-3 py-3 text-xs leading-5 text-slate-600">
                      <div>开始：{item.startDate}</div>
                      <div>结束：{item.endDate}</div>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${item.className}`}>
                        {item.label}
                      </span>
                      {item.salesRuleGap ? (
                        <div className="mt-1 text-xs text-rose-600">
                          缺：{item.salesRuleGap.missingItems.slice(0, 3).join('、')}
                        </div>
                      ) : null}
                      <div className={`mt-1 text-xs ${item.inDefaultComparison ? 'text-emerald-700' : 'text-slate-500'}`}>
                        {item.defaultCompareRole}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs leading-5 text-slate-600">{item.nextAction}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-col gap-1 text-xs font-semibold">
                        <Link href={item.primaryHref} className="text-blue-700 hover:text-blue-900">{item.primaryLabel}</Link>
                        {item.status === 'rules_missing' ? (
                          <Link href={item.fundHref} className="text-slate-500 hover:text-slate-800">先看详情</Link>
                        ) : item.fundCode ? (
                          <Link href={item.salesRuleHref} className="text-amber-700 hover:text-amber-900">
                            {item.salesRuleGap?.alertsHref ? '开复查队列' : '查规则'}
                          </Link>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {activePurchaseQueue.length === 0 ? (
            <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              当前没有可作为研究入口的未见离任基金；经理评价只能保留为履历观察。
            </div>
          ) : null}
          {managerFundPurchaseQueue.length > 12 ? (
            <div className="mt-3 text-xs text-slate-500">
              已展示前 12 条任职记录；完整列表见下方管理基金卡片。
            </div>
          ) : null}
        </div>
      </div>

      {/* 管理基金列表 */}
      {allFundRows.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">管理基金</h2>
              <p className="mt-1 text-sm text-gray-500">展示 Tushare 任职区间；结束日期缺失代表仍需按最新公告复核。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              {activeFundCodes.length} 只未见离任日期
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {allFundRows.map((fund, index) => {
              const fundCode = fund.wind_code || ''
              const fundName = fund.name || fund.fund_name || fundCode || `基金 ${index + 1}`
              const salesRuleGap = fundCode ? managerSalesRuleGapMap.get(fundCode.toUpperCase()) || null : null
              const fundHref = fundCode
                ? fundDetailHrefForCode(fundCode)
                : appendReturnTo('/funds', currentManagerHref)
              return (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
              >
                <Link href={fundHref}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{fundName}</p>
                      <p className="mt-1 text-xs text-gray-500">{fundCode || '代码缺失'}{fund.type ? ` · ${fund.type}` : ''}</p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${fund.end_date ? 'bg-slate-100 text-slate-500' : 'bg-emerald-50 text-emerald-700'}`}>
                      {fund.end_date ? '历史任职' : '未见离任'}
                    </span>
                  </div>
                  <div className="mt-3">
                    {salesRuleGapLoading ? (
                      <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                        销售规则扫描中
                      </div>
                    ) : salesRuleGap ? (
                      <div className="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
                        {salesRuleGap.alertsHref ? '复查队列未清' : '销售规则缺'} {salesRuleGap.missingCount} 项：{salesRuleGap.missingItems.slice(0, 3).join('、')}
                      </div>
                    ) : fundCode ? (
                      <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                        当前未检测到销售规则硬缺口
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-500">
                    <div>
                      <p>开始</p>
                      <p className="mt-1 font-medium text-slate-900">{formatFundDate(fund.start_date || fund.since)}</p>
                    </div>
                    <div>
                      <p>结束</p>
                      <p className="mt-1 font-medium text-slate-900">{formatFundDate(fund.end_date)}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-xs font-medium text-blue-600">进入基金研究诊断 →</p>
                </Link>
              </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 历史业绩 */}
      {manager.historicalPerformance && Object.keys(manager.historicalPerformance).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">历史业绩</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(manager.historicalPerformance).map(([key, value]) => (
              <div key={key} className="border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-500">{key}</p>
                <p className="text-lg font-semibold text-gray-900">
                  {typeof value === 'number' ? value.toFixed(2) : String(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 投资风格分析 */}
      {manager.styleAnalysis && Object.keys(manager.styleAnalysis).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">投资风格分析</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(manager.styleAnalysis).map(([key, value]) => (
              <div key={key} className="border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-500">{key}</p>
                <p className="text-lg font-semibold text-gray-900">
                  {typeof value === 'number' ? value.toFixed(2) : String(value)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 调研报告 */}
      {manager.reports && manager.reports.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">调研报告</h2>
          <div className="space-y-3">
            {manager.reports.map((report) => (
              <div
                key={report.id}
                className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900">
                    {report.title}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatOptionalDate(report.reportDate)}
                  </span>
                </div>
                {report.summary && (
                  <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                    {report.summary}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 评分记录 */}
      {manager.scores && manager.scores.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">评分记录</h2>
          <div className="space-y-2">
            {manager.scores.map((score) => (
              <div
                key={score.id}
                className="flex items-center justify-between border-b border-gray-100 pb-2"
              >
                <span className="text-sm text-gray-600">{score.dimension}</span>
                <div className="flex items-center">
                  <span className="text-sm font-semibold text-gray-900">
                    {Number(score.score).toFixed(2)}
                  </span>
                  <span className="text-xs text-gray-400 ml-2">
                    ({score.calculationMethod})
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 基金经理研究报告 */}
      {manager.aiReports && manager.aiReports.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">基金经理研究报告</h2>
          <div className="space-y-3">
            {manager.aiReports.map((report, index) => (
              <div
                key={report.id || index}
                className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900">
                    {report.reportType || '基金经理研究报告'}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatOptionalDate(report.createdAt)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
