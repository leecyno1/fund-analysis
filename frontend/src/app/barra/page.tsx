'use client'

import { useState, useEffect } from 'react'
import { BarChart2, Search, TrendingUp, PieChart } from 'lucide-react'
import Link from 'next/link'
import { BarraRadarChart, BarraStyleExposure } from '@/components/barra/BarraRadar'

interface BarraAnalysis {
  fund_code: string
  quarter: string
  status: 'ok' | 'partial_evidence' | 'insufficient_evidence'
  exposures: Array<{ factor: string; exposure: number }>
  industry_exposures: Record<string, number>
  risk_contributions: Array<{ factor: string; risk_contribution: number }>
  total_factor_risk: number | null
  specific_risk: number | null
  r_squared: number | null
  num_holdings: number
  top10_weight: number
  missing_items: string[]
}

function formatPercent(value: number | null) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

export default function BarraPage() {
  const [fundCode, setFundCode] = useState('000001.OF')
  const [data, setData] = useState<BarraAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const searchFund = async () => {
    if (!fundCode) return
    setLoading(true)
    setError('')

    try {
      const res = await fetch(`/api/barra/exposure/${fundCode}`)
      if (!res.ok) throw new Error('基金不存在')
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

  const exposures = data?.exposures?.reduce((acc, f) => {
    acc[f.factor] = f.exposure
    return acc
  }, {} as Record<string, number>) || {}

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <BarChart2 className="w-6 h-6 text-blue-600" />
          Barra 风险因子分析
        </h1>
        <p className="text-slate-500 mt-1">展示可核验的风格与行业暴露；风险输入不完整时不估算 R²</p>
      </div>

      {/* 搜索框 */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100 mb-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={fundCode}
            onChange={e => setFundCode(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && searchFund()}
            placeholder="输入基金代码 (如 000001.OF)"
            className="flex-1 px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={searchFund}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            查询
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-12 text-slate-400">加载中...</div>
      )}

      {data && !loading && (
        <div className="grid grid-cols-2 gap-6">
          {data.missing_items.length > 0 && (
            <div className="col-span-2 bg-amber-50 text-amber-800 px-5 py-4 rounded-lg text-sm">
              {data.missing_items.join('；')}
            </div>
          )}
          {/* 风格因子雷达图 */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
            <h3 className="text-md font-semibold text-slate-700 mb-4">风格因子暴露</h3>
            <BarraRadarChart
              exposures={exposures}
              riskContributions={data.risk_contributions}
            />
          </div>

          {/* 风险指标 */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
            <h3 className="text-md font-semibold text-slate-700 mb-4">风险指标</h3>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {formatPercent(data.r_squared)}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">R² 解释度</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-emerald-600">
                    {data.num_holdings}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">持仓数量</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {(data.top10_weight * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Top10 集中度</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-amber-600">
                    {formatPercent(data.total_factor_risk)}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">因子风险</div>
                </div>
              </div>
            </div>
          </div>

          {/* 风格暴露详情 */}
          <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100 col-span-2">
            <h3 className="text-md font-semibold text-slate-700 mb-4">因子暴露详情</h3>
            <BarraStyleExposure exposures={exposures} />
          </div>

          {/* 行业分布 */}
          {data.industry_exposures && Object.keys(data.industry_exposures).length > 0 && (
            <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100 col-span-2">
              <h3 className="text-md font-semibold text-slate-700 mb-4">行业暴露分布</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.industry_exposures)
                  .sort((a, b) => b[1] - a[1])
                  .map(([ind, w]) => (
                    <div
                      key={ind}
                      className="px-3 py-1.5 bg-slate-100 rounded-lg flex items-center gap-2"
                    >
                      <span className="text-sm text-slate-700">{ind}</span>
                      <span className="text-xs font-mono text-blue-600">{(w * 100).toFixed(1)}%</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
