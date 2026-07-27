// 后端 API 基础 URL (通过 Next.js proxy 代理)
const API_BASE = '/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(error.detail || `Request failed: ${res.status}`)
  }

  return res.json()
}

// ============ 基金 API ============

export async function getFund(windCode: string) {
  return request<{
    fund: FundInfo
    performance: PerformanceData
    risk_metrics: RiskMetrics
    style: StyleData
    scoring: FundScoring
  }>(`/funds/${windCode}`)
}

export async function getFundNav(windCode: string, startDate?: string, endDate?: string) {
  const params = new URLSearchParams()
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const qs = params.toString() ? `?${params}` : ''
  return request<{ wind_code: string; data: Array<{ date: string; nav: number }> }>(`/funds/${windCode}/nav${qs}`)
}

export async function getFundHoldings(windCode: string, quarter?: string) {
  const params = quarter ? `?quarter=${quarter}` : ''
  return request<{ wind_code: string; holdings: Holding[] }>(`/funds/${windCode}/holdings${params}`)
}

// ============ 基金经理 API ============

export async function getManagers(page = 1, company?: string) {
  const params = new URLSearchParams({ page: String(page) })
  if (company) params.set('company', company)
  return request<{ managers: ManagerInfo[]; total: number }>(`/managers/?${params}`)
}

export async function getManager(managerId: string) {
  return request<ManagerProfile>(`/managers/${managerId}`)
}

export async function getManagerReports(managerId: string, page = 1) {
  return request<{ reports: ResearchReport[]; total: number }>(`/managers/${managerId}/reports?page=${page}`)
}

export async function getManagerScore(managerId: string) {
  return request<ManagerScoring>(`/managers/${managerId}/score`)
}

export async function getManagerMorningstarRating(managerId: string) {
  return request<{
    overall_score: number
    star_rating: number
    dimension_scores: {
      return: number
      risk_adjusted: number
      stability: number
      experience: number
    }
    grade: string
    percentile_rank: number
  }>(`/managers/${managerId}/morningstar`)
}

// ============ 评分 API ============

export async function getFundScore(windCode: string) {
  return request<FundScoring>(`/scoring/fund/${windCode}`)
}

export async function recalculateScore(windCode: string) {
  return request(`/scoring/fund/${windCode}/recalculate`, { method: 'POST' })
}

export async function getLeaderboard(page = 1, limit = 20) {
  return request<{ rankings: RankingItem[]; total: number }>(`/scoring/leaderboard?limit=${limit}`)
}

export async function getScoringRules() {
  return request<{ rules: ScoringRule[] }>('/scoring/rules')
}

// ============ 调研报告库 API ============

export async function getResearchReports(page = 1, keyword?: string) {
  const params = new URLSearchParams({ page: String(page) })
  if (keyword) params.set('keyword', keyword)
  return request<{ total: number; data: ResearchReport[] }>(`/research-reports/?${params}`)
}

export async function searchSimilarReports(content: string, topK = 5) {
  return request<{ results: Array<ResearchReport & { similarity: number }> }>(
    '/research-reports/search/similar',
    { method: 'POST', body: JSON.stringify({ content, top_k: topK }) }
  )
}

export async function importReport(formData: FormData) {
  const res = await fetch(`${API_BASE}/research-reports/batch-import`, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type for FormData - browser sets it with boundary
    headers: {},
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: `Import failed: ${res.status}` }))
    throw new Error(error.detail || 'Import failed')
  }
  return res.json()
}

// ============ 筛选 API ============

export async function getScreeningTemplates() {
  return request<{ templates: Record<string, ScreeningTemplate> }>('/screening/templates')
}

export async function applyTemplate(templateKey: string, limit = 50) {
  return request<{ total: number; funds: FundCard[] }>(`/screening/template/${templateKey}?limit=${limit}`)
}

export async function customScreening(params: CustomFilterParams) {
  return request<{ total: number; funds: FundCard[] }>(
    '/screening/custom',
    { method: 'POST', body: JSON.stringify(params) }
  )
}

export async function getSavedScreenings() {
  return request<{ data: SavedScreening[] }>('/screening/saved')
}

export async function compareFunds(codes: string[]) {
  return request<ComparisonResult>(
    '/screening/compare',
    { method: 'POST', body: JSON.stringify(codes) }
  )
}

// ============ Barra 风险分析 API ============

export async function getBarraExposure(fundCode: string, quarter?: string) {
  const params = quarter ? `?quarter=${quarter}` : ''
  return request<BarraExposureResult>(`/barra/exposure/${fundCode}${params}`)
}

export async function getBarraFactorReturns(factor: string, startDate?: string, endDate?: string) {
  const params = new URLSearchParams({ factor })
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  return request<{ factor: string; returns: Array<{ date: string; return: number }> }>(`/barra/factor-returns?${params}`)
}

// ============ Brinson 归因 API ============

