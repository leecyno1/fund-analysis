// 评分算法工具库

export interface PerformanceMetrics {
  return_1m?: number
  return_3m?: number
  return_6m?: number
  return_1y?: number
  return_3y?: number
  return_5y?: number
}

export interface RiskMetrics {
  sharpe_1y?: number
  sharpe_3y?: number
  maxdd_1y?: number
  maxdd_3y?: number
  volatility_1y?: number
  volatility_3y?: number
}

export interface ScoreResult {
  dimension: string
  score: number
  weight: number
  weightedScore: number
  details: string
}

export interface FinalScore {
  totalScore: number
  scores: ScoreResult[]
  grade: string
  summary: string
}

/**
 * 业绩评分（0-100）
 * 基于多期收益率的综合评分
 */
export function calculatePerformanceScore(metrics: PerformanceMetrics): ScoreResult {
  let score = 0
  let count = 0
  const details: string[] = []

  // 1个月收益率（权重 10%）
  if (metrics.return_1m !== undefined) {
    const s = normalizeReturn(metrics.return_1m, 0.02, 0.1) // 2%-10%
    score += s * 0.1
    count++
    details.push(`1月收益: ${(metrics.return_1m * 100).toFixed(2)}%`)
  }

  // 3个月收益率（权重 15%）
  if (metrics.return_3m !== undefined) {
    const s = normalizeReturn(metrics.return_3m, 0.05, 0.2)
    score += s * 0.15
    count++
    details.push(`3月收益: ${(metrics.return_3m * 100).toFixed(2)}%`)
  }

  // 6个月收益率（权重 20%）
  if (metrics.return_6m !== undefined) {
    const s = normalizeReturn(metrics.return_6m, 0.1, 0.3)
    score += s * 0.2
    count++
    details.push(`6月收益: ${(metrics.return_6m * 100).toFixed(2)}%`)
  }

  // 1年收益率（权重 25%）
  if (metrics.return_1y !== undefined) {
    const s = normalizeReturn(metrics.return_1y, 0.15, 0.5)
    score += s * 0.25
    count++
    details.push(`1年收益: ${(metrics.return_1y * 100).toFixed(2)}%`)
  }

  // 3年收益率（权重 20%）
  if (metrics.return_3y !== undefined) {
    const s = normalizeReturn(metrics.return_3y, 0.3, 1.0)
    score += s * 0.2
    count++
    details.push(`3年收益: ${(metrics.return_3y * 100).toFixed(2)}%`)
  }

  // 5年收益率（权重 10%）
  if (metrics.return_5y !== undefined) {
    const s = normalizeReturn(metrics.return_5y, 0.5, 1.5)
    score += s * 0.1
    count++
    details.push(`5年收益: ${(metrics.return_5y * 100).toFixed(2)}%`)
  }

  const finalScore = count > 0 ? (score / (count * 0.01)) * 100 : 0

  return {
    dimension: '业绩表现',
    score: Math.min(100, Math.max(0, finalScore)),
    weight: 0.35,
    weightedScore: 0,
    details: details.join('; ')
  }
}

/**
 * 风险评分（0-100）
 * 基于夏普比率、最大回撤、波动率的综合评分
 */
export function calculateRiskScore(metrics: RiskMetrics): ScoreResult {
  let score = 0
  let count = 0
  const details: string[] = []

  // 夏普比率（权重 40%）
  if (metrics.sharpe_1y !== undefined) {
    const s = normalizeSharpe(metrics.sharpe_1y)
    score += s * 0.4
    count++
    details.push(`夏普比率(1年): ${metrics.sharpe_1y.toFixed(2)}`)
  }

  // 最大回撤（权重 35%）
  if (metrics.maxdd_1y !== undefined) {
    const s = normalizeMaxDrawdown(metrics.maxdd_1y)
    score += s * 0.35
    count++
    details.push(`最大回撤(1年): ${(metrics.maxdd_1y * 100).toFixed(2)}%`)
  }

  // 波动率（权重 25%）
  if (metrics.volatility_1y !== undefined) {
    const s = normalizeVolatility(metrics.volatility_1y)
    score += s * 0.25
    count++
    details.push(`波动率(1年): ${(metrics.volatility_1y * 100).toFixed(2)}%`)
  }

  const finalScore = count > 0 ? (score / (count * 0.01)) * 100 : 0

  return {
    dimension: '风险控制',
    score: Math.min(100, Math.max(0, finalScore)),
    weight: 0.30,
    weightedScore: 0,
    details: details.join('; ')
  }
}

/**
 * 稳定性评分（0-100）
 * 基于长期业绩的稳定性
 */
