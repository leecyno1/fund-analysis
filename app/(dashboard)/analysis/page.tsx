'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { Sparkles, TrendingUp, Users, GitCompare, Clock, FileText, BrainCircuit, Search } from 'lucide-react'

interface AnalysisReport {
  id: string
  reportType: string
  rawReportType?: string
  targetType: string
  targetId: string
  compareId: string | null
  content: string
  metadata?: {
    dataSource?: string | null
    mode?: string | null
    model?: string | null
    provider?: string | null
  } | null
  riskLevelGatePolicy?: {
    status: string
    label: string
    detail: string
    tone: 'emerald' | 'amber' | 'slate'
    requiresRegeneration: boolean
    effectiveDate: string
  }
  createdAt: string
}

const reportTypeFilters = [
  { value: 'all', label: '全部报告' },
  { value: 'fund_pool_shortlist_report', label: '研究短名单' },
  { value: 'fund_pre_purchase_check', label: '研究复核' },
  { value: 'fund_comparison_report', label: '横向比较' },
  { value: 'fund_research_report', label: '基金研究' },
]

const reportModeLabel = (report: AnalysisReport) => {
  if (report.metadata?.mode === 'deterministic_fund_comparison') return '横向比较报告'
  if (report.metadata?.mode === 'deterministic_fund_pool_shortlist') return '研究短名单报告'
  if (report.metadata?.mode === 'deterministic_pre_purchase_check') return '研究复核报告'
  if (report.metadata?.mode === 'deterministic_evidence_backed') return '本地证据报告'
  if (report.metadata?.mode === 'llm') return '模型增强报告'
  return '研究报告'
}

const reportModeClassName = (report: AnalysisReport) => {
  if (report.metadata?.mode === 'deterministic_fund_comparison') return 'bg-purple-100 text-purple-800'
  if (report.metadata?.mode === 'deterministic_fund_pool_shortlist') return 'bg-emerald-100 text-emerald-800'
  if (report.metadata?.mode === 'deterministic_pre_purchase_check') return 'bg-amber-100 text-amber-800'
  if (report.metadata?.mode === 'deterministic_evidence_backed') return 'bg-emerald-100 text-emerald-800'
  if (report.metadata?.mode === 'llm') return 'bg-blue-100 text-blue-800'
  return 'bg-gray-100 text-gray-700'
}

const reportSourceLabel = (report: AnalysisReport) => {
  if (report.metadata?.mode === 'deterministic_fund_comparison') return '本地横向比较'
  if (report.metadata?.mode === 'deterministic_fund_pool_shortlist') return '本地短名单核查'
  if (report.metadata?.mode === 'deterministic_pre_purchase_check') return '本地研究复核'
  const source = report.metadata?.dataSource
  if (source === 'tushare') return 'Tushare → PostgreSQL'
  if (source) return source
  return '本地数据库'
}

const riskLevelPolicyBadgeClass = (tone: NonNullable<AnalysisReport['riskLevelGatePolicy']>['tone']) => {
  if (tone === 'emerald') return 'bg-emerald-100 text-emerald-800'
  if (tone === 'amber') return 'bg-amber-100 text-amber-800'
  return 'bg-slate-100 text-slate-700'
}

