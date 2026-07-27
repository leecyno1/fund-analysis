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
