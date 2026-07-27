'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Users, Briefcase, TrendingUp, FileText, Star } from 'lucide-react'
import { ScoreGauge } from '@/components/common/ScoreGauge'
import { getManager, getManagerReports, getManagerScore, getManagerMorningstarRating } from '@/lib/api'
import { formatReturn, getGradeColor } from '@/lib/utils'
import { LineChart, Line, ScatterChart, Scatter, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { isFavorite, toggleFavorite } from '@/lib/favorites'

export default function ManagerDetailPage() {
  const params = useParams()
  const id = params.id as string
  const [manager, setManager] = useState<any>(null)
  const [reports, setReports] = useState<any[]>([])
  const [scoring, setScoring] = useState<any>(null)
  const [morningstar, setMorningstar] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [generatingReport, setGeneratingReport] = useState(false)
  const [aiReport, setAiReport] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('profile')
  const [isFav, setIsFav] = useState(false)

  useEffect(() => {
    setIsFav(isFavorite(id))
  }, [id])

  const handleGenerateReport = async () => {
    setGeneratingReport(true)
    try {
      const response = await fetch(`/api/reports/manager/${id}`, { method: 'POST' })
      const data = await response.json()
      if (data.report) {
        setAiReport(data.report)
      }
    } catch (error) {
      console.error('Failed to generate report:', error)
    } finally {
      setGeneratingReport(false)
    }
  }

  const handleToggleFavorite = () => {
    const newState = toggleFavorite({
      id: id,
      type: 'manager',
      name: manager?.name || id,
    })
    setIsFav(newState)
  }

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getManager(id).catch(() => null),
      getManagerReports(id).catch(() => null),
      getManagerScore(id).catch(() => null),
      getManagerMorningstarRating(id).catch(() => null),
    ]).then(([mgr, reps, score, morning]) => {
      setManager(mgr)
      setReports(reps?.reports || [])
      setScoring(score)
      setMorningstar(morning)
      setLoading(false)
    })
  }, [id])

  if (loading) {
    return <div className="p-8 flex items-center justify-center min-h-screen text-slate-400">加载中...</div>
  }

  if (!manager) {
    return (
      <div className="p-8 text-center">
        <div className="text-slate-400 mb-4">未找到基金经理 {id}</div>
        <Link href="/managers" className="text-blue-600 hover:underline">返回基金经理列表</Link>
      </div>
    )
  }

  const tabs = [
    { key: 'profile', label: '个人档案', icon: Users },
    { key: 'performance', label: '业绩表现', icon: TrendingUp },
    { key: 'reports', label: '调研报告', icon: FileText },
  ]

  const renderStars = (rating: number) => {
    return (
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-5 h-5 ${star <= rating ? 'fill-yellow-400 text-yellow-400' : 'text-slate-300'}`}
          />
        ))}
      </div>
    )
  }

  // 准备风险收益散点图数据
  const riskReturnData = manager?.funds?.map((f: any) => ({
    name: f.name,
    risk: f.risk_metrics?.annualized_volatility_1y || 0,
    return: f.performance?.annualized_return_1y || 0,
    windCode: f.wind_code,
  })).filter((d: any) => d.risk > 0 && d.return !== 0) || []

  // 准备评分雷达图数据
  const radarData = morningstar ? [
    { dimension: '收益能力', score: morningstar.dimension_scores.return, fullMark: 100 },
    { dimension: '风险调整', score: morningstar.dimension_scores.risk_adjusted, fullMark: 100 },
    { dimension: '业绩稳定', score: morningstar.dimension_scores.stability, fullMark: 100 },
    { dimension: '从业经验', score: morningstar.dimension_scores.experience, fullMark: 100 },
  ] : []

  return (
    <div className="p-8">
      <Link href="/managers" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> 返回基金经理列表
      </Link>

      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-slate-100 rounded-full flex items-center justify-center text-xl font-bold text-slate-500">
            {manager.name?.charAt(0) || '?'}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{manager.name}</h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
              <span>{manager.company}</span>
              <span>·</span>
              <span>管理 {manager.fund_count} 只基金</span>
              <span>·</span>
              <span>任职 {manager.tenure_years} 年</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {scoring && (
            <ScoreGauge score={scoring.overall_score} size={100} grade={scoring.overall_grade} />
          )}
          <button
            onClick={handleToggleFavorite}
            className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
              isFav ? 'bg-yellow-100 text-yellow-500' : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
            }`}
          >
            <Star className={`w-5 h-5 ${isFav ? 'fill-yellow-500' : ''}`} />
          </button>
          <button
            onClick={handleGenerateReport}
            disabled={generatingReport}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generatingReport ? '生成中...' : '生成AI报告'}
          </button>
        </div>
      </div>

      {/* Morningstar Rating */}
      {morningstar && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100 p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-slate-600 mb-2">晨星评级</h3>
              {renderStars(morningstar.star_rating)}
              <div className="text-xs text-slate-500 mt-2">
                综合评分: {morningstar.overall_score} 分 · 同类排名前 {(100 - morningstar.percentile_rank).toFixed(0)}%
              </div>
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-xs text-slate-500 mb-1">收益能力</div>
                <div className="text-lg font-semibold text-slate-900">{morningstar.dimension_scores.return.toFixed(0)}</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-slate-500 mb-1">风险调整</div>
                <div className="text-lg font-semibold text-slate-900">{morningstar.dimension_scores.risk_adjusted.toFixed(0)}</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-slate-500 mb-1">业绩稳定</div>
                <div className="text-lg font-semibold text-slate-900">{morningstar.dimension_scores.stability.toFixed(0)}</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-slate-500 mb-1">从业经验</div>
                <div className="text-lg font-semibold text-slate-900">{morningstar.dimension_scores.experience.toFixed(0)}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {tabs.map(tab => (
          <button key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}>
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* AI Report */}
      {aiReport && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6">
          <h3 className="font-semibold text-slate-900 mb-4">AI 分析报告</h3>
          <div className="prose prose-sm max-w-none">
            <pre className="whitespace-pre-wrap text-sm text-slate-600 leading-relaxed">{aiReport}</pre>
          </div>
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">职业履历</h3>
              <div className="space-y-3">
                {manager.career?.map((c: any, i: number) => (
                  <div key={i} className="flex gap-4">
                    <div className="w-24 text-sm text-slate-500">{c.start_date}</div>
                    <div>
                      <div className="text-sm font-medium text-slate-900">{c.company} · {c.position}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">投资理念</h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                {manager.investment_philosophy || '暂无投资理念描述'}
              </p>
            </div>
          </div>
          <div className="space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">管理基金</h3>
              {manager.funds?.length > 0 ? (
                <div className="space-y-2">
                  {manager.funds.map((f: any) => (
                    <Link key={f.wind_code} href={`/funds/${f.wind_code}`}
                      className="block p-2 rounded-lg hover:bg-slate-50 transition-colors">
                      <div className="text-sm font-medium text-slate-900">{f.name}</div>
                      <div className="text-xs text-slate-400">{f.wind_code}</div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-400">暂无数据</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          {/* 风险收益散点图 */}
          {riskReturnData.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">风险收益分布</h3>
              <ResponsiveContainer width="100%" height={350}>
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    type="number"
                    dataKey="risk"
                    name="风险"
                    unit="%"
                    tick={{ fontSize: 12 }}
                    label={{ value: '年化波动率 (%)', position: 'insideBottom', offset: -10, fontSize: 12 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="return"
                    name="收益"
                    unit="%"
                    tick={{ fontSize: 12 }}
                    label={{ value: '年化收益率 (%)', angle: -90, position: 'insideLeft', fontSize: 12 }}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                    formatter={(value: any) => `${(value * 100).toFixed(2)}%`}
                  />
                  <Scatter name="基金" data={riskReturnData} fill="#3b82f6" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 评分雷达图 */}
          {radarData.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">能力评分雷达图</h3>
              <ResponsiveContainer width="100%" height={350}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 12 }} />
                  <Radar name="评分" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.6} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 管理基金业绩表现 */}
          {manager.funds?.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">管理基金业绩</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                      <th className="text-left py-3">基金名称</th>
                      <th className="text-right py-3">近1年收益</th>
                      <th className="text-right py-3">近3年收益</th>
                      <th className="text-right py-3">夏普比率</th>
                      <th className="text-right py-3">最大回撤</th>
                      <th className="text-right py-3">波动率</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {manager.funds.map((f: any) => (
                      <tr key={f.wind_code} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3">
                          <Link href={`/funds/${f.wind_code}`} className="text-sm font-medium text-slate-900 hover:text-blue-600">
                            {f.name}
                          </Link>
                        </td>
                        <td className={`py-3 text-right text-sm font-medium ${
                          (f.performance?.annualized_return_1y || 0) >= 0 ? 'text-red-500' : 'text-green-500'
                        }`}>
                          {f.performance?.annualized_return_1y != null
                            ? `${((f.performance.annualized_return_1y || 0) >= 0 ? '+' : '')}${(f.performance.annualized_return_1y * 100).toFixed(2)}%`
                            : '-'}
                        </td>
                        <td className={`py-3 text-right text-sm font-medium ${
                          (f.performance?.annualized_return_3y || 0) >= 0 ? 'text-red-500' : 'text-green-500'
                        }`}>
                          {f.performance?.annualized_return_3y != null
                            ? `${((f.performance.annualized_return_3y || 0) >= 0 ? '+' : '')}${(f.performance.annualized_return_3y * 100).toFixed(2)}%`
                            : '-'}
                        </td>
                        <td className="py-3 text-right text-sm text-slate-700">
                          {f.performance?.sharpe_ratio?.toFixed(2) || '-'}
                        </td>
                        <td className="py-3 text-right text-sm text-red-500">
                          {f.risk_metrics?.max_drawdown_1y != null
                            ? `${(f.risk_metrics.max_drawdown_1y * 100).toFixed(2)}%`
                            : '-'}
                        </td>
                        <td className="py-3 text-right text-sm text-slate-700">
                          {f.risk_metrics?.annualized_volatility_1y != null
                            ? `${(f.risk_metrics.annualized_volatility_1y * 100).toFixed(2)}%`
                            : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Reports Tab */}
      {activeTab === 'reports' && reports.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100">
          <div className="p-6 border-b border-slate-100">
            <h3 className="font-semibold text-slate-900">调研报告</h3>
          </div>
          <div className="divide-y divide-slate-100">
            {reports.map((r: any) => (
              <div key={r.id} className="p-4">
                <div className="font-medium text-slate-900 text-sm">{r.title}</div>
                <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
                  <span>{r.manager_name}</span>
                  <span>·</span>
                  <span>{r.date}</span>
                  <span>·</span>
                  <span>{r.company}</span>
                </div>
                <p className="text-sm text-slate-600 mt-2 line-clamp-2">{r.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
