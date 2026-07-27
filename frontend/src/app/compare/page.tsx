'use client'

import { useState, useEffect } from 'react'
import { Search, X, TrendingUp, Shield, BarChart3 } from 'lucide-react'
import Link from 'next/link'
import { BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function ComparePage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [selectedFunds, setSelectedFunds] = useState<any[]>([])
  const [compareData, setCompareData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const searchFunds = async (query: string) => {
    if (!query.trim()) {
      setSearchResults([])
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`http://127.0.0.1:8005/api/funds?keyword=${encodeURIComponent(query)}&page_size=10`)
      const data = await res.json()
      setSearchResults(data.funds || [])
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const addFund = async (fund: any) => {
    if (selectedFunds.length >= 4) return
    if (selectedFunds.find(f => f.wind_code === fund.wind_code)) return

    try {
      const res = await fetch(`http://127.0.0.1:8005/api/funds/${fund.wind_code}`)
      const data = await res.json()
      setSelectedFunds([...selectedFunds, { ...fund, details: data }])
      setSearchQuery('')
      setSearchResults([])
    } catch (error) {
      console.error('Failed to fetch fund details:', error)
    }
  }

  const removeFund = (windCode: string) => {
    setSelectedFunds(selectedFunds.filter(f => f.wind_code !== windCode))
  }

  useEffect(() => {
    if (selectedFunds.length >= 2) {
      const returnData = selectedFunds.map(f => ({
        name: f.name?.substring(0, 8) || f.wind_code,
        '1年收益': (f.details?.performance?.annualized_return_1y || 0) * 100,
        '3年收益': (f.details?.performance?.annualized_return_3y || 0) * 100,
      }))

      const riskData = selectedFunds.map(f => ({
        name: f.name?.substring(0, 8) || f.wind_code,
        '波动率': (f.details?.risk_metrics?.annualized_volatility_1y || 0) * 100,
        '最大回撤': Math.abs((f.details?.risk_metrics?.max_drawdown_1y || 0) * 100),
      }))

      const scoreData = selectedFunds.map(f => ({
        name: f.name?.substring(0, 8) || f.wind_code,
        '综合评分': f.details?.scoring?.overall_score || 0,
        '夏普比率': (f.details?.performance?.sharpe_ratio || 0) * 10,
      }))

      setCompareData([{ type: 'return', data: returnData }, { type: 'risk', data: riskData }, { type: 'score', data: scoreData }])
    }
  }, [selectedFunds])

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-slate-900 mb-2">基金对比</h1>
      <p className="text-slate-500 mb-6">选择 2-4 只基金进行横向对比</p>

      {/* Search */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              searchFunds(e.target.value)
            }}
            placeholder="搜索基金名称或代码..."
            className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={selectedFunds.length >= 4}
          />
        </div>
        {searchResults.length > 0 && (
          <div className="mt-2 border border-slate-200 rounded-lg divide-y divide-slate-100 max-h-60 overflow-y-auto">
            {searchResults.map(fund => (
              <button
                key={fund.wind_code}
                onClick={() => addFund(fund)}
                className="w-full px-4 py-3 text-left hover:bg-slate-50 transition-colors"
              >
                <div className="font-medium text-slate-900">{fund.name}</div>
                <div className="text-xs text-slate-400">{fund.wind_code} · {fund.type}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Selected Funds */}
      {selectedFunds.length > 0 && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {selectedFunds.map(fund => (
            <div key={fund.wind_code} className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 relative">
              <button
                onClick={() => removeFund(fund.wind_code)}
                className="absolute top-2 right-2 w-6 h-6 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center"
              >
                <X className="w-4 h-4 text-slate-600" />
              </button>
              <Link href={`/funds/${fund.wind_code}`} className="block">
                <div className="font-medium text-slate-900 mb-1 pr-6">{fund.name}</div>
                <div className="text-xs text-slate-400 mb-3">{fund.wind_code}</div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">1年收益</span>
                    <span className={`font-medium ${(fund.details?.performance?.annualized_return_1y || 0) >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {fund.details?.performance?.annualized_return_1y != null
                        ? `${((fund.details.performance.annualized_return_1y || 0) >= 0 ? '+' : '')}${(fund.details.performance.annualized_return_1y * 100).toFixed(2)}%`
                        : '-'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">夏普比率</span>
                    <span className="font-medium text-slate-900">{fund.details?.performance?.sharpe_ratio?.toFixed(2) || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">综合评分</span>
                    <span className="font-medium text-slate-900">{fund.details?.scoring?.overall_score?.toFixed(1) || '-'}</span>
                  </div>
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* Comparison Charts */}
      {selectedFunds.length >= 2 && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              收益对比
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={compareData[0]?.data || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                <Legend />
                <Bar dataKey="1年收益" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="3年收益" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5" />
              风险对比
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={compareData[1]?.data || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                <Legend />
                <Bar dataKey="波动率" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="最大回撤" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              综合评分对比
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={compareData[2]?.data || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="综合评分" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="夏普比率" fill="#ec4899" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {selectedFunds.length < 2 && (
        <div className="bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 p-12 text-center">
          <p className="text-slate-400">请至少选择 2 只基金进行对比</p>
        </div>
      )}
    </div>
  )
}
