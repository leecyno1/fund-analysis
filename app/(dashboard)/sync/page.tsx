'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { RefreshCw, Database, CheckCircle, AlertCircle, Clock, FileText } from 'lucide-react'
import { materialEvidenceHref } from '@/lib/research-platform/routes'

interface SyncStatus {
  status: string
  dataSource: string
  mockMode: boolean
  counts: {
    funds: number
    managers: number
  }
  lastSync: {
    funds: string | null
    managers: string | null
  }
  backendServiceUrl: string
}

interface SyncResult {
  success: boolean
  message: string
  results: {
    funds: { created: number; updated: number; errors: number }
    managers: { created: number; updated: number; errors: number }
    details: Array<{
      code?: string
      name?: string
      action: string
      error?: string
      reason?: string
      managerCount?: number
      managerTenureStart?: string | null
      rollingMetrics?: {
        saved?: number
        windows?: string[]
      } | null
      tenureMetrics?: {
        saved?: number
        window?: string
      } | null
      warnings?: string[]
    }>
  }
  timestamp: string
}

interface RealDataReportResult {
  success: boolean
  source: string
  dataSource: string
  mockMode: boolean
  purchasePlan?: PurchasePlan
  plannedAmount?: number | null
  total: number
  savedCount: number
  failedCount: number
  results: Array<{
    ok: boolean
    windCode: string
    purchasePlan?: PurchasePlan
    plannedAmount?: number | null
    error?: string
    reportHref?: string
    sync?: {
      managerCount: number
      managerIds: string[]
      warnings: string[]
    }
    report?: {
      id: string
      mode: string
      provider: string
      model: string
      wordCount: number
      isModelGenerated: boolean
      purchasePlan?: PurchasePlan
      plannedAmount?: number | null
      generationLabel: string
    }
    currentSalesRuleGate?: {
      status: 'ready' | 'blocked'
      missingCount: number
      missingItems: string[]
      actionHref: string
      nextAction: string
      source: string
    }
    buyBeforeAction?: {
      status: string
      label: string
      href: string
      detail: string
    }
  }>
  timestamp: string
}

type PurchasePlan = 'lump_sum' | 'sip'

const purchasePlanLabels: Record<PurchasePlan, string> = {
  lump_sum: '一次性配置',
  sip: '定投',
}

function defaultPlannedAmountForPlan(purchasePlan: PurchasePlan) {
  return purchasePlan === 'lump_sum' ? 10000 : 1000
}

function normalizePlannedAmountInput(value: unknown, purchasePlan: PurchasePlan) {
  const amount = Number(value)
  return Number.isFinite(amount) && amount > 0
    ? String(Math.round(amount))
    : String(defaultPlannedAmountForPlan(purchasePlan))
}