export async function getBrinsonAttribution(fundCode: string, benchmark = '000300', quarter?: string) {
  const params = new URLSearchParams({ benchmark })
  if (quarter) params.set('quarter', quarter)
  return request<BrinsonResult>(`/brinson/attribution/${fundCode}?${params}`)
}

// ============ AI 报告 API ============

export async function generateFundReport(windCode: string) {
  return request<{ report_id: string; status: string }>(`/reports/fund/${windCode}`, { method: 'POST' })
}

export async function generateManagerReport(managerId: string) {
  return request<{ report_id: string; status: string }>(`/reports/manager/${managerId}`, { method: 'POST' })
}

export async function getReport(reportId: string) {
  return request<AIReport>(`/reports/${reportId}`)
}

export async function getReportHistory(page = 1) {
  return request<{ total: number; reports: AIReport[] }>(`/reports/history?page=${page}`)
}

// ============ Types ============

export interface FundInfo {
  wind_code: string
  name: string
  full_name: string
  type: string
  manager: string
  management_company: string
  establishment_date: string
  total_asset: number
}

export interface PerformanceData {
  annualized_return_1y: number
  annualized_return_3y: number
  max_drawdown: number
  sharpe_ratio: number
  volatility: number
  sortino: number
  calmar_ratio: number
  win_rate_1y: number
}

export interface RiskMetrics {
  annualized_volatility_1y: number
  annualized_volatility_2y: number
  max_drawdown_1y: number
  max_drawdown_2y: number
  var_95: number
  beta: number
  alpha: number
  tracking_error: number
  information_ratio: number
}

export interface StyleData {
  SIZE: number
  SIZENL: number
  BETA: number
  MOMENTUM: number
  RESVOL: number
  SRSIZE: number
  LIQUIDITY: number
  BHADGE: number
  LEVERAGE: number
  STORIE: number
}

export interface FundCard extends FundInfo {
  performance?: PerformanceData
  risk_metrics?: RiskMetrics
  overall_score?: number
  overall_grade?: string
  scoring?: { overall_score: number; overall_grade: string }
}

export interface Holding {
  stock_code: string
  stock_name: string
  weight: number
  industry: string
  shares?: number
}

export interface ManagerInfo {
  manager_id: string
  name: string
  company: string
  tenure_years: number
  fund_count: number
  avg_score: number
}

export interface ManagerProfile {
  manager: ManagerInfo
  funds: FundCard[]
  scoring: ManagerScoring
  reports: ResearchReport[]
}

export interface ManagerScoring {
  overall_score: number
  overall_grade: string
  dimension_scores: Record<string, number>
}

export interface FundScoring {
  overall_score: number
  overall_grade: string
  dimension_scores: Record<string, { score: number; weighted_score: number }>
  metric_scores: Record<string, number>
}

export interface RankingItem {
  rank: number
  wind_code: string
  name: string
  type: string
  overall_score: number
  grade: string
  return_1y: number
  sharpe: number
  max_drawdown: number
}

export interface ScoringRule {
  dimension: string
  metric_name: string
  min_val: number
  max_val: number
  weight: number
  higher_is_better: boolean
}

export interface ResearchReport {
  id: string
  title: string
  manager_name?: string
  date?: string
  company?: string
  content?: string
  tags: string[]
  source: string
  summary?: string
}

export interface ScreeningTemplate {
  key: string
  name: string
  description: string
  criteria: Array<{ field: string; operator: string; value: number }>
}

export interface CustomFilterParams {
  return_min?: number
  return_max?: number
  sharpe_min?: number
  max_drawdown_max?: number
  volatility_max?: number
  score_min?: number
  fund_type?: string
  [key: string]: string | number | undefined
}

export interface SavedScreening {
  id: string
  name: string
  params: CustomFilterParams
  created_at: string
  result_count: number
}

export interface ComparisonResult {
  funds: FundCard[]
  metrics_summary: Record<string, { best: number; best_code: string }>
}

export interface AIReport {
  id: string
  type: 'fund' | 'manager'
  target_id: string
  content?: string
  created_at: string
}

// ============ Barra / Brinson Types ============

export interface BarraExposureResult {
  fund_code: string
  quarter: string
  exposures: BarraFactor[]
  total_factor_risk: number
  specific_risk: number
  r_squared: number
}

export interface BarraFactor {
  factor: string
  exposure: number
  factor_vol: number
  risk_contribution: number
}

export interface BrinsonResult {
  fund_code: string
  benchmark: string
  quarter: string
  returns: {
    portfolio: number
    benchmark: number
    active: number
  }
  attribution: {
    allocation_effect: number
    selection_effect: number
    interaction_effect: number
    total: number
  }
  industry_detail: IndustryAttribution[]
}

export interface IndustryAttribution {
  industry: string
  portfolio_weight: number
  benchmark_weight: number
  portfolio_return: number
  benchmark_return: number
  allocation_contrib: number
  selection_contrib: number
}