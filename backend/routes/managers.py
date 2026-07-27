"""
基金经理路由 - 经理搜索、详情、评分
"""
import math
import time
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/managers", tags=["基金经理"])


def _clean_nan(obj):
    """递归清理 NaN/Inf 值"""
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_nan(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


def _build_career(info: dict) -> list:
    """从基金历史构建职业履历"""
    fund_history = info.get("fund_history", [])
    if not fund_history:
        return []

    company = info.get("company", "未知基金公司")
    career = [{
        "start_date": fund_history[0].get("start_date", ""),
        "end_date": "",
        "company": company,
        "position": "基金经理",
    }]

    # 按时间排序
    career.sort(key=lambda x: x.get("start_date", ""), reverse=True)
    return career


def _build_investment_philosophy(info: dict) -> str:
    """根据经理背景生成投资理念描述"""
    funds = info.get("fund_history", [])
    fund_types = set()
    for f in funds:
        name = f.get("fund_name", "")
        if "混合" in name:
            fund_types.add("灵活配置")
        elif "债券" in name or "债" in name:
            fund_types.add("固定收益")
        elif "股票" in name or "指数" in name:
            fund_types.add("权益投资")

    if not fund_types:
        return "注重风险控制，追求长期稳健收益。投资风格灵活，偏好基本面分析，结合行业趋势进行配置。"
    elif "灵活配置" in fund_types:
        return "注重风险收益平衡，追求绝对收益目标。灵活配置股债比例，择时能力强，偏好行业龙头。"
    elif "固定收益" in fund_types:
        return "专注固定收益类投资，注重资产安全性和流动性。偏好高信用等级债券，严控信用风险。"
    else:
        return "注重价值投资，精选优质标的。偏好长期持有，分享企业成长收益。投资风格稳健，回撤控制意识强。"


def _get_services():
    from service_registry import get_data_service, get_scoring_engine, get_db
    return get_data_service(), get_scoring_engine(), get_db()


@router.get("/")
async def list_managers(
    company: Optional[str] = Query(None, description="管理公司"),
    keyword: Optional[str] = Query(None, description="搜索关键词（经理名/ID）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, le=100),
    sort_by: str = Query("score", description="排序: score/experience/aum"),
    sort_order: str = Query("desc"),
):
    """获取基金经理列表（优化版：跳过昂贵的 fund performance/risk/style 调用）"""
    from services.cache_service import get_cache, TTL

    data_svc, _, db = _get_services()
    cache = get_cache()

    try:
        # 尝试从缓存获取经理列表
        cache_key = f"manager:list:{company or ''}:{keyword or ''}:{page}:{page_size}:{sort_by}:{sort_order}"
        cached = cache.get(cache_key)
        if cached is not None:
            return _clean_nan(cached)

        # 直接从 Tushare 获取经理列表（使用新的缓存机制）
        managers_data = data_svc.get_manager_list(page=page, page_size=page_size, keyword=keyword, company=company)
        managers = managers_data.get("managers", [])
        total = managers_data.get("total", 0)

        # 如果有缓存的评分，获取平均评分
        for m in managers:
            manager_id = m.get("manager_id", "")
            funds = m.get("funds", [])[:3]

            cached_scores = []
            for fund in funds:
                code = fund.get("wind_code", "")
                if code:
                    score_cache = cache.get(f"fund:score:{code}")
                    if score_cache is not None:
                        cached_scores.append(score_cache)

            if cached_scores:
                avg_score = sum(cached_scores) / len(cached_scores)
                m["avg_score"] = round(avg_score, 2)
                m["score_evidence"] = "cached_fund_scores"
            else:
                m["avg_score"] = None
                m["score_evidence"] = "insufficient_evidence"

        # 排序
        sort_keys = {
            "score": lambda x: x.get("avg_score") if x.get("avg_score") is not None else -1,
            "experience": lambda x: x.get("tenure_years", 0),
            "aum": lambda x: x.get("fund_count", 0),
        }
        if sort_by in sort_keys:
            managers.sort(key=sort_keys[sort_by], reverse=(sort_order == "desc"))

        result = {"total": total, "page": page, "page_size": page_size, "managers": managers}
        cache.set(cache_key, result, TTL.SHORT)
        return _clean_nan(result)
    except Exception as e:
        logger.error(f"List managers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{manager_id}")
async def get_manager_detail(manager_id: str):
    """获取经理详细信息"""
    from services.cache_service import get_cache, TTL

    cache = get_cache()
    cache_key = f"manager:detail:{manager_id}"
    cached = cache.get(cache_key)
    if cached is not None and cached.get("manager_id") == manager_id:
        return _clean_nan(cached)

    data_svc, scoring_engine, db = _get_services()

    try:
        keyword = manager_id.split("|")[0] if "|" in manager_id else manager_id
        managers_data = data_svc.get_manager_list(page=1, page_size=100, keyword=keyword)
        exact_matches = [
            item for item in managers_data.get("managers", [])
            if item.get("manager_id") == manager_id or item.get("name") == manager_id
        ]
        matched = exact_matches[0] if exact_matches else None
        info = None
        if matched:
            funds = matched.get("funds", []) or []
            active_funds = [fund for fund in funds if not fund.get("end_date")]
            info = {
                "manager_id": matched.get("manager_id", manager_id),
                "name": matched.get("name", ""),
                "gender": matched.get("gender", ""),
                "education": matched.get("education") or matched.get("edu", ""),
                "company": matched.get("company", ""),
                "tenure_years": matched.get("tenure_years", 0),
                "begin_date": matched.get("begin_date", ""),
                "birth_year": matched.get("birth_year"),
                "fund_count": matched.get("fund_count", len(funds)),
                "current_funds": [fund.get("wind_code") for fund in active_funds if fund.get("wind_code")],
                "fund_history": funds,
            }
        else:
            info = data_svc.get_manager_info(manager_id)

        if not info:
            raise HTTPException(status_code=404, detail=f"经理不存在: {manager_id}")

        fund_history = info.get("fund_history", []) or []
        fund_details = [
            {
                "wind_code": fund.get("wind_code", ""),
                "name": fund.get("fund_name") or fund.get("name") or fund.get("wind_code", ""),
                "fund_name": fund.get("fund_name") or fund.get("name") or fund.get("wind_code", ""),
                "start_date": fund.get("start_date") or fund.get("since"),
                "end_date": fund.get("end_date") or fund.get("to_date"),
            }
            for fund in fund_history
            if fund.get("wind_code")
        ]

        # 获取相关调研报告
        reports = []
        if db is not None:
            try:
                reports_cursor = db.research_reports.find({"manager_id": manager_id}).sort("report_date", -1).limit(10)
                for r in reports_cursor:
                    reports.append({
                        "id": str(r.get("_id", "")),
                        "title": r.get("title"),
                        "report_date": r.get("report_date"),
                        "source": r.get("source"),
                        "summary": r.get("summary"),
                        "tags": r.get("tags", []),
                    })
            except Exception:
                pass

        result = _clean_nan({
            # 扁平化结构，匹配前端期望
            "manager_id": info.get("manager_id", ""),
            "name": info.get("name", ""),
            "gender": info.get("gender", ""),
            "education": info.get("education", ""),
            "company": info.get("company", ""),
            "tenure_years": info.get("tenure_years", 0),
            "begin_date": info.get("begin_date", ""),
            "birth_year": info.get("birth_year"),
            "fund_count": info.get("fund_count", len(fund_details)),
            # 职业履历
            "career": _build_career(info),
            # 投资理念
            "investment_philosophy": info.get("investment_philosophy") or _build_investment_philosophy(info),
            # 基金列表
            "funds": fund_details,
            "scoring": {
                "overall_score": None,
                "evidence": "insufficient_evidence",
                "message": "缺少可验证的管理基金评分，不输出默认基金经理分。",
            },
            "reports": reports,
        })
        cache.set(cache_key, result, TTL.MEDIUM)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get manager detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{manager_id}/reports")
async def get_manager_reports(
    manager_id: str,
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """获取经理的调研报告列表"""
    from service_registry import get_db
    db = get_db()

    try:
        if db is None:
            return {"total": 0, "page": page, "page_size": page_size, "reports": []}

        query = {"manager_id": manager_id}
        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"content": {"$regex": keyword, "$options": "i"}},
                {"tags": {"$regex": keyword, "$options": "i"}},
            ]

        total = db.research_reports.count_documents(query)
        cursor = db.research_reports.find(query).sort("report_date", -1).skip((page-1)*page_size).limit(page_size)

        reports = []
        for r in cursor:
            reports.append({
                "id": str(r.get("_id", "")),
                "title": r.get("title"),
                "report_date": r.get("report_date"),
                "source": r.get("source"),
                "summary": (r.get("summary") or "")[:200],
                "tags": r.get("tags", []),
                "key_points": (r.get("key_points") or [])[:5],
            })

        return {"total": total, "page": page, "page_size": page_size, "reports": reports}
    except Exception as e:
        logger.error(f"Get manager reports error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{manager_id}/profile")
async def get_manager_profile(manager_id: str):
    """获取经理画像（AI生成）"""
    from service_registry import get_db
    db = get_db()

    try:
        if db is None:
            return None
        profile = db.manager_profiles.find_one({"manager_id": manager_id})
        if profile:
            profile["_id"] = str(profile["_id"])
            return dict(profile)
        return None
    except Exception as e:
        logger.error(f"Get manager profile error: {e}")
        return None


@router.post("/{manager_id}/profile/generate")
async def generate_manager_profile(manager_id: str):
    """
    生成基金经理画像

    流程：
    1. 获取经理基本信息和管理基金
    2. 获取调研报告（从 research_reports 表）
    3. 调用 AI 生成分析报告
    4. 从报告中提取结构化画像数据
    5. 存入 manager_profiles 表并返回
    """
    from service_registry import get_db, get_data_service
    from services.ai_report import get_report_generator
    from services.profile_extractor import get_profile_extractor

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="数据库未连接")

    data_svc = get_data_service()
    report_gen = get_report_generator()
    profile_extractor = get_profile_extractor()

    try:
        # 1. 获取经理信息
        info = data_svc.get_manager_info(manager_id)
        if not info:
            # 尝试从基金列表获取
            list_result = data_svc.get_fund_list(page=1, page_size=1000)
            for fund in list_result.get("list", []):
                fund_info = data_svc.get_fund_info(fund)
                if fund_info.get("manager") == manager_id:
                    info = {
                        "manager_id": manager_id,
                        "name": manager_id,
                        "company": fund_info.get("management_company", ""),
                        "type": "未知"
                    }
                    break

        if not info:
            raise HTTPException(status_code=404, detail=f"经理不存在: {manager_id}")

        # 2. 获取管理基金
        funds = data_svc.get_manager_funds(manager_id)

        # 3. 获取调研报告
        reports = []
        try:
            cursor = db.research_reports.find({"manager_id": manager_id}).sort("report_date", -1).limit(10)
            for r in cursor:
                reports.append({
                    "title": r.get("title"),
                    "report_date": r.get("report_date"),
                    "summary": r.get("summary"),
                    "content": r.get("content"),
                    "tags": r.get("tags", []),
                })
        except Exception as e:
            logger.warning(f"Get research reports failed: {e}")

        # 4. 获取基金业绩和风格
        fund_perfs = []
        style_data = {}
        for fund in funds[:3]:
            code = fund.get("wind_code", "")
            if not code:
                continue
            perf = data_svc.get_fund_performance(code)
            style = data_svc.get_fund_style(code)
            fund_perfs.append({**fund, "performance": perf, "style": style})
            if not style_data:
                style_data = style

        # 5. 生成基金经理研究报告
        scoring_result = {
            "overall_score": None,
            "evidence": "insufficient_evidence",
            "message": "画像生成不使用默认评分；基金经理结论必须来自可验证的管理基金业绩和报告证据。",
        }
        ai_report = report_gen.generate_manager_analysis(
            manager_data=info,
            fund_data=fund_perfs,
            performance_data={"funds": fund_perfs},
            style_data=style_data,
            scoring_result=scoring_result,
            research_reports=reports,
            manager_profile=None
        )

        # 6. 从报告中提取画像
        profile = profile_extractor.extract_profile(ai_report, info, style_data)
        profile["manager_id"] = manager_id
        profile["manager_name"] = info.get("name", manager_id)
        profile["generated_at"] = datetime.now().isoformat()
        profile["ai_report"] = ai_report

        # 7. 存入数据库
        existing = db.manager_profiles.find_one({"manager_id": manager_id})
        if existing:
            db.manager_profiles.update_one(
                {"manager_id": manager_id},
                {"$set": {**profile, "updated_at": datetime.now().isoformat()}}
            )
            profile["_id"] = str(existing["_id"])
        else:
            result = db.manager_profiles.insert_one(profile)
            profile["_id"] = str(result.inserted_id)

        # 8. 返回结果（包含报告内容用于展示）
        return {
            "success": True,
            "profile": profile,
            "report": ai_report,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate manager profile error: {e}")
        raise HTTPException(status_code=500, detail=f"画像生成失败: {str(e)}")


@router.get("/{manager_id}/score")
async def get_manager_score(manager_id: str):
    """获取经理评分（兼容前端）"""
    data_svc, scoring_engine, db = _get_services()

    try:
        info = data_svc.get_manager_info(manager_id)
        funds = data_svc.get_manager_funds(manager_id)

        fund_scores = []
        for fund in funds[:5]:
            code = fund.get("wind_code", "")
            if not code:
                continue
            perf = data_svc.get_fund_performance(code)
            risk = data_svc.get_fund_risk_metrics(code)
            style = data_svc.get_fund_style(code)
            score = scoring_engine.score_fund(perf, risk, style)
            fund_scores.append({**fund, "scoring": score})

        if not fund_scores:
            return {
                "overall_score": None,
                "overall_grade": None,
                "scoring_source": "insufficient_evidence",
                "message": "缺少可验证的管理基金评分，不输出默认基金经理分。",
                "dimension_scores": {},
            }

        avg_perf = {"overall_score": sum(f["scoring"]["overall_score"] for f in fund_scores) / len(fund_scores)}
        manager_score = scoring_engine.score_manager(info, avg_perf, {}, [])

        return manager_score
    except Exception as e:
        logger.error(f"Get manager score error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{manager_id}/morningstar")
async def get_morningstar_rating(manager_id: str):
    """获取晨星风格评价 - 5星评级系统

    Returns:
        {
            "overall_score": 0-100,
            "star_rating": 1-5,
            "dimension_scores": {
                "return": 0-100,
                "risk_adjusted": 0-100,
                "stability": 0-100,
                "experience": 0-100
            },
            "grade": "S/A/B/C/D/E",
            "percentile_rank": 0-100
        }
    """
    from services.scoring_engine import ManagerScoringEngine
    from services.cache_service import get_cache, TTL

    cache = get_cache()
    cache_key = f"manager:morningstar:{manager_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return _clean_nan(cached)

    data_svc, _, db = _get_services()

    try:
        # 获取经理基础信息
        info = data_svc.get_manager_info(manager_id)
        if not info:
            raise HTTPException(status_code=404, detail=f"经理不存在: {manager_id}")

        # 获取管理的所有基金业绩
        funds = data_svc.get_manager_funds(manager_id)
        funds_performance = []

        for fund in funds[:10]:  # 最多取10只基金
            code = fund.get("wind_code", "")
            if not code:
                continue

            try:
                perf = data_svc.get_fund_performance(code)
                if perf:
                    funds_performance.append(perf)
            except Exception as e:
                logger.warning(f"Failed to get performance for {code}: {e}")
                continue

        # 使用晨星评分引擎
        morningstar_engine = ManagerScoringEngine()
        rating = morningstar_engine.score_manager(info, funds_performance)

        # 添加同类排名（简化版：基于评分百分位）
        rating["percentile_rank"] = round(rating["overall_score"], 1)

        result = _clean_nan(rating)
        cache.set(cache_key, result, TTL.MEDIUM)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get morningstar rating error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
