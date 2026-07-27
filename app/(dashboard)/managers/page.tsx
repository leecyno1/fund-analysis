'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { AlertCircle, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { materialEvidenceHref } from '@/lib/research-platform/routes'

type RiskProfile = 'conservative' | 'balanced' | 'aggressive'
type InvestmentHorizon = 'lt1y' | '1to3y' | 'gt3y'
type PurchasePlan = 'lump_sum' | 'sip'

type ManagerFund = {
  wind_code?: string
  end_date?: string | null
}

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
  funds?: ManagerFund[]
}

type SalesRuleGap = {
  windCode: string
  priority: 'high' | 'medium' | 'low'
  missingItems: string[]
  missingCount: number
  nextAction?: string
  riskLevelSourceBacked?: boolean
  riskLevelEvidenceLabel?: string
  riskLevelEvidenceDetail?: string
}

type ManagerSalesRuleSummary = {
  totalFunds: number
  checkedFunds: number
  gapFunds: number
  highPriority: number
  missingItems: number
  gaps: SalesRuleGap[]
}

const validWindCodePattern = /^[0-9A-Z]{6,12}\.(OF|SH|SZ|BJ)$/i

const purchasePlanLabels: Record<PurchasePlan, string> = {
  lump_sum: '一次性配置假设',
  sip: '定投假设',
}

function escapeTsvValue(value: unknown) {
  return String(value ?? '')
    .replace(/\t/g, ' ')
    .replace(/\r?\n/g, ' ')
}

function buildTsv(rows: Array<Record<string, unknown>>) {
  if (!rows.length) return ''
  const headers = Object.keys(rows[0])
  return [
    headers.join('\t'),
    ...rows.map((row) => headers.map((header) => escapeTsvValue(row[header])).join('\t')),
  ].join('\n')
}

function pickParam<T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return value && allowed.includes(value as T) ? (value as T) : fallback
}

function appendReturnTo(href: string, returnTo: string) {
  const separator = href.includes('?') ? '&' : '?'
  return `${href}${separator}returnTo=${encodeURIComponent(returnTo)}`
}

function getBrowserParam(name: string) {
  if (typeof window === 'undefined') return null
  return new URLSearchParams(window.location.search).get(name)
}

function getBrowserSearchParam() {
  return getBrowserParam('search')?.trim() || ''
}

