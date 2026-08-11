'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { ArrowLeft, BarChart3, CircleAlert, ExternalLink, GitCompareArrows } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CamelFund } from '@/lib/backend-api'
import {
  asRecord,
  drawdownMetric,
  formatAsset,
  formatPercent,
  managerName,
  numberValue,
  returnMetric,
  sharpeMetric,
  styleLabel,
  type SimpleFund,
  windowMetrics,
} from '@/lib/simple-fund-view'

type NavPoint = { date: string; nav: number }

export type ComparisonFund = {
  fund: CamelFund
  nav: NavPoint[]
  classification: {
    status: string
    peerGroup: string
    peerGroupId: string
    benchmark: string
  }
  evaluation: {
    status: string
    sampleStatus: string
    validPeerCount: number
    minimumPeerCount: number
    score: number | null
    grade: string
  }
}

const colors = ['#176a52', '#a45d45', '#6b7334', '#2e6284', '#7b5384', '#8a702e']
const windows = [
  { value: '6m', label: '近 6 月', days: 190 },
  { value: '1y', label: '近 1 年', days: 370 },
  { value: '3y', label: '近 3 年', days: 1120 },
] as const

function normalizedChartData(funds: ComparisonFund[], days: number) {
  const threshold = new Date()
  threshold.setDate(threshold.getDate() - days)
  const startDate = threshold.toISOString().slice(0, 10)
  const merged = new Map<string, Record<string, string | number>>()

  for (const item of funds) {
    const rows = item.nav.filter((row) => row.date >= startDate)
    const base = rows[0]?.nav
    if (!base) continue
    for (const row of rows) {
      const point = merged.get(row.date) || { date: row.date }
      point[item.fund.windCode] = Number(((row.nav / base) * 100).toFixed(2))
      merged.set(row.date, point)
    }
  }
  return Array.from(merged.values()).sort((left, right) => String(left.date).localeCompare(String(right.date)))
}

function volatilityMetric(fund: SimpleFund, window: string) {
  const rolling = windowMetrics(fund, window)
  const risk = asRecord(fund.riskMetrics)
  return numberValue(
    rolling.annualized_volatility,
    risk[`annualized_volatility_${window}`],
    risk[`volatility_${window}`],
  )
}

