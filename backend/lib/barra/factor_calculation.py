"""
Barra 多因子风险模型 - 基于十大重仓股计算
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Barra 风格因子定义
BARRA_FACTORS = {
    "SIZE": {"name": "规模因子", "description": "大盘/小盘暴露"},
    "SIZENL": {"name": "非线性规模", "description": "非线性规模效应"},
    "BETA": {"name": "Beta因子", "description": "市场系统性风险"},
    "MOMENTUM": {"name": "动量因子", "description": "历史收益动量"},
    "RESVOL": {"name": "残余波动率", "description": "特异性波动率"},
    "SRSIZE": {"name": "短期规模", "description": "短期规模效应"},
    "LIQUIDITY": {"name": "流动性因子", "description": "交易流动性"},
    "BHADGE": {"name": "价值因子", "description": "账面市值比"},
    "LEVERAGE": {"name": "杠杆因子", "description": "财务杠杆"},
    "STORIE": {"name": "成长因子", "description": "营收/利润增速"},
}

# 行业因子映射 (申万一级行业)
INDUSTRY_FACTORS = [
    "银行", "非银金融", "房地产", "食品饮料", "医药生物",
    "电子", "计算机", "通信", "电力设备", "汽车",
    "机械设备", "基础化工", "钢铁", "煤炭", "有色金属",
    "石油石化", "公用事业", "交通运输", "建筑材料", "建筑装饰",
]


class BarraCalculator:
    """Barra 风险因子计算器"""

    def __init__(self):
        self.factor_cov_matrix = self._get_factor_cov_matrix()

    def _get_factor_cov_matrix(self) -> Dict[str, Dict[str, float]]:
        """简化版因子协方差矩阵（基于经验数据）"""
        return {
            "SIZE":        {"SIZE": 0.01, "SIZENL": 0.003, "BETA": 0.002, "MOMENTUM": 0, "RESVOL": 0.001},
            "SIZENL":      {"SIZE": 0.003, "SIZENL": 0.008, "BETA": 0.001, "MOMENTUM": 0, "RESVOL": 0.001},
            "BETA":        {"SIZE": 0.002, "SIZENL": 0.001, "BETA": 0.015, "MOMENTUM": -0.001, "RESVOL": 0.002},
            "MOMENTUM":    {"SIZE": 0, "SIZENL": 0, "BETA": -0.001, "MOMENTUM": 0.04, "RESVOL": 0},
            "RESVOL":      {"SIZE": 0.001, "SIZENL": 0.001, "BETA": 0.002, "MOMENTUM": 0, "RESVOL": 0.02},
        }

    def calculate_exposure(
        self,
        holdings: List[Dict[str, Any]],
        style_factors: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        计算组合的因子暴露度

        基于十大重仓股加权平均
        """
        if not holdings:
            return self._unavailable_exposure(["持仓明细缺失，不能计算 Barra 风格/行业暴露"])
        style_factors = style_factors or {}

        # 计算总权重
        total_weight = sum(h.get("weight", 0) for h in holdings)
        if total_weight <= 0:
            return self._unavailable_exposure(["持仓权重缺失或合计为 0，不能计算 Barra 暴露"])

        # 归一化权重
        for h in holdings:
            h["_norm_weight"] = h.get("weight", 0) / total_weight

        # 计算风格因子暴露度
        exposures = {}
        for factor_key in BARRA_FACTORS:
            if factor_key in style_factors and style_factors[factor_key] is not None:
                exposures[factor_key] = style_factors[factor_key]
        missing_style_factors = [factor_key for factor_key in BARRA_FACTORS if factor_key not in exposures]

        # 计算行业暴露度
        industry_exposure = {}
        for ind in INDUSTRY_FACTORS:
            ind_weight = sum(
                h.get("_norm_weight", 0)
                for h in holdings
                if h.get("industry", "") == ind
            )
            industry_exposure[ind] = ind_weight

        # 过滤掉0暴露行业
        industry_exposure = {k: v for k, v in industry_exposure.items() if v > 0.01}

        return {
            "status": "ok" if not missing_style_factors else "partial",
            "style_exposures": exposures,
            "industry_exposures": industry_exposure,
            "total_holdings": len(holdings),
            "top10_weight": total_weight,
            "missing_items": [f"Barra 风格因子 {factor} 缺失，未用启发式估算" for factor in missing_style_factors],
        }

    def calculate_risk_contribution(
        self,
        exposures: Dict[str, float],
        portfolio_vol: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """
        计算因子风险贡献

        基于因子暴露度和因子波动率
        """
        factor_vols = {
            "SIZE": 0.10, "SIZENL": 0.09, "BETA": 0.12, "MOMENTUM": 0.20,
            "RESVOL": 0.14, "SRSIZE": 0.08, "LIQUIDITY": 0.06,
            "BHADGE": 0.08, "LEVERAGE": 0.05, "STORIE": 0.10,
        }

        results = []
        total_risk = 0.0

        for factor, exposure in exposures.items():
            vol = factor_vols.get(factor, 0.1)
            # 风险贡献 = exposure^2 * vol^2
            risk_contrib = (exposure ** 2) * (vol ** 2)
            total_risk += risk_contrib

            results.append({
                "factor": factor,
                "factor_name": BARRA_FACTORS.get(factor, {}).get("name", factor),
                "exposure": round(exposure, 4),
                "factor_vol": vol,
                "risk_contribution_raw": risk_contrib,
            })

        # 计算风险贡献占比
        for r in results:
            r["risk_contribution"] = round(r["risk_contribution_raw"] / max(total_risk, 0.001), 4)
            r["exposure"] = round(r["exposure"], 4)

        # 按风险贡献排序
        results.sort(key=lambda x: x["risk_contribution"], reverse=True)
        return results

    def calculate_r_squared(
        self,
        exposures: Dict[str, float],
        specific_var: float = 0.02,
    ) -> float:
        """计算因子解释度 R²"""
        total_var = 0.0
        factor_vols = {
            "SIZE": 0.10, "SIZENL": 0.09, "BETA": 0.12, "MOMENTUM": 0.20,
            "RESVOL": 0.14, "SRSIZE": 0.08, "LIQUIDITY": 0.06,
            "BHADGE": 0.08, "LEVERAGE": 0.05, "STORIE": 0.10,
        }

        for factor, exposure in exposures.items():
            vol = factor_vols.get(factor, 0.1)
            total_var += (exposure ** 2) * (vol ** 2)

        total_var += specific_var
        factor_risk = total_var - specific_var
        r_squared = factor_risk / max(total_var, 0.001)
        return round(r_squared, 4)

    def get_exposure_result(
        self,
        holdings: List[Dict[str, Any]],
        style_factors: Dict[str, float],
        quarter: str,
    ) -> Dict[str, Any]:
        """获取完整的 Barra 暴露度结果"""
        exposure_data = self.calculate_exposure(holdings, style_factors)
        style_exposures = exposure_data.get("style_exposures", {})
        if not style_exposures:
            return {
                "status": "insufficient_evidence",
                "quarter": quarter,
                "style_exposures": {},
                "industry_exposures": {},
                "risk_contributions": [],
                "total_factor_risk": None,
                "specific_risk": None,
                "r_squared": None,
                "num_holdings": exposure_data.get("total_holdings", 0),
                "top10_weight": round(exposure_data.get("top10_weight", 0), 4),
                "missing_items": exposure_data.get("missing_items", ["Barra 风格因子数据缺失"]),
            }

        risk_contributions = self.calculate_risk_contribution(style_exposures)
        r_squared = self.calculate_r_squared(style_exposures)
        total_factor_risk = sum(r["risk_contribution_raw"] for r in risk_contributions)

        return {
            "quarter": quarter,
            "style_exposures": {
                k: round(v, 4) for k, v in style_exposures.items()
            },
            "industry_exposures": {
                k: round(v, 4) for k, v in exposure_data.get("industry_exposures", {}).items()
            },
            "risk_contributions": risk_contributions,
            "total_factor_risk": round(total_factor_risk, 6),
            "specific_risk": 0.02,
            "r_squared": r_squared,
            "num_holdings": exposure_data.get("total_holdings", 0),
            "top10_weight": round(exposure_data.get("top10_weight", 0), 4),
            "status": exposure_data.get("status", "ok"),
            "missing_items": exposure_data.get("missing_items", []),
        }

    def _unavailable_exposure(self, missing_items: List[str]) -> Dict[str, Any]:
        """证据不足时显式返回不可用，禁止用随机暴露冒充 Barra 结果。"""
        return {
            "status": "insufficient_evidence",
            "style_exposures": {},
            "industry_exposures": {},
            "total_holdings": 0,
            "top10_weight": 0,
            "missing_items": missing_items,
        }
