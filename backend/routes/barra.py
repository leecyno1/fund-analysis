"""
Barra 风险因子 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/barra", tags=["Barra风险分析"])


@router.get("/exposure/{fund_code}", deprecated=True)
async def get_barra_exposure(
    fund_code: str,
    quarter: str = Query(None, description="季度, 如: 2024Q1"),
):
    """获取基金 Barra 因子暴露度"""
    try:
        from lib.barra.factor_calculation import BarraCalculator
        from service_registry import get_data_service

        data_svc = get_data_service()
        calculator = BarraCalculator()

        if quarter is None:
            year = datetime.now().year
            q = (datetime.now().month - 1) // 3 + 1
            quarter = f"{year}Q{q}"

        holdings = data_svc.get_fund_holdings(fund_code, quarter)
        style_factors = data_svc.get_fund_style(fund_code)
        result = calculator.get_exposure_result(holdings, style_factors, quarter)
        if result.get("status") == "insufficient_evidence":
            return {
                "fund_code": fund_code,
                "quarter": quarter,
                "status": "insufficient_evidence",
                "source": "evidence_gate",
                "exposures": [],
                "industry_exposures": {},
                "risk_contributions": [],
                "total_factor_risk": None,
                "specific_risk": None,
                "r_squared": None,
                "num_holdings": result.get("num_holdings", 0),
                "top10_weight": result.get("top10_weight", 0),
                "missing_items": result.get("missing_items", []),
            }

        # 持久化到数据库
        try:
            from repositories import get_factor_repo
            factor_repo = get_factor_repo()
            factor_repo.save_exposures(
                fund_code, quarter,
                result.get("style_exposures", {}),
                result.get("risk_contributions", [])
            )
        except Exception as db_err:
            logger.warning(f"Failed to save Barra exposures to DB: {db_err}")

        return {
            "fund_code": fund_code,
            "quarter": quarter,
            "exposures": [
                {
                    "factor": k,
                    "exposure": v,
                    "factor_vol": 0.12,
                    "risk_contribution": next(
                        (r["risk_contribution"] for r in result.get("risk_contributions", []) if r["factor"] == k),
                        0.0
                    ),
                }
                for k, v in result.get("style_exposures", {}).items()
            ],
            "industry_exposures": result.get("industry_exposures", {}),
            "risk_contributions": result.get("risk_contributions", []),
            "total_factor_risk": result.get("total_factor_risk", 0),
            "specific_risk": result.get("specific_risk", 0.02),
            "r_squared": result.get("r_squared", 0),
            "num_holdings": result.get("num_holdings", 0),
            "top10_weight": result.get("top10_weight", 0),
            "status": result.get("status", "ok"),
            "missing_items": result.get("missing_items", []),
        }
    except Exception as e:
        logger.error(f"Barra exposure error for {fund_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-decomposition/{fund_code}", deprecated=True)
async def get_risk_decomposition(
    fund_code: str,
    quarter: str = Query(None),
):
    """获取风险分解"""
    try:
        from lib.barra.factor_calculation import BarraCalculator
        from service_registry import get_data_service

        data_svc = get_data_service()
        calculator = BarraCalculator()

        if quarter is None:
            year = datetime.now().year
            q = (datetime.now().month - 1) // 3 + 1
            quarter = f"{year}Q{q}"

        holdings = data_svc.get_fund_holdings(fund_code, quarter)
        style_factors = data_svc.get_fund_style(fund_code)
        result = calculator.get_exposure_result(holdings, style_factors, quarter)
        if result.get("status") == "insufficient_evidence":
            return {
                "fund_code": fund_code,
                "quarter": quarter,
                "status": "insufficient_evidence",
                "source": "evidence_gate",
                "factor_risk": None,
                "specific_risk": None,
                "factor_risk_pct": None,
                "specific_risk_pct": None,
                "r_squared": None,
                "risk_contributions": [],
                "missing_items": result.get("missing_items", []),
            }

        total = result.get("total_factor_risk", 0) + result.get("specific_risk", 0)
        factor_risk_pct = result.get("total_factor_risk", 0) / max(total, 0.001)
        specific_risk_pct = result.get("specific_risk", 0) / max(total, 0.001)

        return {
            "fund_code": fund_code,
            "quarter": quarter,
            "factor_risk": round(result.get("total_factor_risk", 0), 6),
            "specific_risk": round(result.get("specific_risk", 0), 6),
            "factor_risk_pct": round(factor_risk_pct, 4),
            "specific_risk_pct": round(specific_risk_pct, 4),
            "r_squared": result.get("r_squared", 0),
            "risk_contributions": result.get("risk_contributions", []),
        }
    except Exception as e:
        logger.error(f"Risk decomposition error for {fund_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/score/{fund_code}", deprecated=True)
async def get_barra_score(
    fund_code: str,
    quarter: str = Query(None),
):
    """兼容旧调用方：Barra 不再生成基金评价分数。"""
    return {
        "fund_code": fund_code,
        "quarter": quarter,
        "status": "deprecated",
        "source": "methodology_scope",
        "role": "explanatory_evidence",
        "included_in_fund_evaluation_score": False,
        "overall_score": None,
        "grade": "not_applicable",
        "dimensions": {},
        "details": {},
        "replacement_endpoint": f"/api/funds/{fund_code}/evaluation",
        "missing_items": [
            "Barra 只用于解释风格暴露和风险来源，不单独判断基金优劣",
            "旧版手工加权 Barra 分数已停止输出",
        ],
    }
