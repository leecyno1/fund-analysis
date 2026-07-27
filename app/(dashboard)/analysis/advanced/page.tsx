'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, BarChart3, BrainCircuit, Layers3, Loader2, Wand2 } from 'lucide-react'

type FactorLens = {
  fund?: { wind_code?: string; name?: string; type?: string }
  date_range?: { start?: string | null; end?: string | null; observations?: number }
  style_exposures?: Array<{ factor: string; label: string; exposure: number; direction: string }>
  risk_contributions?: Array<{ factor: string; label: string; risk_contribution: number; exposure: number }>
  factor_score?: number
  diagnostics?: string[]
  metrics?: Record<string, number | null>
  status?: 'ok' | 'insufficient_evidence'
  source?: string
  missing_items?: string[]
}

type Attribution = {
  benchmark?: { label?: string; source?: string }
  returns?: { fund?: number | null; benchmark?: number | null; active?: number | null }
  effects?: Array<{ name: string; label: string; value: number }>
  diagnostics?: Record<string, number | null>
  recommendations?: string[]
  status?: 'ok' | 'insufficient_evidence'
  source?: string
  missing_items?: string[]
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '暂无'
  return `${(value * 100).toFixed(2)}%`
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '暂无'
  return value.toFixed(2)
}

function barWidth(value: number) {
  return `${Math.max(2, Math.min(100, Math.abs(value) * 100))}%`
}

