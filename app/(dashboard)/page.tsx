import Link from 'next/link'
import { TrendingUp, Users, FileText, BarChart3, Globe2, Layers3, BellRing, Sparkles, Target, ShieldCheck, Trophy, AlertTriangle, ArrowRight, ClipboardCheck, Database } from 'lucide-react'
import { backendApiBaseUrl } from '@/lib/backend-api'
import { getSalesRuleGaps } from '@/lib/sales-rule-gaps'
import { getSalesRuleImpact, type SalesRuleImpactPayload } from '@/lib/sales-rule-impact'
import { canonicalResearchHref, materialEvidenceHref, reviewEventsHref } from '@/lib/research-platform/routes'

export const dynamic = 'force-dynamic'

async function fetchJson(url: string) {
  const response = await fetch(url, { cache: 'no-store' })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || payload.error || '读取失败')
  return payload
}

function appendReturnTo(href: string, returnTo: string) {
  if (href.includes('returnTo=')) return href
  const separator = href.includes('?') ? '&' : '?'
  return `${href}${separator}returnTo=${encodeURIComponent(returnTo)}`
}

const dashboardPurchasePlans = [
  { value: 'sip', label: '定投口径' },
  { value: 'lump_sum', label: '一次性口径' },
] as const

function withPurchasePlan(href: string, purchasePlan: typeof dashboardPurchasePlans[number]['value']) {
  const [pathWithQuery, hash = ''] = canonicalResearchHref(href).split('#')
  const [pathname, query = ''] = pathWithQuery.split('?')
  const params = new URLSearchParams(query)
  params.set('purchasePlan', purchasePlan)
  const nextHref = `${pathname}?${params.toString()}`
  return hash ? `${nextHref}#${hash}` : nextHref
}