export default function SyncPage() {
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [reporting, setReporting] = useState(false)
  const [lastResult, setLastResult] = useState<SyncResult | null>(null)
  const [lastReportResult, setLastReportResult] = useState<RealDataReportResult | null>(null)
  const [codeInput, setCodeInput] = useState('')
  const [purchasePlan, setPurchasePlan] = useState<PurchasePlan>('sip')
  const [plannedAmount, setPlannedAmount] = useState('1000')

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/sync/wind')
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('获取同步状态失败:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timeout = globalThis.setTimeout(() => {
      void fetchStatus()
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [fetchStatus])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const queryCodes = params.get('codes')
    const queryPurchasePlan = params.get('purchasePlan')
    const nextPurchasePlan = queryPurchasePlan === 'lump_sum' || queryPurchasePlan === 'sip' ? queryPurchasePlan : 'sip'
    if (queryCodes) setCodeInput(queryCodes)
    setPurchasePlan(nextPurchasePlan)
    setPlannedAmount(normalizePlannedAmountInput(
      params.get('plannedAmount') || params.get(nextPurchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount'),
      nextPurchasePlan,
    ))
  }, [])

  const currentPlannedAmount = () => Number(normalizePlannedAmountInput(plannedAmount, purchasePlan))

  const purchaseContextParams = (codes: string[] = []) => {
    const amount = String(currentPlannedAmount())
    const params = new URLSearchParams({
      purchasePlan,
      plannedAmount: amount,
      [purchasePlan === 'lump_sum' ? 'lumpSumAmount' : 'monthlyAmount']: amount,
    })
    if (codes.length) params.set('codes', codes.join(','))
    return params.toString()
  }

  const applyPurchasePlan = (nextPlan: PurchasePlan) => {
    const oldDefault = String(defaultPlannedAmountForPlan(purchasePlan))
    const shouldResetAmount = !plannedAmount.trim() || plannedAmount.trim() === oldDefault
    setPurchasePlan(nextPlan)
    if (shouldResetAmount) setPlannedAmount(String(defaultPlannedAmountForPlan(nextPlan)))
  }

  const parseFundCodes = () => Array.from(new Set(
    codeInput
      .split(/[\s,，;；]+/u)
      .map((code) => code.trim().toUpperCase())
      .filter((code) => /^[0-9A-Z]{6,12}\.(OF|SH|SZ|BJ)$/i.test(code)),
  )).slice(0, 50)

  const parsedFundCodes = parseFundCodes()
  const invalidCodeCount = codeInput.trim()
    ? codeInput.split(/[\s,，;；]+/u).map((code) => code.trim()).filter(Boolean).length - parsedFundCodes.length
    : 0
  const salesRulesHref = materialEvidenceHref(new URLSearchParams(purchaseContextParams(parsedFundCodes)))

  const handleSync = async (type: 'fund' | 'manager' | 'all', codes?: string[]) => {
    setSyncing(true)
    setLastResult(null)

    try {
      const response = await fetch('/api/sync/wind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, codes: codes?.length ? codes : undefined, force: false })
      })

      const result = await response.json()
      if (!response.ok) {
        throw new Error(result.details || result.error || '同步失败')
      }
      setLastResult(result)

      if (result.success) {
        await fetchStatus()
      }
    } catch (error) {
      console.error('同步失败:', error)
      setLastResult({
        success: false,
        message: '同步失败',
        results: {
          funds: { created: 0, updated: 0, errors: 0 },
          managers: { created: 0, updated: 0, errors: 0 },
          details: [{
            action: 'error',
            error: error instanceof Error ? error.message : '未知错误',
          }]
        },
        timestamp: new Date().toISOString()
      })
    } finally {
      setSyncing(false)
    }
  }

  const handleRealDataReports = async () => {
    setReporting(true)
    setLastReportResult(null)

    try {
      const response = await fetch('/api/reports/real-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          codes: parsedFundCodes,
          includeResearch: false,
          reportDepth: 'standard',
          purchasePlan,
          plannedAmount: currentPlannedAmount(),
        }),
      })
      const result = await response.json()
      setLastReportResult({
        success: Boolean(result.success),
        source: result.source || 'tushare_to_postgres_to_local_fund_report',
        dataSource: result.dataSource || 'unknown',
        mockMode: Boolean(result.mockMode),
        purchasePlan: result.purchasePlan === 'lump_sum' ? 'lump_sum' : 'sip',
        plannedAmount: Number.isFinite(Number(result.plannedAmount)) && Number(result.plannedAmount) > 0 ? Number(result.plannedAmount) : currentPlannedAmount(),
        total: Number(result.total || 0),
        savedCount: Number(result.savedCount || 0),
        failedCount: Number(result.failedCount || 0),
        results: Array.isArray(result.results) ? result.results : [],
        timestamp: result.timestamp || new Date().toISOString(),
      })
      await fetchStatus()
    } catch (error) {
      console.error('真实研究报告生成失败:', error)
      setLastReportResult({
        success: false,
        source: 'tushare_to_postgres_to_local_fund_report',
        dataSource: 'unknown',
        mockMode: false,
        purchasePlan,
        plannedAmount: currentPlannedAmount(),
        total: parsedFundCodes.length,
        savedCount: 0,
        failedCount: parsedFundCodes.length,
        results: parsedFundCodes.map((windCode) => ({
          ok: false,
          windCode,
          error: error instanceof Error ? error.message : '真实研究报告生成失败',
        })),
        timestamp: new Date().toISOString(),
      })
    } finally {
      setReporting(false)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '从未同步'
    return new Date(dateString).toLocaleString('zh-CN')
  }

  const realDataReportGateSummary = lastReportResult ? (() => {
    const readyItems = lastReportResult.results.filter((item) => item.ok && item.currentSalesRuleGate?.status === 'ready')
    const blockedItems = lastReportResult.results.filter((item) => item.ok && item.currentSalesRuleGate?.status === 'blocked')
    const failedItems = lastReportResult.results.filter((item) => !item.ok)
    const blockedCodes = blockedItems.map((item) => item.windCode).filter(Boolean)
    return {
      readyItems,
      blockedItems,
      failedItems,
      blockedCodes,
      blockedSalesRulesHref: materialEvidenceHref(new URLSearchParams(purchaseContextParams(blockedCodes))),
      reportsHref: '/reports?reportType=fund_research_report',
      primaryLabel: readyItems.length
        ? '继续研究复核'
        : blockedItems.length
          ? '先补销售规则'
          : failedItems.length
            ? '查看失败原因'
            : '查看报告',
      primaryHref: readyItems[0]?.buyBeforeAction?.href
        || (blockedCodes.length ? materialEvidenceHref(new URLSearchParams(purchaseContextParams(blockedCodes))) : '/reports?reportType=fund_research_report'),
      detail: readyItems.length
        ? `${readyItems.length} 份报告未检测到销售规则硬缺口；仍需进入详情页复核净值回放、费用、持仓和替代候选。`
        : blockedItems.length
          ? `${blockedItems.length} 份报告已保存但销售规则仍待补；补齐前只能作为研究观察，不能作为正式研究结论。`
          : failedItems.length
            ? `${failedItems.length} 只基金真实报告未生成成功；请先查看错误或重跑同步。`
            : '当前没有可用报告结果。',
    }
  })() : null

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">数据同步</h1>
        <p className="mt-1 text-sm text-gray-500">
          管理 Tushare → FastAPI → PostgreSQL 的真实基金数据同步
        </p>
      </div>

      {/* 同步状态 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">当前状态</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <Database className="w-5 h-5 text-blue-600 mr-2" />
              <span className="text-sm text-gray-500">数据库基金数</span>
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-2">
              {status?.counts.funds || 0}
            </p>
          </div>

          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <Database className="w-5 h-5 text-green-600 mr-2" />
              <span className="text-sm text-gray-500">数据库经理数</span>
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-2">
              {status?.counts.managers || 0}
            </p>
          </div>

          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <Clock className="w-5 h-5 text-purple-600 mr-2" />
              <span className="text-sm text-gray-500">基金最后同步</span>
            </div>
            <p className="text-sm text-gray-900 mt-2">
              {formatDate(status?.lastSync.funds || null)}
            </p>
          </div>

          <div className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <Clock className="w-5 h-5 text-orange-600 mr-2" />
              <span className="text-sm text-gray-500">经理最后同步</span>
            </div>
            <p className="text-sm text-gray-900 mt-2">
              {formatDate(status?.lastSync.managers || null)}
            </p>
          </div>
        </div>

        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-600">
            <span className="font-medium">后端服务地址: </span>
            <code className="bg-white px-2 py-1 rounded border">
              {status?.backendServiceUrl || '未配置'}
            </code>
          </p>
          <p className="mt-2 text-sm text-gray-600">
            <span className="font-medium">数据源: </span>
            {status?.dataSource || 'tushare'}
            {status?.mockMode ? '（Mock 模式，请检查 TUSHARE_TOKEN）' : '（真实 API 模式）'}
          </p>
        </div>
      </div>

      {/* 同步操作 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">同步操作</h2>
        <div className="mb-5 rounded-2xl border border-blue-100 bg-blue-50 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-blue-950">指定基金精同步</h3>
              <p className="mt-1 text-xs leading-5 text-blue-800">
                粘贴基金代码后，只同步这些基金的基础信息、净值、风险、经理关系；适合先补筛选结果或销售规则缺口样本。
              </p>
            </div>
            <label className="text-xs font-medium text-blue-900">
              研究口径
              <select
                value={purchasePlan}
                onChange={(event) => applyPurchasePlan(event.target.value as PurchasePlan)}
                className="mt-1 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-slate-900"
              >
                <option value="sip">{purchasePlanLabels.sip}</option>
                <option value="lump_sum">{purchasePlanLabels.lump_sum}</option>
              </select>
            </label>
            <label className="text-xs font-medium text-blue-900">
              计划金额
              <input
                type="number"
                min={1}
                step={1}
                value={plannedAmount}
                onChange={(event) => setPlannedAmount(event.target.value)}
                className="mt-1 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-slate-900"
              />
            </label>
            <div className="flex flex-wrap gap-2 text-xs">
              <button
                type="button"
                onClick={() => setCodeInput('020001.OF,202001.OF,040001.OF,320007.OF')}
                className="rounded-lg bg-white px-3 py-2 font-medium text-blue-700 ring-1 ring-blue-100 hover:bg-blue-100"
              >
                填入常用验收样本
              </button>
              <Link href={salesRulesHref} className="rounded-lg bg-white px-3 py-2 font-medium text-blue-700 ring-1 ring-blue-100 hover:bg-blue-100">
                去补这些销售规则
              </Link>
            </div>
          </div>
          <textarea
            value={codeInput}
            onChange={(event) => setCodeInput(event.target.value)}
            placeholder="例如：020001.OF, 202001.OF, 320007.OF"
            className="mt-3 h-24 w-full rounded-xl border border-blue-100 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:ring-2 focus:ring-blue-400"
          />
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-blue-800">
            <span>已识别 {parsedFundCodes.length} 只基金{invalidCodeCount > 0 ? `，忽略 ${invalidCodeCount} 个重复/无效代码` : ''}</span>
            {parsedFundCodes.length ? <span className="font-mono">{parsedFundCodes.slice(0, 8).join(' / ')}{parsedFundCodes.length > 8 ? ' / ...' : ''}</span> : null}
          </div>
          <div className="mt-3 flex flex-wrap gap-3">
            <button
              onClick={() => handleSync('fund', parsedFundCodes)}
              disabled={syncing || reporting || parsedFundCodes.length === 0}
              className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
              同步指定基金
            </button>
            <button
              onClick={handleRealDataReports}
              disabled={syncing || reporting || parsedFundCodes.length === 0}
              className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FileText className={`mr-2 h-4 w-4 ${reporting ? 'animate-pulse' : ''}`} />
              拉取真实数据并生成报告
            </button>
            <Link
              href="/reports?reportType=fund_research_report"
              className="inline-flex items-center justify-center rounded-lg border border-emerald-200 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50"
            >
              查看本地研究报告
            </Link>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => handleSync('fund')}
            disabled={syncing}
            className="flex items-center justify-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            同步基金数据
          </button>

          <button
            onClick={() => handleSync('manager')}
            disabled={syncing}
            className="flex items-center justify-center px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            同步经理数据
          </button>

          <button
            onClick={() => handleSync('all')}
            disabled={syncing}
            className="flex items-center justify-center px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? 'animate-spin' : ''}`} />
            全部同步
          </button>
        </div>
      </div>

      {/* 同步结果 */}
      {lastResult && (
        <div className={`bg-white rounded-lg shadow p-6 border-l-4 ${
          lastResult.success ? 'border-green-500' : 'border-red-500'
        }`}>
          <div className="flex items-center mb-4">
            {lastResult.success ? (
              <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
            )}
            <h2 className="text-lg font-semibold text-gray-900">同步结果</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">基金同步</h3>
              <div className="space-y-1 text-sm">
                <p className="text-green-600">
                  创建: {lastResult.results.funds.created}
                </p>
                <p className="text-blue-600">
                  更新: {lastResult.results.funds.updated}
                </p>
                <p className="text-red-600">
                  失败: {lastResult.results.funds.errors}
                </p>
              </div>
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">经理同步</h3>
              <div className="space-y-1 text-sm">
                <p className="text-green-600">
                  创建: {lastResult.results.managers.created}
                </p>
                <p className="text-blue-600">
                  更新: {lastResult.results.managers.updated}
                </p>
                <p className="text-red-600">
                  失败: {lastResult.results.managers.errors}
                </p>
              </div>
            </div>
          </div>

          {/* 同步详情 */}
          {lastResult.results.details.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">同步详情</h3>
              <div className="max-h-60 overflow-y-auto">
                <div className="space-y-2">
                  {lastResult.results.details.map((detail, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between text-sm border-b border-gray-100 pb-2"
                    >
                      <span className="text-gray-600">
                        {detail.code || detail.name}
                      </span>
                      <div className="flex flex-col items-end gap-1">
                        <span className={`px-2 py-1 rounded text-xs ${
                          detail.action === 'created' ? 'bg-green-100 text-green-800' :
                          detail.action === 'updated' ? 'bg-blue-100 text-blue-800' :
                          detail.action === 'skipped' ? 'bg-gray-100 text-gray-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {detail.action === 'created' ? '创建' :
                           detail.action === 'updated' ? '更新' :
                           detail.action === 'skipped' ? '跳过' :
                           detail.action === 'error' ? '失败' : detail.action}
                        </span>
                        {typeof detail.managerCount === 'number' ? (
                          <span className="text-xs text-gray-400">现任经理 {detail.managerCount} 位</span>
                        ) : null}
                        {detail.managerTenureStart ? (
                          <span className="text-xs text-slate-500">任期起点 {detail.managerTenureStart}</span>
                        ) : null}
                        {detail.rollingMetrics ? (
                          <span className={`text-xs ${Number(detail.rollingMetrics.saved || 0) > 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                            滚动指标补证 {detail.rollingMetrics.saved || 0} 条{detail.rollingMetrics.windows?.length ? ` · ${detail.rollingMetrics.windows.join('/')}` : ''}
                          </span>
                        ) : null}
                        {detail.tenureMetrics ? (
                          <span className={`text-xs ${Number(detail.tenureMetrics.saved || 0) > 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                            经理任期切片 {detail.tenureMetrics.saved || 0} 条
                          </span>
                        ) : null}
                        {detail.error ? <span className="max-w-sm text-right text-xs text-red-500">{detail.error}</span> : null}
                        {detail.warnings?.length ? <span className="max-w-sm text-right text-xs text-amber-600">{detail.warnings.slice(0, 2).join('；')}</span> : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <p className="text-xs text-gray-400 mt-4">
            同步时间: {new Date(lastResult.timestamp).toLocaleString('zh-CN')}
          </p>
        </div>
      )}

      {lastReportResult && (
        <div className={`rounded-lg bg-white p-6 shadow border-l-4 ${
          lastReportResult.success ? 'border-emerald-500' : 'border-amber-500'
        }`}>
          <div className="mb-4 flex items-center">
            {lastReportResult.success ? (
              <CheckCircle className="mr-2 h-5 w-5 text-emerald-600" />
            ) : (
              <AlertCircle className="mr-2 h-5 w-5 text-amber-600" />
            )}
            <div>
              <h2 className="text-lg font-semibold text-gray-900">真实数据研究报告结果</h2>
              <div className="mt-1 text-xs text-gray-500">
                研究口径：{purchasePlanLabels[lastReportResult.purchasePlan || 'sip']} · 计划金额 {Number(lastReportResult.plannedAmount || 0).toLocaleString('zh-CN')} 元
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-gray-200 p-4">
              <div className="text-sm text-gray-500">数据源</div>
              <div className="mt-1 text-lg font-semibold text-gray-900">
                {lastReportResult.dataSource}{lastReportResult.mockMode ? ' · Mock' : ' · 真实'}
              </div>
            </div>
            <div className="rounded-lg border border-gray-200 p-4">
              <div className="text-sm text-gray-500">已保存报告</div>
              <div className="mt-1 text-lg font-semibold text-emerald-700">{lastReportResult.savedCount}</div>
            </div>
            <div className="rounded-lg border border-gray-200 p-4">
              <div className="text-sm text-gray-500">失败</div>
              <div className="mt-1 text-lg font-semibold text-amber-700">{lastReportResult.failedCount}</div>
            </div>
            <div className="rounded-lg border border-gray-200 p-4">
              <div className="text-sm text-gray-500">生成时间</div>
              <div className="mt-1 text-sm font-medium text-gray-900">{new Date(lastReportResult.timestamp).toLocaleString('zh-CN')}</div>
            </div>
          </div>

          {realDataReportGateSummary ? (
            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4" data-testid="real-data-report-buy-before-summary">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">真实报告研究门禁汇总</div>
                  <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-600">
                    {realDataReportGateSummary.detail} 同步和报告保存不等于正式研究结论；销售规则、R1-R5 来源、费用、赎回、限购和计划金额门禁仍是正式路径硬条件。
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-emerald-100 px-2.5 py-1 font-semibold text-emerald-800">
                      可继续复核 {realDataReportGateSummary.readyItems.length}
                    </span>
                    <span className="rounded-full bg-amber-100 px-2.5 py-1 font-semibold text-amber-800">
                      规则待补 {realDataReportGateSummary.blockedItems.length}
                    </span>
                    <span className="rounded-full bg-rose-100 px-2.5 py-1 font-semibold text-rose-800">
                      生成失败 {realDataReportGateSummary.failedItems.length}
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Link href={realDataReportGateSummary.primaryHref} className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">
                    {realDataReportGateSummary.primaryLabel}
                  </Link>
                  {realDataReportGateSummary.blockedCodes.length ? (
                    <Link href={realDataReportGateSummary.blockedSalesRulesHref} className="rounded-lg bg-white px-3 py-2 text-xs font-semibold text-amber-800 ring-1 ring-amber-200 hover:bg-amber-50">
                      批量补规则（{realDataReportGateSummary.blockedCodes.length}）
                    </Link>
                  ) : null}
                  <Link href={realDataReportGateSummary.reportsHref} className="rounded-lg bg-white px-3 py-2 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50">
                    查看报告库
                  </Link>
                </div>
              </div>
            </div>
          ) : null}

          <div className="mt-4 space-y-2">
            {lastReportResult.results.map((item) => (
              <div key={item.windCode} className="flex flex-col gap-2 rounded-xl border border-gray-100 p-3 text-sm md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="font-semibold text-gray-900">{item.windCode}</div>
                    {item.currentSalesRuleGate?.status === 'blocked' ? (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                        销售规则待补，仅研究观察
                      </span>
                    ) : item.currentSalesRuleGate?.status === 'ready' ? (
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                        门禁未见硬缺口
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    {item.ok
                      ? `经理 ${item.sync?.managerCount ?? 0} 位 · ${item.report?.generationLabel || item.report?.mode || 'report'} · ${item.report?.wordCount || 0} 字符 · 计划金额 ${(item.plannedAmount || item.report?.plannedAmount || lastReportResult.plannedAmount || 0).toLocaleString('zh-CN')} 元`
                      : item.error || '生成失败'}
                  </div>
                  {item.ok && item.report && !item.report.isModelGenerated ? (
                    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700" data-testid="real-data-report-generation-mode">
                      当前是本地证据报告：已使用 Tushare 入库数据生成并保存；模型 Key 未进入后端运行环境或模型调用不可用时不会冒充 DeepSeek 结论。
                    </div>
                  ) : item.ok && item.report?.isModelGenerated ? (
                    <div className="mt-2 rounded-lg border border-violet-100 bg-violet-50 px-3 py-2 text-xs leading-5 text-violet-800" data-testid="real-data-report-generation-mode">
                      模型增强报告：{item.report.provider || 'LLM'} · {item.report.model || 'configured model'}。
                    </div>
                  ) : null}
                  {item.currentSalesRuleGate?.status === 'blocked' ? (
                    <div className="mt-2 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800" data-testid="real-data-report-sales-rule-gate">
                      <div className="font-semibold">
                        报告已保存，但不能作为正式研究结论：仍缺 {item.currentSalesRuleGate.missingCount} 项销售规则。
                      </div>
                      <div>
                        缺口：{item.currentSalesRuleGate.missingItems.slice(0, 6).join('、') || '销售平台关键字段待补'}。
                      </div>
                    </div>
                  ) : null}
                  {item.buyBeforeAction ? (
                    <div className="mt-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900" data-testid="real-data-report-buy-before-action">
                      <div className="font-semibold">研究下一步：{item.buyBeforeAction.status}</div>
                      <div>{item.buyBeforeAction.detail}</div>
                    </div>
                  ) : null}
                  {item.sync?.warnings?.length ? (
                    <div className="mt-1 text-xs text-amber-600">{item.sync.warnings.slice(0, 2).join('；')}</div>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.reportHref ? (
                    <Link
                      href={item.reportHref}
                      className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-700"
                    >
                      打开报告
                    </Link>
                  ) : null}
                  <Link
                    href={`/funds/${encodeURIComponent(item.windCode)}?profile=balanced&horizon=1to3y&${purchaseContextParams()}`}
                    className="rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    基金详情
                  </Link>
                  {item.buyBeforeAction ? (
                    <Link
                      href={item.buyBeforeAction.href}
                      className="rounded-lg border border-blue-200 px-3 py-2 text-xs font-medium text-blue-700 hover:bg-blue-50"
                    >
                      {item.buyBeforeAction.label}
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
