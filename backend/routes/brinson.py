"""
Brinson 业绩归因 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/brinson", tags=["Brinson业绩归因"])


def _missing_benchmark_attribution(fund_code: str, benchmark: str, quarter: str, fund_return: float):
    return {
        "fund_code": fund_code,
        "benchmark": benchmark,
        "quarter": quarter,
        "status": "insufficient_evidence",
        "source": "evidence_gate",
        "returns": {
            "fund": round(fund_return, 4),
            "benchmark": None,
            "active": None,
        },
        "attribution": {
            "allocation_effect": None,
            "selection_effect": None,
            "interaction_effect": None,
            "residual": None,
            "total": None,
        },
        "industry_detail": [],
        "missing_items": ["基准区间收益缺失，不能输出可验证的 Brinson 归因"],
    }


@router.get("/attribution/{fund_code}")
async def get_brinson_attribution(
    fund_code: str,
    benchmark: str = Query("000300", description="基准指数代码"),
    quarter: str = Query(None, description="季度, 如: 2024Q1"),
):
    """获取 Brinson 业绩归因"""
    try:
        from lib.brinson.attribution import BrinsonAttributor
        from service_registry import get_data_service

        data_svc = get_data_service()
        attributor = BrinsonAttributor()

        if quarter is None:
            year = datetime.now().year
            q = (datetime.now().month - 1) // 3 + 1
            quarter = f"{year}Q{q}"

        # 获取基金收益
        perf = data_svc.get_fund_performance(fund_code)
        fund_return = perf.get("annualized_return_1y", 0)

        benchmark_return = perf.get("benchmark_return_1y")
        if benchmark_return is None:
            return _missing_benchmark_attribution(fund_code, benchmark, quarter, fund_return)

        # 获取持仓
        holdings = data_svc.get_fund_holdings(fund_code, quarter)

        # 计算归因
        attribution = attributor.calculate_attribution(
            holdings, fund_return, benchmark_return
        )
        if attribution.get("status") == "insufficient_evidence":
            return {
                "fund_code": fund_code,
                "benchmark": benchmark,
                "quarter": quarter,
                "status": "insufficient_evidence",
                "source": "evidence_gate",
                "returns": {
                    "fund": round(fund_return, 4),
                    "benchmark": round(benchmark_return, 4),
                    "active": round(fund_return - benchmark_return, 4),
                },
                "attribution": {
                    "allocation_effect": None,
                    "selection_effect": None,
                    "interaction_effect": None,
                    "residual": None,
                    "total": None,
                },
                "industry_detail": [],
                "missing_items": attribution.get("missing_items", []),
            }

        return {
            "fund_code": fund_code,
            "benchmark": benchmark,
            "quarter": quarter,
            "returns": {
                "fund": round(fund_return, 4),
                "benchmark": round(benchmark_return, 4),
                "active": round(fund_return - benchmark_return, 4),
            },
            "attribution": {
                "allocation_effect": attribution.get("allocation_effect", 0),
                "selection_effect": attribution.get("selection_effect", 0),
                "interaction_effect": attribution.get("interaction_effect", 0),
                "residual": attribution.get("residual", 0),
                "total": round(
                    attribution.get("allocation_effect", 0)
                    + attribution.get("selection_effect", 0)
                    + attribution.get("interaction_effect", 0),
                    4
                ),
            },
            "industry_detail": attribution.get("industry_details", []),
        }
    except Exception as e:
        logger.error(f"Brinson attribution error for {fund_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{fund_code}")
async def get_brinson_history(
    fund_code: str,
    quarters: int = Query(8, ge=1, le=16, description="最近季度数"),
):
    """获取归因历史"""
    try:
        from lib.brinson.attribution import BrinsonAttributor
        from service_registry import get_data_service

        data_svc = get_data_service()
        attributor = BrinsonAttributor()

        attributions = []
        perf = data_svc.get_fund_performance(fund_code)
        fund_return = perf.get("annualized_return_1y", 0)
        benchmark_return = perf.get("benchmark_return_1y")
        if benchmark_return is None:
            return {
                "fund_code": fund_code,
                "status": "insufficient_evidence",
                "source": "evidence_gate",
                "attributions": [],
                "summary": {
                    "avg_allocation": None,
                    "avg_selection": None,
                    "total_active": None,
                    "information_ratio": None,
                },
                "missing_items": ["基准区间收益缺失，不能输出可验证的 Brinson 历史归因"],
            }

        for i in range(quarters):
            year = datetime.now().year
            q = (datetime.now().month - 1) // 3 + 1 - i
            while q <= 0:
                q += 4
                year -= 1
            quarter = f"{year}Q{q}"

            holdings = data_svc.get_fund_holdings(fund_code, quarter)
            attr = attributor.calculate_attribution(holdings, fund_return * 0.25, benchmark_return * 0.25)
            if attr.get("status") == "insufficient_evidence":
                attributions.append({
                    "quarter": quarter,
                    "status": "insufficient_evidence",
                    "active_return": attr.get("active_return", 0),
                    "allocation_effect": None,
                    "selection_effect": None,
                    "interaction_effect": None,
                    "missing_items": attr.get("missing_items", []),
                })
                continue
            attributions.append({
                "quarter": quarter,
                "active_return": attr.get("active_return", 0),
                "allocation_effect": attr.get("allocation_effect", 0),
                "selection_effect": attr.get("selection_effect", 0),
                "interaction_effect": attr.get("interaction_effect", 0),
            })

        # 汇总统计
        available_attributions = [item for item in attributions if item.get("status") != "insufficient_evidence"]
        if not available_attributions:
            return {
                "fund_code": fund_code,
                "status": "insufficient_evidence",
                "source": "evidence_gate",
                "attributions": attributions,
                "summary": {
                    "avg_allocation": None,
                    "avg_selection": None,
                    "total_active": round(sum(a["active_return"] for a in attributions), 4),
                    "information_ratio": None,
                },
                "missing_items": sorted({
                    missing
                    for item in attributions
                    for missing in item.get("missing_items", [])
                }),
            }

        avg_alloc = sum(a["allocation_effect"] for a in available_attributions) / len(available_attributions)
        avg_sel = sum(a["selection_effect"] for a in available_attributions) / len(available_attributions)
        total_active = sum(a["active_return"] for a in attributions)
        active_returns = [a["active_return"] for a in attributions if a["active_return"] != 0]
        ir = (sum(active_returns) / len(active_returns)) / (sum((r - sum(active_returns)/len(active_returns))**2 for r in active_returns) / len(active_returns)) ** 0.5 if len(active_returns) > 1 else 0

        return {
            "fund_code": fund_code,
            "attributions": attributions,
            "summary": {
                "avg_allocation": round(avg_alloc, 4),
                "avg_selection": round(avg_sel, 4),
                "total_active": round(total_active, 4),
                "information_ratio": round(ir, 4),
            },
        }
    except Exception as e:
        logger.error(f"Brinson history error for {fund_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
