"""
Brinson-Fachler 业绩归因模型 - 基于十大重仓股简化版
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# 申万一级行业列表
SW_INDUSTRIES = [
    "银行", "非银金融", "房地产", "食品饮料", "医药生物",
    "电子", "计算机", "通信", "电力设备", "汽车",
    "机械设备", "基础化工", "钢铁", "煤炭", "有色金属",
    "石油石化", "公用事业", "交通运输", "建筑材料", "建筑装饰",
    "轻工制造", "商贸零售", "社会服务", "传媒", "美容护理",
]

# 沪深300 基准行业权重 (近似值)
BENCHMARK_INDUSTRY_WEIGHTS = {
    "银行": 0.11, "非银金融": 0.08, "食品饮料": 0.07,
    "电力设备": 0.06, "医药生物": 0.06, "电子": 0.05,
    "计算机": 0.04, "煤炭": 0.03, "房地产": 0.03,
    "汽车": 0.03, "有色金属": 0.03, "化工": 0.03,
    "机械设备": 0.02, "交通运输": 0.02, "军工": 0.02,
}


class BrinsonAttributor:
    """Brinson 业绩归因计算器"""

    def __init__(self):
        self.benchmark_weights = BENCHMARK_INDUSTRY_WEIGHTS

    def calculate_from_industry_inputs(
        self,
        portfolio_industries: Dict[str, Dict[str, float]],
        benchmark_industries: Dict[str, Dict[str, float]],
        fund_return: float,
        benchmark_return: float,
        portfolio_coverage: float,
        benchmark_coverage: float,
        return_coverage: float,
    ) -> Dict[str, Any]:
        """使用明确的行业权重与区间收益计算 Brinson-Fachler 归因。"""
        if not portfolio_industries:
            return self._unavailable_attribution(
                fund_return,
                benchmark_return,
                ["基金行业权重缺失，不能计算 Brinson 配置与选择效应"],
            )
        if not benchmark_industries:
            return self._unavailable_attribution(
                fund_return,
                benchmark_return,
                ["基准行业权重缺失，不能计算 Brinson 配置效应"],
            )

        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0
        industry_details = []
        missing_items = []

        for industry in sorted(set(portfolio_industries) | set(benchmark_industries)):
            portfolio = portfolio_industries.get(industry) or {}
            benchmark = benchmark_industries.get(industry) or {}
            portfolio_weight = float(portfolio.get("weight") or 0)
            benchmark_weight = float(benchmark.get("weight") or 0)
            benchmark_industry_return = benchmark.get("return")
            portfolio_industry_return = portfolio.get("return")

            if benchmark_industry_return is None and benchmark_weight == 0 and portfolio_weight > 0:
                benchmark_industry_return = benchmark_return
            if benchmark_industry_return is None:
                missing_items.append(f"{industry} 缺少基准行业收益")
                continue
            if portfolio_weight > 0 and portfolio_industry_return is None:
                missing_items.append(f"{industry} 缺少基金持仓区间收益")
                continue
            if portfolio_industry_return is None:
                portfolio_industry_return = benchmark_industry_return

            allocation = (portfolio_weight - benchmark_weight) * (
                float(benchmark_industry_return) - benchmark_return
            )
            selection = benchmark_weight * (
                float(portfolio_industry_return) - float(benchmark_industry_return)
            )
            interaction = (portfolio_weight - benchmark_weight) * (
                float(portfolio_industry_return) - float(benchmark_industry_return)
            )

            allocation_effect += allocation
            selection_effect += selection
            interaction_effect += interaction
            industry_details.append({
                "industry": industry,
                "portfolio_weight": round(portfolio_weight, 6),
                "benchmark_weight": round(benchmark_weight, 6),
                "weight_diff": round(portfolio_weight - benchmark_weight, 6),
                "portfolio_return": round(float(portfolio_industry_return), 6),
                "benchmark_return": round(float(benchmark_industry_return), 6),
                "allocation_contrib": round(allocation, 6),
                "selection_contrib": round(selection, 6),
                "interaction_contrib": round(interaction, 6),
            })

        if missing_items:
            return self._unavailable_attribution(fund_return, benchmark_return, missing_items)

        active_return = fund_return - benchmark_return
        explained_return = allocation_effect + selection_effect + interaction_effect
        residual = active_return - explained_return
        if portfolio_coverage < 0.8:
            missing_items.append(f"基金持仓披露覆盖率仅 {portfolio_coverage:.1%}，结果只代表已披露持仓")
        if benchmark_coverage < 0.95:
            missing_items.append(f"基准成分收益覆盖率仅 {benchmark_coverage:.1%}")
        if return_coverage < 0.95:
            missing_items.append(f"基金持仓收益覆盖率仅 {return_coverage:.1%}")

        industry_details.sort(
            key=lambda item: abs(item["allocation_contrib"] + item["selection_contrib"] + item["interaction_contrib"]),
            reverse=True,
        )
        return {
            "status": "partial_evidence" if missing_items else "ok",
            "source": "brinson_fachler_industry_inputs",
            "active_return": round(active_return, 6),
            "allocation_effect": round(allocation_effect, 6),
            "selection_effect": round(selection_effect, 6),
            "interaction_effect": round(interaction_effect, 6),
            "residual": round(residual, 6),
            "explained_return": round(explained_return, 6),
            "industry_details": industry_details,
            "coverage": {
                "portfolio_holdings": round(portfolio_coverage, 6),
                "benchmark_constituents": round(benchmark_coverage, 6),
                "holding_returns": round(return_coverage, 6),
            },
            "missing_items": missing_items,
        }

    def calculate_attribution(
        self,
        holdings: List[Dict[str, Any]],
        fund_return: float,
        benchmark_return: float,
        industry_returns: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        计算 Brinson 业绩归因

        由于只有十大重仓股，使用简化版模型：

        - 总超额收益 = 组合收益 - 基准收益
        - 行业配置效应 = Σ(基准权重 - 组合权重) × 行业收益差
        - 个股选择效应 = Σ 组合权重 × (个股收益 - 行业平均收益)
        - 交互效应 = Σ(组合权重 - 基准权重) × (个股收益 - 行业平均收益)
        """
        if not holdings:
            return self._unavailable_attribution(
                fund_return,
                benchmark_return,
                ["持仓明细缺失，不能计算 Brinson 行业配置/选择效应"],
            )

        active_return = fund_return - benchmark_return

        # 估算基金行业配置
        industry_weights = {}
        total_weight = sum(h.get("weight", 0) for h in holdings)
        for h in holdings:
            ind = h.get("industry", "其他")
            industry_weights[ind] = industry_weights.get(ind, 0) + h.get("weight", 0)

        # 归一化
        if total_weight > 0:
            industry_weights = {k: v / total_weight for k, v in industry_weights.items()}

        if industry_returns is None:
            return self._unavailable_attribution(
                fund_return,
                benchmark_return,
                ["行业收益率序列缺失，不能输出可验证的 Brinson 归因"],
            )

        # 计算行业配置效应
        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0
        industry_details = []

        all_industries = set(list(industry_weights.keys()) + list(self.benchmark_weights.keys()))

        for ind in all_industries:
            fund_weight = industry_weights.get(ind, 0)
            bench_weight = self.benchmark_weights.get(ind, 0)
            ind_return = industry_returns.get(ind, benchmark_return)
            bench_ind_return = industry_returns.get(f"benchmark:{ind}")
            if bench_ind_return is None:
                return self._unavailable_attribution(
                    fund_return,
                    benchmark_return,
                    [f"{ind} 行业缺少基准行业收益，不能输出可验证的配置效应"],
                )

            if fund_weight > 0 or bench_weight > 0:
                stock_returns = [
                    h.get("return")
                    for h in holdings
                    if h.get("industry", "") == ind and h.get("return") is not None
                ]
                if not stock_returns:
                    return self._unavailable_attribution(
                        fund_return,
                        benchmark_return,
                        [f"{ind} 行业持仓缺少个股区间收益，不能输出可验证的选股效应"],
                    )
                avg_stock_return = sum(stock_returns) / max(len(stock_returns), 1)

                # 行业选择效应 (组合在行业内的超额)
                selection_contrib = fund_weight * (avg_stock_return - ind_return)

                # 资产配置效应 (相对基准的偏离)
                allocation_contrib = (bench_weight - 0) * (ind_return - bench_ind_return)

                # 交互效应
                interaction_contrib = (fund_weight - bench_weight) * (avg_stock_return - ind_return)

                allocation_effect += allocation_contrib
                selection_effect += selection_contrib
                interaction_effect += interaction_contrib

                industry_details.append({
                    "industry": ind,
                    "portfolio_weight": round(fund_weight, 4),
                    "benchmark_weight": round(bench_weight, 4),
                    "weight_diff": round(fund_weight - bench_weight, 4),
                    "portfolio_return": round(avg_stock_return, 4),
                    "benchmark_return": round(bench_ind_return, 4),
                    "allocation_contrib": round(allocation_contrib, 4),
                    "selection_contrib": round(selection_contrib, 4),
                })

        # 按权重排序
        industry_details.sort(key=lambda x: x["portfolio_weight"], reverse=True)

        # 归因残差
        explained = allocation_effect + selection_effect + interaction_effect
        residual = active_return - explained

        return {
            "active_return": round(active_return, 4),
            "allocation_effect": round(allocation_effect, 4),
            "selection_effect": round(selection_effect, 4),
            "interaction_effect": round(interaction_effect, 4),
            "residual": round(residual, 4),
            "explained_return": round(explained, 4),
            "industry_details": industry_details[:10],
        }

    def _unavailable_attribution(self, fund_return: float, benchmark_return: float, missing_items: List[str]) -> Dict[str, Any]:
        """证据不足时显式返回不可用，禁止用随机/估算数据冒充归因。"""
        active = fund_return - benchmark_return
        return {
            "status": "insufficient_evidence",
            "source": "evidence_gate",
            "active_return": round(active, 4),
            "allocation_effect": None,
            "selection_effect": None,
            "interaction_effect": None,
            "residual": None,
            "explained_return": None,
            "industry_details": [],
            "missing_items": missing_items,
        }
