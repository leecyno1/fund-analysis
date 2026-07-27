'use client'

import { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, Users, Shield, FileText, ChevronRight, PieChart } from 'lucide-react'
import Link from 'next/link'
import { getLeaderboard, getResearchReports } from '@/lib/api'
import { BarChart, Bar, PieChart as RePieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function DashboardPage() {
  const [leaderboard, setLeaderboard] = useState<any>(null)
  const [stats, setStats] = useState({
    totalFunds: 0,
    totalManagers: 0,
    avgScore: 0,
    reportCount: 0,
  })
  const [scoreDistribution, setScoreDistribution] = useState<any[]>([])
  const [gradeDistribution, setGradeDistribution] = useState<any[]>([])
  const [typeDistribution, setTypeDistribution] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getLeaderboard(1, 50).catch(() => ({ rankings: [], total: 0 })),
      getResearchReports(1).catch(() => ({ reports: [], total: 0 })),
      fetch('/api/funds?page=1&page_size=1').then(r => r.json()).catch(() => ({ total: 0 })),
      fetch('/api/managers?page=1&page_size=1').then(r => r.json()).catch(() => ({ total: 0 })),
    ]).then(([lb, reports, fundsData, managersData]) => {
      setLeaderboard(lb)

      const scores = lb?.rankings?.map((r: any) => r.overall_score).filter((s: number) => s > 0) || []
      const avgScore = scores.length > 0 ? scores.reduce((a: number, b: number) => a + b, 0) / scores.length : 0

      setStats({
        totalFunds: fundsData.total || 0,
        totalManagers: managersData.total || 0,
        avgScore: avgScore,
        reportCount: reports.total || 0,
      })

      // 计算评分分布
      const scoreBuckets = [
        { range: '0-20', count: 0 },
        { range: '20-40', count: 0 },
        { range: '40-60', count: 0 },
        { range: '60-80', count: 0 },
        { range: '80-100', count: 0 },
      ]
      scores.forEach((score: number) => {
        if (score < 20) scoreBuckets[0].count++
        else if (score < 40) scoreBuckets[1].count++
        else if (score < 60) scoreBuckets[2].count++
        else if (score < 80) scoreBuckets[3].count++
        else scoreBuckets[4].count++
      })
      setScoreDistribution(scoreBuckets)

      // 计算评级分布
      const grades = lb?.rankings?.map((r: any) => r.grade).filter(Boolean) || []
      const gradeCount: Record<string, number> = {}
      grades.forEach((g: string) => {
        gradeCount[g] = (gradeCount[g] || 0) + 1
      })
      const gradeData = Object.entries(gradeCount).map(([grade, count]) => ({
        grade,
        count,
        percentage: ((count / grades.length) * 100).toFixed(1)
      }))
      setGradeDistribution(gradeData)

      // 计算基金类型分布
      const types = lb?.rankings?.map((r: any) => r.type).filter(Boolean) || []
      const typeCount: Record<string, number> = {}
      types.forEach((t: string) => {
        typeCount[t] = (typeCount[t] || 0) + 1
      })
      const typeData = Object.entries(typeCount).map(([type, count]) => ({
        type,
        count,
        percentage: ((count / types.length) * 100).toFixed(1)
      }))
      setTypeDistribution(typeData)

      setLoading(false)
    })
  }, [])

  const COLORS = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444']
  const GRADE_COLORS: Record<string, string> = {
    S: '#8b5cf6',
    A: '#10b981',
    B: '#3b82f6',
    C: '#f59e0b',
    D: '#fb923c',
    E: '#ef4444',
  }
  const TYPE_COLORS: Record<string, string> = {
    '股票型': '#3b82f6',
    '混合型': '#10b981',
    '债券型': '#f59e0b',
    '货币型': '#8b5cf6',
    '指数型': '#ef4444',
    'QDII': '#ec4899',
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900">基金评价系统</h1>
        <p className="text-slate-500 mt-1">基金经理综合评价 · 数据驱动筛选 · AI 深度分析</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        {[
          { label: '基金覆盖', value: stats.totalFunds > 0 ? stats.totalFunds.toLocaleString() : '-', icon: BarChart3, color: 'text-blue-600', bg: 'bg-blue-50' },
          { label: '基金经理', value: stats.totalManagers > 0 ? stats.totalManagers.toLocaleString() : '-', icon: Users, color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: '平均评分', value: stats.avgScore > 0 ? `${stats.avgScore.toFixed(1)}分` : '-', icon: TrendingUp, color: 'text-purple-600', bg: 'bg-purple-50' },
          { label: '调研报告', value: stats.reportCount > 0 ? stats.reportCount.toLocaleString() : '-', icon: FileText, color: 'text-orange-600', bg: 'bg-orange-50' },
        ].map((stat, i) => (
          <div key={i} className="bg-white rounded-xl p-6 shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className={`w-10 h-10 rounded-lg ${stat.bg} flex items-center justify-center`}>
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900">{stat.value}</div>
            <div className="text-sm text-slate-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {!loading && scoreDistribution.length > 0 && (
        <div className="grid grid-cols-3 gap-6 mb-8">
          {/* Score Distribution */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">评分分布</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={scoreDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="range" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                  labelStyle={{ color: '#475569', fontWeight: 600 }}
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Grade Distribution */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">评级分布</h3>
            <ResponsiveContainer width="100%" height={250}>
              <RePieChart>
                <Pie
                  data={gradeDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ grade, percentage }) => `${grade} (${percentage}%)`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {gradeDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={GRADE_COLORS[entry.grade] || COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                />
              </RePieChart>
            </ResponsiveContainer>
          </div>

          {/* Type Distribution */}
          {typeDistribution.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">基金类型分布</h3>
              <ResponsiveContainer width="100%" height={250}>
                <RePieChart>
                  <Pie
                    data={typeDistribution}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ type, percentage }) => `${type} (${percentage}%)`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="count"
                  >
                    {typeDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={TYPE_COLORS[entry.type] || COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
                  />
                </RePieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Quick Navigation */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { href: '/funds', title: '基金列表', desc: '搜索浏览所有基金', color: 'border-blue-200 hover:border-blue-400' },
          { href: '/managers', title: '基金经理', desc: '查看经理档案与评分', color: 'border-emerald-200 hover:border-emerald-400' },
          { href: '/screening', title: '基金筛选', desc: '多维度条件筛选', color: 'border-purple-200 hover:border-purple-400' },
        ].map((item) => (
          <Link key={item.href} href={item.href}
            className={`bg-white rounded-xl p-5 border-2 ${item.color} transition-all hover:shadow-md group`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">{item.title}</div>
                <div className="text-sm text-slate-500 mt-1">{item.desc}</div>
              </div>
              <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-blue-400 transition-colors" />
            </div>
          </Link>
        ))}
      </div>

      {/* Leaderboard */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100">
        <div className="p-6 border-b border-slate-100">
          <h2 className="text-lg font-semibold text-slate-900">综合评分排行 TOP 10</h2>
        </div>
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-slate-400">
              <div className="animate-pulse-subtle">加载中...</div>
            </div>
          ) : leaderboard?.rankings?.length > 0 ? (
            <table className="w-full">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left py-2 w-12">排名</th>
                  <th className="text-left py-2">基金名称</th>
                  <th className="text-left py-2 w-20">类型</th>
                  <th className="text-right py-2 w-20">综合评分</th>
                  <th className="text-right py-2 w-20">评级</th>
                  <th className="text-right py-2 w-24">近1年收益</th>
                  <th className="text-right py-2 w-20">夏普比率</th>
                  <th className="text-right py-2 w-24">最大回撤</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {leaderboard.rankings.slice(0, 10).map((item: any) => (
                  <tr key={item.rank} className="hover:bg-slate-50 transition-colors">
                    <td className="py-3">
                      <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold
                        ${item.rank <= 3 ? 'bg-yellow-100 text-yellow-700' : 'bg-slate-100 text-slate-600'}`}>
                        {item.rank}
                      </span>
                    </td>
                    <td className="py-3">
                      <Link href={`/funds/${item.wind_code}`} className="font-medium text-slate-900 hover:text-blue-600 transition-colors">
                        {item.name}
                      </Link>
                      <div className="text-xs text-slate-400">{item.wind_code}</div>
                    </td>
                    <td className="py-3 text-sm text-slate-600">{item.type}</td>
                    <td className="py-3 text-right font-bold text-slate-900">{item.overall_score?.toFixed(1)}</td>
                    <td className="py-3 text-right">
                      <GradeBadge grade={item.grade} />
                    </td>
                    <td className={`py-3 text-right font-medium ${item.return_1y >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {item.return_1y != null ? `${(item.return_1y >= 0 ? '+' : '')}${(item.return_1y * 100).toFixed(2)}%` : '-'}
                    </td>
                    <td className="py-3 text-right text-slate-700">{item.sharpe?.toFixed(2) || '-'}</td>
                    <td className="py-3 text-right text-red-500">
                      {item.max_drawdown != null ? `${(item.max_drawdown * 100).toFixed(2)}%` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-12 text-slate-400">暂无数据（请确保后端运行在 127.0.0.1:8005）</div>
          )}
        </div>
      </div>
    </div>
  )
}

function GradeBadge({ grade }: { grade: string }) {
  const colors: Record<string, string> = {
    S: 'bg-purple-500', A: 'bg-emerald-500', B: 'bg-blue-500',
    C: 'bg-yellow-500 text-black', D: 'bg-orange-500', E: 'bg-red-500',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold text-white ${colors[grade] || 'bg-gray-400'}`}>
      {grade}
    </span>
  )
}