function withDashboardFunnelContext(
  href: string,
  purchasePlan: typeof dashboardPurchasePlans[number]['value'] = 'sip',
  stage = 'overview',
) {
  const [pathWithQuery, hash = ''] = canonicalResearchHref(href).split('#')
  const [pathname, query = ''] = pathWithQuery.split('?')
  const params = new URLSearchParams(query)
  params.set('profile', params.get('profile') || 'balanced')
  params.set('horizon', params.get('horizon') || '1to3y')
  params.set('purchasePlan', purchasePlan)
  params.set('plannedAmount', params.get('plannedAmount') || defaultPlannedAmountForPlan(purchasePlan))
  params.set(purchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount', params.get('plannedAmount') || defaultPlannedAmountForPlan(purchasePlan))
  params.set('source', 'dashboard_funnel')
  params.set('funnelStage', stage)
  const nextHref = `${pathname}?${params.toString()}`
  return hash ? `${nextHref}#${hash}` : nextHref
}

function formatNumber(value: number | null | undefined) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function formatCoverage(value: number | null | undefined) {
  return `${Number(value || 0).toFixed(1)}%`
}

function numberFromBucket(bucket: Record<string, unknown> | undefined, key: string) {
  const value = bucket?.[key]
  const numberValue = Number(value || 0)
  return Number.isFinite(numberValue) ? numberValue : 0
}

function normalizeAlertPurchasePlan(value: unknown) {
  return value === 'lump_sum' ? 'lump_sum' : 'sip'
}

function defaultPlannedAmountForPlan(purchasePlan: typeof dashboardPurchasePlans[number]['value']) {
  return purchasePlan === 'lump_sum' ? '10000' : '1000'
}

function stringFromUnknown(value: unknown) {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return ''
}

function asRecord(value: unknown): Record<string, unknown> {
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

type DashboardAlertEvent = {
  id?: string
  fund_id?: string | null
  pool_member_id?: string | null
  event_type?: string
  severity?: string
  title?: string
  message?: string
  status?: string
  details?: unknown
}

function alertFundCode(event: DashboardAlertEvent) {
  const details = asRecord(event.details)
  return (
    stringFromUnknown(details.wind_code) ||
    stringFromUnknown(details.fund_code) ||
    stringFromUnknown(event.fund_id)
  ).toUpperCase()
}

function salesRuleAlertHref(event: DashboardAlertEvent, returnTo = '/overview') {
  const details = asRecord(event.details)
  const purchasePlan = normalizeAlertPurchasePlan(details.purchase_plan || details.purchasePlan)
  const rawAmount = stringFromUnknown(details.planned_amount ?? details.plannedAmount)
  const plannedAmount = rawAmount && Number(rawAmount) > 0 ? rawAmount : defaultPlannedAmountForPlan(purchasePlan)
  const fundCode = alertFundCode(event)
  const params = new URLSearchParams({
    purchasePlan,
    plannedAmount,
    returnTo,
  })
  if (fundCode) params.set('codes', fundCode)
  return materialEvidenceHref(params)
}

function summarizeDashboardAlerts(events: DashboardAlertEvent[]) {
  const unresolvedEvents = events.filter((event) => event.status !== 'resolved')
  const salesRuleEvidenceAlerts = unresolvedEvents.filter((event) => event.event_type === 'sales_rule_evidence')
  const firstSalesRuleEvidenceAlert = salesRuleEvidenceAlerts.find((event) => event.severity === 'high') || salesRuleEvidenceAlerts[0] || null
  return {
    unresolvedAlertCount: unresolvedEvents.length,
    highAlertCount: unresolvedEvents.filter((event) => event.severity === 'high').length,
    salesRuleEvidenceAlertCount: salesRuleEvidenceAlerts.length,
    firstSalesRuleEvidenceAlert: firstSalesRuleEvidenceAlert
      ? {
          fundCode: alertFundCode(firstSalesRuleEvidenceAlert),
          title: stringFromUnknown(firstSalesRuleEvidenceAlert.title) || '材料核验/R1-R5证据待补',
          message: stringFromUnknown(firstSalesRuleEvidenceAlert.message) || '材料核验、R1-R5来源、费率或赎回规则需要复查。',
          severity: stringFromUnknown(firstSalesRuleEvidenceAlert.severity) || 'medium',
          salesRulesHref: salesRuleAlertHref(firstSalesRuleEvidenceAlert),
        }
      : null,
  }
}

function latestShortlistDecisionCard(reports: Array<Record<string, unknown>>) {
  for (const report of reports) {
    const dataSources = asRecord(report.data_sources)
    const members = Array.isArray(dataSources.members) ? dataSources.members : []
    for (const member of members) {
      const memberRecord = asRecord(member)
      const card = asRecord(memberRecord.decisionCard)
      const salesRuleMissingCount = Number(memberRecord.salesRuleMissingCount || 0)
      const nextActions = Array.isArray(memberRecord.nextActions) ? memberRecord.nextActions.map((item) => String(item || '').trim()).filter(Boolean) : []
      const missingItems = Array.isArray(memberRecord.salesRuleMissingItems) ? memberRecord.salesRuleMissingItems.map((item) => String(item || '').trim()).filter(Boolean) : []
      const label = String(card.label || memberRecord.decisionLabel || '').trim()
      if (!label && !nextActions.length && !salesRuleMissingCount) continue
      return {
        reportId: String(report.id || ''),
        windCode: String(memberRecord.windCode || '').trim().toUpperCase(),
        fundName: String(memberRecord.fundName || memberRecord.windCode || '').trim(),
        label: label || (salesRuleMissingCount ? '先补证再判断' : '回到研究清单复核'),
        primaryAction: String(card.primaryAction || nextActions[0] || (salesRuleMissingCount ? '优先补材料核验，再决定是否保留候选' : '回到研究清单复核研究证据')).trim(),
        reason: Array.isArray(card.reasons) && card.reasons.length
          ? String(card.reasons[0] || '')
          : salesRuleMissingCount
            ? `材料核验仍缺 ${salesRuleMissingCount} 项${missingItems.length ? `：${missingItems.slice(0, 3).join('、')}` : ''}`
            : nextActions[0] || '研究清单证据需要复核',
        reverseTrigger: Array.isArray(card.reverseTriggers) && card.reverseTriggers.length
          ? String(card.reverseTriggers[0] || '')
          : salesRuleMissingCount
            ? '材料核验硬缺口清零，并记录来源日期与平台字段'
            : '补齐同类横评、成本证据和历史净值回放后重新生成短名单',
      }
    }
  }
  return null
}

async function fetchDashboardOverview() {
  const overview = {
    marketFundTotal: 0,
    candidateCount: 0,
    salesRuleReadyCandidateCount: 0,
    salesRuleGapCount: 0,
    highPriorityGapCount: 0,
    reportTotal: 0,
    shortlistReportCount: 0,
    latestReportLabel: '暂无报告',
    salesRuleImpact: null as SalesRuleImpactPayload | null,
    latestShortlistDecision: null as null | {
      reportId: string
      windCode: string
      fundName: string
      label: string
      primaryAction: string
      reason: string
      reverseTrigger: string
    },
    unresolvedAlertCount: 0,
    highAlertCount: 0,
    salesRuleEvidenceAlertCount: 0,
    firstSalesRuleEvidenceAlert: null as null | {
      fundCode: string
      title: string
      message: string
      severity: string
      salesRulesHref: string
    },
    salesRulesHref: materialEvidenceHref(),
    salesRuleGapCodes: [] as string[],
    gapPreview: [] as Array<{ windCode: string; fundName: string; missingCount: number; nextAction: string }>,
    marketResearchChecklist: {
      complete: 0,
      repair: 0,
      blocked: 0,
      primaryGapBuckets: {} as Record<string, number>,
      source: '',
    },
    dataSource: 'backend.tushare_postgres',
    errors: [] as string[],
  }

  const [fundsResult, poolsResult, gapsResult, reportsResult, impactResult, alertsResult] = await Promise.allSettled([
    fetchJson(`${backendApiBaseUrl}/api/funds?page=1&page_size=1`),
    fetchJson(`${backendApiBaseUrl}/api/fund-pools`),
    getSalesRuleGaps('candidate', 300),
    fetchJson(`${backendApiBaseUrl}/api/reports?page=1&limit=50`),
    getSalesRuleImpact(),
    fetchJson(`${backendApiBaseUrl}/api/alerts`),
  ])

  if (fundsResult.status === 'fulfilled') {
    overview.marketFundTotal = Number(fundsResult.value.total || 0)
    const checklist = fundsResult.value.summary?.market_research_checklist || fundsResult.value.summary?.marketResearchChecklist || null
    const statusBuckets = checklist?.status_buckets || checklist?.statusBuckets || {}
    overview.marketResearchChecklist = {
      complete: numberFromBucket(statusBuckets, 'complete'),
      repair: numberFromBucket(statusBuckets, 'repair'),
      blocked: numberFromBucket(statusBuckets, 'blocked'),
      primaryGapBuckets: checklist?.primary_gap_buckets || checklist?.primaryGapBuckets || {},
      source: checklist?.source || '',
    }
  } else {
    overview.errors.push('基金总数读取失败')
  }

  if (gapsResult.status === 'fulfilled') {
    overview.candidateCount = gapsResult.value.totalMembers
    overview.salesRuleGapCount = gapsResult.value.gapCount
    overview.salesRuleReadyCandidateCount = Math.max(overview.candidateCount - overview.salesRuleGapCount, 0)
    overview.highPriorityGapCount = gapsResult.value.summary.high
    overview.salesRuleGapCodes = Array.from(new Set((gapsResult.value.gaps || [])
      .map((gap) => gap.windCode)
      .filter(Boolean)))
      .slice(0, 40)
    overview.gapPreview = (gapsResult.value.gaps || [])
      .slice(0, 6)
      .map((gap) => ({
        windCode: gap.windCode,
        fundName: gap.fundName,
        missingCount: gap.missingCount,
        nextAction: gap.nextAction,
      }))
    if (overview.salesRuleGapCodes.length > 0) {
      const params = new URLSearchParams({
        codes: overview.salesRuleGapCodes.join(','),
      })
      overview.salesRulesHref = materialEvidenceHref(params)
    }
  } else {
    overview.errors.push('研究清单材料核验缺口读取失败')
  }

  if (reportsResult.status === 'fulfilled') {
    const reports = reportsResult.value.reports || []
    overview.reportTotal = Number(reportsResult.value.total || reports.length || 0)
    overview.shortlistReportCount = reports.filter((report: Record<string, unknown>) => report.report_type === 'fund_pool_shortlist_report').length
    overview.latestShortlistDecision = latestShortlistDecisionCard(reports)
    const latest = reports[0]
    overview.latestReportLabel = latest
      ? `${latest.target_id || ''} ${latest.report_type === 'fund_pool_shortlist_report' ? '研究短名单报告' : latest.report_type === 'fund_pre_purchase_check' ? '研究复核报告' : '研究报告'}`
      : '暂无报告'
  } else {
    overview.errors.push('报告库读取失败')
  }

  if (poolsResult.status === 'rejected') {
    overview.errors.push('研究清单读取失败')
  }

  if (impactResult.status === 'fulfilled') {
    overview.salesRuleImpact = impactResult.value
    if (!overview.marketFundTotal) overview.marketFundTotal = impactResult.value.totalFunds
  } else {
    overview.errors.push('适当性影响读取失败')
  }

  if (alertsResult.status === 'fulfilled') {
    const alertSummary = summarizeDashboardAlerts(Array.isArray(alertsResult.value.events) ? alertsResult.value.events : [])
    overview.unresolvedAlertCount = alertSummary.unresolvedAlertCount
    overview.highAlertCount = alertSummary.highAlertCount
    overview.salesRuleEvidenceAlertCount = alertSummary.salesRuleEvidenceAlertCount
    overview.firstSalesRuleEvidenceAlert = alertSummary.firstSalesRuleEvidenceAlert
  } else {
    overview.errors.push('复查队列读取失败')
  }

  return overview
}

export default async function HomePage() {
  const overview = await fetchDashboardOverview()
  const hasSalesRuleBlocks = overview.salesRuleGapCount > 0
  const hasStaleSalesRuleAlerts = overview.salesRuleEvidenceAlertCount > 0
  const riskLevelMissingCount = overview.salesRuleImpact?.summary.riskLevelMissingCount ?? 0
  const riskLevelCoverage = overview.salesRuleImpact?.summary.riskLevelCoverage ?? 0
  const checklistKnownTotal = overview.marketResearchChecklist.complete + overview.marketResearchChecklist.repair + overview.marketResearchChecklist.blocked
  const checklistReadyCount = overview.marketResearchChecklist.complete
  const formalReportReadyCount = Math.max(overview.salesRuleReadyCandidateCount - (hasStaleSalesRuleAlerts ? overview.salesRuleEvidenceAlertCount : 0), 0)
  const firstChecklistGap = Object.entries(overview.marketResearchChecklist.primaryGapBuckets)
    .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0))[0] || null
  const dashboardSalesRulesHrefFor = (purchasePlan: typeof dashboardPurchasePlans[number]['value']) =>
    appendReturnTo(withPurchasePlan(overview.salesRulesHref, purchasePlan), '/')
  const dashboardResearchListHref = canonicalResearchHref('/pools?status=candidate')
  const dashboardPeerComparisonHref = canonicalResearchHref('/rankings?profile=balanced&horizon=1to3y&sourceLimit=300')
  const dashboardProfileScreeningHref = canonicalResearchHref('/investor-selection?profile=balanced&horizon=1to3y&sourceLimit=300')
  const dashboardPriority: {
    tone: string
    eyebrow: string
    title: string
    detail: string
    action: string
    href: string
    chips: string[]
    secondaryAction?: string
    secondaryHref?: string
  } = hasStaleSalesRuleAlerts
    ? {
        tone: 'rose',
        eyebrow: '今日优先事项',
        title: '先处理过期材料核验/R1-R5证据',
        detail: `复查队列有 ${overview.salesRuleEvidenceAlertCount} 条材料核验/R1-R5 证据过期或待补事件，其中高优先级 ${overview.highAlertCount} 条；补齐前相关候选不能恢复研究结论。`,
        action: '打开过期证据复查',
        href: reviewEventsHref({ returnTo: '/' }),
        secondaryAction: overview.firstSalesRuleEvidenceAlert ? '补首只销售证据' : undefined,
        secondaryHref: overview.firstSalesRuleEvidenceAlert?.salesRulesHref,
        chips: [
          overview.firstSalesRuleEvidenceAlert?.fundCode ? `${overview.firstSalesRuleEvidenceAlert.fundCode} 待补` : '',
          `未解决 ${overview.unresolvedAlertCount}`,
          `规则/R1-R5过期 ${overview.salesRuleEvidenceAlertCount}`,
        ].filter(Boolean),
      }
    : hasSalesRuleBlocks
    ? {
        tone: 'amber',
        eyebrow: '今日优先事项',
        title: '先补材料核验硬缺口',
        detail: `研究清单 ${overview.salesRuleGapCount}/${overview.candidateCount} 只基金被申购、费率、赎回、限购或风险等级证据拦截；补齐前不进入正式研究复核报告。`,
        action: '打开补证台账',
        href: dashboardSalesRulesHrefFor('sip'),
        chips: overview.gapPreview.slice(0, 4).map((gap) => `${gap.windCode} 缺${gap.missingCount}`),
      }
    : overview.candidateCount === 0
      ? {
          tone: 'blue',
          eyebrow: '今日优先事项',
          title: '先建立可研究研究清单',
          detail: `本地基金库已有 ${overview.marketFundTotal.toLocaleString('zh-CN')} 只基金，但研究清单为空；先从全市场或同类横评挑出可研究标的。`,
          action: '去同类横评选样本',
          href: withPurchasePlan(dashboardPeerComparisonHref, 'sip'),
          chips: ['全市场扩样本', '画像化研究筛选', '加入研究清单'],
        }
      : overview.shortlistReportCount === 0
        ? {
            tone: 'emerald',
            eyebrow: '今日优先事项',
            title: '生成第一份正式研究短名单',
            detail: `研究清单暂未发现材料核验硬缺口，可以从研究清单继续横向比较、历史净值回放并保存研究短名单报告。`,
            action: '进入研究清单复核',
            href: dashboardResearchListHref,
            chips: ['横向比较', '费用后回放', '报告留痕'],
          }
        : {
            tone: 'violet',
            eyebrow: '今日优先事项',
            title: '复核最新报告与研究清单',
            detail: `已有 ${overview.reportTotal} 份报告，最新记录：${overview.latestReportLabel}；建议按当前画像重跑榜单，检查报告是否仍然有效。`,
            action: '进入报告库',
            href: '/reports',
            chips: ['报告有效性', '研究清单复核', '重新筛选'],
          }
  const researchFlow = [
    {
      title: '全市场扩样本',
      detail: '从真实基金库搜索、筛选、排序，把可研究标的放入研究清单。',
      href: '/market',
      action: '打开全市场浏览器',
      tone: 'blue',
    },
    {
      title: '画像化研究筛选',
      detail: '按风险画像、持有期、研究口径生成可解释榜单，不直接替代研究复核。',
      href: dashboardProfileScreeningHref,
      action: '进入画像化研究筛选',
      tone: 'indigo',
    },
    {
      title: '研究清单分层',
      detail: '区分可研究、待补材料核验、待补研究证据，避免假阳性短名单。',
      href: dashboardResearchListHref,
      action: '查看研究清单',
      tone: 'violet',
    },
    {
      title: '材料核验补证',
      detail: '申购状态、费率、赎回、限购、风险等级缺失时，正式研究复核报告会被拦截。',
      href: dashboardSalesRulesHrefFor('sip'),
      action: hasSalesRuleBlocks ? '补当前硬缺口' : '检查规则台账',
      tone: hasSalesRuleBlocks ? 'amber' : 'emerald',
    },
    {
      title: '报告留痕',
      detail: '缺口未补只能生成补证快照；补齐后才能保存正式研究短名单报告。',
      href: '/reports',
      action: '进入报告库',
      tone: 'slate',
    },
  ]

  const researchPathWorkbench = [
    {
      title: '全市场扩样本',
      intent: '我还没有足够样本',
      metric: `${formatNumber(overview.marketFundTotal)} 只真实入库基金`,
      blocker: riskLevelMissingCount > 0
        ? `R1-R5待补 ${formatNumber(riskLevelMissingCount)} 只，浏览可以继续，正式研究结论不能放行`
        : '风险等级覆盖已可进入适当性匹配复核',
      proof: '从全市场浏览器筛选、排序、加入研究清单',
      href: '/market?profile=balanced&horizon=1to3y&sortBy=screeningScore&sortOrder=desc',
      tone: 'blue',
    },
    {
      title: '画像化研究筛选',
      intent: '我知道风险画像和持有期',
      metric: `覆盖率 ${formatCoverage(riskLevelCoverage)}`,
      blocker: riskLevelMissingCount > 0
        ? '缺R1-R5时只输出研究优先级，不输出可研究匹配池'
        : '可按画像进入研究清单复核',
      proof: '按稳健/均衡/进取、持有期、研究口径筛出解释型榜单',
      href: dashboardProfileScreeningHref,
      tone: 'indigo',
    },
    {
      title: '单基金研究复核体检',
      intent: '我已经有目标基金',
      metric: `研究清单 ${formatNumber(overview.candidateCount)} 只`,
      blocker: hasSalesRuleBlocks
        ? '详情页体检会标出材料核验、R1-R5、历史净值回放和替代比较缺口'
        : '可进入单基金详情继续做研究复核',
      proof: '先查基金详情，再生成正式研究复核报告或补证快照',
      href: '/funds?profile=balanced&horizon=1to3y',
      tone: 'violet',
    },
    {
      title: '横向比较',
      intent: '我要比较几只候选',
      metric: `规则可放行 ${formatNumber(overview.salesRuleReadyCandidateCount)} 只`,
      blocker: hasSalesRuleBlocks
        ? '材料核验、费率可比性或历史净值回放缺失时，只保留研究排序'
        : '可继续生成对比矩阵并保存研究复核报告',
      proof: '同画像、同研究口径、同证据口径下比较',
      href: '/analysis/comparison?profile=balanced&horizon=1to3y&autoReplay=1',
      tone: 'emerald',
    },
    {
      title: '材料核验/R1-R5补证',
      intent: '我看到候选被硬拦截',
      metric: `硬缺口 ${formatNumber(overview.salesRuleGapCount)} 只`,
      blocker: '必须有销售平台/合同/招募说明书类来源和来源日期，不能用fund_basic替代',
      proof: '补申购状态、费率、赎回、最低申购、限购、销售风险等级',
      href: materialEvidenceHref({ scope: 'market', focus: 'risk_level', queueMode: 'high_score_missing_risk' }),
      tone: hasSalesRuleBlocks || riskLevelMissingCount > 0 ? 'amber' : 'emerald',
    },
    {
      title: '正式研究复核报告留痕',
      intent: '我要沉淀可复核结论',
      metric: `${formatNumber(overview.reportTotal)} 份报告`,
      blocker: hasSalesRuleBlocks || riskLevelMissingCount > 0
        ? '硬证据未清零前只能留补证快照，不能写成正式研究结论'
        : '可保存正式研究短名单或单基金核查报告',
      proof: '报告记录数据来源、缺口、反转条件和下一次复核点',
      href: '/reports?reportType=fund_pre_purchase_check',
      tone: 'slate',
    },
  ]

  const purchaseResearchFunnel = [
    {
      stage: 'market',
      title: '全市场研究底座',
      value: overview.marketFundTotal,
      denominator: overview.marketFundTotal,
      label: '真实入库基金',
      detail: '来自本地后端基金库，是筛选和分析的基础样本。',
      href: '/market',
      action: '打开全市场',
      tone: 'blue',
    },
    {
      stage: 'research_checklist',
      title: '研究复核研究体检通过',
      value: checklistReadyCount,
      denominator: checklistKnownTotal || overview.marketFundTotal,
      label: checklistKnownTotal ? `${formatCoverage(checklistKnownTotal ? (checklistReadyCount / checklistKnownTotal) * 100 : 0)} 通过` : '体检汇总待补',
      detail: firstChecklistGap
        ? `首要缺口：${firstChecklistGap[0]} ${formatNumber(Number(firstChecklistGap[1] || 0))} 只。`
        : '基础、绩效、风险、经理、持仓和材料核验均需有证据。',
      href: firstChecklistGap
        ? `/market?researchChecklistStatus=repair&researchChecklistGap=${encodeURIComponent(firstChecklistGap[0])}&sortBy=researchChecklist&sortOrder=asc`
        : '/market?researchChecklistStatus=complete&sortBy=researchChecklist&sortOrder=desc',
      action: firstChecklistGap ? '处理体检缺口' : '查看通过样本',
      tone: checklistReadyCount > 0 ? 'emerald' : 'amber',
    },
    {
      stage: 'candidate_pool',
      title: '研究清单样本',
      value: overview.candidateCount,
      denominator: overview.marketFundTotal,
      label: '观察/候选承接',
      detail: '只能承接基金研究对象；未过门禁不能成为正式研究候选。',
      href: dashboardResearchListHref,
      action: '查看研究清单',
      tone: 'violet',
    },
    {
      stage: 'sales_rules',
      title: '材料核验暂可放行',
      value: overview.salesRuleReadyCandidateCount,
      denominator: Math.max(overview.candidateCount, 1),
      label: hasSalesRuleBlocks ? `${formatNumber(overview.salesRuleGapCount)} 只仍阻断` : '研究清单未见硬缺口',
      detail: '申购状态、费率、赎回、限购、R1-R5和计划金额必须逐项闭环。',
      href: hasSalesRuleBlocks ? overview.salesRulesHref : dashboardResearchListHref,
      action: hasSalesRuleBlocks ? '补材料核验' : '进入复核',
      tone: hasSalesRuleBlocks ? 'amber' : 'emerald',
    },
    {
      stage: 'formal_report',
      title: '正式报告可沉淀',
      value: formalReportReadyCount,
      denominator: Math.max(overview.candidateCount, 1),
      label: `${formatNumber(overview.reportTotal)} 份报告库记录`,
      detail: hasStaleSalesRuleAlerts
        ? '复查队列未清零前，历史报告只能回看或生成补证快照。'
        : '通过材料核验后，还要完成横评、回放、持仓和反证留痕。',
      href: hasStaleSalesRuleAlerts ? reviewEventsHref({ returnTo: '/' }) : '/reports',
      action: hasStaleSalesRuleAlerts ? '先清复查队列' : '查看报告库',
      tone: hasStaleSalesRuleAlerts ? 'rose' : 'slate',
    },
  ]

  const toneClass: Record<string, string> = {
    blue: 'border-blue-100 bg-blue-50 text-blue-900',
    indigo: 'border-indigo-100 bg-indigo-50 text-indigo-900',
    violet: 'border-violet-100 bg-violet-50 text-violet-900',
    amber: 'border-amber-100 bg-amber-50 text-amber-900',
    emerald: 'border-emerald-100 bg-emerald-50 text-emerald-900',
    slate: 'border-slate-100 bg-slate-50 text-slate-900',
    rose: 'border-rose-100 bg-rose-50 text-rose-900',
  }

  const priorityToneClass: Record<string, string> = {
    rose: 'border-rose-100 bg-rose-50 text-rose-900',
    amber: 'border-amber-100 bg-amber-50 text-amber-900',
    blue: 'border-blue-100 bg-blue-50 text-blue-900',
    emerald: 'border-emerald-100 bg-emerald-50 text-emerald-900',
    violet: 'border-violet-100 bg-violet-50 text-violet-900',
  }

  return (
    <div className="space-y-8">
      <div className="rounded-lg bg-gradient-to-r from-blue-600 to-blue-800 p-8 text-white shadow-lg">
        <h1 className="mb-2 text-3xl font-bold">欢迎使用基金研究引擎</h1>
        <p className="text-blue-100">
          专注基金筛选、基金分析和基金经理评价；研究结论必须经过材料核验硬证据校验。
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          {hasSalesRuleBlocks ? dashboardPurchasePlans.map((plan) => (
            <Link key={plan.value} href={dashboardSalesRulesHrefFor(plan.value)} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50">
              {plan.label}补硬缺口
              <ArrowRight className="h-4 w-4" />
            </Link>
          )) : (
            <Link href="/market" className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50">
              从全市场开始研究
              <ArrowRight className="h-4 w-4" />
            </Link>
          )}
          <Link href={dashboardResearchListHref} className="inline-flex items-center gap-2 rounded-lg border border-white/30 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10">
            查看研究清单门禁
          </Link>
        </div>
      </div>

      <div className={`rounded-3xl border p-6 shadow ${priorityToneClass[dashboardPriority.tone] || priorityToneClass.violet}`} data-testid="dashboard-priority-action">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex rounded-full bg-white/70 px-2.5 py-1 text-xs font-semibold ring-1 ring-black/5">
              {dashboardPriority.eyebrow}
            </div>
            <h2 className="mt-3 text-xl font-bold">{dashboardPriority.title}</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 opacity-85">{dashboardPriority.detail}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {dashboardPriority.chips.length ? dashboardPriority.chips.map((chip) => (
                <span key={chip} className="rounded-full bg-white/70 px-2.5 py-1 text-xs ring-1 ring-black/5">{chip}</span>
              )) : (
                <span className="rounded-full bg-white/70 px-2.5 py-1 text-xs ring-1 ring-black/5">暂无阻断样本</span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {hasStaleSalesRuleAlerts ? (
              <>
                <Link href={dashboardPriority.href} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-slate-50">
                  {dashboardPriority.action}
                  <ArrowRight className="h-4 w-4" />
                </Link>
                {dashboardPriority.secondaryHref ? (
                  <Link href={dashboardPriority.secondaryHref} className="inline-flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
                    {dashboardPriority.secondaryAction}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                ) : null}
              </>
            ) : hasSalesRuleBlocks ? dashboardPurchasePlans.map((plan) => (
              <Link key={plan.value} href={appendReturnTo(withPurchasePlan(overview.salesRulesHref, plan.value), '/')} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-slate-50">
                {plan.label}
                <ArrowRight className="h-4 w-4" />
              </Link>
            )) : (
              <Link href={dashboardPriority.href} className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 ring-1 ring-black/5 hover:bg-slate-50">
                {dashboardPriority.action}
                <ArrowRight className="h-4 w-4" />
              </Link>
            )}
          </div>
        </div>
      </div>

      {hasStaleSalesRuleAlerts ? (
        <div className="rounded-3xl border border-rose-100 bg-white p-6 shadow" data-testid="dashboard-stale-sales-rule-alerts">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="inline-flex rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 ring-1 ring-rose-100">
                材料核验/R1-R5过期
              </div>
              <h2 className="mt-3 text-xl font-bold text-slate-950">过期证据已进入研究复核拦截</h2>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
                当前复查队列有 {overview.salesRuleEvidenceAlertCount} 条未解决的材料核验/R1-R5 证据事件；
                这类事件优先级高于普通候选缺口，必须补齐 30 日内来源、费率、赎回和申赎限制后再恢复研究复核报告。
              </p>
              {overview.firstSalesRuleEvidenceAlert ? (
                <div className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-800 ring-1 ring-rose-100">
                  <span className="font-semibold">{overview.firstSalesRuleEvidenceAlert.fundCode || overview.firstSalesRuleEvidenceAlert.title}：</span>
                  {overview.firstSalesRuleEvidenceAlert.message}
                </div>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Link href={reviewEventsHref({ returnTo: '/' })} className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">
                打开复查队列
                <ArrowRight className="h-4 w-4" />
              </Link>
              {overview.firstSalesRuleEvidenceAlert ? (
                <Link href={overview.firstSalesRuleEvidenceAlert.salesRulesHref} className="inline-flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
                  补材料核验/R1-R5
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <div className="rounded-3xl border border-slate-200 bg-slate-950 p-6 text-white shadow" data-testid="dashboard-research-path-workbench">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-cyan-100 ring-1 ring-white/15">
              Start Here
            </div>
            <h2 className="mt-3 text-2xl font-bold">基金研究路径工作台</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">
              只覆盖基金筛选、基金分析、基金经理评价和研究证据核查；每条路径都保留定投/一次性口径，硬证据不足时只给研究动作，不给申赎指令。
            </p>
          </div>
          <div className="rounded-2xl bg-white/10 px-4 py-3 text-sm ring-1 ring-white/15">
            <div className="text-xs text-slate-300">当前总门禁</div>
            <div className="mt-1 font-semibold text-white">
              {riskLevelMissingCount > 0 ? `R1-R5待补 ${formatNumber(riskLevelMissingCount)} 只` : 'R1-R5覆盖待复核'}
            </div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {researchPathWorkbench.map((item) => (
            <div key={item.title} className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 shadow-inner">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold text-cyan-200">{item.intent}</div>
                  <h3 className="mt-1 text-base font-bold text-white">{item.title}</h3>
                </div>
                <span className="shrink-0 rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10">
                  {item.metric}
                </span>
              </div>
              <p className="mt-3 min-h-12 text-sm leading-6 text-slate-300">{item.blocker}</p>
              <div className="mt-3 rounded-xl bg-slate-900/70 px-3 py-2 text-xs leading-5 text-slate-300 ring-1 ring-white/10">
                <span className="font-semibold text-slate-100">证据动作：</span>{item.proof}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {dashboardPurchasePlans.map((plan) => (
                  <Link
                    key={plan.value}
                    href={appendReturnTo(withDashboardFunnelContext(item.href, plan.value, item.title), '/overview')}
                    className="inline-flex items-center gap-1 rounded-xl bg-white px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-cyan-50"
                  >
                    {plan.label}进入
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow" data-testid="dashboard-purchase-research-funnel">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
              选基闭环漏斗
            </div>
            <h2 className="mt-3 text-xl font-bold text-slate-950">从全市场到正式研究复核报告，看到每一步卡点</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
              这张漏斗只覆盖基金研究模块：基金筛选、基金分析、基金经理评价、材料核验补证和报告留痕。
              上游治理、资产配置、组合配置、申赎执行不进入这里。
            </p>
          </div>
          <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-100">
            <div className="text-xs text-slate-500">当前最大阻断</div>
            <div className="mt-1 font-semibold text-slate-950">
              {hasStaleSalesRuleAlerts
                ? `复查队列 ${formatNumber(overview.salesRuleEvidenceAlertCount)} 条`
                : hasSalesRuleBlocks
                  ? `材料核验 ${formatNumber(overview.salesRuleGapCount)} 只`
                  : firstChecklistGap
                    ? `${firstChecklistGap[0]} ${formatNumber(Number(firstChecklistGap[1] || 0))} 只`
                    : '进入逐基金复核'}
            </div>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-5">
          {purchaseResearchFunnel.map((step, index) => {
            const denominator = Math.max(Number(step.denominator || 0), 1)
            const ratio = Math.max(0, Math.min(100, Math.round((Number(step.value || 0) / denominator) * 100)))
            return (
              <Link
                key={step.title}
                href={appendReturnTo(withDashboardFunnelContext(step.href, 'sip', step.stage), '/overview')}
                className={`rounded-2xl border p-4 transition hover:-translate-y-0.5 hover:shadow ${toneClass[step.tone] || toneClass.slate}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold opacity-70">步骤 {index + 1}</div>
                    <div className="mt-1 text-sm font-bold">{step.title}</div>
                  </div>
                  <span className="rounded-full bg-white/80 px-2 py-0.5 text-xs font-semibold ring-1 ring-black/5">
                    {ratio}%
                  </span>
                </div>
                <div className="mt-3 text-2xl font-bold">{formatNumber(step.value)}</div>
                <div className="mt-1 text-xs font-semibold opacity-75">{step.label}</div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/70 ring-1 ring-black/5">
                  <div className="h-full rounded-full bg-current opacity-60" style={{ width: `${ratio}%` }} />
                </div>
                <p className="mt-3 min-h-16 text-xs leading-5 opacity-80">{step.detail}</p>
                <div className="mt-2 rounded-lg bg-white/70 px-2 py-1 text-[11px] leading-4 opacity-75 ring-1 ring-black/5">
                  队列来源：dashboard_funnel / {step.stage}；保留均衡型、1-3 年、定投 1,000 元口径。
                </div>
                <div className="mt-3 inline-flex items-center gap-1 text-xs font-semibold">
                  {step.action}
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </Link>
            )
          })}
        </div>

        <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-800" data-testid="dashboard-funnel-hard-boundary">
          硬边界：筛选分、经理分、同类横评、研究清单状态或历史报告都不能绕过材料核验/R1-R5、计划金额、执行可行性、同类横评和正式研究复核报告门禁；证据不足时只生成补证动作。
        </div>
      </div>

      {overview.salesRuleImpact ? (
        <div className="rounded-3xl border border-rose-100 bg-white p-6 shadow" data-testid="dashboard-buy-gate-radar">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="inline-flex rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 ring-1 ring-rose-100">
                研究复核总门禁
              </div>
              <h2 className="mt-3 text-xl font-bold text-slate-950">全市场适当性匹配池当前不可用</h2>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
                本地全市场 {formatNumber(overview.salesRuleImpact.totalFunds)} 只基金中，{formatNumber(overview.salesRuleImpact.summary.riskLevelMissingCount)} 只缺销售风险等级；
                未补 R1-R5 前，稳健/均衡/进取匹配池都不能作为真实可研究结论。
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {dashboardPurchasePlans.map((plan) => (
                <Link
                  key={plan.value}
                  href={appendReturnTo(withPurchasePlan(materialEvidenceHref({ scope: 'market', focus: 'risk_level', queueMode: 'high_score_missing_risk' }), plan.value), '/')}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
                >
                  {plan.label}补风险等级
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ))}
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs text-slate-500">风险等级覆盖率</div>
              <div className="mt-1 text-2xl font-bold text-rose-700">{formatCoverage(overview.salesRuleImpact.summary.riskLevelCoverage)}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs text-slate-500">风险等级待补</div>
              <div className="mt-1 text-2xl font-bold text-amber-700">{formatNumber(overview.salesRuleImpact.summary.riskLevelMissingCount)}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs text-slate-500">潜在解锁槽位</div>
              <div className="mt-1 text-2xl font-bold text-slate-900">{formatNumber(overview.salesRuleImpact.summary.totalReopenableSlots)}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs text-slate-500">研究清单门禁拦截</div>
              <div className="mt-1 text-2xl font-bold text-rose-700">{formatNumber(overview.salesRuleGapCount)}</div>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-3">
            {overview.salesRuleImpact.profiles.map((profile) => (
              <div key={profile.key} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold text-slate-950">{profile.label}</div>
                    <div className="mt-1 text-xs text-slate-500">最高可接受 R{profile.maxSalesRiskLevel}</div>
                  </div>
                  <Link href={`/market?salesRiskFilter=matched&profile=${profile.key}&sortBy=screeningScore&sortOrder=desc`} className="rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium text-blue-700 ring-1 ring-blue-100 hover:bg-blue-50">
                    看匹配池
                  </Link>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-lg bg-white px-2 py-2">
                    <div className="text-slate-500">已匹配</div>
                    <div className="mt-1 text-base font-bold text-emerald-700">{formatNumber(profile.matchedCount)}</div>
                  </div>
                  <div className="rounded-lg bg-white px-2 py-2">
                    <div className="text-slate-500">不匹配</div>
                    <div className="mt-1 text-base font-bold text-rose-700">{formatNumber(profile.mismatchCount)}</div>
                  </div>
                  <div className="rounded-lg bg-white px-2 py-2">
                    <div className="text-slate-500">待补</div>
                    <div className="mt-1 text-base font-bold text-amber-700">{formatNumber(profile.missingRiskCount)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
        <div className="rounded-2xl bg-white p-5 shadow">
          <div className="text-xs text-gray-500">全市场基金</div>
          <div className="mt-2 text-3xl font-semibold text-gray-900">{overview.marketFundTotal.toLocaleString('zh-CN')}</div>
          <Link href="/market" className="mt-2 inline-flex text-xs font-medium text-blue-600 hover:text-blue-800">去筛选</Link>
        </div>
        <div className="rounded-2xl bg-white p-5 shadow">
          <div className="text-xs text-gray-500">研究清单样本</div>
          <div className="mt-2 text-3xl font-semibold text-gray-900">{overview.candidateCount}</div>
          <Link href={dashboardResearchListHref} className="mt-2 inline-flex text-xs font-medium text-indigo-600 hover:text-indigo-800">看短名单</Link>
        </div>
        <div className="rounded-2xl bg-white p-5 shadow">
          <div className="text-xs text-gray-500">规则可放行候选</div>
          <div className="mt-2 text-3xl font-semibold text-emerald-700">{overview.salesRuleReadyCandidateCount}</div>
          <Link href={dashboardResearchListHref} className="mt-2 inline-flex text-xs font-medium text-emerald-700 hover:text-emerald-900">看分层</Link>
        </div>
        <div className="rounded-2xl bg-white p-5 shadow">
          <div className="text-xs text-gray-500">材料核验缺口</div>
          <div className="mt-2 text-3xl font-semibold text-amber-700">{overview.salesRuleGapCount}</div>
          <Link href={dashboardSalesRulesHrefFor('sip')} className="mt-2 inline-flex text-xs font-medium text-amber-700 hover:text-amber-900">补证据</Link>
        </div>
        <div className="rounded-2xl bg-white p-5 shadow">
          <div className="text-xs text-gray-500">高优先级缺口</div>
          <div className="mt-2 text-3xl font-semibold text-rose-700">{overview.highPriorityGapCount}</div>
          <Link href={dashboardSalesRulesHrefFor('sip')} className="mt-2 inline-flex text-xs font-medium text-rose-700 hover:text-rose-900">先处理</Link>
        </div>
        <div className="rounded-2xl bg-white p-5 shadow">
          <div className="text-xs text-gray-500">已保存报告</div>
          <div className="mt-2 text-3xl font-semibold text-gray-900">{overview.reportTotal}</div>
          <Link href="/reports" className="mt-2 inline-flex text-xs font-medium text-purple-600 hover:text-purple-800">进报告库</Link>
        </div>
      </div>

      {overview.errors.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          部分实时指标读取失败：{overview.errors.join('、')}。页面入口仍可继续使用。
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <div className="rounded-2xl border border-slate-100 bg-white p-6 shadow">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-slate-900">
                <ClipboardCheck className="h-5 w-5 text-blue-600" />
                <h2 className="text-lg font-semibold">今日研究复核作战台</h2>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                当前研究清单共有 {overview.candidateCount} 只基金，其中 {overview.salesRuleReadyCandidateCount} 只材料核验暂未发现硬缺口，
                {overview.salesRuleGapCount} 只仍被申购/费率/赎回/限购/风险等级等证据拦截。
              </p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${hasSalesRuleBlocks ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-100' : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100'}`}>
              {hasSalesRuleBlocks ? '正式短名单待补证' : '可生成正式短名单'}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
            <Link href="/market" className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-blue-900 hover:bg-blue-100">
              <div className="text-sm font-semibold">1. 找样本</div>
              <div className="mt-1 text-xs leading-5 text-blue-700">全市场基金 {overview.marketFundTotal.toLocaleString('zh-CN')} 只，先扩大可研究样本。</div>
            </Link>
            <Link href={dashboardResearchListHref} className="rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-indigo-900 hover:bg-indigo-100">
              <div className="text-sm font-semibold">2. 分候选</div>
              <div className="mt-1 text-xs leading-5 text-indigo-700">候选、观察、核心跟踪分层，硬缺口不允许直接晋级。</div>
            </Link>
            <Link href={dashboardSalesRulesHrefFor('sip')} className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-amber-900 hover:bg-amber-100">
              <div className="text-sm font-semibold">3. 补证据</div>
              <div className="mt-1 text-xs leading-5 text-amber-700">高优先级缺口 {overview.highPriorityGapCount} 只，补齐后再出正式报告。</div>
            </Link>
          </div>

          <div className="mt-5 rounded-xl border border-slate-100 bg-slate-50 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <Database className="h-4 w-4" />
              当前数据口径
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              基金样本来自本地后端基金库；材料核验从本地证据台账核对；报告库当前 {overview.reportTotal} 份，
              其中研究短名单报告 {overview.shortlistReportCount} 份。最新记录：{overview.latestReportLabel}。
            </p>
          </div>
          {overview.latestShortlistDecision ? (
            <Link
              href={overview.latestShortlistDecision.reportId ? `/reports/${overview.latestShortlistDecision.reportId}` : '/reports'}
              className="mt-4 block rounded-xl border border-cyan-100 bg-cyan-50 p-4 text-cyan-950 hover:bg-cyan-100"
              data-testid="dashboard-latest-shortlist-decision"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="text-xs font-semibold text-cyan-700">最新短名单研究复核决策卡</div>
                  <div className="mt-1 text-base font-semibold">
                    {overview.latestShortlistDecision.fundName || overview.latestShortlistDecision.windCode} · {overview.latestShortlistDecision.label}
                  </div>
                  <div className="mt-2 text-sm leading-6 text-cyan-800">{overview.latestShortlistDecision.primaryAction}</div>
                </div>
                <span className="shrink-0 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-cyan-700 ring-1 ring-cyan-100">
                  不输出申赎指令
                </span>
              </div>
              <div className="mt-3 grid gap-2 text-xs leading-5 md:grid-cols-2">
                <div className="rounded-lg bg-white/75 px-3 py-2 text-cyan-800">
                  <span className="font-semibold">当前判断依据：</span>{overview.latestShortlistDecision.reason}
                </div>
                <div className="rounded-lg bg-white/75 px-3 py-2 text-amber-800">
                  <span className="font-semibold">结论反转条件：</span>{overview.latestShortlistDecision.reverseTrigger}
                </div>
              </div>
            </Link>
          ) : null}
        </div>

        <div className="rounded-2xl border border-amber-100 bg-amber-50 p-6 shadow">
          <div className="flex items-center gap-2 text-amber-900">
            <AlertTriangle className="h-5 w-5" />
            <h2 className="text-lg font-semibold">最该先补的硬缺口</h2>
          </div>
          {overview.gapPreview.length ? (
            <div className="mt-4 space-y-3">
              {overview.gapPreview.map((gap) => (
                <div
                  key={gap.windCode}
                  className="rounded-xl bg-white p-3 text-sm ring-1 ring-amber-100"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-amber-950">{gap.fundName}</div>
                      <div className="mt-1 text-xs text-amber-700">{gap.windCode}</div>
                    </div>
                    <span className="shrink-0 rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
                      缺 {gap.missingCount} 项
                    </span>
                  </div>
                  <div className="mt-2 text-xs leading-5 text-amber-700">{gap.nextAction}</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {dashboardPurchasePlans.map((plan) => (
                      <Link
                        key={plan.value}
                        href={appendReturnTo(withPurchasePlan(materialEvidenceHref({ codes: gap.windCode }), plan.value), '/')}
                        className="rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-200"
                      >
                        {plan.label}补证
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
              <div className="flex flex-wrap gap-2">
                {dashboardPurchasePlans.map((plan) => (
                  <Link key={plan.value} href={appendReturnTo(withPurchasePlan(overview.salesRulesHref, plan.value), '/')} className="inline-flex items-center gap-2 text-sm font-semibold text-amber-800 hover:text-amber-950">
                    {plan.label}批量补证 <ArrowRight className="h-4 w-4" />
                  </Link>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-xl bg-white p-4 text-sm leading-6 text-emerald-700 ring-1 ring-emerald-100">
              当前研究清单未检测到材料核验硬缺口，可以继续做横向比较、历史净值回放和正式报告留痕。
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {researchFlow.map((item, index) => (
          <Link key={item.title} href={item.href} className={`rounded-xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow ${toneClass[item.tone]}`}>
            <div className="text-xs font-semibold opacity-70">步骤 {index + 1}</div>
            <div className="mt-2 text-base font-semibold">{item.title}</div>
            <p className="mt-2 min-h-16 text-sm leading-6 opacity-80">{item.detail}</p>
            <div className="mt-4 inline-flex items-center gap-1 text-sm font-semibold">
              {item.action}
              <ArrowRight className="h-4 w-4" />
            </div>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="rounded-xl border border-blue-100 bg-blue-50 p-5">
          <div className="flex items-center gap-3 text-blue-900">
            <Globe2 className="h-5 w-5" />
            <h2 className="text-base font-semibold">推荐起点：全市场浏览器</h2>
          </div>
          <p className="mt-2 text-sm text-blue-800">
            从全市场检索、筛选和排序基金，直接加入研究清单，作为研究工作流的第一站。
          </p>
          <Link href="/market" className="mt-4 inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            进入全市场浏览器
          </Link>
        </div>

        <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-5">
          <div className="flex items-center gap-3 text-indigo-900">
            <Target className="h-5 w-5" />
            <h2 className="text-base font-semibold">画像化研究筛选</h2>
          </div>
          <p className="mt-2 text-sm text-indigo-800">
            基于风险画像、收益回撤、规模和数据完整度，对真实入库基金生成可解释初筛榜单。
          </p>
          <Link href={dashboardProfileScreeningHref} className="mt-4 inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            打开画像化研究筛选
          </Link>
        </div>

        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5">
          <div className="flex items-center gap-3 text-amber-900">
            <Trophy className="h-5 w-5" />
            <h2 className="text-base font-semibold">同类横评</h2>
          </div>
          <p className="mt-2 text-sm text-amber-800">
            按综合、收益、低回撤、同类优势、持有体验、经理任期和成本生成研究榜单。
          </p>
          <Link href={dashboardPeerComparisonHref} className="mt-4 inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600">
            查看同类横评
          </Link>
        </div>

        <div className="rounded-xl border border-violet-100 bg-violet-50 p-5">
          <div className="flex items-center gap-3 text-violet-900">
            <Layers3 className="h-5 w-5" />
            <h2 className="text-base font-semibold">研究池管理</h2>
          </div>
          <p className="mt-2 text-sm text-violet-800">
            对候选、观察、核心和淘汰状态进行维护，沉淀结论、证据和下次复查日期。
          </p>
          <Link href={dashboardResearchListHref} className="mt-4 inline-flex items-center rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700">
            查看研究清单
          </Link>
        </div>

        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5">
          <div className="flex items-center gap-3 text-amber-900">
            <BellRing className="h-5 w-5" />
            <h2 className="text-base font-semibold">基金复查队列</h2>
          </div>
          <p className="mt-2 text-sm text-amber-800">
            对重点基金设置净值、回撤、规模和经理变动复查，服务基金研究持续跟踪。
          </p>
          <Link href={reviewEventsHref({ returnTo: '/' })} className="mt-4 inline-flex items-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600">
            打开复查队列
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Link href="/market">
          <div className="cursor-pointer rounded-lg border-2 border-transparent bg-white p-6 shadow transition-shadow hover:border-blue-500 hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-blue-100 p-3">
                <Globe2 className="h-6 w-6 text-blue-600" />
              </div>
              <Sparkles className="h-5 w-5 text-blue-600" />
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">全市场浏览器</h3>
            <p className="text-sm text-gray-500">搜索、筛选、排序全市场基金，并一键加入研究清单。</p>
          </div>
        </Link>

        <Link href="/funds">
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-blue-100 p-3">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">基金详情库</h3>
            <p className="text-sm text-gray-500">查看基金基础信息、净值、评分与可信度摘要。</p>
          </div>
        </Link>

        <Link href={dashboardProfileScreeningHref}>
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-indigo-100 p-3">
                <Target className="h-6 w-6 text-indigo-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">画像化研究筛选</h3>
            <p className="text-sm text-gray-500">按风险画像生成可解释匹配榜单，支持加入对比篮继续研究。</p>
          </div>
        </Link>

        <Link href={dashboardPeerComparisonHref}>
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-amber-100 p-3">
                <Trophy className="h-6 w-6 text-amber-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">同类横评</h3>
            <p className="text-sm text-gray-500">用真实入库基金生成综合、收益、回撤、同类、经理和成本榜单。</p>
          </div>
        </Link>

        <Link href={appendReturnTo(materialEvidenceHref(), '/')}>
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-cyan-100 p-3">
                <ShieldCheck className="h-6 w-6 text-cyan-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">材料核验</h3>
            <p className="text-sm text-gray-500">维护申购费、赎回费、限购和风险等级，补齐研究复核必核证据。</p>
          </div>
        </Link>

        <Link href={dashboardResearchListHref}>
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-indigo-100 p-3">
                <Layers3 className="h-6 w-6 text-indigo-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">研究清单</h3>
            <p className="text-sm text-gray-500">管理候选、观察、核心与淘汰池，维护研究结论和证据。</p>
          </div>
        </Link>

        <Link href={reviewEventsHref({ returnTo: '/' })}>
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-amber-100 p-3">
                <BellRing className="h-6 w-6 text-amber-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">复查队列</h3>
            <p className="text-sm text-gray-500">跟踪重点基金的净值、回撤、规模和经理变化，提醒研究复核。</p>
          </div>
        </Link>

        <Link href="/managers">
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-green-100 p-3">
                <Users className="h-6 w-6 text-green-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">基金经理</h3>
            <p className="text-sm text-gray-500">评价基金经理投资能力，追踪管理业绩。</p>
          </div>
        </Link>

        <Link href="/reports">
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-purple-100 p-3">
                <FileText className="h-6 w-6 text-purple-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">调研报告</h3>
            <p className="text-sm text-gray-500">管理调研报告库，支持智能检索和相似度推荐。</p>
          </div>
        </Link>

        <Link href="/analysis">
          <div className="cursor-pointer rounded-lg bg-white p-6 shadow transition-shadow hover:shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="rounded-lg bg-orange-100 p-3">
                <BarChart3 className="h-6 w-6 text-orange-600" />
              </div>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-gray-900">基金研究</h3>
            <p className="text-sm text-gray-500">生成基金研究备忘录，沉淀可复核的研究判断。</p>
          </div>
        </Link>
      </div>

      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-xl font-semibold text-gray-900">业务验收路径</h2>
        <div className="space-y-3">
          <div className="flex items-start">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 font-semibold text-blue-600">1</div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">从全市场浏览器找样本</h3>
              <p className="text-sm text-gray-500">搜索真实基金、按类型/规模/收益风险筛选，并把值得研究的基金加入研究清单。</p>
            </div>
          </div>
          <div className="flex items-start">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 font-semibold text-blue-600">2</div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">研究清单先做硬门禁</h3>
              <p className="text-sm text-gray-500">候选基金会自动分成可研究、待补材料核验、待补研究证据；硬缺口不能进正式短名单。</p>
            </div>
          </div>
          <div className="flex items-start">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 font-semibold text-blue-600">3</div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">补材料核验证据</h3>
              <p className="text-sm text-gray-500">补齐申购状态、申购费率、赎回费、最低申购、定投、限购、风险等级和来源日期。</p>
            </div>
          </div>
          <div className="flex items-start">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 font-semibold text-blue-600">4</div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">横向比较并生成报告</h3>
              <p className="text-sm text-gray-500">规则补齐后再做同类对比、历史净值回放和正式研究复核报告；缺口未补只允许生成补证快照。</p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-xl font-semibold text-gray-900">模块边界</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-gray-200 p-4">
            <p className="mb-1 text-sm text-gray-500">当前专注</p>
            <p className="text-lg font-semibold text-green-600">基金筛选 / 分析 / 经理评价</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-4">
            <p className="mb-1 text-sm text-gray-500">硬门禁</p>
            <p className="text-lg font-semibold text-amber-600">候选材料核验缺口 {overview.salesRuleGapCount} 只</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-4">
            <p className="mb-1 text-sm text-gray-500">明确不扩展</p>
            <p className="text-lg font-semibold text-slate-600">不做上游治理 / 资产配置 / 申赎执行</p>
          </div>
        </div>
      </div>
    </div>
  )
}
