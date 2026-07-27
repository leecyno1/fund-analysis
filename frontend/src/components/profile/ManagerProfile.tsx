'use client'

import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface ManagerProfileData {
  manager: {
    manager_id: string
    name: string
    company: string
    experience_years?: number
    management_years?: number
    education?: string
  }
  funds: Array<{
    wind_code: string
    name: string
    scoring: { overall_score: number; overall_grade: string }
    performance: { annualized_return_1y: number }
  }>
  scoring: {
    overall_score: number
    overall_grade: string
    dimension_scores: Record<string, number>
  }
  reports?: Array<{ title: string; date: string; summary?: string }>
}

interface ManagerProfileProps {
  data: ManagerProfileData
}

export function ManagerProfileCard({ data }: ManagerProfileProps) {
  const { manager, funds, scoring } = data

  return (
    <div className="space-y-6">
      {/* 基本信息卡片 */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">{manager.name}</h2>
            <p className="text-slate-500 mt-0.5">{manager.company}</p>
          </div>
          <div className="text-right">
            <div className={`text-2xl font-bold ${
              scoring.overall_grade === 'S' ? 'text-purple-600' :
              scoring.overall_grade === 'A' ? 'text-emerald-600' :
              scoring.overall_grade === 'B' ? 'text-blue-600' :
              'text-slate-600'
            }`}>
              {scoring.overall_score.toFixed(1)}
            </div>
            <div className="text-sm text-slate-400">综合评分</div>
          </div>
        </div>

        {/* 能力圈 */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: '从业年限', value: manager.experience_years ?? manager.management_years ?? 5, unit: '年' },
            { label: '管理基金', value: funds.length, unit: '只' },
            { label: '学历', value: manager.education || '硕士', unit: '' },
            { label: '综合等级', value: scoring.overall_grade, unit: '' },
          ].map(item => (
            <div key={item.label} className="bg-slate-50 rounded-lg p-3 text-center">
              <div className="text-sm font-medium text-slate-900">{item.value}{item.unit}</div>
              <div className="text-xs text-slate-400 mt-0.5">{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 维度评分 */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">能力维度评分</h3>
        <div className="space-y-3">
          {Object.entries(scoring.dimension_scores).map(([dim, score]) => (
            <div key={dim} className="flex items-center gap-3">
              <span className="text-xs text-slate-500 w-20">{dim}</span>
              <div className="flex-1 bg-slate-100 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500"
                  style={{ width: `${score}%` }}
                />
              </div>
              <span className="text-xs font-mono font-medium text-slate-700 w-10 text-right">{score.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 管理基金 */}
      {funds.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">在管基金</h3>
          <div className="space-y-2">
            {funds.map(fund => (
              <div key={fund.wind_code} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <div>
                  <div className="text-sm font-medium text-slate-900">{fund.name}</div>
                  <div className="text-xs text-slate-400">{fund.wind_code}</div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-sm font-mono ${(fund.performance?.annualized_return_1y ?? 0) >= 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {((fund.performance?.annualized_return_1y ?? 0) * 100).toFixed(2)}%
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold text-white ${
                    fund.scoring?.overall_grade === 'S' ? 'bg-purple-500' :
                    fund.scoring?.overall_grade === 'A' ? 'bg-emerald-500' :
                    fund.scoring?.overall_grade === 'B' ? 'bg-blue-500' :
                    'bg-slate-400'
                  }`}>
                    {fund.scoring?.overall_grade || 'B'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


interface CompetenceCircleProps {
  dimensions: Record<string, number>
  size?: number
}

export function CompetenceCircle({ dimensions, size = 200 }: CompetenceCircleProps) {
  const entries = Object.entries(dimensions)
  const n = entries.length
  const center = size / 2
  const maxRadius = size * 0.35

  const points = entries.map(([key, value], i) => {
    const angle = (i / n) * 2 * Math.PI - Math.PI / 2
    const r = (value / 100) * maxRadius
    return {
      key,
      value,
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
      labelX: center + (maxRadius + 20) * Math.cos(angle),
      labelY: center + (maxRadius + 20) * Math.sin(angle),
      anchor: angle > Math.PI / 2 || angle < -Math.PI / 2 ? 'end' : 'start',
    }
  })

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-xs mx-auto">
      {/* 背景网格 */}
      {[25, 50, 75].map(r => (
        <circle key={r} cx={center} cy={center} r={r} fill="none" stroke="#e2e8f0" strokeWidth="0.5" strokeDasharray="2,2" />
      ))}

      {/* 数据区域 */}
      <polygon
        points={points.map(p => `${p.x},${p.y}`).join(' ')}
        fill="#3b82f6"
        fillOpacity="0.15"
        stroke="#3b82f6"
        strokeWidth="1.5"
      />

      {/* 维度标签和点 */}
      {points.map(p => (
        <g key={p.key}>
          <line x1={center} y1={center} x2={p.x} y2={p.y} stroke="#cbd5e1" strokeWidth="0.5" />
          <circle cx={p.x} cy={p.y} r="4" fill="#3b82f6" stroke="white" strokeWidth="1.5" />
          <text
            x={p.labelX}
            y={p.labelY + 4}
            textAnchor={p.anchor}
            fontSize="9"
            fill="#475569"
          >
            {p.key} ({p.value.toFixed(0)})
          </text>
        </g>
      ))}

      {/* 中心 */}
      <circle cx={center} cy={center} r="3" fill="#94a3b8" />
    </svg>
  )
}


interface TrendIndicatorProps {
  value: number
  label: string
  unit?: string
  invert?: boolean
}

export function TrendIndicator({ value, label, unit = '%', invert = false }: TrendIndicatorProps) {
  const isPositive = invert ? value < 0 : value > 0
  const isNeutral = Math.abs(value) < 0.01

  return (
    <div className="flex items-center gap-1.5">
      {isNeutral ? (
        <Minus className="w-3.5 h-3.5 text-slate-400" />
      ) : isPositive ? (
        <TrendingUp className="w-3.5 h-3.5 text-rose-500" />
      ) : (
        <TrendingDown className="w-3.5 h-3.5 text-emerald-500" />
      )}
      <span className={`text-sm font-mono font-medium ${isNeutral ? 'text-slate-400' : isPositive ? 'text-rose-600' : 'text-emerald-600'}`}>
        {isPositive ? '+' : ''}{value.toFixed(2)}{unit}
      </span>
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  )
}


interface PhilosophyConsistencyProps {
  reports: Array<{ title: string; date: string; key_points?: string[] }>
}

export function PhilosophyConsistency({ reports }: PhilosophyConsistencyProps) {
  if (!reports || reports.length < 2) {
    return (
      <div className="text-center py-4 text-slate-400 text-sm">
        调研纪要不足，无法评估理念一致性
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-600">投资理念一致性</span>
        <span className="text-sm font-medium text-emerald-600">
          {reports.length} 份纪要
        </span>
      </div>
      <div className="space-y-2">
        {reports.map((r, i) => (
          <div key={i} className="bg-slate-50 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-slate-700">{r.title}</span>
              <span className="text-xs text-slate-400">{r.date}</span>
            </div>
            {r.key_points && r.key_points.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {r.key_points.map((p, j) => (
                  <span key={j} className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">
                    {p}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}