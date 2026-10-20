'use client'

import { useState } from 'react'
import { LoaderCircle, Sparkles, TriangleAlert } from 'lucide-react'

type QuarterEffect = {
  quarter: string
  dominant: string
  effects: { allocation: number; selection: number; interaction: number }
  residual: number | null
  residual_share: number | null
  portfolio_coverage: number | null
}

type AttributionConclusion = {
  status: 'available' | 'insufficient'
  reason?: string
  quarters_used?: number
  dominant_source_label?: string
  stability?: number
  sign_consistency?: number
  avg_residual_share?: number | null
  alpha_replicability_label?: string
  conclusion?: string
  quarters?: QuarterEffect[]
  errors?: { quarter: string; error: string }[]
  limitations?: string[]
}

const sourceLabels: Record<string, string> = {
  allocation: '行业配置',
  selection: '行业内选股',
  interaction: '交互',
}

function formatPercent(value: number | null | undefined, digits = 1) {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export default function FundAttributionConclusionPanel({ windCode }: { windCode: string }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState<AttributionConclusion | null>(null)

  const generate = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(
        `/api/funds/${encodeURIComponent(windCode)}/attribution-conclusion?quarters=4${data ? '&refresh=true' : ''}`,
        { cache: 'no-store' },
      )
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || payload.detail || '归因结论生成失败')
      setData(payload as AttributionConclusion)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-2xl border border-[#e3e0d5] bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#18231e]">归因结论（多季 Brinson）</h2>
          <p className="mt-1 text-xs text-[#68746e]">
            逐季拆解配置/选股/交互效应，回答"近几季主要靠什么赚钱、这种来源稳不稳定"。
            首次计算约 8 秒，之后缓存 1 小时；只解释历史，不进入评分。
          </p>
        </div>
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="inline-flex h-9 items-center gap-2 rounded-md bg-[#173f35] px-4 text-xs font-bold text-white hover:bg-[#225747] disabled:opacity-60"
        >
          {loading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          {data ? '刷新结论' : '生成归因结论'}
        </button>
      </div>

      {error ? <p className="mt-4 rounded-lg bg-[#fdf1ef] px-3 py-2 text-xs text-[#a84d47]">{error}</p> : null}

      {data?.status === 'insufficient' ? (
        <p className="mt-4 rounded-lg bg-[#fff9eb] px-3 py-2 text-xs leading-6 text-[#8d6a2f]">
          证据不足：{data.reason || '最近季度缺少可用的 Brinson 归因'}。债基/货币基金或持仓披露不足时不强行输出结论。
        </p>
      ) : null}

      {data?.status === 'available' ? (
        <div className="mt-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ['主贡献来源', data.dominant_source_label || '—'],
              ['主导稳定性', formatPercent(data.stability, 0)],
              ['方向一致率', formatPercent(data.sign_consistency, 0)],
              ['平均残差占比', formatPercent(data.avg_residual_share, 0)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-[#e3e8e4] bg-[#fafbf9] p-3">
                <div className="text-[11px] text-[#748079]">{label}</div>
                <div className="mt-1 text-base font-bold text-[#1d2923]">{value}</div>
              </div>
            ))}
          </div>
          <p className="text-sm leading-7 text-[#34433b]">{data.conclusion}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-[#68746e]">
            <span className="rounded-full bg-[#edf4f0] px-3 py-1 text-[#245f4b]">
              可复制性：{data.alpha_replicability_label || '—'}
            </span>
            <span>使用季度：{data.quarters_used ?? 0} 个</span>
          </div>
          {Array.isArray(data.quarters) && data.quarters.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-xs">
                <thead>
                  <tr className="border-b border-[#e3e8e4] text-left text-[#748079]">
                    <th className="px-2 py-2 font-medium">季度</th>
                    <th className="px-2 py-2 text-right font-medium">配置</th>
                    <th className="px-2 py-2 text-right font-medium">选股</th>
                    <th className="px-2 py-2 text-right font-medium">交互</th>
                    <th className="px-2 py-2 text-right font-medium">残差</th>
                    <th className="px-2 py-2 font-medium">主导</th>
                  </tr>
                </thead>
                <tbody>
                  {data.quarters.map((item) => (
                    <tr key={item.quarter} className="border-b border-[#eef1ee] last:border-0">
                      <td className="px-2 py-2 font-medium text-[#1d2923]">{item.quarter}</td>
                      <td className="px-2 py-2 text-right">{formatPercent(item.effects?.allocation)}</td>
                      <td className="px-2 py-2 text-right">{formatPercent(item.effects?.selection)}</td>
                      <td className="px-2 py-2 text-right">{formatPercent(item.effects?.interaction)}</td>
                      <td className="px-2 py-2 text-right">{formatPercent(item.residual)}</td>
                      <td className="px-2 py-2 text-[#245f4b]">{sourceLabels[item.dominant] || item.dominant}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {Array.isArray(data.errors) && data.errors.length ? (
            <p className="flex items-start gap-2 text-xs text-[#8d6a2f]">
              <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {data.errors.map((item) => `${item.quarter}: ${item.error}`).join('；')}
            </p>
          ) : null}
          {Array.isArray(data.limitations) && data.limitations.length ? (
            <p className="text-[11px] leading-5 text-[#8b958f]">{data.limitations[0]}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
