import type { CamelFund } from '@/lib/backend-api'

type UnknownRecord = Record<string, unknown>

export type SimpleFund = CamelFund & {
  managers?: Array<UnknownRecord>
  researchProfile?: UnknownRecord | null
  rollingMetrics?: UnknownRecord
  dataQuality?: UnknownRecord | null
  professionalScoring?: UnknownRecord | null
  recommendationEvidence?: UnknownRecord | null
}

export function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as UnknownRecord : {}
}

export function numberValue(...values: unknown[]) {
  for (const value of values) {
    if (value == null || value === '') continue
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

export function textValue(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
    if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  }
  return ''
}

export function windowMetrics(fund: SimpleFund, window: string) {
  return asRecord(asRecord(fund.rollingMetrics)[window])
}

export function returnMetric(fund: SimpleFund, window = '1y') {
  const performance = asRecord(fund.performanceData)
  const rolling = windowMetrics(fund, window)
  return numberValue(
    rolling.annualized_return,
    rolling.total_return,
    performance[`annualized_return_${window}`],
    window === '1y' ? performance.annualized_return_1y : null,
  )
}

export function drawdownMetric(fund: SimpleFund, window = '1y') {
  const risk = asRecord(fund.riskMetrics)
  const performance = asRecord(fund.performanceData)
  const rolling = windowMetrics(fund, window)
  return numberValue(
    rolling.max_drawdown,
    risk[`max_drawdown_${window}`],
    risk.max_drawdown,
    performance.max_drawdown,
  )
}

export function sharpeMetric(fund: SimpleFund, window = '1y') {
  const risk = asRecord(fund.riskMetrics)
  const performance = asRecord(fund.performanceData)
  const rolling = windowMetrics(fund, window)
  return numberValue(rolling.sharpe_ratio, risk.sharpe_ratio, performance.sharpe_ratio)
}

export function styleLabel(fund: SimpleFund) {
  const profile = asRecord(fund.researchProfile)
  const suggestions = Array.isArray(profile.memoStyleSuggestions)
    ? profile.memoStyleSuggestions
    : Array.isArray(profile.memo_style_suggestions) ? profile.memo_style_suggestions : []
  const firstSuggestion = suggestions.length ? asRecord(suggestions[0]) : {}
  return textValue(profile.styleLabel, profile.style_label, firstSuggestion.value) || '风格待确认'
}

export function styleLabelStatus(fund: SimpleFund) {
  const profile = asRecord(fund.researchProfile)
  if (textValue(profile.styleLabel, profile.style_label)) return 'confirmed'
  const suggestions = Array.isArray(profile.memoStyleSuggestions)
    ? profile.memoStyleSuggestions
    : Array.isArray(profile.memo_style_suggestions) ? profile.memo_style_suggestions : []
  return suggestions.length ? 'llm_suggested' : 'unavailable'
}

const styleAliases: Record<string, string[]> = {
  '大盘成长': ['大盘成长', 'large growth', 'large_growth'],
  '成长': ['成长', 'growth'],
  '价值': ['价值', 'value'],
  '均衡': ['均衡', '平衡', '混合', 'blend', 'balanced'],
  '质量': ['质量', '品质', 'quality'],
  '红利': ['红利', '股息', 'dividend'],
  '小盘': ['小盘', 'small cap', 'small_cap', 'small'],
  '行业主题': ['行业', '主题', 'sector', 'thematic'],
  '低波稳健': ['低波', '稳健', 'low volatility', 'low_volatility', 'defensive'],
}

function normalizedStyleText(value: string) {
  return value.trim().toLowerCase().replaceAll('型', '').replace(/[\s_-]+/gu, ' ')
}

export function matchesStyleLabel(fund: SimpleFund, selectedStyle: string) {
  if (!selectedStyle) return true
  const target = normalizedStyleText(selectedStyle)
  const aliases = styleAliases[selectedStyle] || [selectedStyle]
  const profileTags = asRecord(fund.researchProfile).strategyTags
  const profile = asRecord(fund.researchProfile)
  const memoSuggestions = Array.isArray(profile.memoStyleSuggestions)
    ? profile.memoStyleSuggestions
    : Array.isArray(profile.memo_style_suggestions) ? profile.memo_style_suggestions : []
  const tags = [
    styleLabel(fund),
    peerGroup(fund),
    fund.type,
    ...(Array.isArray(profileTags) ? profileTags : []),
    ...memoSuggestions.map((item) => textValue(asRecord(item).value)),
  ].map((value) => normalizedStyleText(String(value || ''))).join(' ')

  if (aliases.some((alias) => tags.includes(normalizedStyleText(alias)))) return true
  if (target === '低波稳健') {
    const drawdown = drawdownMetric(fund)
    return drawdown != null && Math.abs(drawdown) <= 0.12
  }
  return false
}

export function peerGroup(fund: SimpleFund) {
  const profile = asRecord(fund.researchProfile)
  return textValue(profile.peerGroup, profile.peer_group, fund.type) || '类别待确认'
}

export function professionalPeerGroup(fund: SimpleFund) {
  const profile = asRecord(fund.researchProfile)
  return textValue(profile.peerGroup, profile.peer_group)
}

export function professionalPeerGroupId(fund: SimpleFund) {
  const profile = asRecord(fund.researchProfile)
  return textValue(profile.peerGroupId, profile.peer_group_id, profile.peerGroupKey, profile.peer_group_key)
}

export function managerName(fund: SimpleFund) {
  const managers = Array.isArray(fund.managers) ? fund.managers : []
  const first = managers.length ? asRecord(managers[0]) : {}
  return textValue(first.name) || '经理待补充'
}

export function evidenceCoverage(fund: SimpleFund) {
  const direct = numberValue(fund.evidenceCoverageScore)
  if (direct != null) return direct > 1 ? Math.min(100, direct) : Math.min(100, direct * 100)

  let complete = 0
  const checks = [fund.nav, returnMetric(fund), drawdownMetric(fund), fund.totalAsset, styleLabel(fund) !== '风格待确认']
  for (const check of checks) {
    if (check !== null && check !== undefined && check !== false) complete += 1
  }
  return complete * 20
}

export function formatPercent(value: number | null, digits = 1) {
  if (value == null) return '—'
  const normalized = Math.abs(value) <= 2 ? value * 100 : value
  return `${normalized.toFixed(digits)}%`
}

export function formatAsset(value: number | null) {
  if (value == null) return '—'
  return `${value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })} 亿`
}

export function professionalFundScore(fund: SimpleFund) {
  const scoring = asRecord(fund.professionalScoring)
  const status = textValue(scoring.status)
  if (status === 'insufficient_evidence') return null
  return numberValue(scoring.overall_score, scoring.overallScore)
}

export function professionalScoreStatus(fund: SimpleFund) {
  return textValue(asRecord(fund.professionalScoring).status) || 'unavailable'
}

export function professionalScorePercentile(fund: SimpleFund) {
  const peerPercentiles = asRecord(fund.peerPercentiles)
  const metrics = asRecord(peerPercentiles.metrics)
  const professional = asRecord(metrics.professional_score)
  return numberValue(professional.percentile)
}

export function recommendationEvidence(fund: SimpleFund) {
  const evidence = asRecord(fund.recommendationEvidence)
  const alternatives = Array.isArray(evidence.alternatives)
    ? evidence.alternatives.map((item) => asRecord(item)).filter((item) => textValue(item.windCode, item.wind_code))
    : []
  return {
    reasons: Array.isArray(evidence.reasons) ? evidence.reasons.map(String).filter(Boolean) : [],
    risks: Array.isArray(evidence.risks) ? evidence.risks.map(String).filter(Boolean) : [],
    dataAsOf: textValue(evidence.dataAsOf, evidence.data_as_of),
    methodologyVersion: textValue(evidence.methodologyVersion, evidence.methodology_version),
    alternatives: alternatives.map((item) => ({
      windCode: textValue(item.windCode, item.wind_code),
      name: textValue(item.name, item.windCode, item.wind_code),
      styleLabel: textValue(item.styleLabel, item.style_label),
      overallScore: numberValue(item.overallScore, item.overall_score),
      reason: textValue(item.reason),
    })),
  }
}