export function calculateStabilityScore(
  performanceMetrics: PerformanceMetrics,
  riskMetrics: RiskMetrics
): ScoreResult {
  let score = 0
  let count = 0
  const details: string[] = []

  // 长期收益稳定性（3年、5年）
  if (performanceMetrics.return_3y !== undefined && performanceMetrics.return_1y !== undefined) {
    const consistency = Math.abs(performanceMetrics.return_3y / 3 - performanceMetrics.return_1y)
    const s = 100 - Math.min(100, consistency * 200)
    score += s * 0.4
    count++
    details.push(`收益一致性: ${s.toFixed(0)}分`)
  }

  // 长期夏普比率
  if (riskMetrics.sharpe_3y !== undefined) {
    const s = normalizeSharpe(riskMetrics.sharpe_3y)
    score += s * 0.3
    count++
    details.push(`夏普比率(3年): ${riskMetrics.sharpe_3y.toFixed(2)}`)
  }

  // 长期最大回撤
  if (riskMetrics.maxdd_3y !== undefined) {
    const s = normalizeMaxDrawdown(riskMetrics.maxdd_3y)
    score += s * 0.3
    count++
    details.push(`最大回撤(3年): ${(riskMetrics.maxdd_3y * 100).toFixed(2)}%`)
  }

  const finalScore = count > 0 ? score / count : 0

  return {
    dimension: '稳定性',
    score: Math.min(100, Math.max(0, finalScore)),
    weight: 0.20,
    weightedScore: 0,
    details: details.join('; ')
  }
}

/**
 * 管理能力评分（0-100）
 * 基于基金经理的经验和管理规模
 */
export function calculateManagementScore(
  workYears?: number,
  managementYears?: number,
  fundsCount?: number
): ScoreResult {
  let score = 0
  const details: string[] = []

  // 从业年限（权重 30%）
  if (workYears !== undefined) {
    const s = Math.min(100, (workYears / 15) * 100)
    score += s * 0.3
    details.push(`从业年限: ${workYears}年`)
  }

  // 管理年限（权重 40%）
  if (managementYears !== undefined) {
    const s = Math.min(100, (managementYears / 10) * 100)
    score += s * 0.4
    details.push(`管理年限: ${managementYears.toFixed(1)}年`)
  }

  // 管理基金数（权重 30%）
  if (fundsCount !== undefined) {
    const s = Math.min(100, (fundsCount / 10) * 100)
    score += s * 0.3
    details.push(`管理基金: ${fundsCount}只`)
  }

  return {
    dimension: '管理能力',
    score: Math.min(100, Math.max(0, score)),
    weight: 0.15,
    weightedScore: 0,
    details: details.join('; ')
  }
}

/**
 * 计算综合评分
 */
export function calculateFinalScore(scores: ScoreResult[]): FinalScore {
  let totalWeightedScore = 0
  let totalWeight = 0

  const processedScores = scores.map(s => {
    const weightedScore = s.score * s.weight
    totalWeightedScore += weightedScore
    totalWeight += s.weight
    return { ...s, weightedScore }
  })

  const totalScore = totalWeight > 0 ? totalWeightedScore / totalWeight : 0

  // 评级
  let grade = 'D'
  if (totalScore >= 90) grade = 'A+'
  else if (totalScore >= 85) grade = 'A'
  else if (totalScore >= 80) grade = 'A-'
  else if (totalScore >= 75) grade = 'B+'
  else if (totalScore >= 70) grade = 'B'
  else if (totalScore >= 65) grade = 'B-'
  else if (totalScore >= 60) grade = 'C+'
  else if (totalScore >= 55) grade = 'C'
  else if (totalScore >= 50) grade = 'C-'

  // 总结
  let summary = ''
  if (totalScore >= 80) {
    summary = '优秀：该标的表现出色，只能作为重点研究线索；仍需材料核验、风险等级、费率和研究复核报告确认。'
  } else if (totalScore >= 70) {
    summary = '良好：该标的整体表现较稳，可作为研究样本继续核查；仍需完成正式研究证据复核。'
  } else if (totalScore >= 60) {
    summary = '中等：该标的表现中规中矩，需结合材料核验、同类分位和研究复核报告综合判断。'
  } else {
    summary = '较弱：该标的表现欠佳，不应直接进入正式研究清单。'
  }

  return {
    totalScore: Math.round(totalScore * 100) / 100,
    scores: processedScores,
    grade,
    summary
  }
}

// 辅助函数：归一化收益率
function normalizeReturn(value: number, min: number, max: number): number {
  if (value <= min) return 0
  if (value >= max) return 100
  return ((value - min) / (max - min)) * 100
}

// 辅助函数：归一化夏普比率
function normalizeSharpe(value: number): number {
  // 夏普比率：< 0 差，0-1 一般，1-2 良好，> 2 优秀
  if (value <= 0) return 0
  if (value >= 2) return 100
  return (value / 2) * 100
}

// 辅助函数：归一化最大回撤
function normalizeMaxDrawdown(value: number): number {
  // 最大回撤：越小越好，0% 最好，-50% 很差
  const absValue = Math.abs(value)
  if (absValue >= 0.5) return 0
  if (absValue <= 0.05) return 100
  return (1 - absValue / 0.5) * 100
}

// 辅助函数：归一化波动率
function normalizeVolatility(value: number): number {
  // 波动率：越小越好，< 10% 优秀，> 30% 较差
  if (value >= 0.3) return 0
  if (value <= 0.1) return 100
  return (1 - (value - 0.1) / 0.2) * 100
}
