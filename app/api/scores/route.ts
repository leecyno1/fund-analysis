import { NextResponse } from 'next/server'
import { backendApiBaseUrl } from '@/lib/backend-api'
import {
  calculateFinalScore,
  calculateManagementScore,
  type FinalScore,
  type ScoreResult,
} from '@/lib/scoring'

type TargetType = 'fund' | 'manager'
type ScoreMethod = 'auto' | 'manual'

type ManualScore = {
  dimension: string
  score: number
}

type ScoreRequest = {
  targetType: TargetType
  targetId: string
  method?: ScoreMethod
  manualScores?: ManualScore[]
}

type BackendDimensionScore = {
  score?: number
  weight?: number
  weighted_score?: number
  evidence?: string[]
  count?: number
}

type BackendScoringPayload = {
  scoring_source?: string
  scoring?: {
    overall_score?: number
    overall_grade?: string
    dimension_scores?: Record<string, BackendDimensionScore>
    missing_data?: string[]
    data_quality?: unknown
    positive_factors?: string[]
    negative_factors?: string[]
    scoring_time?: string
    calculation_method?: string
  }
  dimensions?: Array<{ name?: string; key?: string; weight?: number; score?: number }>
  scoring_history?: unknown[]
}

type ManagerDetail = {
  name?: string
  workYears?: number | null
  managementYears?: number | null
  currentFunds?: string[]
  fundCount?: number
}

const dimensionLabels: Record<string, string> = {
  return: '收益能力',
  risk: '风险控制',
  risk_adjusted: '风险调整收益',
  style: '风格稳定性',
  consistency: '收益一致性',
  manager_tenure: '经理任期',
  data_quality: '数据质量',
  management: '管理能力',
}

function scoreToGrade(totalScore: number) {
  if (totalScore >= 90) return 'A+'
  if (totalScore >= 85) return 'A'
  if (totalScore >= 80) return 'A-'
  if (totalScore >= 75) return 'B+'
  if (totalScore >= 70) return 'B'
  if (totalScore >= 65) return 'B-'
  if (totalScore >= 60) return 'C+'
  if (totalScore >= 55) return 'C'
  if (totalScore >= 50) return 'C-'
  return 'D'
}

function buildSummary(totalScore: number, missingData: string[] = []) {
  const qualityNote = missingData.length > 0
    ? `；仍缺 ${missingData.length} 项评分证据，研究复核需补齐`
    : '；评分证据相对完整'
  if (totalScore >= 80) return `优秀：综合评分较高，只能作为重点研究线索${qualityNote}；仍需材料核验、风险等级、费率和研究复核报告确认。`
  if (totalScore >= 70) return `良好：综合表现较稳，可作为研究样本继续核查${qualityNote}；仍需完成正式研究证据复核。`
  if (totalScore >= 60) return `中等：需结合费率、限购、经理任期和同类分位再判断${qualityNote}；不输出正式研究结论。`
  return `谨慎：当前评分偏弱或证据不足，不应直接进入正式研究清单${qualityNote}。`
}

function finalScoreFromBackend(payload: BackendScoringPayload): FinalScore {
  const scoring = payload.scoring || {}
  const dimensionScores = scoring.dimension_scores || {}
  const dimensions: ScoreResult[] = Object.entries(dimensionScores).map(([key, item]) => {
    const score = Number(item.score ?? 0)
    const weight = Number(item.weight ?? payload.dimensions?.find((dimension) => dimension.key === key)?.weight ?? 0)
    const evidence = Array.isArray(item.evidence) && item.evidence.length > 0
      ? item.evidence.join('；')
      : item.count !== undefined
        ? `基于 ${item.count} 项指标`
        : '后端专业评分'
    return {
      dimension: dimensionLabels[key] || key,
      score,
      weight,
      weightedScore: Number(item.weighted_score ?? score * weight),
      details: evidence,
    }
  })

  if (dimensions.length === 0 && payload.dimensions?.length) {
    payload.dimensions.forEach((dimension) => {
      const score = Number(dimension.score ?? 0)
      const weight = Number(dimension.weight ?? 0)
      dimensions.push({
        dimension: dimension.name || dimension.key || '评分维度',
        score,
        weight,
        weightedScore: score * weight,
        details: '后端量化评分',
      })
    })
  }

  const totalScore = Number(scoring.overall_score ?? calculateFinalScore(dimensions).totalScore)
  return {
    totalScore,
    scores: dimensions,
    grade: scoring.overall_grade || scoreToGrade(totalScore),
    summary: buildSummary(totalScore, scoring.missing_data || []),
  }
}

function finalScoreFromManual(manualScores: ManualScore[] = []) {
  const scores: ScoreResult[] = manualScores.map((item) => ({
    dimension: item.dimension,
    score: item.score,
    weight: manualScores.length > 0 ? 1 / manualScores.length : 0,
    weightedScore: 0,
    details: '手动评分；未写入数据库',
  }))
  return calculateFinalScore(scores)
}