export default function SimpleComparisonClient({ funds }: { funds: ComparisonFund[] }) {
  const [window, setWindow] = useState<(typeof windows)[number]['value']>('1y')
  const selectedWindow = windows.find((item) => item.value === window) || windows[1]
  const peerGroupIds = Array.from(new Set(funds.map((item) => item.classification.peerGroupId).filter(Boolean)))
  const fullyClassified = funds.every((item) => item.classification.status === 'classified' && item.classification.peerGroupId)
  const comparable = fullyClassified && peerGroupIds.length === 1
  const chartData = useMemo(() => normalizedChartData(funds, selectedWindow.days), [funds, selectedWindow.days])
  const peerGroup = comparable ? funds[0].classification.peerGroup : ''

  return (
    <div className="space-y-7">
      <section className="border-b border-[#dce1dc] pb-7">
        <Link href="/discover" className="inline-flex items-center gap-2 text-xs font-bold text-[#28745c]"><ArrowLeft className="h-4 w-4" />返回基金浏览器</Link>
        <div className="mt-5 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-xs font-bold uppercase text-[#28745c]"><GitCompareArrows className="h-4 w-4" />基金比较</div>
            <h1 className="mt-3 text-3xl font-bold leading-tight text-[#18231e] sm:text-4xl">只在同类基金之间比较</h1>
            <p className="mt-3 text-sm leading-7 text-[#65716b] sm:text-base">先用专业分类确认同类组，再比较净值、收益和风险。量化结果用于研究，不生成买卖或仓位建议。</p>
          </div>
          <div className="text-sm text-[#66726c]">已选 {funds.length} / 6 只</div>
        </div>
      </section>

      {!comparable ? (
        <section className="border border-[#e1c890] bg-[#fff8e8] p-5 text-[#73541e]">
          <div className="flex gap-3">
            <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <h2 className="font-bold">这些基金不在同一个专业同类组</h2>
              <p className="mt-2 text-sm leading-7">系统已停止横向指标和净值比较。请返回基金浏览器，选择分类一致的基金。</p>
            </div>
          </div>
        </section>
      ) : (
        <section className="flex flex-wrap items-center gap-3 border-l-4 border-[#2b775d] bg-[#eef5f1] px-5 py-4 text-sm text-[#2b5e4c]">
          <strong>{peerGroup}</strong>
          <span>同类组校验通过</span>
          <span className="text-[#6d7a74]">基准：{funds[0].classification.benchmark || '待补充'}</span>
        </section>
      )}

      <section className="overflow-x-auto border border-[#dbe1dc] bg-white">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="bg-[#f1f4f1] text-xs text-[#66726c]">
            <tr>
              <th className="px-4 py-3">基金</th>
              <th className="px-4 py-3">专业同类组</th>
              <th className="px-4 py-3">风格</th>
              <th className="px-4 py-3">经理</th>
              <th className="px-4 py-3 text-right">专业评分</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5e9e5]">
            {funds.map((item, index) => (
              <tr key={item.fund.windCode}>
                <td className="px-4 py-4">
                  <Link href={`/funds/${encodeURIComponent(item.fund.windCode)}`} className="inline-flex items-center gap-1 font-bold text-[#1d2a24] hover:text-[#28745c]">
                    <span className="mr-1 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colors[index] }} />
                    {item.fund.name || item.fund.windCode}<ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                  <div className="mt-1 text-xs text-[#78837d]">{item.fund.windCode}</div>
                </td>
                <td className="px-4 py-4">{item.classification.peerGroup || '分类待确认'}</td>
                <td className="px-4 py-4">{styleLabel(item.fund)}</td>
                <td className="px-4 py-4">{managerName(item.fund)}</td>
                <td className="px-4 py-4 text-right font-bold text-[#28654f]">
                  {item.evaluation.score == null ? '—' : item.evaluation.score.toFixed(1)}
                  {item.evaluation.score != null && item.evaluation.status === 'partial' ? <span className="mt-1 block text-[10px] font-normal text-[#987235]">部分证据</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {comparable ? (
        <>
          <section className="border border-[#dbe1dc] bg-white p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-bold"><BarChart3 className="h-5 w-5 text-[#28745c]" />归一化净值</h2>
                <p className="mt-1 text-xs text-[#7a8580]">各基金区间首日设为 100，便于比较走势；曲线来自真实净值。</p>
              </div>
              <div className="inline-flex border border-[#cfd6d0] bg-[#f7f8f5] p-1">
                {windows.map((item) => (
                  <button key={item.value} type="button" onClick={() => setWindow(item.value)} className={`h-8 px-3 text-xs font-bold ${window === item.value ? 'bg-[#173f35] text-white' : 'text-[#67736d]'}`}>{item.label}</button>
                ))}
              </div>
            </div>
            {chartData.length ? (
              <div className="mt-6 h-[320px] w-full sm:h-[390px]">
                <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 320, height: 320 }}>
                  <LineChart data={chartData} margin={{ top: 6, right: 8, bottom: 6, left: -16 }}>
                    <CartesianGrid stroke="#e6eae6" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" minTickGap={48} tick={{ fontSize: 11, fill: '#718078' }} tickLine={false} axisLine={false} />
                    <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11, fill: '#718078' }} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(value) => [`${Number(value).toFixed(2)}`, '归一化净值']} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {funds.map((item, index) => <Line key={item.fund.windCode} dataKey={item.fund.windCode} name={item.fund.name || item.fund.windCode} stroke={colors[index]} strokeWidth={2} dot={false} connectNulls />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <div className="mt-6 grid h-64 place-items-center border border-dashed border-[#cdd5cf] text-sm text-[#79847e]">当前区间没有可用净值数据</div>}
          </section>

          <section>
            <div className="pb-4">
              <h2 className="text-lg font-bold">核心指标</h2>
              <p className="mt-1 text-xs text-[#7a8580]">指标窗口与上方时间选择一致；缺失数据不会估算补齐。</p>
            </div>
            <div className="overflow-x-auto border border-[#dbe1dc] bg-white">
              <table className="w-full min-w-[820px] border-collapse text-left text-sm">
                <thead className="bg-[#f1f4f1] text-xs text-[#66726c]">
                  <tr>
                    <th className="px-4 py-3">基金</th>
                    <th className="px-4 py-3 text-right">区间收益</th>
                    <th className="px-4 py-3 text-right">最大回撤</th>
                    <th className="px-4 py-3 text-right">年化波动</th>
                    <th className="px-4 py-3 text-right">Sharpe</th>
                    <th className="px-4 py-3 text-right">规模</th>
                    <th className="px-4 py-3 text-right">同类有效样本</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#e5e9e5]">
                  {funds.map((item) => {
                    const fund = item.fund as SimpleFund
                    return (
                      <tr key={item.fund.windCode}>
                        <td className="px-4 py-4 font-bold">{item.fund.name || item.fund.windCode}</td>
                        <td className="px-4 py-4 text-right">{formatPercent(returnMetric(fund, window))}</td>
                        <td className="px-4 py-4 text-right text-[#984f48]">{formatPercent(drawdownMetric(fund, window))}</td>
                        <td className="px-4 py-4 text-right">{formatPercent(volatilityMetric(fund, window))}</td>
                        <td className="px-4 py-4 text-right">{sharpeMetric(fund, window)?.toFixed(2) || '—'}</td>
                        <td className="px-4 py-4 text-right">{formatAsset(item.fund.totalAsset)}</td>
                        <td className="px-4 py-4 text-right">{item.evaluation.validPeerCount || '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}
