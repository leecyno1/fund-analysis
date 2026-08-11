'use client'

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  BarChart3,
  BookOpenCheck,
  ChartNoAxesCombined,
  CircleAlert,
  Database,
  LoaderCircle,
  Play,
  ShieldCheck,
} from 'lucide-react'

type Status = 'ok' | 'partial_evidence' | 'insufficient_evidence' | 'not_applicable'

type BarraEvidence = {
  status?: Status
  formal_model_ready?: boolean
  quarter?: string
  factor_exposures?: Array<{ factor: string; exposure: number }>
  industry_exposures?: Record<string, number>
  risk_contributions?: Array<{ factor: string; factor_name?: string; risk_contribution?: number }>
  r_squared?: number | null
  holdings_count?: number
  holdings_disclosed_weight?: number
  missing_items?: string[]
}

type BrinsonEvidence = {
  status?: Status
  benchmark?: string
  period?: {
    quarter?: string
    start?: string
    end?: string
    holding_snapshot_quarter?: string
    benchmark_weight_date?: string
  }
  returns?: { fund?: number | null; benchmark?: number | null; active?: number | null }
  effects?: Array<{ name: string; label: string; value?: number | null }>
  industry_detail?: Array<{
    industry: string
    portfolio_weight: number
    benchmark_weight: number
    allocation_contrib: number
    selection_contrib: number
    interaction_contrib: number
  }>
  coverage?: {
    portfolio_holdings?: number
    benchmark_constituents?: number
    holding_returns?: number
  }
  missing_items?: string[]
}

type NavEvidence = {
  status?: 'ok' | 'insufficient_evidence'
  benchmark?: { label?: string; source?: string }
  returns?: { fund?: number | null; benchmark?: number | null; active?: number | null }
  effects?: Array<{ name: string; label: string; value: number }>
  missing_items?: string[]
}

type AttributionBundle = {
  status: Status
  quarter: string
  holding_snapshot_quarter: string
  benchmark?: string | null
  benchmark_source?: 'fund_classification_catalog' | 'fund_declared_benchmark_equity_component' | 'user_override' | 'missing_classification_benchmark' | 'missing_verifiable_attribution_benchmark'
  benchmark_detail?: { benchmark_name?: string; declared_weight?: number | null; declared_benchmark?: string; role?: string }
  fund?: { wind_code?: string; name?: string; type?: string }
  barra: BarraEvidence
  brinson: BrinsonEvidence
  nav_return_attribution: NavEvidence
}

const statusCopy: Record<Status, { label: string; tone: string }> = {
  ok: { label: '正式结果可用', tone: 'bg-[#e4f1ea] text-[#1f684e]' },
  partial_evidence: { label: '部分证据可用', tone: 'bg-[#fff3d8] text-[#815a16]' },
  insufficient_evidence: { label: '证据不足', tone: 'bg-[#f7e9e5] text-[#944f44]' },
  not_applicable: { label: '当前基金不适用', tone: 'bg-[#edf0ed] text-[#66726c]' },
}

function formatPercent(value?: number | null, digits = 2) {
  return value == null || Number.isNaN(value) ? '—' : `${(value * 100).toFixed(digits)}%`
}

function StatusBadge({ status = 'insufficient_evidence' }: { status?: Status }) {
  const copy = statusCopy[status]
  return <span className={`rounded-sm px-2.5 py-1 text-[11px] font-bold ${copy.tone}`}>{copy.label}</span>
}

function MissingEvidence({ items }: { items?: string[] }) {
  if (!items?.length) return null
  return (
    <div className="mt-4 border border-[#ead59f] bg-[#fff9ea] px-4 py-3 text-xs leading-6 text-[#73541c]">
      {items.map((item) => <div key={item}>• {item}</div>)}
    </div>
  )
}

