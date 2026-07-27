'use client'

import { useMemo } from 'react'

interface BrinsonAttribution {
  returns: { portfolio: number; benchmark: number; active: number }
  attribution: {
    allocation_effect: number
    selection_effect: number
    interaction_effect: number
    residual: number
    total: number
  }
  industry_detail?: Array<{
    industry: string
    portfolio_weight: number
    benchmark_weight: number
    portfolio_return: number
    benchmark_return: number
    allocation_contrib: number
    selection_contrib: number
  }>
}

interface BrinsonWaterfallProps {
  attribution: BrinsonAttribution
  compact?: boolean
}

export function BrinsonWaterfall({ attribution, compact = false }: BrinsonWaterfallProps) {
  const { returns, attr } = useMemo(() => ({
    returns: attribution.returns,
    attr: attribution.attribution,
  }), [attribution])

  const maxAbs = useMemo(() => Math.max(
    Math.abs(attr.allocation_effect),
    Math.abs(attr.selection_effect),
    Math.abs(attr.interaction_effect),
    Math.abs(attr.residual),
    0.05
  ), [attr])

  const barHeight = (v: number) => `${(Math.abs(v) / maxAbs) * 100}%`

  if (compact) {
    return (
      <div className="grid grid-cols-4 gap-2 text-center">
        {[
          { label: '行业配置', value: attr.allocation_effect, color: 'text-blue-600' },
          { label: '个股选择', value: attr.selection_effect, color: 'text-emerald-600' },
          { label: '交互效应', value: attr.interaction_effect, color: 'text-amber-600' },
          { label: '超额收益', value: returns.active, color: 'text-purple-600 font-bold' },
        ].map(item => (
          <div key={item.label}>
            <div className={`text-sm font-mono font-bold ${item.color}`}>
              {item.value >= 0 ? '+' : ''}{(item.value * 100).toFixed(2)}%
            </div>
            <div className="text-xs text-slate-500 mt-0.5">{item.label}</div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 水晶图 */}
      <div className="relative h-40 flex items-end justify-center gap-4">
        {[
          { label: '行业配置\n效应', value: attr.allocation_effect, pos: attr.allocation_effect >= 0, color: '#3b82f6' },
          { label: '个股选择\n效应', value: attr.selection_effect, pos: attr.selection_effect >= 0, color: '#10b981' },
          { label: '交互\n效应', value: attr.interaction_effect, pos: attr.interaction_effect >= 0, color: '#f59e0b' },
          { label: '残余', value: attr.residual, pos: attr.residual >= 0, color: '#94a3b8' },
        ].map((item, i) => (
          <div key={item.label} className="flex flex-col items-center" style={{ width: 60 }}>
            <div className="text-[10px] text-slate-500 text-center leading-tight whitespace-pre-wrap mb-1">
              {item.label}
            </div>
            <div className="relative w-10 bg-slate-100 rounded-t" style={{ height: barHeight(item.value) }}>
              <div
                className="absolute w-full rounded-t"
                style={{
                  bottom: item.pos ? 0 : '50%',
                  height: item.pos ? '100%' : '50%',
                  backgroundColor: item.color,
                  opacity: 0.8,
                }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-xs font-mono font-bold ${item.pos ? 'text-slate-700' : 'text-slate-400'}`}>
                  {(item.value * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ))}

        {/* 总超额收益标注 */}
        <div className="absolute top-0 right-0 bg-purple-100 rounded px-2 py-1">
          <span className="text-xs text-purple-700 font-medium">
            超额收益: <span className="font-mono font-bold">{(returns.active * 100).toFixed(2)}%</span>
          </span>
        </div>
      </div>

      {/* 归因说明 */}
      <div className="grid grid-cols-3 gap-3 text-xs text-slate-600">
        <div className="bg-blue-50 rounded p-2">
          <div className="font-medium text-blue-700">行业配置</div>
          <div className="font-mono text-blue-600 mt-0.5">
            {(attr.allocation_effect * 100).toFixed(2)}%
          </div>
          <div className="text-slate-500 mt-0.5">超配/低配行业的收益贡献</div>
        </div>
        <div className="bg-emerald-50 rounded p-2">
          <div className="font-medium text-emerald-700">个股选择</div>
          <div className="font-mono text-emerald-600 mt-0.5">
            {(attr.selection_effect * 100).toFixed(2)}%
          </div>
          <div className="text-slate-500 mt-0.5">选股超越行业的收益</div>
        </div>
        <div className="bg-amber-50 rounded p-2">
          <div className="font-medium text-amber-700">交互效应</div>
          <div className="font-mono text-amber-600 mt-0.5">
            {(attr.interaction_effect * 100).toFixed(2)}%
          </div>
          <div className="text-slate-500 mt-0.5">配置与选股交叉影响</div>
        </div>
      </div>

      {/* 行业明细 */}
      {attribution.industry_detail && attribution.industry_detail.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-medium text-slate-500 mb-2">行业归因明细</div>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {attribution.industry_detail.map((ind) => (
              <div key={ind.industry} className="flex items-center gap-2 text-xs py-1 border-b border-slate-50">
                <span className="w-16 text-slate-600">{ind.industry}</span>
                <span className="text-slate-400 w-10 text-right">
                  {(ind.portfolio_weight * 100).toFixed(1)}%
                </span>
                <div className="flex-1 flex gap-1">
                  {ind.allocation_contrib > 0.001 && (
                    <div className="h-4 bg-blue-200 rounded-sm" style={{ width: `${ind.allocation_contrib * 2000}%` }} title="配置效应" />
                  )}
                  {ind.selection_contrib > 0.001 && (
                    <div className="h-4 bg-emerald-200 rounded-sm" style={{ width: `${ind.selection_contrib * 2000}%` }} title="选择效应" />
                  )}
                </div>
                <span className={`font-mono w-16 text-right ${(ind.allocation_contrib + ind.selection_contrib) >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                  {(ind.allocation_contrib + ind.selection_contrib) >= 0 ? '+' : ''}
                  {((ind.allocation_contrib + ind.selection_contrib) * 100).toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


interface BrinsonReturnsProps {
  attribution: BrinsonAttribution
}

export function BrinsonReturns({ attribution }: BrinsonReturnsProps) {
  const { returns, attr } = attribution
  const activePct = returns.active * 100
  const allocPct = attr.allocation_effect * 100
  const selPct = attr.selection_effect * 100

  return (
    <div className="flex items-center justify-between gap-4">
      {/* 收益柱状图 */}
      <div className="flex-1">
        <div className="flex items-end justify-center gap-6 h-24">
          {[
            { label: '组合收益', value: returns.portfolio, color: '#6366f1' },
            { label: '基准收益', value: returns.benchmark, color: '#94a3b8' },
          ].map(item => (
            <div key={item.label} className="flex flex-col items-center" style={{ width: 70 }}>
              <div className="text-xs font-mono font-bold mb-1" style={{ color: item.color }}>
                {(item.value * 100).toFixed(2)}%
              </div>
              <div
                className="w-12 rounded-t"
                style={{
                  height: `${Math.abs(item.value) * 400}%`,
                  backgroundColor: item.color,
                  opacity: 0.7,
                  minHeight: item.value > 0 ? '4px' : '0',
                }}
              />
              <div className="text-[10px] text-slate-500 mt-1">{item.label}</div>
            </div>
          ))}
        </div>
        <div className="text-center mt-2">
          <span className={`text-sm font-bold font-mono ${activePct >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
            {activePct >= 0 ? '+' : ''}{activePct.toFixed(2)}%
          </span>
          <span className="text-xs text-slate-400 ml-1">超额</span>
        </div>
      </div>

      {/* 效应分解 */}
      <div className="border-l border-slate-200 pl-4 space-y-1">
        <div className="text-[10px] text-slate-400 mb-1">收益分解</div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-sm bg-blue-500" />
          <span className="text-xs text-slate-600 w-12">配置</span>
          <span className={`text-xs font-mono font-medium ${allocPct >= 0 ? 'text-blue-600' : 'text-blue-400'}`}>
            {allocPct >= 0 ? '+' : ''}{allocPct.toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-sm bg-emerald-500" />
          <span className="text-xs text-slate-600 w-12">选股</span>
          <span className={`text-xs font-mono font-medium ${selPct >= 0 ? 'text-emerald-600' : 'text-emerald-400'}`}>
            {selPct >= 0 ? '+' : ''}{selPct.toFixed(2)}%
          </span>
        </div>
        {attr.interaction_effect !== 0 && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-sm bg-amber-500" />
            <span className="text-xs text-slate-600 w-12">交互</span>
            <span className="text-xs font-mono font-medium text-amber-600">
              {(attr.interaction_effect * 100).toFixed(2)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}