async function scoreFund(targetId: string) {
  const response = await fetch(`${backendApiBaseUrl}/api/scoring/fund/${encodeURIComponent(targetId)}/professional`, {
    cache: 'no-store',
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const fallbackResponse = await fetch(`${backendApiBaseUrl}/api/scoring/fund/${encodeURIComponent(targetId)}`, {
      cache: 'no-store',
    })
    const fallbackPayload = await fallbackResponse.json().catch(() => ({}))
    if (!fallbackResponse.ok) {
      throw new Error(fallbackPayload.detail || fallbackPayload.error || payload.detail || '基金评分失败')
    }
    return fallbackPayload as BackendScoringPayload
  }
  return payload as BackendScoringPayload
}

async function scoreManager(targetId: string, requestUrl: string) {
  const origin = new URL(requestUrl).origin
  const response = await fetch(`${origin}/api/managers/${encodeURIComponent(targetId)}`, {
    cache: 'no-store',
  })
  const manager = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(manager.error || '基金经理评分失败')
  }

  const detail = manager as ManagerDetail
  const score = calculateManagementScore(
    detail.workYears ?? undefined,
    detail.managementYears ?? undefined,
    detail.fundCount ?? detail.currentFunds?.length ?? 0,
  )
  const finalScore = calculateFinalScore([score])
  return {
    scoring_source: 'manager_detail_exact_match',
    scoring: {
      overall_score: finalScore.totalScore,
      overall_grade: finalScore.grade,
      dimension_scores: {
        management: {
          score: score.score,
          weight: score.weight,
          evidence: [score.details || '基于经理任期和管理基金记录'],
        },
      },
      missing_data: [],
      scoring_time: new Date().toISOString(),
      calculation_method: 'manager_detail_exact_match',
    },
    scoring_history: [],
  } satisfies BackendScoringPayload
}

function responseFromScore(args: {
  targetType: TargetType
  targetId: string
  finalScore: FinalScore
  method: ScoreMethod
  payload?: BackendScoringPayload
}) {
  const latestScores = Object.fromEntries(
    args.finalScore.scores.map((score) => [
      score.dimension,
      {
        dimension: score.dimension,
        score: score.score,
        weight: score.weight,
        weightedScore: score.weightedScore,
        details: score.details,
      },
    ]),
  )
  return NextResponse.json({
    success: true,
    targetType: args.targetType,
    targetId: args.targetId,
    method: args.method,
    scoringSource: args.payload?.scoring_source || args.payload?.scoring?.calculation_method || args.method,
    finalScore: args.finalScore,
    scores: latestScores,
    history: args.payload?.scoring_history || [],
    missingData: args.payload?.scoring?.missing_data || [],
    dataQuality: args.payload?.scoring?.data_quality || null,
    positiveFactors: args.payload?.scoring?.positive_factors || [],
    negativeFactors: args.payload?.scoring?.negative_factors || [],
    buyBeforeBoundary: {
      label: '评分仅用于研究排序',
      detail: '该分数只用于基金研究排序；进入正式研究清单前必须通过材料核验、R1-R5 适当性、费用、赎回、限购、净值回放和正式研究复核报告门禁。',
      requiredGates: ['材料核验硬缺口', 'R1-R5 适当性', '费用与赎回规则', '限购/起购或定投规则', '净值回放', '正式研究复核报告'],
    },
    persisted: false,
  })
}

export async function POST(request: Request) {
  try {
    const body: ScoreRequest = await request.json()
    const { targetType, targetId, method = 'auto', manualScores } = body

    if (!targetId || !targetType) {
      return NextResponse.json({ error: '请提供 targetType 和 targetId' }, { status: 400 })
    }

    if (method === 'manual') {
      const finalScore = finalScoreFromManual(manualScores || [])
      return responseFromScore({ targetType, targetId, finalScore, method })
    }

    const payload = targetType === 'manager'
      ? await scoreManager(targetId, request.url)
      : await scoreFund(targetId)
    const finalScore = finalScoreFromBackend(payload)

    return responseFromScore({ targetType, targetId, finalScore, method, payload })
  } catch (error) {
    console.error('评分失败:', error)
    return NextResponse.json(
      { error: '评分失败', details: error instanceof Error ? error.message : '未知错误' },
      { status: 500 },
    )
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const targetId = searchParams.get('targetId')
    const targetType = searchParams.get('targetType') as TargetType | null

    if (!targetId || !targetType || !['fund', 'manager'].includes(targetType)) {
      return NextResponse.json({ error: '请提供有效的 targetType 和 targetId' }, { status: 400 })
    }

    const payload = targetType === 'manager'
      ? await scoreManager(targetId, request.url)
      : await scoreFund(targetId)
    const finalScore = finalScoreFromBackend(payload)

    return responseFromScore({ targetType, targetId, finalScore, method: 'auto', payload })
  } catch (error) {
    console.error('获取评分失败:', error)
    return NextResponse.json(
      { error: '获取评分失败', details: error instanceof Error ? error.message : '未知错误' },
      { status: 500 },
    )
  }
}
