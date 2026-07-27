'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Search, Filter, ChevronDown, RefreshCw } from 'lucide-react'
import { cn, formatReturn, getGradeColor } from '@/lib/utils'
import { searchFunds } from '@/lib/api'
import type { FundCard } from '@/lib/api'
import { FundTableSkeleton } from '@/components/skeleton/FundSkeleton'
import { EmptyState } from '@/components/common/EmptyState'

const FUND_TYPES = [
  { value: '', label: '全部类型' },
  { value: 'stock', label: '股票型' },
  { value: 'hybrid', label: '混合型' },
  { value: 'bond', label: '债券型' },
  { value: 'index', label: '指数型' },
  { value: 'money', label: '货币型' },
  { value: 'QDII', label: 'QDII' },
  { value: 'FOF', label: 'FOF' },
]

const SORT_OPTIONS = [
  { value: 'rank', label: '综合评分' },
  { value: 'return', label: '收益率' },
  { value: 'risk', label: '风险控制' },
  { value: 'sharpe', label: '夏普比率' },
  { value: 'name', label: '名称' },
]

export default function FundsPage() {
  const [funds, setFunds] = useState<FundCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [fundType, setFundType] = useState('')
  const [sortBy, setSortBy] = useState('rank')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ page: String(page), page_size: '50', sort_by: sortBy, sort_order: 'desc' })
    if (keyword) params.set('keyword', keyword)
    if (fundType) params.set('fund_type', fundType)
    fetch(`/api/funds/?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`请求失败: ${r.status}`)
        return r.json()
      })
      .then(data => {
        setFunds(data.funds || [])
        setTotal(data.total || 0)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to fetch funds:', err)
        setError(err.message)
        setLoading(false)
      })
  }, [keyword, fundType, sortBy, page])

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">基金列表</h1>
          <p className="text-slate-500 text-sm mt-1">共 {total} 只基金</p>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 mb-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="搜索基金名称或代码..."
              value={keyword}
              onChange={e => { setKeyword(e.target.value); setPage(1) }}
              className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
          <select
            value={fundType}
            onChange={e => { setFundType(e.target.value); setPage(1) }}
            className="px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            {FUND_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* Fund List */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        {loading ? (
          <FundTableSkeleton rows={8} />
        ) : error ? (
          <EmptyState
            type="error"
            title="加载失败"
            description={error}
            action={
              <button
                onClick={() => window.location.reload()}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                重新加载
              </button>
            }
          />
        ) : funds.length === 0 ? (
          <EmptyState
            type="data"
            title="未找到基金"
            description="请检查搜索条件或确保后端服务正在运行"
            action={
              <button
                onClick={() => window.location.reload()}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                重新加载
              </button>
            }
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider bg-slate-50">
                <th className="text-left px-6 py-3 font-medium">基金名称</th>
                <th className="text-left px-4 py-3 font-medium w-20">类型</th>
                <th className="text-right px-4 py-3 font-medium w-20">综合评分</th>
                <th className="text-right px-4 py-3 font-medium w-16">评级</th>
                <th className="text-right px-4 py-3 font-medium w-24">近1年收益</th>
                <th className="text-right px-4 py-3 font-medium w-24">近3年收益</th>
                <th className="text-right px-4 py-3 font-medium w-20">夏普比率</th>
                <th className="text-right px-4 py-3 font-medium w-24">最大回撤</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {funds.map((fund) => (
                <tr key={fund.wind_code} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <Link href={`/funds/${fund.wind_code}`} className="block">
                      <div className="font-medium text-slate-900 hover:text-blue-600 transition-colors">
                        {fund.name || fund.wind_code}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">{fund.wind_code}</div>
                    </Link>
                  </td>
                  <td className="px-4 py-4 text-sm text-slate-600">{fund.type}</td>
                  <td className="px-4 py-4 text-right font-bold text-slate-900">
                    {fund.scoring?.overall_score != null ? fund.scoring.overall_score.toFixed(1) :
                     fund.overall_score != null ? fund.overall_score.toFixed(1) : '-'}
                  </td>
                  <td className="px-4 py-4 text-right">
                    {(fund.scoring?.overall_grade || fund.overall_grade) && (
                      <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-bold text-white ${getGradeColor(fund.scoring?.overall_grade || fund.overall_grade)}`}>
                        {fund.scoring?.overall_grade || fund.overall_grade}
                      </span>
                    )}
                  </td>
                  <td className={`px-4 py-4 text-right text-sm font-medium ${fund.performance ? (fund.performance.annualized_return_1y >= 0 ? 'text-red-500' : 'text-green-500') : 'text-slate-400'}`}>
                    {fund.performance ? formatReturn(fund.performance.annualized_return_1y) : '-'}
                  </td>
                  <td className={`px-4 py-4 text-right text-sm font-medium ${fund.performance ? (fund.performance.annualized_return_3y >= 0 ? 'text-red-500' : 'text-green-500') : 'text-slate-400'}`}>
                    {fund.performance ? formatReturn(fund.performance.annualized_return_3y) : '-'}
                  </td>
                  <td className="px-4 py-4 text-right text-sm text-slate-700">
                    {fund.performance?.sharpe_ratio?.toFixed(2) || '-'}
                  </td>
                  <td className="px-4 py-4 text-right text-sm text-red-500">
                    {fund.performance?.max_drawdown ? `${(fund.performance.max_drawdown * 100).toFixed(2)}%` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm disabled:opacity-40 hover:bg-slate-50 disabled:cursor-not-allowed">
            上一页
          </button>
          <span className="text-sm text-slate-500 px-4">第 {page} / {Math.ceil(total / 50)} 页</span>
          <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 50)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm disabled:opacity-40 hover:bg-slate-50 disabled:cursor-not-allowed">
            下一页
          </button>
        </div>
      )}
    </div>
  )
}