export default function AdvancedAnalysisPage() {
  const [fundCode, setFundCode] = useState('000002.OF')
  const [factorLens, setFactorLens] = useState<FactorLens | null>(null)
  const [attribution, setAttribution] = useState<Attribution | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [status, setStatus] = useState('')

  const loadFactorLens = async () => {
    const code = fundCode.trim()
    if (!code) return
    setLoading('factor')
    setStatus('正在读取因子镜头...')
    try {
      const response = await fetch(`/api/investment-analysis/fund/${encodeURIComponent(code)}/factor-lens`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '读取因子镜头失败')
      setFactorLens(payload)
      setStatus(payload.status === 'insufficient_evidence' ? '因子镜头证据不足：请先补齐净值/风格证据' : '因子镜头已生成')
    } catch (error) {
      setStatus(`错误：${error instanceof Error ? error.message : '读取因子镜头失败'}`)
    } finally {
      setLoading(null)
    }
  }

  const loadAttribution = async () => {
    const code = fundCode.trim()
    if (!code) return
    setLoading('attribution')
    setStatus('正在计算主动归因...')
    try {
      const response = await fetch(`/api/investment-analysis/fund/${encodeURIComponent(code)}/attribution`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '读取主动归因失败')
      setAttribution(payload)
      setStatus(payload.status === 'insufficient_evidence' ? '主动归因证据不足：请先补齐基准或同类收益序列' : '主动归因已生成')
    } catch (error) {
      setStatus(`错误：${error instanceof Error ? error.message : '读取主动归因失败'}`)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Link href="/analysis" className="inline-flex items-center text-gray-600 hover:text-gray-900">
        <ArrowLeft className="mr-2 h-4 w-4" />
        返回基金研究
      </Link>

      <div className="overflow-hidden rounded-3xl bg-slate-950 shadow-xl">
        <div className="relative p-7 text-white md:p-9">
          <div className="absolute -right-12 -top-12 h-52 w-52 rounded-full bg-cyan-400/20 blur-3xl" />
          <div className="absolute bottom-0 left-1/3 h-40 w-40 rounded-full bg-blue-400/10 blur-3xl" />
          <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs text-cyan-100 ring-1 ring-white/10">
                <BrainCircuit className="h-3.5 w-3.5" />
                高级基金研究
              </div>
              <h1 className="mt-4 text-3xl font-bold tracking-tight">因子镜头 · 主动归因</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                专注单只基金研究：解释风格暴露、风险来源、主动收益结构和研究复核提示，不进入组合配置或下游流程。
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-center text-xs">
              <div className="rounded-2xl bg-white/10 p-4 ring-1 ring-white/10">Factor Lens</div>
              <div className="rounded-2xl bg-white/10 p-4 ring-1 ring-white/10">Attribution</div>
            </div>
          </div>
        </div>
      </div>

      {status ? (
        <div className={`rounded-2xl border px-4 py-3 text-sm ${status.startsWith('错误') ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-blue-200 bg-blue-50 text-blue-800'}`}>
          {status}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <section className="rounded-2xl bg-white p-6 shadow">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900">单基金研究对象</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium text-gray-700">基金代码</span>
            <input
              value={fundCode}
              onChange={(event) => setFundCode(event.target.value)}
              className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <div className="mt-4 grid grid-cols-1 gap-2">
            <button
              type="button"
              onClick={() => void loadFactorLens()}
              disabled={loading !== null}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-blue-300"
            >
              {loading === 'factor' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Layers3 className="h-4 w-4" />}
              生成因子镜头
            </button>
            <button
              type="button"
              onClick={() => void loadAttribution()}
              disabled={loading !== null}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-slate-400"
            >
              {loading === 'attribution' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
              生成主动归因
            </button>
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600">
            输出定位：基金研究证据，不承担组合配置、正式研究结论或审批职责。
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <div className="rounded-2xl bg-white p-6 shadow">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">因子镜头</h2>
                <p className="mt-1 text-sm text-gray-500">风格暴露、风险贡献和研究诊断。</p>
              </div>
              <div className="text-right">
                <div className="text-3xl font-bold text-blue-700">{formatNumber(factorLens?.factor_score)}</div>
                <div className="text-xs text-gray-500">{factorLens?.status === 'insufficient_evidence' ? '证据不足' : '因子分'}</div>
              </div>
            </div>
            {factorLens?.status === 'insufficient_evidence' ? (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                暂不输出正式因子分：{(factorLens.missing_items || ['关键证据待补']).join('；')}
              </div>
            ) : null}
            <div className="mt-5 space-y-3">
              {(factorLens?.style_exposures || []).map((item) => (
                <div key={item.factor}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-medium text-gray-700">{item.label}</span>
                    <span className="font-mono text-gray-500">{item.exposure.toFixed(3)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-100">
                    <div className="h-2 rounded-full bg-blue-500" style={{ width: barWidth(item.exposure) }} />
                  </div>
                </div>
              ))}
            </div>
            <ul className="mt-5 space-y-2 text-sm text-gray-700">
              {(factorLens?.diagnostics || ['暂无因子结果，请先生成因子镜头。']).map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </div>

          <div className="rounded-2xl bg-white p-6 shadow">
            <h2 className="text-lg font-semibold text-gray-900">主动归因</h2>
            <p className="mt-1 text-sm text-gray-500">基准：{attribution?.benchmark?.label || '未生成'} · {attribution?.benchmark?.source || '-'}</p>
            {attribution?.status === 'insufficient_evidence' ? (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                暂不输出主动归因结论：{(attribution.missing_items || ['基准证据待补']).join('；')}
              </div>
            ) : null}
            <div className="mt-4 grid grid-cols-3 gap-3 text-center text-sm">
              <div className="rounded-xl bg-gray-50 p-3">
                <div className="text-gray-500">基金收益</div>
                <div className="mt-1 font-semibold text-gray-900">{formatPercent(attribution?.returns?.fund)}</div>
              </div>
              <div className="rounded-xl bg-gray-50 p-3">
                <div className="text-gray-500">基准收益</div>
                <div className="mt-1 font-semibold text-gray-900">{formatPercent(attribution?.returns?.benchmark)}</div>
              </div>
              <div className="rounded-xl bg-gray-50 p-3">
                <div className="text-gray-500">主动收益</div>
                <div className="mt-1 font-semibold text-gray-900">{formatPercent(attribution?.returns?.active)}</div>
              </div>
            </div>
            <div className="mt-5 space-y-3">
              {(attribution?.effects || []).map((item) => (
                <div key={item.name} className="rounded-xl border border-gray-200 p-3">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium text-gray-700">{item.label}</span>
                    <span className={item.value >= 0 ? 'text-emerald-700' : 'text-rose-700'}>{formatPercent(item.value)}</span>
                  </div>
                </div>
              ))}
            </div>
            <ul className="mt-5 space-y-2 text-sm text-gray-700">
              {(attribution?.recommendations || ['暂无归因结果，请先生成主动归因。']).map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </div>
        </section>
      </div>
    </div>
  )
}
