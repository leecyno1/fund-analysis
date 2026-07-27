import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPercent(value: number | null | undefined, decimals: number = 2): string {
  if (value == null) return '-'
  return `${(value * 100).toFixed(decimals)}%`
}

export function formatMoney(value: number | null | undefined, decimals: number = 2): string {
  if (value == null) return '-'
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(decimals)}亿`
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(decimals)}万`
  return value.toFixed(decimals)
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN')
  } catch {
    return dateStr
  }
}

export function getGradeColor(grade: string): string {
  const map: Record<string, string> = {
    'S': 'bg-purple-500 text-white',
    'A': 'bg-emerald-500 text-white',
    'B': 'bg-blue-500 text-white',
    'C': 'bg-yellow-500 text-black',
    'D': 'bg-orange-500 text-white',
    'F': 'bg-red-500 text-white',
  }
  return map[grade] || 'bg-gray-400 text-white'
}

export function getScoreColor(score: number): string {
  if (score >= 90) return '#22c55e'
  if (score >= 75) return '#0ea5e9'
  if (score >= 60) return '#f59e0b'
  if (score >= 40) return '#f97316'
  return '#ef4444'
}

export function getReturnColor(value: number | null): string {
  if (value == null) return 'text-gray-400'
  if (value > 0) return 'text-red-500'
  if (value < 0) return 'text-green-500'
  return 'text-gray-500'
}

export function formatReturn(value: number | null | undefined, decimals: number = 2): string {
  if (value == null) return '-'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(decimals)}%`
}