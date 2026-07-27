'use client'

import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface ScoreGaugeProps {
  score: number
  size?: number
  grade?: string
  showLabel?: boolean
}

export function ScoreGauge({ score, size = 120, grade, showLabel = true }: ScoreGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0)
  const radius = (size - 16) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (animatedScore / 100) * circumference
  const color = getScoreColor(score)

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(score), 100)
    return () => clearTimeout(timer)
  }, [score])

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#f1f5f9"
          strokeWidth={8}
        />
        {/* Score ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{animatedScore.toFixed(0)}</span>
        {showLabel && (
          <span className="text-xs text-slate-400">{score.toFixed(1)}</span>
        )}
        {grade && (
          <span
            className={cn(
              'absolute -bottom-1 px-1.5 py-0.5 rounded text-xs font-bold text-white',
              getGradeBg(grade)
            )}
          >
            {grade}
          </span>
        )}
      </div>
    </div>
  )
}

function getScoreColor(score: number): string {
  if (score >= 90) return '#22c55e'
  if (score >= 75) return '#0ea5e9'
  if (score >= 60) return '#f59e0b'
  if (score >= 40) return '#f97316'
  return '#ef4444'
}

function getGradeBg(grade: string): string {
  const map: Record<string, string> = {
    S: 'bg-purple-500', A: 'bg-emerald-500', B: 'bg-blue-500',
    C: 'bg-yellow-500 text-black', D: 'bg-orange-500', F: 'bg-red-500',
  }
  return map[grade] || 'bg-gray-400'
}
