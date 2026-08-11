'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpenText,
  Bot,
  CalendarDays,
  ChartNoAxesCombined,
  CircleAlert,
  Database,
  GitCompareArrows,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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

export type FundNavPoint = {
  date: string
  nav: number
}

export type FundPeerMetric = {
  key: string
  label: string
  value: number | null
  unit: string
  percentile: number | null
  rank: number | null
  peerCount: number
  sampleStatus: string
  metricWindow: string
}

export type FundEvaluation = {
  status: string
  classificationStatus: string
  peerGroup: string
  peerGroupId: string
  benchmark: string
  strategyFamily: string
  activePassive: string
  confidence: number | null
  sampleStatus: string
  validPeerCount: number
  minimumPeerCount: number
  score: number | null
  grade: string
  dimensions: Array<{
    key: string
    score: number | null
    weight: number | null
  }>
  peerMetrics: FundPeerMetric[]
  positiveFactors: string[]
  negativeFactors: string[]
  missingItems: string[]
  dataQualityStatus: string
  dataQualityScore: number | null
}

export type FundResearchMemo = {
  id: string
  title: string
  managerName: string
  reportDate: string
  source: string
  summary: string
  classifications: string[]
  styleLabels: string[]
  keyPoints: string[]
}

type Props = {
  fund: CamelFund
  nav: FundNavPoint[]
  evaluation: FundEvaluation
  researchMemos: FundResearchMemo[]
}

const windows = [
  { value: '6m', label: '近 6 月', days: 190 },
  { value: '1y', label: '近 1 年', days: 370 },
  { value: '3y', label: '近 3 年', days: 1120 },
] as const

const dimensionLabels: Record<string, string> = {
  return: '收益能力',
  risk: '风险控制',
  risk_adjusted: '风险调整后收益',
  consistency: '表现稳定性',
  manager_tenure: '经理任期',
  tracking_quality: '跟踪质量',
  cost_efficiency: '成本效率',
  scale_liquidity: '规模与流动性',
  income_competitiveness: '收益竞争力',
  capital_preservation: '净值稳定性',
  income_stability: '收益稳定性',
  data_quality: '数据质量',
}

const activePassiveLabels: Record<string, string> = {
  active: '主动管理',
  passive: '被动跟踪',
  enhanced_index: '指数增强',
}

