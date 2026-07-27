'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Filter, Sliders, Save, Play, ArrowRight, RefreshCw } from 'lucide-react'
import { cn, formatReturn, getGradeColor } from '@/lib/utils'
import { getScreeningTemplates, customScreening } from '@/lib/api'
import { FundTableSkeleton } from '@/components/skeleton/FundSkeleton'
import { EmptyState } from '@/components/common/EmptyState'

const TEMPLATES = [
  { key: 'high_sharpe', name: '高夏普比率', desc: '风险调整收益优秀的基金', color: 'border-blue-200' },
  { key: 'low_risk', name: '低风险稳健', desc: '回撤控制良好，波动小', color: 'border-emerald-200' },
  { key: 'growth_style', name: '成长风格', desc: '偏向成长股的基金', color: 'border-purple-200' },
  { key: 'value_style', name: '价值风格', desc: '偏向价值股的基金', color: 'border-amber-200' },
  { key: 'top_ranked', name: '综合排名靠前', desc: '综合评分最高的基金', color: 'border-orange-200' },
]

export default function ScreeningPage() {
  const router = useRouter()
  const [results, setResults] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [activeTemplate, setActiveTemplate] = useState<string | null>(null)
  const [customFilters, setCustomFilters] = useState({
    return_min: '',
    sharpe_min: '',
    max_drawdown_max: '',
    volatility_max: '',
    score_min: '',
    fund_type: '',
  })

  const handleTemplateSearch = async (key: string) => {
    setActiveTemplate(key)
    setLoading(true)
    setHasSearched(true)
    setError(null)
    try {
      const res = await fetch(`/api/screening/template/${key}`)
      if (!res.ok) throw new Error(`请求失败: ${res.status}`)
      const data = await res.json()
      setResults(data.funds || [])
      setTotal(data.total || 0)
    } catch (err: any) {
      console.error('Template search failed:', err)
      setError(err.message)
      setResults([])
    }
    setLoading(false)
  }

  const handleCustomSearch = async () => {
    setActiveTemplate(null)
    setLoading(true)
    setHasSearched(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      Object.entries(customFilters).forEach(([k, v]) => {
        if (v) params.set(k, v)
      })
      const res = await fetch(`/api/screening/custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          Object.fromEntries(Object.entries(customFilters).filter(([, v]) => v !== ''))
        ),
      })
      if (!res.ok) throw new Error(`请求失败: ${res.status}`)
      const data = await res.json()
      setResults(data.funds || [])
      setTotal(data.total || 0)
    } catch (err: any) {
      console.error('Custom search failed:', err)
      setError(err.message)
      setResults([])
    }
    setLoading(false)
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">基金筛选</h1>
        <p className="text-slate-500 text-sm mt-1">多维度条件筛选，快速找到目标基金</p>
      </div>

      {/* Templates */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">快速模板</h2>
        <div className="grid grid-cols-5 gap-3">
          {TEMPLATES.map(t => (
            <button
              key={t.key}
              onClick={() => handleTemplateSearch(t.key)}
              className={cn(
                'bg-white rounded-xl border-2 p-4 text-left hover:shadow-md transition-all',
                activeTemplate === t.key
                  ? `${t.color} shadow-md`
                  : 'border-slate-100 hover:border-slate-200'
              )}
            >
              <div className="font-medium text-slate-900 text-sm">{t.name}</div>
              <div className="text-xs text-slate-500 mt-1">{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Custom Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700">自定义筛选条件</h2>
          <button
            onClick={handleCustomSearch}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                筛选中...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                开始筛选
              </>
            )}
          </button>
        </div>
        <div className="grid grid-cols-5 gap-4">
          {[
            { key: 'return_min', label: '近1年收益下限', placeholder: '0.10', suffix: '%' },
            { key: 'sharpe_min', label: '夏普比率下限', placeholder: '1.5', suffix: '' },
            { key: 'max_drawdown_max', label: '最大回撤上限', placeholder: '-0.15', suffix: '%' },
            { key: 'volatility_max', label: '波动率上限', placeholder: '0.25', suffix: '' },
            { key: 'score_min', label: '综合评分下限', placeholder: '75', suffix: '分' },
          ].map(field => (
            <div key={field.key}>
              <label className="block text-xs text-slate-500 mb-1">{field.label}</label>
              <input
                type="text"
                placeholder={field.placeholder}
                value={customFilters[field.key as keyof typeof customFilters]}
                onChange={e => setCustomFilters({ ...customFilters, [field.key]: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          ))}
          <div>
            <label className="block text-xs text-slate-500 mb-1">基金类型</label>
            <select
              value={customFilters.fund_type}
              onChange={e => setCustomFilters({ ...customFilters, fund_type: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="">全部</option>
              <option value="stock">股票型</option>
              <option value="hybrid">混合型</option>
              <option value="bond">债券型</option>
              <option value="index">指数型</option>
            </select>
          </div>
        </div>
      </div>

      {/* Results */}
      {hasSearched && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <span className="text-sm text-slate-500">找到 {total} 只基金</span>
          </div>
          {loading ? (
            <FundTableSkeleton rows={6} />
          ) : error ? (
            <EmptyState
              type="error"
              title="筛选失败"
              description={error}
              action={
                <button
                  onClick={() => setHasSearched(false)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  重试
                </button>
              }
            />
          ) : results.length === 0 ? (
            <EmptyState
              type="search"
              title="未找到符合条件的基金"
              description="请尝试调整筛选条件"
            />
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-xs text-slate-500 uppercase bg-slate-50">
                  <th className="text-left px-6 py-3 font-medium">基金名称</th>
                  <th className="text-left px-4 py-3 font-medium w-20">类型</th>
                  <th className="text-right px-4 py-3 font-medium w-20">评分</th>
                  <th className="text-right px-4 py-3 font-medium w-16">评级</th>
                  <th className="text-right px-4 py-3 font-medium w-24">近1年收益</th>
                  <th className="text-right px-4 py-3 font-medium w-20">夏普比率</th>
                  <th className="text-right px-4 py-3 font-medium w-24">最大回撤</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((fund) => (
                  <tr key={fund.wind_code} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-3">
                      <div className="font-medium text-slate-900">{fund.name || fund.wind_code}</div>
                      <div className="text-xs text-slate-400">{fund.wind_code}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">{fund.type}</td>
                    <td className="px-4 py-3 text-right font-bold text-slate-900">
                      {fund.overall_score?.toFixed(1) || '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {fund.overall_grade && (
                        <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold text-white ${getGradeColor(fund.overall_grade)}`}>
                          {fund.overall_grade}
                        </span>
                      )}
                    </td>
                    <td className={`px-4 py-3 text-right text-sm font-medium ${fund.performance ? (fund.performance.annualized_return_1y >= 0 ? 'text-red-500' : 'text-green-500') : 'text-slate-400'}`}>
                      {fund.performance ? formatReturn(fund.performance.annualized_return_1y) : '-'}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-slate-700">
                      {fund.performance?.sharpe_ratio?.toFixed(2) || '-'}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-red-500">
                      {fund.performance?.max_drawdown ? `${(fund.performance.max_drawdown * 100).toFixed(2)}%` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
