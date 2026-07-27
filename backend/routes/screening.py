"""
基金筛选路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/screening", tags=["基金筛选"])

# 内置筛选模板
BUILTIN_TEMPLATES = {
    "high_sharpe": {
        "name": "高夏普比率",
        "description": "风险调整收益优秀的基金",
        "criteria": [
            {"field": "sharpe_ratio", "operator": ">=", "value": 1.5},
            {"field": "annualized_return_1y", "operator": ">=", "value": 0.10},
            {"field": "max_drawdown", "operator": "<=", "value": -0.15},
        ],
    },
    "low_risk": {
        "name": "低回撤稳健",
        "description": "最大回撤小、波动低的稳健基金",
        "criteria": [
            {"field": "max_drawdown", "operator": ">=", "value": -0.20},
            {"field": "annualized_volatility_1y", "operator": "<=", "value": 0.15},
            {"field": "annualized_return_1y", "operator": ">=", "value": 0.05},
        ],
    },
    "growth_style": {
        "name": "成长风格",
        "description": "偏好成长股的基金经理管理的基金",
        "criteria": [
            {"field": "MOMENTUM", "operator": ">=", "value": 0.3},
            {"field": "RESVOL", "operator": ">=", "value": 0.1},
        ],
    },
    "value_style": {
        "name": "价值风格",
        "description": "偏好价值股的基金",
        "criteria": [
            {"field": "BHADGE", "operator": "<=", "value": -0.2},
            {"field": "STORIE", "operator": ">=", "value": 0.3},
        ],
    },
    "top_ranked": {
        "name": "近1年业绩Top",
        "description": "近1年业绩排名前20%的基金",
        "criteria": [
            {"field": "annualized_return_1y", "operator": ">=", "value": 0.20},
            {"field": "sharpe_ratio", "operator": ">=", "value": 1.0},
        ],
    },
}


def evaluate_criteria(fund_data: Dict, criteria: List[Dict]) -> tuple[bool, Dict]:
    """评估单只基金是否满足条件"""
    results = {}
    for c in criteria:
        field = c["field"]
        operator = c["operator"]
        target = c["value"]

        value = None
        if field in fund_data.get("performance", {}):
            value = fund_data["performance"][field]
        elif field in fund_data.get("risk_metrics", {}):
            value = fund_data["risk_metrics"][field]
        elif field in fund_data.get("style", {}):
            value = fund_data["style"][field]
        elif field in fund_data:
            value = fund_data[field]

        if value is None:
            results[field] = {"matched": False, "reason": "数据缺失"}
            continue

        matched = False
        if operator == ">":
            matched = value > target
        elif operator == ">=":
            matched = value >= target
        elif operator == "<":
            matched = value < target
        elif operator == "<=":
            matched = value <= target
        elif operator == "==":
            matched = value == target
        elif operator == "!=":
            matched = value != target

        results[field] = {"value": value, "target": target, "operator": operator, "matched": matched}

    all_matched = all(r.get("matched", False) for r in results.values())
    return all_matched, results


def _criterion_value(criteria: List[Dict], field: str, operator: str):
    values = [
        c.get("value")
        for c in criteria
        if c.get("field") == field and c.get("operator") == operator
    ]
    return values[0] if values else None


def _criteria_to_repo_filters(criteria: List[Dict]) -> Dict[str, Any]:
    """把旧筛选条件翻译到数据库仓库层，避免抽样后本地筛选。"""
    return {
        "return_1y_min": _criterion_value(criteria, "annualized_return_1y", ">="),
        "return_1y_max": _criterion_value(criteria, "annualized_return_1y", "<="),
        "return_3y_min": _criterion_value(criteria, "annualized_return_3y", ">="),
        "return_3y_max": _criterion_value(criteria, "annualized_return_3y", "<="),
        "max_drawdown_1y_max": _criterion_value(criteria, "max_drawdown", "<="),
        "volatility_1y_max": _criterion_value(criteria, "annualized_volatility_1y", "<="),
        "sharpe_1y_min": _criterion_value(criteria, "sharpe_ratio", ">="),
    }


def _sort_to_repo(sort_by: str, sort_order: str) -> tuple[str, str]:
    sort_map = {
        "score": "screening_score",
        "return": "return",
        "risk": "risk",
        "sharpe": "sharpe",
    }
    direction = "asc" if str(sort_order).lower() == "asc" else "desc"
    return sort_map.get(sort_by, "screening_score"), direction


def _format_screening_fund(row: Dict[str, Any]) -> Dict[str, Any]:
    perf = row.get("performance_data") or {}
    risk = row.get("risk_metrics") or {}
    return {
        "wind_code": row.get("wind_code"),
        "name": row.get("name"),
        "type": row.get("type"),
        "nav": row.get("nav"),
        "nav_date": row.get("nav_date"),
        "total_asset": row.get("total_asset"),
        "establishment_date": row.get("establishment_date"),
        "performance": perf,
        "risk_metrics": risk,
        "screening_score": row.get("screening_score"),
        "holding_count": row.get("holding_count"),
        "scoring": {
            "overall_score": row.get("screening_score"),
            "overall_grade": None,
            "source": "database_screening_score_v1",
        },
        "evaluation": {
            "source": "database_predicate_pushdown",
            "matched": True,
        },
    }


@router.get("/templates")
async def get_screening_templates():
    """获取内置筛选模板"""
    return {"templates": BUILTIN_TEMPLATES}


@router.get("/template/{template_key}")
async def screening_by_template(
    template_key: str,
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("score"),
    sort_order: str = Query("desc"),
):
    """使用内置模板进行筛选 (GET)"""
    if template_key not in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"模板 '{template_key}' 不存在")

    template = BUILTIN_TEMPLATES[template_key]
    return await _do_custom_screening(template["criteria"], sort_by, sort_order, limit)


@router.post("/custom")
async def custom_screening(
    criteria: List[dict],
    fund_type: Optional[str] = Query(None),
    sort_by: str = Query("score", description="排序: score/return/risk/sharpe"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
):
    """自定义筛选"""
    return await _do_custom_screening(criteria, sort_by, sort_order, limit, fund_type)


async def _do_custom_screening(
    criteria: List[dict],
    sort_by: str,
    sort_order: str,
    limit: int,
    fund_type: Optional[str] = None,
):
    """执行筛选的内部函数"""
    try:
        from repositories import get_fund_repo

        repo_filters = _criteria_to_repo_filters(criteria)
        repo_sort_by, repo_sort_order = _sort_to_repo(sort_by, sort_order)
        list_result = get_fund_repo().list_funds(
            fund_type=fund_type,
            page=1,
            page_size=limit,
            tradable_only=True,
            sort_by=repo_sort_by,
            sort_order=repo_sort_order,
            **{key: value for key, value in repo_filters.items() if value is not None},
        )
        matched_funds = [_format_screening_fund(row) for row in list_result.get("funds", [])]
        return {
            "total": list_result.get("total", len(matched_funds)),
            "funds": matched_funds,
            "source": "database",
            "screening_source": "database_predicate_pushdown",
            "criteria_supported": repo_filters,
        }
    except Exception as e:
        logger.error(f"Custom screening error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_screening_criteria(
    name: str,
    criteria: List[dict],
    description: Optional[str] = None,
    is_public: bool = False,
    created_by: str = "manual",
):
    """保存自定义筛选条件"""
    from service_registry import get_db
    db = get_db()

    if db is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        doc = {
            "name": name,
            "description": description or "",
            "criteria": criteria,
            "created_by": created_by,
            "is_public": is_public,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = db.screening_criteria.insert_one(doc)
        return {"id": str(result.inserted_id), "status": "saved"}
    except Exception as e:
        logger.error(f"Save screening criteria error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved")
async def get_saved_criterias(
    created_by: Optional[str] = Query(None),
    include_public: bool = True,
):
    """获取已保存的筛选条件"""
    from service_registry import get_db
    db = get_db()

    if db is None:
        return {"data": []}

    try:
        query = {}
        if include_public and not created_by:
            query["is_public"] = True
        elif created_by:
            query["$or"] = [{"created_by": created_by}, {"is_public": True}]

        cursor = db.screening_criteria.find(query).sort("created_at", -1)
        items = []
        for doc in cursor:
            items.append({
                "id": str(doc.get("_id", "")),
                "name": doc.get("name"),
                "description": doc.get("description"),
                "criteria": doc.get("criteria"),
                "created_by": doc.get("created_by"),
                "is_public": doc.get("is_public"),
                "created_at": doc.get("created_at"),
            })
        return {"data": items}
    except Exception as e:
        logger.error(f"Get saved criteria error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_funds(
    wind_codes: List[str],
):
    """对比多只基金"""
    from service_registry import get_data_service, get_scoring_engine
    data_svc = get_data_service()
    scoring_engine = get_scoring_engine()

    try:
        fund_comparisons = []
        for code in wind_codes:
            info = data_svc.get_fund_info(code)
            perf = data_svc.get_fund_performance(code)
            risk = data_svc.get_fund_risk_metrics(code)
            style = data_svc.get_fund_style(code)
            scoring = scoring_engine.score_fund(perf, risk, style)
            fund_comparisons.append({
                "wind_code": code,
                "name": info.get("name"),
                "type": info.get("type"),
                "performance": perf,
                "risk_metrics": risk,
                "style": style,
                "scoring": scoring,
            })

        metrics_summary = {}
        for fc in fund_comparisons:
            for key, val in {**fc["performance"], **fc["risk_metrics"]}.items():
                if val is not None and isinstance(val, (int, float)):
                    if key not in metrics_summary:
                        metrics_summary[key] = {"values": [], "best": None, "best_code": None}
                    metrics_summary[key]["values"].append((fc["wind_code"], val))
                    if metrics_summary[key]["best"] is None or val > metrics_summary[key]["best"]:
                        metrics_summary[key]["best"] = val
                        metrics_summary[key]["best_code"] = fc["wind_code"]

        return {
            "funds": fund_comparisons,
            "metrics_summary": metrics_summary,
        }
    except Exception as e:
        logger.error(f"Compare funds error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