function humanizeFactor(value: string) {
  return Object.entries(dimensionLabels).reduce(
    (result, [key, label]) => result.replace(new RegExp(`\\b${key}\\b`, 'gu'), label),
    value,
  )
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN')
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

function metricValue(metric: FundPeerMetric) {
  if (metric.value == null) return '—'
  if (metric.unit === 'percent') return formatPercent(metric.value, 2)
  if (metric.unit === 'cny_100m') return formatAsset(metric.value)
  return metric.value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function chartWindow(nav: FundNavPoint[], days: number) {
  if (!nav.length) return []
  const lastDate = new Date(nav[nav.length - 1].date)
  if (Number.isNaN(lastDate.getTime())) return nav
  lastDate.setDate(lastDate.getDate() - days)
  const threshold = lastDate.toISOString().slice(0, 10)
  return nav.filter((point) => point.date >= threshold)
}

function scoreMessage(evaluation: FundEvaluation) {
  if (evaluation.classificationStatus !== 'classified') return '专业分类证据不足，暂不输出综合分。'
  return '评价数据尚未满足当前类别方法，暂不输出综合分。'
}

export default function SimpleFundDetailClient({ fund, nav, evaluation, researchMemos }: Props) {
  const [window, setWindow] = useState<(typeof windows)[number]['value']>('1y')
  const selectedWindow = windows.find((item) => item.value === window) || windows[1]
  const chartData = useMemo(() => chartWindow(nav, selectedWindow.days), [nav, selectedWindow.days])
  const typedFund = fund as SimpleFund
  const professionalScoreReady = evaluation.score != null
  const scoreIsPartial = evaluation.status === 'partial'
  const usablePeerMetrics = evaluation.peerMetrics.filter((metric) => metric.sampleStatus === 'sufficient' && metric.percentile != null)
  const manager = managerName(typedFund)
  const researchProfile = asRecord(fund.researchProfile)
  const managerTenureStart = typeof researchProfile.managerTenureStart === 'string'
    ? researchProfile.managerTenureStart
    : ''
  const classification = evaluation.peerGroup || '专业分类待确认'
  const benchmark = evaluation.benchmark || String(fund.benchmark || '') || '基准待补充'
  const analysisHref = `/analysis?${new URLSearchParams({ fundCode: fund.windCode }).toString()}`
  const attributionHref = `/analysis/advanced?${new URLSearchParams({ fundCode: fund.windCode }).toString()}`

  return (
    <div className="space-y-7">
      <section className="border-b border-[#dce1dc] pb-7">
        <Link href="/discover" className="inline-flex items-center gap-2 text-xs font-bold text-[#28745c]"><ArrowLeft className="h-4 w-4" />返回找基金</Link>
        <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs text-[#66726c]">
              <span className="font-bold text-[#28745c]">{classification}</span>
              <span>{fund.windCode}</span>
              <span>{fund.type || '类型待补充'}</span>
            </div>
            <h1 className="mt-3 break-words text-3xl font-bold leading-tight text-[#18231e] sm:text-4xl">{fund.name || fund.windCode}</h1>
            <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-sm text-[#65716b]">
              <span className="inline-flex items-center gap-2"><UserRound className="h-4 w-4 text-[#28745c]" />{manager}</span>
              {managerTenureStart ? <span>现任团队起点 {formatDate(managerTenureStart)}</span> : null}
              <span>{styleLabel(typedFund)}</span>
              <span>{activePassiveLabels[evaluation.activePassive] || evaluation.activePassive || '管理方式待确认'}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href={analysisHref} className="inline-flex h-11 items-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white hover:bg-[#225747]"><Bot className="h-4 w-4" />开始 AI 分析</Link>
            <Link href={attributionHref} className="inline-flex h-11 items-center gap-2 rounded-md border border-[#7fa18f] bg-[#edf4f0] px-5 text-sm font-bold text-[#245f4b] hover:bg-[#e2eee8]"><ChartNoAxesCombined className="h-4 w-4" />业绩归因</Link>
            <Link href="/discover" className="inline-flex h-11 items-center gap-2 rounded-md border border-[#bfc9c2] bg-white px-5 text-sm font-bold text-[#315e4d] hover:border-[#7fa18f]"><GitCompareArrows className="h-4 w-4" />找同类比较</Link>
          </div>
        </div>
      </section>

      <section className="grid overflow-hidden border border-[#dbe1dc] bg-white sm:grid-cols-2 xl:grid-cols-7">
        {[
          ['最新净值', fund.nav == null ? '—' : fund.nav.toFixed(4), formatDate(fund.navDate)],
          ['近 1 年收益', professionalScoreReady ? formatPercent(returnMetric(typedFund, '1y')) : '—', professionalScoreReady ? '基金数据口径' : '评价证据待补'],
          ['近 1 年最大回撤', professionalScoreReady ? formatPercent(drawdownMetric(typedFund, '1y')) : '—', professionalScoreReady ? '越小通常越稳' : '评价证据待补'],
          ['近 1 年年化波动', professionalScoreReady ? formatPercent(volatilityMetric(typedFund, '1y')) : '—', professionalScoreReady ? '波动幅度' : '评价证据待补'],
          ['近 1 年 Sharpe', professionalScoreReady ? sharpeMetric(typedFund, '1y')?.toFixed(2) || '—' : '—', professionalScoreReady ? '风险调整后收益' : '评价证据待补'],
          ['基金规模', formatAsset(fund.totalAsset), '单位：亿元'],
          ['成立日期', formatDate(fund.establishmentDate), '基础档案'],
        ].map(([label, value, note], index) => (
          <div key={label} className={`min-w-0 p-5 ${index ? 'border-t border-[#e4e8e4] sm:border-l sm:border-t-0' : ''} ${index > 1 ? 'sm:border-t xl:border-t-0' : ''} ${index > 0 && index % 2 === 0 ? 'sm:border-l-0 xl:border-l' : ''}`}>
            <div className="text-xs text-[#748079]">{label}</div>
            <div className="mt-2 break-words text-xl font-bold text-[#1d2923]">{value}</div>
            <div className="mt-2 text-[11px] text-[#919a95]">{note}</div>
          </div>
        ))}
      </section>

      <section className="grid gap-7 xl:grid-cols-[minmax(0,1.55fr)_minmax(20rem,0.75fr)]">
        <div className="border border-[#dbe1dc] bg-white p-4 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-bold"><ChartNoAxesCombined className="h-5 w-5 text-[#28745c]" />历史净值</h2>
              <p className="mt-1 text-xs leading-6 text-[#7a8580]">曲线来自基金真实净值，不使用模拟数据。</p>
            </div>
            <div className="inline-flex border border-[#cfd6d0] bg-[#f7f8f5] p-1">
              {windows.map((item) => (
                <button key={item.value} type="button" onClick={() => setWindow(item.value)} className={`h-8 px-3 text-xs font-bold ${window === item.value ? 'bg-[#173f35] text-white' : 'text-[#67736d]'}`}>{item.label}</button>
              ))}
            </div>
          </div>
          {professionalScoreReady && chartData.length ? (
            <div className="mt-6 h-[310px] w-full sm:h-[390px]">
              <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 320, height: 310 }}>
                <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: -12 }}>
                  <CartesianGrid stroke="#e6eae6" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" minTickGap={48} tick={{ fontSize: 11, fill: '#718078' }} tickLine={false} axisLine={false} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11, fill: '#718078' }} tickLine={false} axisLine={false} tickFormatter={(value) => Number(value).toFixed(2)} />
                  <Tooltip labelFormatter={(label) => formatDate(String(label))} formatter={(value) => [Number(value).toFixed(4), '净值']} />
                  <Line type="monotone" dataKey="nav" stroke="#176a52" strokeWidth={2.4} dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="mt-6 grid h-[310px] place-items-center border border-dashed border-[#cdd5cf] px-5 text-center text-sm text-[#79847e]">{professionalScoreReady ? '当前区间没有可用净值数据' : '净值序列尚未通过当前类别的评价证据门禁'}</div>}
        </div>

        <div className="border border-[#dbe1dc] bg-white">
          <div className="border-b border-[#e1e6e2] p-5">
            <div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><ShieldCheck className="h-4 w-4" />专业分类</div>
            <h2 className="mt-3 text-xl font-bold text-[#1c2923]">{classification}</h2>
            <dl className="mt-5 space-y-3 text-sm">
              <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3"><dt className="text-[#7b8680]">评价基准</dt><dd className="break-words font-medium">{benchmark}</dd></div>
              <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3"><dt className="text-[#7b8680]">策略类别</dt><dd className="break-words font-medium">{evaluation.strategyFamily || fund.type || '待确认'}</dd></div>
              <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3"><dt className="text-[#7b8680]">风格标签</dt><dd className="break-words font-medium">{styleLabel(typedFund)}</dd></div>
              <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3"><dt className="text-[#7b8680]">基金经理</dt><dd className="break-words font-medium">{manager}</dd></div>
            </dl>
          </div>
          <div className="p-5">
            <p className="text-xs leading-6 text-[#66726c]">系统先确定专业同类组，再选择该类别的指标和权重。不同类型基金不直接比分。</p>
          </div>
        </div>
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-3 pb-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold"><BarChart3 className="h-5 w-5 text-[#28745c]" />分类内专业评价</h2>
            <p className="mt-1 text-xs leading-6 text-[#7a8580]">基金自身评分使用当前类别的专用方法；同类样本不足时只停止分位排名。</p>
          </div>
          <div className="text-xs text-[#748079]">同类有效样本 {evaluation.validPeerCount || '—'} 只</div>
        </div>

        <div className="grid overflow-hidden border border-[#dbe1dc] bg-white lg:grid-cols-[18rem_minmax(0,1fr)]">
          <div className="border-b border-[#e0e5e1] p-6 lg:border-b-0 lg:border-r">
            {professionalScoreReady ? (
              <>
                <div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><span>类别方法评分</span>{scoreIsPartial ? <span className="rounded-sm bg-[#fff1d4] px-1.5 py-0.5 text-[10px] text-[#845f1d]">部分证据</span> : null}</div>
                <div className="mt-3 flex items-end gap-3"><strong className="text-5xl leading-none text-[#173f35]">{evaluation.score?.toFixed(1)}</strong><span className="pb-1 text-sm text-[#748079]">/ 100{evaluation.grade ? ` · ${evaluation.grade}` : ''}</span></div>
                <p className="mt-5 text-xs leading-6 text-[#66726c]">{scoreIsPartial ? '核心 1 年指标已参与评价，经理任期等辅助证据待补。' : '分数由当前基金类别的专用方法计算，AI 不参与改分。'}</p>
              </>
            ) : (
              <div className="flex gap-3 text-[#73541e]">
                <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" />
                <div><strong className="text-sm">暂不输出综合分</strong><p className="mt-2 text-xs leading-6">{scoreMessage(evaluation)}</p></div>
              </div>
            )}
          </div>

          <div className="min-w-0">
            {professionalScoreReady && evaluation.dimensions.length ? (
              <div className="grid gap-px border-b border-[#e0e5e1] bg-[#e4e8e4] sm:grid-cols-2 xl:grid-cols-3">
                {evaluation.dimensions.map((dimension) => (
                  <div key={dimension.key} className="bg-white p-5">
                    <div className="flex items-center justify-between gap-3 text-xs"><span className="font-bold">{dimensionLabels[dimension.key] || dimension.key}</span><span className="text-[#28745c]">{dimension.score == null ? '—' : dimension.score.toFixed(1)}</span></div>
                    <div className="mt-3 h-1.5 overflow-hidden bg-[#e5eae6]"><div className="h-full bg-[#3a8068]" style={{ width: `${Math.max(0, Math.min(100, dimension.score || 0))}%` }} /></div>
                    <div className="mt-2 text-[11px] text-[#8a948f]">权重 {dimension.weight == null ? '—' : formatPercent(dimension.weight, 0)}</div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="grid gap-6 p-5 sm:grid-cols-2 sm:p-6">
              <div>
                <h3 className="text-sm font-bold text-[#28654f]">已确认优势</h3>
                {evaluation.positiveFactors.length ? <ul className="mt-3 space-y-2 text-xs leading-6 text-[#536159]">{evaluation.positiveFactors.slice(0, 5).map((item) => <li key={item} className="flex gap-2"><span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#28745c]" />{humanizeFactor(item)}</li>)}</ul> : <p className="mt-3 text-xs leading-6 text-[#858f8a]">暂无足够证据归纳优势。</p>}
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#915248]">风险与待核对项</h3>
                {[...evaluation.negativeFactors, ...evaluation.missingItems].length ? <ul className="mt-3 space-y-2 text-xs leading-6 text-[#5e5b55]">{Array.from(new Set([...evaluation.negativeFactors, ...evaluation.missingItems])).slice(0, 5).map((item) => <li key={item} className="flex gap-2"><span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#a45d54]" />{humanizeFactor(item)}</li>)}</ul> : <p className="mt-3 text-xs leading-6 text-[#858f8a]">当前没有额外数据缺口。</p>}
              </div>
            </div>
          </div>
        </div>
      </section>

      {evaluation.sampleStatus !== 'sufficient' && professionalScoreReady ? (
        <section className="flex gap-3 border border-[#e4cc99] bg-[#fff8e8] px-5 py-4 text-sm text-[#73541e]">
          <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <div><strong>同类排名暂不可用</strong><p className="mt-1 text-xs leading-6">当前有效样本 {evaluation.validPeerCount} 只，最低需要 {evaluation.minimumPeerCount} 只。基金自身评分仍可查看，但不展示同类分位和排名。</p></div>
        </section>
      ) : null}

      {usablePeerMetrics.length ? (
        <section>
          <div className="pb-4">
            <h2 className="text-lg font-bold">同类位置</h2>
            <p className="mt-1 text-xs leading-6 text-[#7a8580]">百分位越高表示在该指标的同类排序越靠前；不跨类别比较。</p>
          </div>
          <div className="grid overflow-hidden border border-[#dbe1dc] bg-white sm:grid-cols-2 xl:grid-cols-4">
            {usablePeerMetrics.map((metric, index) => (
              <div key={metric.key} className={`p-5 ${index ? 'border-t border-[#e2e6e3] sm:border-l sm:border-t-0' : ''} ${index > 1 ? 'sm:border-t xl:border-t-0' : ''} ${index === 2 ? 'sm:border-l-0 xl:border-l' : ''}`}>
                <div className="text-xs font-bold text-[#59665f]">{metric.label}</div>
                <div className="mt-3 flex items-end justify-between gap-3"><strong className="text-2xl text-[#1d2923]">{metricValue(metric)}</strong><span className="text-xs font-bold text-[#28745c]">{metric.percentile?.toFixed(0)}%</span></div>
                <div className="mt-3 h-1.5 overflow-hidden bg-[#e4e9e5]"><div className="h-full bg-[#3a8068]" style={{ width: `${Math.max(0, Math.min(100, metric.percentile || 0))}%` }} /></div>
                <div className="mt-2 text-[11px] text-[#89938e]">同类第 {metric.rank || '—'} / {metric.peerCount || '—'} 名</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <div className="flex flex-wrap items-end justify-between gap-3 pb-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold"><BookOpenText className="h-5 w-5 text-[#28745c]" />相关调研纪要</h2>
            <p className="mt-1 text-xs leading-6 text-[#7a8580]">只显示已绑定当前基金代码的本地纪要。</p>
          </div>
          <Link href="/research" className="inline-flex items-center gap-1 text-xs font-bold text-[#28745c]">打开调研库<ArrowRight className="h-4 w-4" /></Link>
        </div>
        {researchMemos.length ? (
          <div className="divide-y divide-[#e0e5e1] border border-[#dbe1dc] bg-white">
            {researchMemos.map((memo) => (
              <article key={memo.id} className="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:p-6">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-x-4 gap-y-2 text-[11px] text-[#7a8580]"><span className="inline-flex items-center gap-1"><UserRound className="h-3.5 w-3.5" />{memo.managerName || manager}</span><span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{formatDate(memo.reportDate)}</span>{memo.source ? <span>{memo.source}</span> : null}</div>
                  <h3 className="mt-2 break-words text-sm font-bold text-[#1d2923]">{memo.title || '无标题纪要'}</h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-6 text-[#66726c]">{memo.summary || memo.keyPoints.join('；') || '该纪要暂无摘要。'}</p>
                </div>
                <div className="flex max-w-sm flex-wrap content-start gap-2 md:justify-end">
                  {[...memo.classifications, ...memo.styleLabels].slice(0, 5).map((tag, index) => <span key={`${tag}-${index}`} className="rounded-sm bg-[#edf1ed] px-2 py-1 text-[11px] text-[#53625b]">{tag}</span>)}
                </div>
              </article>
            ))}
          </div>
        ) : <div className="border border-dashed border-[#cbd3cd] bg-white px-6 py-10 text-center text-sm text-[#748079]">调研库中还没有绑定这只基金的纪要。</div>}
      </section>

      <section className="grid gap-3 border-t border-[#dce1dc] pt-6 md:grid-cols-3">
        <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><Database className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>基金档案、净值与指标均来自后端数据库。</span></div>
        <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>专业评分受分类与核心指标门禁约束；同类样本门禁只控制分位排名。</span></div>
        <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><BarChart3 className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>Barra 和 Brinson 只用于解释，不改变评分。</span></div>
      </section>
    </div>
  )
}
