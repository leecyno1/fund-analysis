'use client'

import { useMemo } from 'react'

interface BarraRadarProps {
  exposures: Record<string, number>
  riskContributions?: Array<{ factor: string; risk_contribution: number; exposure?: number }>
  compact?: boolean
}

const FACTOR_LABELS: Record<string, string> = {
  SIZE: '规模',
  SIZENL: '非线性规模',
  BETA: 'Beta',
  MOMENTUM: '动量',
  RESVOL: '残余波动',
  SRSIZE: '短期规模',
  LIQUIDITY: '流动性',
  BHADGE: '价值',
  LEVERAGE: '杠杆',
  STORIE: '成长',
}

export function BarraRadarChart({ exposures, riskContributions, compact = false }: BarraRadarProps) {
  const factors = Object.keys(FACTOR_LABELS).filter(f => f in exposures)
  const maxAbs = useMemo(() => Math.max(...Object.values(exposures).map(Math.abs), 1), [exposures])

  const points = useMemo(() => {
    const n = factors.length
    return factors.map((f, i) => {
      const angle = (i / n) * 2 * Math.PI - Math.PI / 2
      const r = (Math.abs(exposures[f]) / maxAbs) * 80
      const val = exposures[f]
      return {
        factor: f,
        label: FACTOR_LABELS[f],
        value: val,
        x: 150 + r * Math.cos(angle),
        y: 150 + r * Math.sin(angle),
        cx: 150 + 85 * Math.cos(angle),
        cy: 150 + 85 * Math.sin(angle),
        angle,
      }
    })
  }, [factors, exposures, maxAbs])

  if (compact) {
    return (
      <div className="grid grid-cols-5 gap-1">
        {factors.map(f => (
          <div key={f} className="text-center">
            <div className={`text-xs font-mono ${exposures[f] > 0 ? 'text-rose-500' : 'text-blue-500'}`}>
              {exposures[f] > 0 ? '+' : ''}{exposures[f].toFixed(2)}
            </div>
            <div className="text-[10px] text-slate-500">{FACTOR_LABELS[f]}</div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="relative">
      <svg viewBox="0 0 300 300" className="w-full max-w-sm mx-auto">
        {/* 背景网格 */}
        {[20, 40, 60, 80].map(r => (
          <g key={r}>
            <polygon
              points={points.map(p => {
                const a = p.angle
                const px = 150 + r * Math.cos(a)
                const py = 150 + r * Math.sin(a)
                return `${px},${py}`
              }).join(' ')}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="0.5"
              strokeDasharray="2,2"
            />
          </g>
        ))}

        {/* 轴线 */}
        {points.map(p => (
          <line
            key={p.factor}
            x1="150" y1="150"
            x2={p.cx} y2={p.cy}
            stroke="#cbd5e1"
            strokeWidth="0.5"
          />
        ))}

        {/* 数据多边形 */}
        <polygon
          points={points.map(p => `${p.x},${p.y}`).join(' ')}
          fill={exposures.BETA > 0.8 ? '#fef3c7' : '#dbeafe'}
          fillOpacity="0.4"
          stroke="#3b82f6"
          strokeWidth="2"
        />

        {/* 数据点 */}
        {points.map(p => (
          <g key={p.factor}>
            <circle
              cx={p.x} cy={p.y} r="4"
              fill={p.value > 0 ? '#ef4444' : '#3b82f6'}
              stroke="white"
              strokeWidth="1.5"
            />
            <text
              x={p.cx + (p.cx > 150 ? 8 : -8)}
              y={p.cy + 4}
              textAnchor={p.cx > 150 ? 'start' : 'end'}
              fontSize="10"
              fill="#475569"
            >
              {p.label}
            </text>
            <text
              x={p.x} y={p.y - 8}
              textAnchor="middle"
              fontSize="9"
              fill={p.value > 0 ? '#dc2626' : '#2563eb'}
              fontFamily="monospace"
            >
              {p.value.toFixed(2)}
            </text>
          </g>
        ))}

        {/* 中心 */}
        <circle cx="150" cy="150" r="3" fill="#94a3b8" />
      </svg>

      {riskContributions && (
        <div className="mt-3 space-y-1">
          <div className="text-xs font-medium text-slate-500 mb-1">风险贡献 TOP 3</div>
          {riskContributions.slice(0, 3).map(r => (
            <div key={r.factor} className="flex items-center gap-2">
              <span className="text-xs text-slate-600 w-16">{FACTOR_LABELS[r.factor] || r.factor}</span>
              <div className="flex-1 bg-slate-100 rounded-full h-1.5">
                <div
                  className="bg-blue-500 h-1.5 rounded-full"
                  style={{ width: `${Math.min(100, r.risk_contribution * 500)}%` }}
                />
              </div>
              <span className="text-xs font-mono text-slate-500 w-12 text-right">
                {(r.risk_contribution * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


interface BarraStyleExposureProps {
  exposures: Record<string, number>
}

export function BarraStyleExposure({ exposures }: BarraStyleExposureProps) {
  const absExposures = Object.entries(exposures).map(([k, v]) => ({ k, v, abs: Math.abs(v) }))
  const maxAbs = Math.max(...absExposures.map(e => e.abs), 0.01)

  return (
    <div className="space-y-2">
      {absExposures.sort((a, b) => b.abs - a.abs).map(({ k, v }) => (
        <div key={k} className="flex items-center gap-3">
          <span className="text-xs text-slate-500 w-16">{FACTOR_LABELS[k] || k}</span>
          <div className="relative flex-1 h-5 bg-slate-100 rounded">
            <div
              className={`absolute top-0 h-full rounded ${v > 0 ? 'bg-rose-100' : 'bg-blue-100'}`}
              style={{
                left: v > 0 ? '50%' : `${50 - (v / maxAbs) * 50}%`,
                width: `${(v / maxAbs) * 50}%`,
              }}
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-xs font-mono font-medium ${v > 0 ? 'text-rose-600' : 'text-blue-600'}`}>
                {v > 0 ? '+' : ''}{v.toFixed(3)}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
