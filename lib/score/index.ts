/**
 * 评分引擎 - 基金和经理的多维度评分系统
 * 维度：收益能力、风险控制、择时能力、选股能力、风格稳定性、规模适应性
 */

export interface ScoreInput {
  targetType: "fund" | "manager";
  targetId: string;
  // 收益数据
  returns: number[]; // 各区间收益 [近1月, 近3月, 近6月, 近1年, 近2年, 近3年]
  benchmarkReturns: number[];
  // 风险数据
  volatility: number;      // 年化波动率
  maxDrawdown: number;     // 最大回撤
  sharpe: number;          // 夏普比率
  sortino: number;         // 索提诺比率
  // 归因数据
  allocationEffect?: number;  // 资产配置效应
  selectionEffect?: number;   // 个股选择效应
  interactionEffect?: number; // 交互效应
  // 持仓数据
  holdingsConcentration: number; // 前十大持仓集中度
  turnoverRate?: number;        // 换手率
  // 规模数据
  assetScale: number; // 规模（亿元）
  // 时间加权
  managementYears: number;
}

// 各维度权重配置
export const SCORE_WEIGHTS = {
  fund: {
    returnAbility: 0.25,
    riskControl: 0.25,
    stockSelection: 0.20,
    styleStability: 0.15,
    scaleAdaptability: 0.15,
  },
  manager: {
    returnAbility: 0.20,
    riskControl: 0.20,
    stockSelection: 0.20,
    philosophyConsistency: 0.20,
    competenceStability: 0.20,
  },
};

/** 计算收益能力得分 (0-100) */
export function calculateReturnScore(returns: number[], benchmarkReturns: number[]): number {
  // vs基准的超额收益
  const excessReturns = returns.map((r, i) => r - (benchmarkReturns[i] ?? 0));
  const avgExcess = excessReturns.reduce((a, b) => a + b, 0) / excessReturns.length;

  // vs同类排名
  // 简化：收益越高得分越高，使用指数变换映射到0-100
  const score = 50 + (avgExcess / 5) * 30;
  return clamp(score, 0, 100);
}

/** 计算风险控制得分 (0-100) */
export function calculateRiskControlScore(
  maxDrawdown: number,
  volatility: number,
  sharpe: number
): number {
  // 最大回撤得分：回撤越小越好
  const ddScore = maxDrawdown < 5 ? 100 : Math.max(0, 100 - (maxDrawdown - 5) * 3);

  // 波动率得分：波动越小越好
  const volScore = volatility < 10 ? 100 : Math.max(0, 100 - (volatility - 10) * 2);

  // 夏普得分：夏普>1.5优秀，<0.5差
  const sharpeScore = sharpe > 2 ? 100 : Math.max(0, sharpe * 40);

  return (ddScore * 0.4 + volScore * 0.3 + sharpeScore * 0.3);
}

/** 计算选股能力得分 (0-100) */
export function calculateStockSelectionScore(
  selectionEffect?: number,
  returns?: number[],
  benchmarkReturns?: number[]
): number {
  if (selectionEffect !== undefined) {
    // 直接使用归因数据
    // selectionEffect 单位是%，0.5% = 50BP
    const score = 50 + (selectionEffect - 0.2) * 100;
    return clamp(score, 0, 100);
  }

  // 回退方案：从收益中提取选股贡献
  if (returns && benchmarkReturns) {
    const avgExcess = returns.reduce((sum, r, i) => sum + (r - (benchmarkReturns[i] ?? 0)), 0) / returns.length;
    const score = 50 + avgExcess * 20;
    return clamp(score, 0, 100);
  }

  return 50;
}

/** 计算风格稳定性得分 (0-100) */
export function calculateStyleStabilityScore(
  holdingsConcentration: number,
  turnoverRate?: number
): number {
  // 集中度：前十大 >70% = 高集中，<40% = 分散
  let concScore = 100;
  if (holdingsConcentration > 70) concScore = 60;
  if (holdingsConcentration > 80) concScore = 40;

  // 换手率：年换手 0.5-2 = 适中，>4 = 高换手
  let turnoverScore = 80;
  if (turnoverRate !== undefined) {
    if (turnoverRate < 0.5) turnoverScore = 70;
    else if (turnoverRate > 3) turnoverScore = 50;
    else if (turnoverRate > 5) turnoverScore = 30;
  }

  return (concScore * 0.6 + turnoverScore * 0.4);
}

/** 计算规模适应性得分 (0-100) */
export function calculateScaleAdaptabilityScore(assetScale: number): number {
  // 规模 <5亿：运营风险
  // 规模 >100亿：策略容量限制
  if (assetScale < 2) return 40;
  if (assetScale < 5) return 60;
  if (assetScale < 30) return 100;
  if (assetScale < 80) return 85;
  if (assetScale < 150) return 60;
  return 30;
}

/** 计算综合得分 */
export function calculateComprehensiveScore(
  input: ScoreInput,
  weights: Record<string, number>
): Record<string, number> {
  const returnScore = calculateReturnScore(input.returns, input.benchmarkReturns);
  const riskControlScore = calculateRiskControlScore(input.maxDrawdown, input.volatility, input.sharpe);
  const stockSelectionScore = calculateStockSelectionScore(
    input.selectionEffect, input.returns, input.benchmarkReturns
  );
  const styleStabilityScore = calculateStyleStabilityScore(
    input.holdingsConcentration, input.turnoverRate
  );
  const scaleScore = calculateScaleAdaptabilityScore(input.assetScale);

  const dimensionScores = {
    returnAbility: returnScore,
    riskControl: riskControlScore,
    stockSelection: stockSelectionScore,
    styleStability: styleStabilityScore,
    scaleAdaptability: scaleScore,
  };

  // 加权综合得分
  const totalScore = Object.entries(dimensionScores).reduce(
    (sum, [key, score]) => sum + score * (weights[key] ?? 0),
    0
  );

  return {
    ...dimensionScores,
    total: Math.round(totalScore * 10) / 10,
  };
}

/** 辅助函数 */
function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** 生成评分详情（用于展示） */
export function generateScoreDetails(
  dimensionScores: Record<string, number>,
  rawData: ScoreInput
): Record<string, string> {
  const details: Record<string, string> = {};

  for (const [dim, score] of Object.entries(dimensionScores)) {
    if (dim === "total") continue;
    const starCount = Math.round(score / 20); // 5星制
    details[dim] = `${score.toFixed(1)}分 ${"★".repeat(starCount)}${"☆".repeat(5 - starCount)}`;
  }

  return details;
}