export default function AnalysisPage() {
  const [reports, setReports] = useState<AnalysisReport[]>([])
  const [loading, setLoading] = useState(true)
  const [reportType, setReportType] = useState('all')
  const [searchInput, setSearchInput] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')

  const fetchReports = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '20' })
      if (reportType !== 'all') params.set('reportType', reportType)
      if (appliedSearch.trim()) params.set('search', appliedSearch.trim())
      const response = await fetch(`/api/analysis?${params.toString()}`)
      const data = await response.json()
      setReports(data.data || [])
    } catch (error) {
      console.error('获取分析报告列表失败:', error)
    } finally {
      setLoading(false)
    }
  }, [appliedSearch, reportType])

  useEffect(() => {
    const timeout = globalThis.setTimeout(() => {
      void fetchReports()
    }, 0)
    return () => globalThis.clearTimeout(timeout)
  }, [fetchReports])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">基金研究</h1>
        <p className="mt-1 text-sm text-gray-500">
          读取本地 PostgreSQL 的真实基金数据，生成基金、基金经理和同类对比的研究备忘录
        </p>
      </div>

      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-900">
        <div className="font-semibold">真实数据链路已接入</div>
        <div className="mt-1 leading-6">
          报告列表来自本地 PostgreSQL 的 `ai_analysis_reports`，基金基础、申赎状态、费率和净值绩效字段来自 Tushare 入库结果；页面不展示演示报告。
        </div>
      </div>

      {/* 分析类型卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Link href="/analysis/fund">
          <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow cursor-pointer border-2 border-transparent hover:border-blue-500">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <TrendingUp className="w-6 h-6 text-blue-600" />
              </div>
              <Sparkles className="w-5 h-5 text-blue-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">基金分析</h3>
            <p className="text-sm text-gray-500">
              深度分析基金业绩、风险指标和投资策略
            </p>
          </div>
        </Link>

        <Link href="/analysis/manager">
          <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow cursor-pointer border-2 border-transparent hover:border-green-500">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <Users className="w-6 h-6 text-green-600" />
              </div>
              <Sparkles className="w-5 h-5 text-green-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">基金经理分析</h3>
            <p className="text-sm text-gray-500">
              评估基金经理投资能力和管理风格
            </p>
          </div>
        </Link>

        <Link href="/analysis/comparison">
          <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow cursor-pointer border-2 border-transparent hover:border-purple-500">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <GitCompare className="w-6 h-6 text-purple-600" />
              </div>
              <Sparkles className="w-5 h-5 text-purple-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">对比分析</h3>
            <p className="text-sm text-gray-500">
              对比两只基金的业绩和风险特征
            </p>
          </div>
        </Link>

        <Link href="/analysis/advanced">
          <div className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow cursor-pointer border-2 border-transparent hover:border-slate-500">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-slate-100 rounded-lg">
                <BrainCircuit className="w-6 h-6 text-slate-700" />
              </div>
              <Sparkles className="w-5 h-5 text-slate-700" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">高级基金研究</h3>
            <p className="text-sm text-gray-500">
              因子镜头和主动收益归因
            </p>
          </div>
        </Link>
      </div>

      {/* 历史分析报告 */}
      <div className="bg-white rounded-lg shadow">
        <div className="space-y-4 border-b border-gray-200 p-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">最近的基金研究报告</h2>
              <p className="mt-1 text-sm text-gray-500">按研究短名单、研究复核、基金研究快速找回已保存证据。</p>
            </div>
            <div className="flex gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                <input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') setAppliedSearch(searchInput)
                  }}
                  placeholder="搜索基金、短名单、核查结论"
                  className="w-64 rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm"
                />
              </div>
              <button
                type="button"
                onClick={() => setAppliedSearch(searchInput)}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                搜索
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {reportTypeFilters.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setReportType(item.value)}
                className={`rounded-full px-3 py-1.5 text-sm ${
                  reportType === item.value
                    ? 'bg-slate-900 text-white'
                    : 'border border-gray-200 text-gray-700 hover:bg-gray-50'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : reports.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">暂无分析报告</p>
            <p className="text-sm text-gray-400 mt-2">
              选择上方的分析类型开始生成报告
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {reports.map((report) => (
              <Link
                key={report.id}
                href={`/reports/${report.id}`}
                className="block p-6 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                        {report.reportType}
                      </span>
                      <span className={`px-2 py-1 text-xs rounded ${reportModeClassName(report)}`}>
                        {reportModeLabel(report)}
                      </span>
                      <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded">
                        {reportSourceLabel(report)}
                      </span>
                      {report.compareId && (
                        <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded">
                          对比分析
                        </span>
                      )}
                      {report.riskLevelGatePolicy ? (
                        <span className={`px-2 py-1 text-xs rounded font-semibold ${riskLevelPolicyBadgeClass(report.riskLevelGatePolicy.tone)}`} data-testid="analysis-report-risk-level-policy">
                          R1-R5：{report.riskLevelGatePolicy.label}
                        </span>
                      ) : null}
                    </div>
                    {report.riskLevelGatePolicy?.requiresRegeneration ? (
                      <div className="mb-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900" data-testid="analysis-report-risk-level-policy-card">
                        <div className="font-semibold">旧门禁/未标记：不能证明已采用 30 天 R1-R5 来源背书</div>
                        <div className="mt-1 text-amber-800">{report.riskLevelGatePolicy.detail}</div>
                      </div>
                    ) : null}
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {report.content.substring(0, 150)}...
                    </p>
                  </div>
                  <div className="ml-4 flex items-center text-sm text-gray-500">
                    <Clock className="w-4 h-4 mr-1" />
                    {new Date(report.createdAt).toLocaleDateString('zh-CN')}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* 使用说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-sm font-medium text-blue-900 mb-2">使用说明</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• 选择研究类型，输入基金或基金经理 ID</li>
          <li>• 系统会优先加载本地 PostgreSQL 中的 Tushare 入库数据</li>
          <li>• 生成过程采用流式输出，实时展示研究内容</li>
          <li>• 研究报告会自动保存，可随时查看历史记录</li>
          <li>• 若模型 API Key 未安全配置，系统会降级为本地证据报告并显式标记证据缺口</li>
        </ul>
      </div>
    </div>
  )
}
