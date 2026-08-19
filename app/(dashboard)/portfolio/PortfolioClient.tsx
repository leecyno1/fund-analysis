'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  BadgeCheck,
  GitCompareArrows,
  Layers,
  LoaderCircle,
  Plus,
  RefreshCw,
  Scale,
  Trash2,
} from 'lucide-react'

type PortfolioListItem = {
  id: string
  name: string
  objective: string | null
  status: string
  holding_count: number
  total_weight: number | string | null
}

type Holding = {
  wind_code: string
  fund_name: string | null
  weight: number | string | null
  weight_source: string | null
  note: string | null
  evaluation: {
    overall_score: number | null
    grade: string | null
    evaluated_at: string | null
  } | null
}

type Target = {
  peer_group_key: string
  peer_group_name: string | null
  target_weight: number | string
}

type PortfolioDetail = {
  id: string
  name: string
  objective: string | null
  status: string
  targets: Target[]
  holdings: Holding[]
  weight_summary: {
    holding_count: number
    weighted_count: number
    total_weight: number
    is_complete: boolean
  }
}

type Analysis = {
  holding_count: number
  weights: Record<string, number>
  overlap: {
    status: string
    reason?: string
    pairs?: Array<{
      fund_a: string
      fund_b: string
      overlap_ratio: number | null
      similarity_level: string | null
      quarter: string | null
      common_holding_count?: number | null
    }>
  }
  style_aggregate: {
    status: string
    coverage: number
    coverage_note?: string
    reason?: string
    factors?: Array<{ factor: string; label: string; unit: string | null; weighted_exposure: number }>
  }
  correlation: {
    status: string
    lookback_days: number
    reason?: string
    pairs?: Array<{ fund_a: string; fund_b: string; correlation: number | null; overlap_days: number; status: string }>
  }
  boundary: string
}

const card = 'rounded-xl border border-[#d9ded9] bg-white p-4 shadow-sm'
const label = 'text-xs font-semibold text-[#5c6b61]'
const button = 'rounded-lg border border-[#c8d4cb] bg-white px-3 py-1.5 text-sm text-[#1f2d26] transition hover:bg-[#eef3ef] disabled:opacity-50'
const primaryButton = 'rounded-lg bg-[#28745c] px-3 py-1.5 text-sm font-medium text-white transition hover:bg-[#1f5d49] disabled:opacity-50'

function pct(value: number | string | null | undefined): string {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `${(num * 100).toFixed(1)}%`
}