export default function AttributionWorkspace({
  initialFundCode,
  initialBenchmark,
  initialQuarter,
  autoRun,
}: {
  initialFundCode: string
  initialBenchmark: string
  initialQuarter: string
  autoRun: boolean
}) {
  const [fundCode, setFundCode] = useState(initialFundCode)
  const [benchmark, setBenchmark] = useState(initialBenchmark)
  const [quarter, setQuarter] = useState(initialQuarter)
  const [result, setResult] = useState<AttributionBundle | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const hasAutoRun = useRef(false)

  const runAttribution = useCallback(async () => {
    const code = fundCode.trim().toUpperCase()
    if (!code) return
    setLoading(true)
    setError('')
    try {
      const query = new URLSearchParams({ benchmark, quarter })
      const response = await fetch(`/api/attribution/fund/${encodeURIComponent(code)}?${query.toString()}`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '业绩归因运行失败')
      setResult(payload)
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : '业绩归因运行失败')
    } finally {
      setLoading(false)
    }
  }, [benchmark, fundCode, quarter])

  useEffect(() => {
    if (!autoRun || hasAutoRun.current) return
    hasAutoRun.current = true
    void runAttribution()
  }, [autoRun, runAttribution])

  const industries = Object.entries(result?.barra.industry_exposures || {})
  const largestIndustry = Math.max(...industries.map(([, weight]) => weight), 0.01)
  const brinsonEffects = result?.brinson.effects || []
  const navEvidence = result?.nav_return_attribution

  return (
    <div className="space-y-7">
      <section className="border-b border-[#dce1dc] pb-7">
        <Link href="/analysis" className="inline-flex items-center gap-2 text-xs font-bold text-[#28745c]"><ArrowLeft className="h-4 w-4" />返回 AI 分析</Link>
        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-end">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-[#28745c]"><ChartNoAxesCombined className="h-4 w-4" />业绩归因</div>
            <h1 className="mt-3 text-3xl font-bold text-[#18231e] sm:text-4xl">收益和风险到底来自哪里</h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-[#65716b]">Barra 解释风格与风险暴露，Brinson 解释行业配置和选择效应。净值行为分析只作为补充，不冒充正式模型。</p>
          </div>
          <div className="grid grid-cols-3 gap-px overflow-hidden border border-[#dbe1dc] bg-[#dbe1dc] text-center text-[11px]">
            <div className="bg-white p-3"><BarChart3 className="mx-auto h-4 w-4 text-[#28745c]" /><span className="mt-2 block">Barra</span></div>
            <div className="bg-white p-3"><ShieldCheck className="mx-auto h-4 w-4 text-[#28745c]" /><span className="mt-2 block">Brinson</span></div>
            <div className="bg-white p-3"><BookOpenCheck className="mx-auto h-4 w-4 text-[#28745c]" /><span className="mt-2 block">证据门禁</span></div>
          </div>
        </div>
      </section>

      <section className="border border-[#dbe1dc] bg-white p-5 sm:p-6">
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_13rem_11rem_auto] md:items-end">
          <label className="block text-sm font-bold">基金代码<input value={fundCode} onChange={(event) => setFundCode(event.target.value)} className="mt-2 h-11 w-full rounded-md border border-[#cfd6d0] px-3 text-sm uppercase outline-none focus:border-[#28745c]" /></label>
          <label className="block text-sm font-bold">比较基准<select value={benchmark} onChange={(event) => setBenchmark(event.target.value)} className="mt-2 h-11 w-full rounded-md border border-[#cfd6d0] bg-white px-3 text-sm outline-none focus:border-[#28745c]"><option value="">自动使用基金分类基准</option><option value="000300.SH">沪深300</option><option value="000905.SH">中证500</option><option value="000852.SH">中证1000</option></select></label>
          <label className="block text-sm font-bold">归因季度<input value={quarter} onChange={(event) => setQuarter(event.target.value.toUpperCase())} placeholder="2026Q2" className="mt-2 h-11 w-full rounded-md border border-[#cfd6d0] px-3 text-sm uppercase outline-none focus:border-[#28745c]" /></label>
          <button type="button" onClick={() => void runAttribution()} disabled={loading} className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-[#173f35] px-5 text-sm font-bold text-white hover:bg-[#225747] disabled:opacity-50">{loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{loading ? '正在计算' : '运行业绩归因'}</button>
        </div>
        <p className="mt-3 text-xs leading-6 text-[#7a8580]">分析季度使用上一季度披露持仓，避免用期末持仓倒推已经发生的收益。</p>
      </section>

      {error ? <div className="border border-[#e5b8ad] bg-[#fff0ed] px-5 py-4 text-sm text-[#8b443a]"><CircleAlert className="mr-2 inline h-4 w-4" />{error}</div> : null}

      {result ? (
        <>
          <section className="grid overflow-hidden border border-[#dbe1dc] bg-white sm:grid-cols-4">
            <div className="p-5"><div className="text-xs text-[#748079]">基金</div><div className="mt-2 font-bold">{result.fund?.name || result.fund?.wind_code}</div><div className="mt-1 text-xs text-[#7a8580]">{result.fund?.wind_code} · {result.fund?.type}</div></div>
            <div className="border-t border-[#e3e7e4] p-5 sm:border-l sm:border-t-0"><div className="text-xs text-[#748079]">归因季度</div><div className="mt-2 font-bold">{result.quarter}</div><div className="mt-1 text-xs text-[#7a8580]">持仓快照 {result.holding_snapshot_quarter}</div></div>
            <div className="border-t border-[#e3e7e4] p-5 sm:border-l sm:border-t-0"><div className="text-xs text-[#748079]">基准</div><div className="mt-2 font-bold">{result.benchmark_detail?.benchmark_name || result.benchmark || '待补'}</div><div className="mt-1 text-xs text-[#7a8580]">{result.benchmark_source === 'user_override' ? '本次手动指定' : result.benchmark_source === 'fund_declared_benchmark_equity_component' ? `来自合同复合基准的权益成分${result.benchmark_detail?.declared_weight != null ? ` · ${formatPercent(result.benchmark_detail.declared_weight, 0)}` : ''}` : result.benchmark_source === 'fund_classification_catalog' ? '来自基金分类目录' : '缺少可核验的归因基准'}</div></div>
            <div className="border-t border-[#e3e7e4] p-5 sm:border-l sm:border-t-0"><div className="text-xs text-[#748079]">综合状态</div><div className="mt-3"><StatusBadge status={result.status} /></div></div>
          </section>

          <section className="grid gap-7 xl:grid-cols-2">
            <article className="border border-[#dbe1dc] bg-white p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-bold">Barra 风格与风险暴露</h2><p className="mt-1 text-xs leading-6 text-[#7a8580]">正式因子缺失时，只展示公开持仓行业暴露。</p></div><StatusBadge status={result.barra.status} /></div>
              <div className="mt-5 grid grid-cols-3 gap-px bg-[#e1e6e2] text-center text-xs"><div className="bg-[#f7f9f7] p-3"><div className="text-[#7b8680]">披露持仓</div><strong className="mt-1 block text-base">{result.barra.holdings_count || 0} 只</strong></div><div className="bg-[#f7f9f7] p-3"><div className="text-[#7b8680]">披露权重</div><strong className="mt-1 block text-base">{formatPercent(result.barra.holdings_disclosed_weight, 1)}</strong></div><div className="bg-[#f7f9f7] p-3"><div className="text-[#7b8680]">正式因子</div><strong className="mt-1 block text-base">{result.barra.formal_model_ready ? '可用' : '待接入'}</strong></div></div>
              {industries.length ? <div className="mt-5 space-y-3">{industries.slice(0, 10).map(([industry, weight]) => <div key={industry}><div className="mb-1 flex justify-between text-xs"><span className="font-bold text-[#4f5d56]">{industry}</span><span>{formatPercent(weight, 1)}</span></div><div className="h-2 bg-[#edf0ed]"><div className="h-full bg-[#3d826a]" style={{ width: `${Math.max(3, weight / largestIndustry * 100)}%` }} /></div></div>)}</div> : <div className="mt-5 border border-dashed border-[#cdd5cf] p-6 text-center text-sm text-[#7a8580]">暂无持仓行业暴露</div>}
              <MissingEvidence items={result.barra.missing_items} />
            </article>

            <article className="border border-[#dbe1dc] bg-white p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-bold">Brinson 行业归因</h2><p className="mt-1 text-xs leading-6 text-[#7a8580]">配置、选择、交互和未披露持仓残差。</p></div><StatusBadge status={result.brinson.status} /></div>
              <div className="mt-5 grid grid-cols-3 gap-px bg-[#e1e6e2] text-center text-xs"><div className="bg-[#f7f9f7] p-3"><div className="text-[#7b8680]">基金收益</div><strong className="mt-1 block text-base">{formatPercent(result.brinson.returns?.fund)}</strong></div><div className="bg-[#f7f9f7] p-3"><div className="text-[#7b8680]">基准收益</div><strong className="mt-1 block text-base">{formatPercent(result.brinson.returns?.benchmark)}</strong></div><div className="bg-[#f7f9f7] p-3"><div className="text-[#7b8680]">主动收益</div><strong className="mt-1 block text-base">{formatPercent(result.brinson.returns?.active)}</strong></div></div>
              {brinsonEffects.length ? <div className="mt-5 grid gap-3 sm:grid-cols-2">{brinsonEffects.map((effect) => <div key={effect.name} className="border border-[#e1e5e2] p-4"><div className="text-xs text-[#6c7872]">{effect.label}</div><div className={`mt-2 text-lg font-bold ${(effect.value || 0) >= 0 ? 'text-[#236c51]' : 'text-[#a04f43]'}`}>{formatPercent(effect.value)}</div></div>)}</div> : <div className="mt-5 border border-dashed border-[#cdd5cf] p-6 text-center text-sm text-[#7a8580]">当前无法输出配置与选择效应</div>}
              {result.brinson.coverage?.portfolio_holdings != null ? <div className="mt-5 text-xs leading-6 text-[#65716b]">持仓披露覆盖 {formatPercent(result.brinson.coverage.portfolio_holdings, 1)} · 持仓收益覆盖 {formatPercent(result.brinson.coverage.holding_returns, 1)} · 基准成分覆盖 {formatPercent(result.brinson.coverage.benchmark_constituents, 1)}</div> : null}
              <MissingEvidence items={result.brinson.missing_items} />
            </article>
          </section>

          <section className="border border-[#dbe1dc] bg-white p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">补充：净值行为解释</h2><p className="mt-1 text-xs leading-6 text-[#7a8580]">用净值与基准序列解释 Beta、主动收益和残差；这不是 Brinson。</p></div><span className="rounded-sm bg-[#edf0ed] px-2.5 py-1 text-[11px] font-bold text-[#66726c]">非正式 Brinson</span></div>
            {navEvidence?.status === 'ok' ? <div className="mt-5 grid gap-3 sm:grid-cols-4"><div className="bg-[#f6f8f6] p-4"><div className="text-xs text-[#748079]">主动收益</div><strong className="mt-2 block">{formatPercent(navEvidence.returns?.active)}</strong></div>{(navEvidence.effects || []).map((effect) => <div key={effect.name} className="bg-[#f6f8f6] p-4"><div className="text-xs text-[#748079]">{effect.label}</div><strong className="mt-2 block">{formatPercent(effect.value)}</strong></div>)}</div> : <MissingEvidence items={navEvidence?.missing_items || ['基金与基准的重叠净值序列不足。']} />}
          </section>

          <section className="grid gap-3 border-t border-[#dce1dc] pt-6 md:grid-cols-3">
            <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><Database className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>基金净值、公开持仓、指数权重和行情来自真实数据源。</span></div>
            <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>持仓披露不足时只输出部分证据，不给完整模型结论。</span></div>
            <div className="flex gap-3 text-xs leading-6 text-[#65716b]"><BarChart3 className="mt-1 h-4 w-4 shrink-0 text-[#28745c]" /><span>归因用于解释，不直接改变基金评价分数。</span></div>
          </section>
        </>
      ) : <div className="border border-dashed border-[#cbd3cd] bg-white px-6 py-14 text-center text-sm text-[#748079]">输入基金代码、基准和季度后现场运行，不批量预计算全市场。</div>}
    </div>
  )
}
