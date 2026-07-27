'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  ArrowLeft, BarChart3, TrendingUp, Shield, Activity,
  PieChart, FileText, RefreshCw, Star
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, AreaChart, Area
} from 'recharts'
import { ScoreGauge } from '@/components/common/ScoreGauge'
import { getFund, getFundNav, getFundHoldings, getFundScore, generateFundReport } from '@/lib/api'
import { isFavorite, toggleFavorite } from '@/lib/favorites'

export default function FundDetailPage() {
  const params = useParams()
  const code = params.code as string
  const [fundData, setFundData] = useState<any>(null)
  const [navData, setNavData] = useState<{ dates: string[]; navs: number[] } | null>(null)
  const [holdings, setHoldings] = useState<any>(null)
  const [scoring, setScoring] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [reportStatus, setReportStatus] = useState<'idle' | 'generating' | 'done'>('idle')
  const [navPeriod, setNavPeriod] = useState('1y')
  const [isFav, setIsFav] = useState(false)

  useEffect(() => {
    setIsFav(isFavorite(code))
  }, [code])

  useEffect(() => {
    setLoading(true)

    // 计算日期范围
    const endDate = new Date().toISOString().split('T')[0]
    const daysMap: Record<string, number> = { '1m': 30, '3m': 90, '6m': 180, '1y': 365, '3y': 1095, '5y': 1825 }
    const days = daysMap[navPeriod] || 365
    const startDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

    Promise.all([
      getFund(code).catch(() => null),
      getFundNav(code, startDate, endDate).catch(() => null),
      getFundHoldings(code).catch(() => null),
      getFundScore(code).catch(() => null),
    ]).then(([fund, nav, hold, score]) => {
      setFundData(fund)

      // 转换 nav 数据格式
      if (nav?.data) {
        setNavData({
          dates: nav.data.map((d: any) => d.date),
          navs: nav.data.map((d: any) => d.nav)
        })
      }

      setHoldings(hold)
      setScoring(score)
      setLoading(false)
    })
  }, [code, navPeriod])

  const handleGenerateReport = async () => {
    setReportStatus('generating')
    try {
      const result = await generateFundReport(code)
      console.log('Report generation started:', result)
      setReportStatus('done')
    } catch {
      setReportStatus('idle')
    }
  }

  const handleToggleFavorite = () => {
    const newState = toggleFavorite({
      id: code,
      type: 'fund',
      name: fundData?.fund?.name || code,
      code: code,
    })
    setIsFav(newState)
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-slate-400 animate-pulse-subtle">加载中...</div>
      </div>
    )
  }

  if (!fundData?.fund) {
    return (
      <div className="p-8 text-center">
        <div className="text-slate-400 mb-4">未找到基金 {code}</div>
        <Link href="/funds" className="text-blue-600 hover:underline">返回基金列表</Link>
      </div>
    )
  }

  const { fund, performance, risk_metrics, style } = fundData
  const chartData = navData?.dates?.map((d: string, i: number) => ({
    date: d.substring(5),
    nav: navData.navs[i],
  })) || []

  const radarData = scoring?.dimensions?.map((d: any) => ({
    dimension: d.name,
    score: d.score,
    fullMark: 100,
  })) || []

  // 计算回撤数据
  const drawdownData = chartData.map((item: any, i: number) => {
    const navs = chartData.slice(0, i + 1).map((d: any) => d.nav)
    const maxNav = Math.max(...navs)
    const drawdown = ((item.nav - maxNav) / maxNav) * 100
    return { date: item.date, drawdown }
  })

  const tabs = [
    { key: 'overview', label: '概况', icon: BarChart3 },
    { key: 'performance', label: '业绩表现', icon: TrendingUp },
    { key: 'risk', label: '风险分析', icon: Shield },
    { key: 'holdings', label: '持仓明细', icon: PieChart },
    { key: 'report', label: 'AI 报告', icon: FileText },
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <Link href="/funds" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-blue-600 mb-3">
            <ArrowLeft className="w-4 h-4" /> 返回基金列表
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">{fund.name || code}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
            <span>{code}</span>
            <span>·</span>
            <span>{fund.type}</span>
            <span>·</span>
            <span>{fund.management_company}</span>
          </div>
        </div>
        {scoring && (
          <div className="flex items-center gap-4">
            <button
              onClick={handleToggleFavorite}
              className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                isFav ? 'bg-yellow-100 text-yellow-500' : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
              }`}
            >
              <Star className={`w-5 h-5 ${isFav ? 'fill-yellow-500' : ''}`} />
            </button>
            <ScoreGauge score={scoring.overall_score} size={100} grade={scoring.overall_grade} />
            <div className="text-right">
              <div className="text-xs text-slate-500">排名百分位</div>
              <div className="text-sm font-semibold">TOP {((1 - scoring.rank_percentile) * 100).toFixed(1)}%</div>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px
              ${activeTab === tab.key ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Performance Summary */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 col-span-2">
            <h3 className="font-semibold text-slate-900 mb-4">业绩概览</h3>
            <div className="grid grid-cols-4 gap-4 mb-6">
              {[
                { label: '近1年收益', value: performance?.annualized_return_1y, color: true },
                { label: '近3年收益', value: performance?.annualized_return_3y, color: true },
                { label: '夏普比率', value: performance?.sharpe_ratio, color: false },
                { label: '最大回撤', value: performance?.max_drawdown, color: false, suffix: '%' },
              ].map((item) => (
                <div key={item.label} className="bg-slate-50 rounded-lg p-4">
                  <div className="text-xs text-slate-500 mb-1">{item.label}</div>
                  <div className={`text-xl font-bold ${item.color ? (item.value >= 0 ? 'text-red-500' : 'text-green-500') : 'text-slate-900'}`}>
                    {item.value != null
                      ? item.suffix
                        ? `${(item.value * 100).toFixed(2)}%`
                        : item.value.toFixed(2)
                      : '-'}
                  </div>
                </div>
              ))}
            </div>
            {/* Nav Chart */}
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-slate-700">净值走势</h4>
              <div className="flex gap-1">
                {['1m', '3m', '6m', '1y', '3y', '5y'].map(period => (
                  <button
                    key={period}
                    onClick={() => setNavPeriod(period)}
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      navPeriod === period
                        ? 'bg-blue-500 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {period}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                  labelStyle={{ color: '#64748b' }}
                />
                <Area type="monotone" dataKey="nav" stroke="#0ea5e9" fill="#0ea5e9" fillOpacity={0.1} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Score Details */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">评分维度</h3>
              {scoring?.dimensions?.map((d: any) => (
                <div key={d.name} className="mb-3">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-slate-600">{d.name}</span>
                    <span className="font-semibold text-slate-900">{d.score.toFixed(1)}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${d.score}%`, backgroundColor: getScoreBarColor(d.score) }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">基本信息</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">基金经理</span><span>{fund.manager}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">成立日期</span><span>{fund.establishment_date}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">基金规模</span><span>{formatAsset(fund.total_asset)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">投资风格</span><span>{style?.style || '-'}</span></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'performance' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">收益指标</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={[
                  { name: '近1年', value: performance?.annualized_return_1y },
                  { name: '近3年', value: performance?.annualized_return_3y },
                ]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => [`${(v * 100).toFixed(2)}%`, '收益率']} />
                  <Bar dataKey="value" fill="#0ea5e9" radius={[4, 4, 0, 0]}
                    label={{ position: 'top', formatter: (v: number) => `${(v * 100).toFixed(1)}%` }} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">风险调整收益</h3>
              <div className="space-y-4">
                {[
                  { label: '夏普比率', value: performance?.sharpe_ratio, desc: '衡量单位风险的超额收益' },
                  { label: '索提诺比率', value: performance?.sortino, desc: '仅考虑下行风险' },
                  { label: '卡玛比率', value: performance?.calmar_ratio, desc: '年化收益/最大回撤' },
                  { label: '胜率', value: performance?.win_rate_1y, desc: '日收益为正的比例', suffix: '%' },
                ].map(item => (
                  <div key={item.label} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div>
                      <div className="text-sm font-medium text-slate-900">{item.label}</div>
                      <div className="text-xs text-slate-400">{item.desc}</div>
                    </div>
                    <div className="text-xl font-bold text-slate-900">
                      {item.value != null ? (item.suffix ? `${(item.value * 100).toFixed(1)}%` : item.value.toFixed(2)) : '-'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 回撤曲线图 */}
          {drawdownData.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">回撤曲线</h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={drawdownData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12 }}
                    formatter={(v: number) => [`${v.toFixed(2)}%`, '回撤']}
                  />
                  <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {activeTab === 'risk' && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
            <h3 className="font-semibold text-slate-900 mb-4">风险指标</h3>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: '年化波动率', value: risk_metrics?.volatility },
                { label: '最大回撤', value: risk_metrics?.max_drawdown, suffix: '%' },
                { label: 'VaR (95%)', value: risk_metrics?.var_95, suffix: '%' },
                { label: 'Beta', value: risk_metrics?.beta },
                { label: '跟踪误差', value: risk_metrics?.tracking_error },
              ].map(item => (
                <div key={item.label} className="bg-slate-50 rounded-lg p-4">
                  <div className="text-xs text-slate-500 mb-1">{item.label}</div>
                  <div className="text-lg font-bold text-slate-900">
                    {item.value != null ? (item.suffix ? `${(item.value * 100).toFixed(2)}%` : item.value.toFixed(3)) : '-'}
                  </div>
                </div>
              ))}
            </div>
          </div>
          {radarData.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="font-semibold text-slate-900 mb-4">雷达图</h3>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Radar name="评分" dataKey="score" stroke="#0ea5e9" fill="#0ea5e9" fillOpacity={0.2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {activeTab === 'holdings' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100">
          <div className="p-6 border-b border-slate-100">
            <h3 className="font-semibold text-slate-900">前十大持仓</h3>
            <div className="text-sm text-slate-500 mt-1">{holdings?.period || ''}</div>
          </div>
          {holdings?.stocks?.length > 0 ? (
            <table className="w-full">
              <thead>
                <tr className="text-xs text-slate-500 uppercase">
                  <th className="text-left px-6 py-3">股票代码</th>
                  <th className="text-left px-4 py-3">股票名称</th>
                  <th className="text-right px-4 py-3">持仓占比</th>
                  <th className="text-right px-4 py-3">持仓变化</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {holdings.stocks.map((s: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-6 py-3 text-sm text-slate-400">{s.code}</td>
                    <td className="px-4 py-3 font-medium text-slate-900">{s.name}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{(s.proportion * 100).toFixed(2)}%</td>
                    <td className={`px-4 py-3 text-right ${s.change >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {s.change >= 0 ? '+' : ''}{(s.change * 100).toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-12 text-center text-slate-400">暂无持仓数据</div>
          )}
        </div>
      )}

      {activeTab === 'report' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-8">
          <h3 className="font-semibold text-slate-900 mb-4">AI 分析报告</h3>
          <p className="text-sm text-slate-500 mb-6">
            基于基金历史业绩、持仓数据、风险指标及调研报告库，生成深度分析评价报告。
          </p>
          <button
            onClick={handleGenerateReport}
            disabled={reportStatus === 'generating'}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {reportStatus === 'generating' ? (
              <><RefreshCw className="w-4 h-4 animate-spin" /> 生成中...</>
            ) : reportStatus === 'done' ? (
              <><Activity className="w-4 h-4" /> 报告已生成</>
            ) : (
              <><FileText className="w-4 h-4" /> 生成 AI 分析报告</>
            )}
          </button>
        </div>
      )}
    </div>
  )
}

function getScoreBarColor(score: number): string {
  if (score >= 90) return '#22c55e'
  if (score >= 75) return '#0ea5e9'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

function formatAsset(value: number | undefined): string {
  if (!value) return '-'
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
  return value.toFixed(2)
}