export default function PortfolioClient() {
  const [portfolios, setPortfolios] = useState<PortfolioListItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<PortfolioDetail | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [newName, setNewName] = useState('')
  const [addCode, setAddCode] = useState('')
  const [weightDraft, setWeightDraft] = useState<Record<string, string>>({})

  const loadPortfolios = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/portfolios', { cache: 'no-store' })
      const payload = await response.json()
      setPortfolios(payload.data || [])
      if (!selectedId && (payload.data || []).length) {
        setSelectedId(payload.data[0].id)
      }
    } catch (exc) {
      setError(`组合列表加载失败: ${exc}`)
    } finally {
      setLoading(false)
    }
  }, [selectedId])

  const loadDetail = useCallback(async (portfolioId: string) => {
    setLoading(true)
    setError('')
    try {
      const [detailResponse, analysisResponse] = await Promise.all([
        fetch(`/api/portfolios/${portfolioId}`, { cache: 'no-store' }),
        fetch(`/api/portfolios/${portfolioId}/analysis`, { cache: 'no-store' }),
      ])
      if (detailResponse.ok) {
        const payload = await detailResponse.json()
        setDetail(payload)
        setWeightDraft(
          Object.fromEntries(
            (payload.holdings || []).map((item: Holding) => [
              item.wind_code,
              item.weight != null ? (Number(item.weight) * 100).toFixed(1) : '',
            ]),
          ),
        )
      } else {
        setDetail(null)
      }
      setAnalysis(analysisResponse.ok ? await analysisResponse.json() : null)
    } catch (exc) {
      setError(`组合详情加载失败: ${exc}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadPortfolios()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId)
  }, [selectedId, loadDetail])

  const createPortfolio = async () => {
    const name = newName.trim()
    if (!name) return
    try {
      const response = await fetch('/api/portfolios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || '创建失败')
      setNewName('')
      setNotice(`组合「${name}」已创建，请在详情中添加持仓。`)
      await loadPortfolios()
      setSelectedId(payload.id)
    } catch (exc) {
      setError(`创建组合失败: ${exc}`)
    }
  }

  const addHolding = async () => {
    const code = addCode.trim().toUpperCase()
    if (!code || !selectedId) return
    try {
      const response = await fetch(`/api/portfolios/${selectedId}/holdings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wind_code: code }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || '添加失败')
      setAddCode('')
      setNotice(`${code} 已加入组合。`)
      await loadDetail(selectedId)
      await loadPortfolios()
    } catch (exc) {
      setError(`添加持仓失败: ${exc}`)
    }
  }

  const removeHolding = async (code: string) => {
    if (!selectedId) return
    try {
      const response = await fetch(`/api/portfolios/${selectedId}/holdings/${encodeURIComponent(code)}`, { method: 'DELETE' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || '移除失败')
      setNotice(`${code} 已移出组合。`)
      await loadDetail(selectedId)
      await loadPortfolios()
    } catch (exc) {
      setError(`移除持仓失败: ${exc}`)
    }
  }

  const applyEqualWeights = async () => {
    if (!selectedId) return
    try {
      const response = await fetch(`/api/portfolios/${selectedId}/weights/equal`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || '等权失败')
      setNotice('已按等权设置全部持仓。')
      await loadDetail(selectedId)
    } catch (exc) {
      setError(`等权失败: ${exc}`)
    }
  }

  const saveCustomWeights = async () => {
    if (!selectedId || !detail) return
    const items = detail.holdings
      .map((item) => ({ wind_code: item.wind_code, weight: Number(weightDraft[item.wind_code]) / 100 }))
      .filter((item) => Number.isFinite(item.weight))
    try {
      const response = await fetch(`/api/portfolios/${selectedId}/weights`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items, source: 'custom' }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || '保存失败')
      setNotice('自定义权重已保存。')
      await loadDetail(selectedId)
    } catch (exc) {
      setError(`保存权重失败: ${exc}`)
    }
  }

  const overlapPairs = analysis?.overlap?.pairs || []
  const correlationPairs = analysis?.correlation?.pairs || []
  const styleFactors = analysis?.style_aggregate?.factors || []

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-[#1f2d26]">
            <Layers className="h-5 w-5 text-[#28745c]" aria-hidden="true" />
            基金组合
          </h1>
          <p className="mt-1 text-sm text-[#5c6b61]">
            研究型组合：目标配置 → 推荐就绪候选 → 等权/自定义权重 → 持仓穿透。不执行交易，不构成投资建议。
          </p>
        </div>
        <button type="button" className={button} onClick={() => (selectedId ? loadDetail(selectedId) : loadPortfolios())}>
          <RefreshCw className="mr-1 inline h-4 w-4" aria-hidden="true" />
          刷新
        </button>
      </header>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800" role="alert">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => setError('')}>关闭</button>
        </div>
      ) : null}
      {notice ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-900" role="status">
          {notice}
          <button type="button" className="ml-2 underline" onClick={() => setNotice('')}>关闭</button>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className={card}>
          <h2 className={label}>组合列表</h2>
          <div className="mt-2 flex gap-2">
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="新组合名称"
              className="min-w-0 flex-1 rounded-lg border border-[#c8d4cb] px-2 py-1.5 text-sm"
            />
            <button type="button" className={primaryButton} onClick={createPortfolio} disabled={!newName.trim()}>
              <Plus className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <ul className="mt-3 space-y-1">
            {portfolios.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                    selectedId === item.id ? 'bg-[#e7f0ea] font-medium text-[#1f2d26]' : 'text-[#3d5347] hover:bg-[#f2f6f3]'
                  }`}
                >
                  <span className="block truncate">{item.name}</span>
                  <span className="mt-0.5 block text-xs text-[#748079]">
                    {item.holding_count} 只持仓 · 权重 {pct(item.total_weight)}
                  </span>
                </button>
              </li>
            ))}
            {!portfolios.length && !loading ? (
              <li className="rounded-lg bg-[#f7f9f8] px-3 py-3 text-sm text-[#748079]">暂无组合，先创建一个。</li>
            ) : null}
          </ul>
        </aside>

        <section className="space-y-4">
          {!detail ? (
            <div className={`${card} text-sm text-[#748079]`}>
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                  加载中…
                </span>
              ) : (
                '选择或创建一个组合开始构建。'
              )}
            </div>
          ) : (
            <>
              <div className={card}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="text-lg font-bold text-[#1f2d26]">{detail.name}</h2>
                    {detail.objective ? <p className="mt-1 text-sm text-[#5c6b61]">{detail.objective}</p> : null}
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <BadgeCheck className="h-4 w-4 text-[#28745c]" aria-hidden="true" />
                    {detail.weight_summary.is_complete ? (
                      <span className="text-emerald-800">权重已配置（{pct(detail.weight_summary.total_weight)}）</span>
                    ) : (
                      <span className="text-amber-700">权重未配齐（{pct(detail.weight_summary.total_weight)}），穿透暂按等权</span>
                    )}
                  </div>
                </div>
                {detail.targets.length ? (
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[#e4e9e5] text-left text-xs text-[#748079]">
                          <th className="py-1.5 pr-3">目标同类组</th>
                          <th className="py-1.5">目标权重</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.targets.map((target) => (
                          <tr key={target.peer_group_key} className="border-b border-[#f0f4f1]">
                            <td className="py-1.5 pr-3">{target.peer_group_name || target.peer_group_key}</td>
                            <td className="py-1.5">{pct(target.target_weight)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>

              <div className={card}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="flex items-center gap-1.5 font-semibold text-[#1f2d26]">
                    <Scale className="h-4 w-4 text-[#28745c]" aria-hidden="true" />
                    持仓与权重（单只 ≤ 40%）
                  </h3>
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      value={addCode}
                      onChange={(event) => setAddCode(event.target.value)}
                      placeholder="基金代码，如 588000.SH"
                      className="w-44 rounded-lg border border-[#c8d4cb] px-2 py-1.5 text-sm"
                    />
                    <button type="button" className={button} onClick={addHolding} disabled={!addCode.trim()}>添加</button>
                    <button type="button" className={button} onClick={applyEqualWeights} disabled={!detail.holdings.length}>等权</button>
                    <button type="button" className={primaryButton} onClick={saveCustomWeights} disabled={!detail.holdings.length}>保存权重</button>
                  </div>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#e4e9e5] text-left text-xs text-[#748079]">
                        <th className="py-1.5 pr-3">基金</th>
                        <th className="py-1.5 pr-3">权重 %</th>
                        <th className="py-1.5 pr-3">来源</th>
                        <th className="py-1.5 pr-3">评价分</th>
                        <th className="py-1.5">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.holdings.map((item) => (
                        <tr key={item.wind_code} className="border-b border-[#f0f4f1]">
                          <td className="py-1.5 pr-3">
                            <span className="font-medium">{item.wind_code}</span>
                            <span className="ml-2 text-xs text-[#748079]">{item.fund_name || ''}</span>
                          </td>
                          <td className="py-1.5 pr-3">
                            <input
                              value={weightDraft[item.wind_code] ?? ''}
                              onChange={(event) => setWeightDraft((prev) => ({ ...prev, [item.wind_code]: event.target.value }))}
                              inputMode="decimal"
                              className="w-20 rounded border border-[#c8d4cb] px-2 py-1 text-sm"
                              aria-label={`${item.wind_code} 权重百分比`}
                            />
                          </td>
                          <td className="py-1.5 pr-3 text-xs text-[#748079]">
                            {item.weight_source === 'equal' ? '等权' : item.weight_source === 'custom' ? '自定义' : '未设置'}
                          </td>
                          <td className="py-1.5 pr-3">
                            {item.evaluation?.overall_score != null ? (
                              <span>{item.evaluation.overall_score}</span>
                            ) : (
                              <span className="text-xs text-[#748079]">暂无快照</span>
                            )}
                          </td>
                          <td className="py-1.5">
                            <button type="button" className="text-[#a05a52] hover:underline" onClick={() => removeHolding(item.wind_code)}>
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                              <span className="sr-only">移除 {item.wind_code}</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                      {!detail.holdings.length ? (
                        <tr>
                          <td colSpan={5} className="py-3 text-sm text-[#748079]">暂无持仓，输入基金代码添加（需满足推荐就绪口径）。</td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className={card}>
                <h3 className="flex items-center gap-1.5 font-semibold text-[#1f2d26]">
                  <GitCompareArrows className="h-4 w-4 text-[#28745c]" aria-hidden="true" />
                  组合穿透
                </h3>

                <h4 className={`${label} mt-3`}>重仓股重叠（同一披露季度前十大）</h4>
                {overlapPairs.length ? (
                  <table className="mt-1 w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#e4e9e5] text-left text-xs text-[#748079]">
                        <th className="py-1.5 pr-3">配对</th>
                        <th className="py-1.5 pr-3">重叠率</th>
                        <th className="py-1.5 pr-3">级别</th>
                        <th className="py-1.5">季度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overlapPairs.map((pair) => (
                        <tr key={`${pair.fund_a}-${pair.fund_b}`} className="border-b border-[#f0f4f1]">
                          <td className="py-1.5 pr-3">{pair.fund_a} × {pair.fund_b}</td>
                          <td className="py-1.5 pr-3">{pair.overlap_ratio != null ? pct(pair.overlap_ratio) : '—'}</td>
                          <td className="py-1.5 pr-3">{pair.similarity_level || '—'}</td>
                          <td className="py-1.5">{pair.quarter || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="mt-1 text-sm text-[#748079]">{analysis?.overlap?.reason || '至少两只持仓才能比较重叠。'}</p>
                )}

                <h4 className={`${label} mt-4`}>风格暴露聚合（权重加权，最新披露季度）</h4>
                {styleFactors.length ? (
                  <div className="mt-1 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                    {styleFactors.map((factor) => (
                      <div key={factor.factor} className="flex items-baseline justify-between border-b border-[#f0f4f1] py-1">
                        <span className="text-[#3d5347]">{factor.label}</span>
                        <span className="font-medium text-[#1f2d26]">{factor.weighted_exposure.toFixed(3)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-[#748079]">{analysis?.style_aggregate?.reason || '暂无风格快照可聚合。'}</p>
                )}
                {analysis?.style_aggregate?.status === 'available' ? (
                  <p className="mt-1 text-xs text-[#748079]">覆盖 {pct(analysis.style_aggregate.coverage)} 权重的持仓；未覆盖部分为残差。</p>
                ) : null}

                <h4 className={`${label} mt-4`}>净值收益率相关性</h4>
                {correlationPairs.length ? (
                  <table className="mt-1 w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#e4e9e5] text-left text-xs text-[#748079]">
                        <th className="py-1.5 pr-3">配对</th>
                        <th className="py-1.5 pr-3">相关系数</th>
                        <th className="py-1.5">重叠天数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {correlationPairs.map((pair) => (
                        <tr key={`${pair.fund_a}-${pair.fund_b}-corr`} className="border-b border-[#f0f4f1]">
                          <td className="py-1.5 pr-3">{pair.fund_a} × {pair.fund_b}</td>
                          <td className="py-1.5 pr-3">{pair.correlation != null ? pair.correlation.toFixed(4) : '样本不足'}</td>
                          <td className="py-1.5">{pair.overlap_days} 天</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="mt-1 text-sm text-[#748079]">{analysis?.correlation?.reason || '至少两只持仓才能计算相关性。'}</p>
                )}

                <p className="mt-4 border-t border-[#f0f4f1] pt-2 text-xs text-[#748079]">{analysis?.boundary}</p>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