function pickPositivePage(value: string | null) {
  const page = Number(value)
  return Number.isInteger(page) && page > 0 ? page : 1
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

export default function ManagersPage() {
  const [managers, setManagers] = useState<Manager[]>([])
  const [loading, setLoading] = useState(true)
  const [salesRuleGapsByCode, setSalesRuleGapsByCode] = useState<Record<string, SalesRuleGap>>({})
  const [salesRuleCheckedCodes, setSalesRuleCheckedCodes] = useState<string[]>([])
  const [salesRuleLoading, setSalesRuleLoading] = useState(false)
  const [salesRuleError, setSalesRuleError] = useState<string | null>(null)
  const [managerProductWorkOrderCopyStatus, setManagerProductWorkOrderCopyStatus] = useState<string | null>(null)
  const [searchText, setSearchText] = useState(() => getBrowserSearchParam())
  const [appliedSearch, setAppliedSearch] = useState(() => getBrowserSearchParam())
  const [page, setPage] = useState(() => pickPositivePage(getBrowserParam('page')))
  const [totalPages, setTotalPages] = useState(1)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [riskProfile, setRiskProfile] = useState<RiskProfile>(() => pickParam(getBrowserParam('profile'), ['conservative', 'balanced', 'aggressive'] as const, 'balanced'))
  const [investmentHorizon, setInvestmentHorizon] = useState<InvestmentHorizon>(() => pickParam(getBrowserParam('horizon'), ['lt1y', '1to3y', 'gt3y'] as const, '1to3y'))
  const [purchasePlan, setPurchasePlan] = useState<PurchasePlan>(() => getBrowserPurchasePlan())
  const [plannedAmount, setPlannedAmount] = useState(() => {
    const initialPurchasePlan = getBrowserPurchasePlan()
    return normalizePlannedAmountInput(getBrowserPlannedAmountForPlan(initialPurchasePlan), initialPurchasePlan)
  })

  useEffect(() => {
    const timeout = globalThis.setTimeout(() => {
      const browserSearch = getBrowserSearchParam()
      setSearchText(browserSearch)
      setAppliedSearch(browserSearch)
      setPage(pickPositivePage(getBrowserParam('page')))
      setRiskProfile(pickParam(getBrowserParam('profile'), ['conservative', 'balanced', 'aggressive'] as const, 'balanced'))
      setInvestmentHorizon(pickParam(getBrowserParam('horizon'), ['lt1y', '1to3y', 'gt3y'] as const, '1to3y'))
      const nextPurchasePlan = getBrowserPurchasePlan()
      setPurchasePlan(nextPurchasePlan)
      setPlannedAmount(normalizePlannedAmountInput(getBrowserPlannedAmountForPlan(nextPurchasePlan), nextPurchasePlan))
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [])

  const plannedAmountParams = useMemo(
    () => plannedAmountSearchParams(purchasePlan, plannedAmount),
    [plannedAmount, purchasePlan],
  )
  const normalizedPlannedAmount = plannedAmountParams.plannedAmount
  const investorContextQuery = new URLSearchParams({
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams,
  }).toString()
  const managerReturnParams = new URLSearchParams({
    page: page.toString(),
    profile: riskProfile,
    horizon: investmentHorizon,
    purchasePlan,
    ...plannedAmountParams,
  })
  if (appliedSearch) managerReturnParams.set('search', appliedSearch)
  const managerReturnHref = `/managers?${managerReturnParams.toString()}`

  const fetchManagers = useCallback(async () => {
    setLoading(true)
    setErrorMessage(null)
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '20',
        ...(appliedSearch && { search: appliedSearch })
      })

      const response = await fetch(`/api/managers?${params}`)
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || '获取基金经理列表失败')

      setManagers(data.data || [])
      setTotalPages(data.pagination?.totalPages || 1)
    } catch (error) {
      console.error('获取基金经理列表失败:', error)
      setManagers([])
      setTotalPages(1)
      setErrorMessage(error instanceof Error ? error.message : '获取基金经理列表失败')
    } finally {
      setLoading(false)
    }
  }, [appliedSearch, page])

  useEffect(() => {
    const timeout = globalThis.setTimeout(() => {
      void fetchManagers()
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [fetchManagers])

  const getManagerResearchCodes = useCallback((manager: Manager) => {
    const explicitCodes = (manager.currentFunds || []).filter(Boolean)
    const fundCodes = (manager.funds || [])
      .filter((fund) => !fund.end_date)
      .map((fund) => fund.wind_code)
      .filter((code): code is string => Boolean(code))
    return Array.from(
      new Set(
        [...explicitCodes, ...fundCodes]
          .map((code) => code.trim().toUpperCase())
          .filter((code) => validWindCodePattern.test(code)),
      ),
    )
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const timeout = globalThis.setTimeout(async () => {
      const codes = Array.from(new Set(managers.flatMap((manager) => getManagerResearchCodes(manager)))).slice(0, 300)
      if (!codes.length) {
        setSalesRuleGapsByCode({})
        setSalesRuleCheckedCodes([])
        setSalesRuleError(null)
        setSalesRuleLoading(false)
        return
      }

      try {
        setSalesRuleLoading(true)
        setSalesRuleError(null)
        const params = new URLSearchParams({
          codes: codes.join(','),
          limit: String(codes.length),
          purchasePlan,
          ...plannedAmountParams,
        })
        const response = await fetch(`/api/evidence-coverage/materials/gaps?${params.toString()}`, {
          cache: 'no-store',
          signal: controller.signal,
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(payload.error || payload.detail || '读取经理列表销售规则缺口失败')
        const gapMap = (payload.gaps || []).reduce((bucket: Record<string, SalesRuleGap>, gap: SalesRuleGap) => {
          bucket[gap.windCode.toUpperCase()] = gap
          return bucket
        }, {})
        setSalesRuleGapsByCode(gapMap)
        setSalesRuleCheckedCodes(codes)
      } catch (error) {
        if (!controller.signal.aborted) {
          console.error('读取经理列表销售规则缺口失败:', error)
          setSalesRuleGapsByCode({})
          setSalesRuleCheckedCodes([])
          setSalesRuleError(error instanceof Error ? error.message : '读取经理列表销售规则缺口失败')
        }
      } finally {
        if (!controller.signal.aborted) setSalesRuleLoading(false)
      }
    }, 0)

    return () => {
      controller.abort()
      globalThis.clearTimeout(timeout)
    }
  }, [getManagerResearchCodes, managers, purchasePlan, plannedAmountParams])

  const getManagerSalesRuleSummary = useCallback((manager: Manager): ManagerSalesRuleSummary => {
    const codes = getManagerResearchCodes(manager)
    const checked = new Set(salesRuleCheckedCodes)
    const gaps = codes.map((code) => salesRuleGapsByCode[code]).filter((gap): gap is SalesRuleGap => Boolean(gap))
    return {
      totalFunds: codes.length,
      checkedFunds: codes.filter((code) => checked.has(code)).length,
      gapFunds: gaps.length,
      highPriority: gaps.filter((gap) => gap.priority === 'high').length,
      missingItems: gaps.reduce((sum, gap) => sum + gap.missingCount, 0),
      gaps,
    }
  }, [getManagerResearchCodes, salesRuleCheckedCodes, salesRuleGapsByCode])

  const buildManagerSalesRulesHref = (manager: Manager) => {
    const codes = getManagerResearchCodes(manager)
    const params = new URLSearchParams()
    if (codes.length) params.set('codes', codes.join(','))
    params.set('purchasePlan', purchasePlan)
    Object.entries(plannedAmountParams).forEach(([key, value]) => params.set(key, value))
    params.set('returnTo', managerReturnHref)
    return materialEvidenceHref(params)
  }

  const managerDetailHref = (manager: Manager) => appendReturnTo(
    `/managers/${encodeURIComponent(manager.id)}?${investorContextQuery}`,
    managerReturnHref,
  )

  const pageSalesRuleSummary = managers.reduce((summary, manager) => {
    const managerSummary = getManagerSalesRuleSummary(manager)
    return {
      researchManagers: summary.researchManagers + (managerSummary.totalFunds > 0 ? 1 : 0),
      gapManagers: summary.gapManagers + (managerSummary.gapFunds > 0 ? 1 : 0),
      completeManagers: summary.completeManagers + (managerSummary.totalFunds > 0 && managerSummary.checkedFunds === managerSummary.totalFunds && managerSummary.gapFunds === 0 ? 1 : 0),
      unknownManagers: summary.unknownManagers + (managerSummary.totalFunds > 0 && managerSummary.checkedFunds < managerSummary.totalFunds ? 1 : 0),
      gapFunds: summary.gapFunds + managerSummary.gapFunds,
      missingItems: summary.missingItems + managerSummary.missingItems,
      highPriority: summary.highPriority + managerSummary.highPriority,
    }
  }, {
    researchManagers: 0,
    gapManagers: 0,
    completeManagers: 0,
    unknownManagers: 0,
    gapFunds: 0,
    missingItems: 0,
    highPriority: 0,
  })
  const managerSalesRulePriorityQueue = managers
    .map((manager) => {
      const summary = getManagerSalesRuleSummary(manager)
      const currentCodes = getManagerResearchCodes(manager)
      const firstGap = [...summary.gaps].sort((left, right) => {
        const priorityWeight = { high: 3, medium: 2, low: 1 }
        return priorityWeight[right.priority] - priorityWeight[left.priority] || right.missingCount - left.missingCount
      })[0] || null
      return {
        manager,
        currentCodes,
        summary,
        firstGap,
        actionHref: buildManagerSalesRulesHref(manager),
        priorityScore: summary.highPriority * 100 + summary.gapFunds * 20 + summary.missingItems + Number(manager.managementYears || 0),
      }
    })
    .filter((item) => item.summary.gapFunds > 0)
    .sort((left, right) => right.priorityScore - left.priorityScore)
    .slice(0, 5)

  const managerEntryShortlist = managers
    .map((manager) => {
      const summary = getManagerSalesRuleSummary(manager)
      const currentCodes = getManagerResearchCodes(manager)
      const managementYears = Number(manager.managementYears || 0)
      const workYears = Number(manager.workYears || 0)
      const unknownFunds = Math.max(0, summary.totalFunds - summary.checkedFunds)
      const tenureScore = Math.min(25, managementYears * 4) + Math.min(10, workYears)
      const currentFundScore = Math.min(20, currentCodes.length * 4)
      const salesRuleScore = summary.totalFunds > 0 && summary.checkedFunds === summary.totalFunds && summary.gapFunds === 0
        ? 35
        : summary.gapFunds > 0
          ? Math.max(0, 18 - summary.highPriority * 6 - summary.missingItems * 2)
          : Math.max(0, 12 - unknownFunds * 4)
      const score = Math.max(0, Math.min(100, Math.round(tenureScore + currentFundScore + salesRuleScore)))
      const status = summary.totalFunds === 0 || managementYears < 1
        ? {
          label: '暂缓',
          className: 'border-slate-200 bg-slate-50 text-slate-700',
          reason: summary.totalFunds === 0 ? '无有效在管基金入口' : '经理任期证据偏薄',
          primaryAction: '先看履历，不进研究复核',
          actionHref: managerDetailHref(manager),
        }
        : summary.gapFunds > 0 || unknownFunds > 0
          ? {
            label: '先补规则',
            className: 'border-amber-200 bg-amber-50 text-amber-800',
            reason: summary.gapFunds > 0 ? `在管基金缺 ${summary.missingItems} 项销售规则证据` : `仍有 ${unknownFunds} 只在管基金未完成规则扫描`,
            primaryAction: '补规则后再横评',
            actionHref: buildManagerSalesRulesHref(manager),
          }
          : {
            label: '优先查看',
            className: 'border-emerald-200 bg-emerald-50 text-emerald-800',
            reason: '在管基金销售规则相对完整，可进入逐基金复核',
            primaryAction: '查看经理入口',
            actionHref: managerDetailHref(manager),
          }
      return {
        manager,
        currentCodes,
        summary,
        score,
        status,
        unknownFunds,
        managementYears,
      }
    })
    .sort((left, right) => {
      const statusWeight = { '优先查看': 3, '先补规则': 2, '暂缓': 1 }
      return statusWeight[right.status.label as keyof typeof statusWeight] - statusWeight[left.status.label as keyof typeof statusWeight]
        || right.score - left.score
        || right.currentCodes.length - left.currentCodes.length
    })
    .slice(0, 6)

  const managerEntryShortlistSummary = managerEntryShortlist.reduce((summary, item) => {
    if (item.status.label === '优先查看') summary.ready += 1
    if (item.status.label === '先补规则') summary.gap += 1
    if (item.status.label === '暂缓') summary.pause += 1
    return summary
  }, { ready: 0, gap: 0, pause: 0 })

  const managerProductEvidenceRows = managers.map((manager, index) => {
    const currentCodes = getManagerResearchCodes(manager)
    const summary = getManagerSalesRuleSummary(manager)
    const firstGap = [...summary.gaps].sort((left, right) => {
      const priorityWeight = { high: 3, medium: 2, low: 1 }
      return priorityWeight[right.priority] - priorityWeight[left.priority] || right.missingCount - left.missingCount
    })[0] || null
    const unknownFunds = Math.max(0, summary.totalFunds - summary.checkedFunds)
    const evidenceStatus = summary.totalFunds === 0
      ? '无有效在管基金入口'
      : summary.gapFunds > 0
        ? '产品证据阻断'
        : unknownFunds > 0
          ? '产品证据未完成扫描'
          : '产品证据可进入逐基金复核'
    const nextAction = summary.totalFunds === 0
      ? '只保留经理履历，不进入基金研究复核队列'
      : summary.gapFunds > 0
        ? '先补齐名下基金销售规则/R1-R5/申赎字段来源'
        : unknownFunds > 0
          ? '重扫名下在管基金销售规则和复查队列'
          : '进入逐只基金研究证据复核'
    return {
      序号: index + 1,
      经理: manager.name,
      公司: manager.company || '公司待补',
      管理年限: manager.managementYears ? `${Number(manager.managementYears).toFixed(1)} 年` : '待补',
      从业年限: manager.workYears ? `${Number(manager.workYears).toFixed(1)} 年` : '待补',
      在管基金数: currentCodes.length,
      已扫描基金数: summary.checkedFunds,
      待补基金数: summary.gapFunds,
      缺口项数: summary.missingItems,
      高优先级基金数: summary.highPriority,
      产品证据状态: evidenceStatus,
      首要缺口基金: firstGap?.windCode || '',
      首要缺口字段: firstGap?.missingItems.slice(0, 6).join('、') || '',
      R1R5来源状态: firstGap?.riskLevelEvidenceLabel || '',
      在管样本: currentCodes.slice(0, 8).join('、'),
      下一动作: nextAction,
      经理入口: managerDetailHref(manager),
      补证入口: buildManagerSalesRulesHref(manager),
      硬边界: '经理评价只服务基金筛选、基金分析和基金经理评价；不能替代逐只基金销售规则、R1-R5、计划金额和研究证据门禁。',
    }
  })

  const managerProductEvidenceSummary = managerProductEvidenceRows.reduce((summary, row) => ({
    currentFunds: summary.currentFunds + Number(row.在管基金数 || 0),
    checkedFunds: summary.checkedFunds + Number(row.已扫描基金数 || 0),
    blockedManagers: summary.blockedManagers + (row.产品证据状态 === '产品证据阻断' ? 1 : 0),
    unknownManagers: summary.unknownManagers + (row.产品证据状态 === '产品证据未完成扫描' ? 1 : 0),
    missingItems: summary.missingItems + Number(row.缺口项数 || 0),
  }), {
    currentFunds: 0,
    checkedFunds: 0,
    blockedManagers: 0,
    unknownManagers: 0,
    missingItems: 0,
  })
  const managerProductWorkOrderTsv = buildTsv(managerProductEvidenceRows)

  const downloadManagerProductWorkOrderTsv = () => {
    if (!managerProductWorkOrderTsv) return
    const blob = new Blob([managerProductWorkOrderTsv], { type: 'text/tab-separated-values;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `manager-product-evidence-work-order-${new Date().toISOString().slice(0, 10)}.tsv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const copyManagerProductWorkOrderTsv = async () => {
    if (!managerProductWorkOrderTsv) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(managerProductWorkOrderTsv)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = managerProductWorkOrderTsv
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.focus()
        textarea.select()
        const copied = document.execCommand('copy')
        textarea.remove()
        if (!copied) throw new Error('clipboard unavailable')
      }
      setManagerProductWorkOrderCopyStatus(`已复制 ${managerProductEvidenceRows.length} 位经理的产品证据工作单 TSV`)
    } catch {
      downloadManagerProductWorkOrderTsv()
      setManagerProductWorkOrderCopyStatus(`复制受限，已转下载 ${managerProductEvidenceRows.length} 位经理的产品证据工作单 TSV`)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    setAppliedSearch(searchText.trim())
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">基金经理</h1>
        <p className="mt-1 text-sm text-gray-500">
          基于本地 Tushare 基金经理任职记录，核查经理经验、任期和管理基金
        </p>
      </div>

      <div className="bg-white p-4 rounded-lg shadow space-y-4">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="搜索基金经理姓名..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            搜索
          </button>
        </form>
        <div className="grid grid-cols-1 gap-3 border-t border-slate-100 pt-4 md:grid-cols-4">
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

      {errorMessage ? (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4" />
          {errorMessage}
        </div>
      ) : null}

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">经理列表研究复核雷达</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              经理评价只负责缩小研究对象；当前按 {Number(normalizedPlannedAmount).toLocaleString('zh-CN')} 元计划金额扫描，名下基金材料核验未补齐前不能沉淀为研究候选。
            </p>
          </div>
          <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
            {salesRuleLoading ? '销售规则扫描中' : `当前页 ${pageSalesRuleSummary.researchManagers} 位经理有在管基金`}
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <div className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900">
            <div className="text-xs text-rose-700">待补经理</div>
            <div className="mt-1 text-2xl font-semibold">{salesRuleLoading ? '-' : pageSalesRuleSummary.gapManagers}</div>
            <div className="mt-1 text-xs">当前在管基金存在硬缺口</div>
          </div>
          <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
            <div className="text-xs text-amber-700">待补基金 / 项</div>
            <div className="mt-1 text-2xl font-semibold">{salesRuleLoading ? '-' : `${pageSalesRuleSummary.gapFunds}/${pageSalesRuleSummary.missingItems}`}</div>
            <div className="mt-1 text-xs">申购、费率、赎回、风险等级等</div>
          </div>
          <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">
            <div className="text-xs text-emerald-700">规则相对完整</div>
            <div className="mt-1 text-2xl font-semibold">{salesRuleLoading ? '-' : pageSalesRuleSummary.completeManagers}</div>
            <div className="mt-1 text-xs">仍需复核平台实时状态</div>
          </div>
          <div className="rounded-xl bg-slate-50 p-4 text-sm text-slate-900">
            <div className="text-xs text-slate-500">未完成扫描</div>
            <div className="mt-1 text-2xl font-semibold">{salesRuleLoading ? '-' : pageSalesRuleSummary.unknownManagers}</div>
            <div className="mt-1 text-xs">接口异常或当前页代码待补</div>
          </div>
        </div>
        {salesRuleError ? (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertCircle className="mt-0.5 h-4 w-4" />
            {salesRuleError}
          </div>
        ) : null}
        {!salesRuleLoading && pageSalesRuleSummary.gapManagers > 0 ? (
          <div className="mt-3 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-800">
            当前页有 {pageSalesRuleSummary.gapManagers} 位经理的当前在管基金未过销售规则硬门禁，共缺 {pageSalesRuleSummary.missingItems} 项；请先从行内“补规则”进入补证台，再做横评或研究复核报告。
          </div>
        ) : null}
        {!salesRuleLoading && managerSalesRulePriorityQueue.length ? (
          <div className="mt-4 rounded-2xl border border-violet-100 bg-violet-50 p-4" data-testid="manager-sales-rule-priority-queue">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-violet-950">经理研究补证优先队列</div>
                <p className="mt-1 text-xs leading-5 text-violet-800">
                  按在管基金硬缺口数量、高优先级和经理管理年限排序；经理只能作为研究入口，正式研究必须落到逐只基金规则。
                </p>
              </div>
              <Link href={managerSalesRulePriorityQueue[0].actionHref} className="shrink-0 rounded-lg bg-violet-700 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-800">
                先补首位经理规则
              </Link>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {managerSalesRulePriorityQueue.map((item, index) => (
                <Link key={`${item.manager.id}-${index}`} href={item.actionHref} className="rounded-xl border border-violet-100 bg-white px-3 py-2 text-xs text-slate-700 hover:bg-violet-50">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-slate-950">#{index + 1} {item.manager.name}</div>
                      <div className="mt-1 text-slate-500">{item.manager.company || '公司待补'} · 管理年限 {item.manager.managementYears ? `${Number(item.manager.managementYears).toFixed(1)} 年` : '待补'}</div>
                    </div>
                    <span className="rounded-full bg-violet-50 px-2 py-0.5 font-semibold text-violet-700">
                      待补 {item.summary.gapFunds} 只 / {item.summary.missingItems} 项
                    </span>
                  </div>
                  {item.firstGap ? (
                    <div className="mt-2 rounded-lg bg-rose-50 px-2 py-1.5 text-rose-800">
                      首要基金 {item.firstGap.windCode}：{item.firstGap.missingItems.slice(0, 4).join('、')}
                      {item.firstGap.riskLevelEvidenceLabel ? `；R1-R5来源：${item.firstGap.riskLevelEvidenceLabel}` : ''}
                    </div>
                  ) : null}
                  <div className="mt-2 text-slate-600">
                    在管样本 {item.currentCodes.slice(0, 4).join('、') || '待补'}{item.currentCodes.length > 4 ? ` 等 ${item.currentCodes.length} 只` : ''}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ) : null}
        {!salesRuleLoading && managers.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4" data-testid="manager-entry-shortlist-scorecard">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-950">经理入口短名单分</div>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  按管理年限、当前在管基金、材料核验完整度、高优先级缺口和计划金额口径排序；只决定研究入口，不给结论。
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-xl bg-emerald-100 px-3 py-2 text-emerald-800">
                  <div className="font-semibold">{managerEntryShortlistSummary.ready}</div>
                  <div>优先查看</div>
                </div>
                <div className="rounded-xl bg-amber-100 px-3 py-2 text-amber-800">
                  <div className="font-semibold">{managerEntryShortlistSummary.gap}</div>
                  <div>先补规则</div>
                </div>
                <div className="rounded-xl bg-slate-200 px-3 py-2 text-slate-700">
                  <div className="font-semibold">{managerEntryShortlistSummary.pause}</div>
                  <div>暂缓</div>
                </div>
              </div>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              {managerEntryShortlist.map((item, index) => (
                <Link key={`${item.manager.id}-entry-${index}`} href={item.status.actionHref} className={`rounded-xl border p-3 text-xs hover:shadow-sm ${item.status.className}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-slate-950">#{index + 1} {item.manager.name}</div>
                      <div className="mt-1 text-slate-500">{item.manager.company || '公司待补'} · 管理 {item.managementYears ? `${item.managementYears.toFixed(1)} 年` : '待补'}</div>
                    </div>
                    <span className="rounded-full bg-white/80 px-2 py-0.5 font-semibold">{item.score} 分</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span className="rounded-full bg-white/80 px-2 py-0.5 font-semibold">{item.status.label}</span>
                    <span className="rounded-full bg-white/80 px-2 py-0.5">在管 {item.currentCodes.length} 只</span>
                    {item.unknownFunds > 0 ? <span className="rounded-full bg-white/80 px-2 py-0.5">未扫 {item.unknownFunds} 只</span> : null}
                  </div>
                  <div className="mt-2 leading-5">{item.status.reason}</div>
                  <div className="mt-2 font-semibold text-slate-700">{item.status.primaryAction}</div>
                </Link>
              ))}
            </div>
            <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-600">
              硬边界：经理入口分只用于缩小研究范围，不能抵消逐只基金材料核验、R1-R5、计划金额和研究证据缺口。
            </div>
          </div>
        ) : null}
        {!salesRuleLoading && managers.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-cyan-100 bg-cyan-50 p-4" data-testid="manager-product-evidence-linkage-card">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-cyan-950">经理旗下基金质量带宽</div>
                <p className="mt-1 text-xs leading-5 text-cyan-800">
                  把经理评价和当前产品证据绑定：同一位经理名下任一基金存在销售规则、R1-R5、计划金额或申赎字段缺口时，只能进入补证队列，不能用经理履历给产品默认正向信用。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  data-testid="manager-product-evidence-copy"
                  onClick={() => void copyManagerProductWorkOrderTsv()}
                  className="rounded-lg border border-cyan-200 bg-white px-3 py-2 text-xs font-semibold text-cyan-800 hover:bg-cyan-100"
                >
                  复制产品证据 TSV
                </button>
                <button
                  type="button"
                  data-testid="manager-product-evidence-download"
                  onClick={downloadManagerProductWorkOrderTsv}
                  className="rounded-lg bg-cyan-700 px-3 py-2 text-xs font-semibold text-white hover:bg-cyan-800"
                >
                  下载产品证据 TSV
                </button>
              </div>
            </div>
            {managerProductWorkOrderCopyStatus ? (
              <div className="mt-3 rounded-lg border border-cyan-200 bg-white px-3 py-2 text-xs text-cyan-800">
                {managerProductWorkOrderCopyStatus}
              </div>
            ) : null}
            <div className="mt-3 grid gap-3 md:grid-cols-5">
              <div className="rounded-xl bg-white p-3 text-xs text-cyan-900">
                <div className="text-cyan-700">在管基金样本</div>
                <div className="mt-1 text-xl font-semibold">{managerProductEvidenceSummary.currentFunds}</div>
              </div>
              <div className="rounded-xl bg-white p-3 text-xs text-cyan-900">
                <div className="text-cyan-700">已扫描基金</div>
                <div className="mt-1 text-xl font-semibold">{managerProductEvidenceSummary.checkedFunds}</div>
              </div>
              <div className="rounded-xl bg-white p-3 text-xs text-rose-900">
                <div className="text-rose-700">产品阻断经理</div>
                <div className="mt-1 text-xl font-semibold">{managerProductEvidenceSummary.blockedManagers}</div>
              </div>
              <div className="rounded-xl bg-white p-3 text-xs text-amber-900">
                <div className="text-amber-700">扫描未完经理</div>
                <div className="mt-1 text-xl font-semibold">{managerProductEvidenceSummary.unknownManagers}</div>
              </div>
              <div className="rounded-xl bg-white p-3 text-xs text-slate-900">
                <div className="text-slate-500">缺口项合计</div>
                <div className="mt-1 text-xl font-semibold">{managerProductEvidenceSummary.missingItems}</div>
              </div>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {managerProductEvidenceRows.slice(0, 4).map((row) => (
                <div key={`${row.经理}-${row.序号}`} className="rounded-xl border border-cyan-100 bg-white px-3 py-2 text-xs text-slate-700">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-slate-950">{row.经理}</div>
                      <div className="mt-1 text-slate-500">{row.公司} · 管理年限 {row.管理年限}</div>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 font-semibold ${row.产品证据状态 === '产品证据阻断' ? 'bg-rose-50 text-rose-700' : row.产品证据状态 === '产品证据未完成扫描' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>
                      {row.产品证据状态}
                    </span>
                  </div>
                  <div className="mt-2 leading-5">
                    在管 {row.在管基金数} 只，已扫 {row.已扫描基金数} 只，待补 {row.待补基金数} 只 / {row.缺口项数} 项。
                    {row.首要缺口基金 ? ` 首要缺口 ${row.首要缺口基金}：${row.首要缺口字段}` : ''}
                  </div>
                  <div className="mt-2 text-slate-500">下一动作：{row.下一动作}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 rounded-xl border border-cyan-100 bg-white px-3 py-2 text-xs leading-5 text-cyan-800">
              工作单只服务基金研究证据修复；Tushare 基金经理履历不能作为 R1-R5 或申赎字段来源，经理维度不能越过逐只基金门禁。
            </div>
          </div>
        ) : null}
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : managers.length === 0 ? (
          <div className="p-8 text-center text-gray-500">暂无数据</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      姓名
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      公司
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      学历
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      从业年限
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      管理年限
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      管理基金数
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      研究规则状态
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {managers.map((manager) => {
                    const currentCodes = getManagerResearchCodes(manager)
                    const salesRuleSummary = getManagerSalesRuleSummary(manager)
                    const salesRulesHref = buildManagerSalesRulesHref(manager)
                    const salesRuleStatus = salesRuleLoading
                      ? { label: '扫描中', className: 'bg-slate-100 text-slate-600', helper: '正在读取名下基金销售规则' }
                      : salesRuleSummary.totalFunds === 0
                        ? { label: '无在管基金', className: 'bg-slate-100 text-slate-600', helper: '仅作经理履历参考，不作为基金研究入口' }
                        : salesRuleSummary.gapFunds > 0
                          ? { label: `在管待补 ${salesRuleSummary.gapFunds} 只`, className: 'bg-rose-50 text-rose-700', helper: `共缺 ${salesRuleSummary.missingItems} 项，高优先级 ${salesRuleSummary.highPriority} 只` }
                          : salesRuleSummary.checkedFunds === salesRuleSummary.totalFunds
                            ? { label: '在管规则相对完整', className: 'bg-emerald-50 text-emerald-700', helper: '可进入具体基金研究复核' }
                            : { label: '待扫描', className: 'bg-amber-50 text-amber-700', helper: '销售规则扫描未完成' }
                    return (
                    <tr key={manager.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {manager.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {manager.company || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {manager.education || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {manager.workYears ? `${manager.workYears} 年` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {manager.managementYears ? `${Number(manager.managementYears).toFixed(1)} 年` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <div>{manager.fundCount ?? manager.currentFunds.length}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          在管 {currentCodes.length} / 历史 {Math.max(0, (manager.fundCount ?? manager.currentFunds.length) - currentCodes.length)}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        <div className="min-w-44">
                          <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${salesRuleStatus.className}`}>
                            {salesRuleStatus.label}
                          </span>
                          <div className="mt-1 text-xs text-slate-500">{salesRuleStatus.helper}</div>
                          {salesRuleSummary.gaps[0] ? (
                            <div className="mt-1 text-xs text-rose-600">
                              {salesRuleSummary.gaps[0].windCode}：{salesRuleSummary.gaps[0].missingItems.slice(0, 2).join('、')}
                            </div>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex flex-col gap-2">
                          <Link
                            href={managerDetailHref(manager)}
                            className="text-blue-600 hover:text-blue-800"
                          >
                            查看详情
                          </Link>
                          {currentCodes.length > 0 ? (
                            <Link href={salesRulesHref} className="text-amber-700 hover:text-amber-900">
                              {salesRuleSummary.gapFunds > 0 ? '补规则' : '查规则'}
                            </Link>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200">
              <div className="flex-1 flex justify-between sm:hidden">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                >
                  上一页
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                >
                  下一页
                </button>
              </div>
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-gray-700">
                    第 <span className="font-medium">{page}</span> 页，共{' '}
                    <span className="font-medium">{totalPages}</span> 页
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="relative inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="relative inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
