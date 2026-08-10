'use client'

import { useState, useEffect } from 'react'
import { PieChart, Search } from 'lucide-react'
import { BrinsonWaterfall, BrinsonReturns } from '@/components/brinson/BrinsonWaterfall'

interface BrinsonAnalysis {
  fund_code: string
  benchmark: string | null
  quarter: string
  status: 'ok' | 'partial_evidence' | 'insufficient_evidence' | 'not_applicable'
  returns: { portfolio: number; benchmark: number; active: number }
  attribution: {
    allocation_effect: number
    selection_effect: number
    interaction_effect: number
    residual: number
    total: number
  }
  industry_detail: Array<{
    industry: string
    portfolio_weight: number
    benchmark_weight: number
    portfolio_return: number
    benchmark_return: number
    allocation_contrib: number
    selection_contrib: number
  }>
  missing_items: string[]
}

export default function BrinsonPage() {
  const [fundCode, setFundCode] = useState('000001.OF')
  const [benchmark, setBenchmark] = useState('')
  const [quarter, setQuarter] = useState('')
  const [data, setData] = useState<BrinsonAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const searchFund = async () => {
    if (!fundCode) return
    setLoading(true)
    setError('')

    try {
      const params = new URLSearchParams()
      if (benchmark) params.set('benchmark', benchmark)
      if (quarter) params.set('quarter', quarter)
      const res = await fetch(`/api/brinson/attribution/${fundCode}?${params}`)
      if (!res.ok) throw new Error('归因分析失败')
      const json = await res.json()
      setData(json)
    } catch (e: any) {
      setError(e.message || '请求失败')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    searchFund()
  }, [])

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <PieChart className="w-6 h-6 text-emerald-600" />
          Brinson 业绩归因分析
        </h1>
        <p className="text-slate-500 mt-1">基于 Brinson-Fachler 模型的超额收益分解</p>
      </div>

      {/* 搜索框 */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100 mb-6">
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            value={fundCode}
            onChange={e => setFundCode(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && searchFund()}
            placeholder="基金代码"
            className="px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 w-48"
          />
          <select
            value={benchmark}
            onChange={e => setBenchmark(e.target.value)}
            className="px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="">自动使用基金分类基准</option>
            <option value="000300">沪深300</option>
            <option value="000905">中证500</option>
            <option value="000852">中证1000</option>
          </select>
          <input
            type="text"
            value={quarter}
            onChange={e => setQuarter(e.target.value)}
            placeholder="季度 (2024Q1)"
            className="px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 w-32"
          />
          <button
            onClick={searchFund}
            disabled={loading}
            className="px-6 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            分析
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-slate-400">计算归因中...</div>
      )}

      {data && !loading && (
        data.attribution.total == null ? (
          <div className="bg-amber-50 text-amber-800 px-5 py-4 rounded-lg">
            <div className="font-medium">当前证据不足，无法输出 Brinson 结论</div>
            <div className="text-sm mt-2">{data.missing_items.join('；')}</div>
          </div>
        ) : <div className="grid grid-cols-2 gap-6">
          {/* 收益对比 */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
            <h3 className="text-md font-semibold text-slate-700 mb-4">收益对比</h3>
            <BrinsonReturns attribution={data} />
          </div>

          {/* 归因分解 */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
            <h3 className="text-md font-semibold text-slate-700 mb-4">收益归因分解</h3>
            <BrinsonWaterfall attribution={data} compact />
          </div>

          {/* 完整归因图 */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100 col-span-2">
            <h3 className="text-md font-semibold text-slate-700 mb-4">完整归因分析</h3>
            <BrinsonWaterfall attribution={data} />
          </div>
        </div>
      )}
    </div>
  )
}
