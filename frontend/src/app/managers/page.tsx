'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Search, ChevronRight, RefreshCw, Star, Filter } from 'lucide-react'
import { cn, getGradeColor } from '@/lib/utils'
import { CardSkeleton } from '@/components/skeleton/FundSkeleton'
import { EmptyState } from '@/components/common/EmptyState'

export default function ManagersPage() {
  const [managers, setManagers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [tenureFilter, setTenureFilter] = useState<string>('all')
  const [companyFilter, setCompanyFilter] = useState<string>('')

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ page: String(page), page_size: '50' })
    if (keyword) params.set('keyword', keyword)
    if (companyFilter) params.set('company', companyFilter)

    fetch(`/api/managers?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`请求失败: ${r.status}`)
        return r.json()
      })
      .then(data => {
        let filteredManagers = data.managers || []

        // 前端过滤任职年限
        if (tenureFilter !== 'all') {
          const minYears = parseInt(tenureFilter)
          filteredManagers = filteredManagers.filter((m: any) => m.tenure_years >= minYears)
        }

        setManagers(filteredManagers)
        setTotal(data.total || 0)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to fetch managers:', err)
        setError(err.message)
        setLoading(false)
      })
  }, [keyword, companyFilter, page, tenureFilter])

  const renderStars = (score: number) => {
    // 将评分映射到星级 (0-100 -> 1-5星)
    const stars = Math.max(1, Math.min(5, Math.ceil(score / 20)))
    return (
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-3 h-3 ${star <= stars ? 'fill-yellow-400 text-yellow-400' : 'text-slate-300'}`}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">基金经理</h1>
        <p className="text-slate-500 text-sm mt-1">查看基金经理档案与业绩评价 · 共 {total} 位经理</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 mb-6">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="搜索基金经理姓名..."
              value={keyword}
              onChange={e => { setKeyword(e.target.value); setPage(1) }}
              className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
          <div className="relative">
            <input
              type="text"
              placeholder="基金公司..."
              value={companyFilter}
              onChange={e => { setCompanyFilter(e.target.value); setPage(1) }}
              className="w-48 pl-3 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs text-slate-500">任职年限:</span>
          <div className="flex gap-2">
            {[
              { label: '全部', value: 'all' },
              { label: '5年+', value: '5' },
              { label: '10年+', value: '10' },
              { label: '15年+', value: '15' },
            ].map(option => (
              <button
                key={option.value}
                onClick={() => { setTenureFilter(option.value); setPage(1) }}
                className={cn(
                  "px-3 py-1 rounded-lg text-xs font-medium transition-colors",
                  tenureFilter === option.value
                    ? "bg-blue-100 text-blue-700"
                    : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(i => <CardSkeleton key={i} />)}
        </div>
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
      ) : managers.length === 0 ? (
        <EmptyState
          type="search"
          title="未找到基金经理"
          description="请尝试其他搜索关键词"
        />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {managers.map((m) => (
            <Link key={m.manager_id} href={`/managers/${m.manager_id}`}
              className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 hover:shadow-md hover:border-blue-200 transition-all group">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center text-slate-500 font-bold">
                    {m.name?.charAt(0) || '?'}
                  </div>
                  <div>
                    <div className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">{m.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{m.company}</div>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-blue-400 transition-colors" />
              </div>
              <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-slate-50">
                <div>
                  <div className="text-xs text-slate-500">管理基金</div>
                  <div className="text-sm font-semibold text-slate-900">{m.fund_count}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">任职年限</div>
                  <div className="text-sm font-semibold text-slate-900">{m.tenure_years}年</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">评级</div>
                  <div className="flex items-center gap-1">
                    {m.avg_score != null ? renderStars(m.avg_score) : <span className="text-xs text-slate-400">-</span>}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {managers.length > 0 && !loading && total > 50 && (
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
