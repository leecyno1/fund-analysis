"""
基金研究报告路由 - 报告生成、查询
"""
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["基金研究报告"])


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _save_report_to_postgres(report_record: dict) -> Optional[str]:
    """保存 AI 研究报告到 PostgreSQL，返回报告 UUID。"""
    import json
    from sqlalchemy import text
    from database import get_engine

    sql = text(
        """
        INSERT INTO ai_analysis_reports (
            target_type, target_id, report_type, content, data_sources,
            research_reports_used, generation_params, created_at
        ) VALUES (
            :target_type, :target_id, :report_type, :content,
            CAST(:data_sources AS jsonb), :research_reports_used,
            CAST(:generation_params AS jsonb), NOW()
        )
        RETURNING id
        """
    )
    with get_engine().begin() as conn:
        row = conn.execute(
            sql,
            {
                "target_type": report_record["target_type"],
                "target_id": report_record["target_id"],
                "report_type": report_record.get("report_type"),
                "content": report_record.get("content"),
                "data_sources": json.dumps(_json_safe(report_record.get("data_sources") or {}), ensure_ascii=False),
                "research_reports_used": report_record.get("research_reports_used") or [],
                "generation_params": json.dumps(_json_safe(report_record.get("generation_params") or {}), ensure_ascii=False),
            },
        ).fetchone()
    return str(row[0]) if row else None


def _is_unusable_llm_report(content: str) -> bool:
    stripped = content.lstrip()
    return (
        stripped.startswith("## 报告生成失败")
        or "当前使用模拟数据" in content
        or "配置模型 API Key 后" in content
    )


def _reject_mock_data_source(data_svc, report_scope: str) -> None:
    if getattr(data_svc, "mock_mode", False):
        raise HTTPException(
            status_code=409,
            detail=f"{report_scope}报告需要真实 Tushare 入库/同步数据；当前数据服务为 mock_mode，已阻止生成研究报告。",
        )


def _ensure_peer_percentile_section(content: str, peer_percentiles: dict) -> str:
    if "## 同类分位与胜负线" in content:
        return content
    try:
        from services.evidence_report import build_peer_percentile_report_section

        return content.rstrip() + "\n\n" + build_peer_percentile_report_section(peer_percentiles)
    except Exception as exc:
        logger.warning(f"Failed to append peer percentile section: {exc}")
        return content


def _ensure_manager_tenure_section(content: str, managers: list, tenure_metrics: list) -> str:
    if "## 现任经理任期切片" in content:
        return content
    try:
        from services.evidence_report import build_manager_tenure_report_section

        return content.rstrip() + "\n\n" + build_manager_tenure_report_section(managers, tenure_metrics)
    except Exception as exc:
        logger.warning(f"Failed to append manager tenure section: {exc}")
        return content


def _ensure_sales_rule_cost_section(content: str, sales_rule_data: dict, purchase_plan: str) -> str:
    if "## 费用与销售规则快照" in content:
        return content
    try:
        from services.evidence_report import build_sales_rule_cost_report_section

        return content.rstrip() + "\n\n" + build_sales_rule_cost_report_section(sales_rule_data, purchase_plan)
    except Exception as exc:
        logger.warning(f"Failed to append sales rule cost section: {exc}")
        return content


def _ensure_buy_before_decision_section(
    content: str,
    peer_percentiles: dict,
    sales_rule_data: dict,
    holdings: list,
    manager_tenure_metrics: list,
    purchase_plan: str,
) -> str:
    if "## 买前总闸门结论" in content:
        return content
    try:
        from services.evidence_report import build_buy_before_decision_section

        section = build_buy_before_decision_section(
            peer_percentiles,
            sales_rule_data,
            holdings,
            manager_tenure_metrics,
            purchase_plan,
        )
        return content.rstrip() + "\n\n" + section
    except Exception as exc:
        logger.warning(f"Failed to append buy-before decision section: {exc}")
        return content


def _purchase_plan_label(purchase_plan: str) -> str:
    return "一次性买入" if purchase_plan == "lump_sum" else "定投"


def _normalize_planned_amount(value, purchase_plan: str):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 10000.0 if purchase_plan == "lump_sum" else 1000.0
    if amount <= 0:
        amount = 10000.0 if purchase_plan == "lump_sum" else 1000.0
    return int(amount) if amount.is_integer() else amount


def _purchase_plan_evidence_fields(purchase_plan: str) -> str:
    if purchase_plan == "lump_sum":
        return "申购状态、起购金额、限购、赎回规则、费率、销售风险等级（R1-R5）"
    return "申购状态、定投支持、定投起点、限购、赎回规则、费率、销售风险等级（R1-R5）"


def _ensure_purchase_plan_notice(content: str, purchase_plan: str, planned_amount=None) -> str:
    if "买入方式口径" in content and "计划金额" in content:
        return content
    label = _purchase_plan_label(purchase_plan)
    fields = _purchase_plan_evidence_fields(purchase_plan)
    amount = _normalize_planned_amount(planned_amount, purchase_plan)
    notice = (
        f"> 买入方式口径：{label}；计划金额：{amount:,} 元。正式买前判断前必须补齐并复核{fields}；"
        "评分和研究报告不能替代销售规则、适当性、费用与净值回放门禁。"
    )
    return f"{notice}\n\n{content}"


def _load_latest_local_holdings(wind_code: str) -> dict:
    try:
        from repositories import get_holding_repo
        rows = get_holding_repo().get_holdings_history(wind_code)
    except Exception as error:
        logger.warning(f"Failed to load local holdings for {wind_code}: {error}")
        return {
            "status": "unavailable",
            "source": "local_postgres.holdings",
            "quarter": None,
            "holdings": [],
            "note": "读取本地持仓表失败，报告不做行业/个股暴露判断。",
        }

    by_quarter = {}
    for row in rows:
        quarter = str(row.get("quarter") or "").upper()
        stock_code = str(row.get("stock_code") or "").strip()
        stock_name = str(row.get("stock_name") or "").strip()
        if not quarter or not (stock_code or stock_name):
            continue
        by_quarter.setdefault(quarter, []).append(row)

    for quarter in sorted(by_quarter.keys(), reverse=True):
        holdings = by_quarter[quarter]
        if len(holdings) >= 5:
            return {
                "status": "available",
                "source": "local_postgres.holdings",
                "quarter": quarter,
                "holdings": holdings,
                "note": "使用本地 PostgreSQL 已入库持仓；买前仍需以基金季报/销售平台披露为准。",
            }

    return {
        "status": "unavailable",
        "source": "local_postgres.holdings",
        "quarter": None,
        "holdings": [],
        "note": "本地持仓表无 >=5 条的可信季度持仓，报告不做行业/个股暴露判断。",
    }


def _load_local_sales_rules(wind_code: str) -> dict:
    try:
        import json
        from sqlalchemy import text
        from database import get_engine

        sql = text("""
            SELECT *
            FROM fund_sales_rules
            WHERE wind_code = :wind_code
            ORDER BY source_updated_at DESC NULLS LAST, updated_at DESC NULLS LAST
            LIMIT 20
        """)
        with get_engine().connect() as conn:
            rows = [dict(row._mapping) for row in conn.execute(sql, {"wind_code": wind_code}).fetchall()]
    except Exception as error:
        logger.warning(f"Failed to load local sales rules for {wind_code}: {error}")
        return {
            "status": "unavailable",
            "source": "local_postgres.fund_sales_rules",
            "rules": [],
            "merged": {},
            "note": "读取本地销售规则失败，报告不做费用/申赎判断。",
        }

    def normalize_rule(row: dict) -> dict:
        rule = _json_safe(row)
        redemption_rules = rule.get("redemption_fee_rules") or []
        if isinstance(redemption_rules, str):
            try:
                redemption_rules = json.loads(redemption_rules)
            except Exception:
                redemption_rules = []
        rule["redemption_fee_rules"] = redemption_rules if isinstance(redemption_rules, list) else []
        return rule

    rules = [normalize_rule(row) for row in rows]
    if not rules:
        return {
            "status": "unavailable",
            "source": "local_postgres.fund_sales_rules",
            "rules": [],
            "merged": {},
            "note": "本地销售规则表无该基金记录；报告不做费用/申赎通过判断。",
        }

    def first_value(key: str):
        for rule in rules:
            value = rule.get(key)
            if value not in (None, "", "unknown", []):
                return value
        return None

    def valid_risk_level(rule: dict) -> bool:
        value = str(rule.get("risk_level") or "").strip().upper()
        return value in {"R1", "R2", "R3", "R4", "R5"}

    def tushare_risk_source(rule: dict) -> bool:
        platform = str(rule.get("platform") or "").strip().lower()
        source_url = str(rule.get("source_url") or "").strip().lower()
        return "tushare" in platform or "tushare.fund_basic" in source_url

    def same_row_risk_source_evidence(rule: dict) -> bool:
        if not valid_risk_level(rule) or tushare_risk_source(rule):
            return False
        return bool(rule.get("source_updated_at") and (rule.get("source_url") or rule.get("notes")))

    def same_row_redemption_source_evidence(rule: dict) -> bool:
        return bool(rule.get("redemption_fee_rules") and rule.get("source_updated_at") and (rule.get("source_url") or rule.get("notes")))

    status_rule = next((rule for rule in rules if rule.get("purchase_status") not in (None, "", "unknown")), rules[0])
    redemption_rule = (
        next((rule for rule in rules if same_row_redemption_source_evidence(rule)), None)
        or next((rule for rule in rules if rule.get("redemption_fee_rules")), None)
        or {}
    )
    risk_rule = (
        next((rule for rule in rules if same_row_risk_source_evidence(rule)), None)
        or next((rule for rule in rules if valid_risk_level(rule) and not tushare_risk_source(rule)), None)
        or next((rule for rule in rules if valid_risk_level(rule)), None)
        or {}
    )
    merged = {
        "platform": first_value("platform"),
        "purchase_status": status_rule.get("purchase_status") or "unknown",
        "purchase_status_label": status_rule.get("purchase_status_label") or "申购待核",
        "min_purchase_amount": first_value("min_purchase_amount"),
        "min_sip_amount": first_value("min_sip_amount"),
        "daily_limit_amount": first_value("daily_limit_amount"),
        "purchase_fee_rate": first_value("purchase_fee_rate"),
        "redemption_fee_rules": redemption_rule.get("redemption_fee_rules") or [],
        "redemption_fee_source_updated_at": redemption_rule.get("source_updated_at"),
        "redemption_fee_source_url": redemption_rule.get("source_url"),
        "redemption_fee_platform": redemption_rule.get("platform"),
        "redemption_fee_notes": redemption_rule.get("notes"),
        "sales_service_fee_rate": first_value("sales_service_fee_rate"),
        "risk_level": risk_rule.get("risk_level"),
        "supports_sip": first_value("supports_sip"),
        "source_updated_at": risk_rule.get("source_updated_at") if risk_rule.get("risk_level") else first_value("source_updated_at"),
        "source_url": risk_rule.get("source_url") if risk_rule.get("risk_level") else first_value("source_url"),
        "notes": risk_rule.get("notes") if risk_rule.get("risk_level") else first_value("notes"),
    }
    return {
        "status": "available",
        "source": "local_postgres.fund_sales_rules",
        "rules": rules,
        "merged": merged,
        "note": "使用本地 PostgreSQL 销售规则快照；买前仍需以销售平台实时页面为准。",
    }


@router.post("/fund/{wind_code}")
async def generate_fund_report(
    wind_code: str,
    background_tasks: BackgroundTasks = None,
    include_research: bool = True,
    report_depth: str = Query("standard", description="standard/deep/brief"),
    purchase_plan: str = Query("sip", description="sip/lump_sum"),
    planned_amount: Optional[float] = Query(None, description="本次买前计划金额"),
):
    """生成基金分析报告"""
    from service_registry import get_data_service, get_scoring_engine, get_db
    data_svc = get_data_service(); scoring_engine = get_scoring_engine(); db = get_db()
    _reject_mock_data_source(data_svc, "基金")
    from services.ai_report import get_report_generator
    from services.evidence_report import build_buy_before_decision_summary, build_fund_research_report
    from services.peer_comparison_service import PeerComparisonService
    from services.search_service import get_search_service

    try:
        safe_purchase_plan = "lump_sum" if purchase_plan == "lump_sum" else "sip"
        safe_planned_amount = _normalize_planned_amount(planned_amount, safe_purchase_plan)
        # 收集数据
        fund_data = data_svc.get_fund_info(wind_code)
        perf = data_svc.get_fund_performance(wind_code)
        risk = data_svc.get_fund_risk_metrics(wind_code)
        style = data_svc.get_fund_style(wind_code)
        scoring = scoring_engine.score_fund(perf, risk, style)
        try:
            peer_percentiles = PeerComparisonService().build_peer_percentiles(wind_code, window="1y")
        except Exception as peer_err:
            logger.warning(f"Peer percentile unavailable for report {wind_code}: {peer_err}")
            peer_percentiles = {
                "target_id": wind_code,
                "sample_status": "unavailable",
                "metrics": {},
                "peer_metric_gap": {
                    "required_more_funds": 0,
                    "suggested_sync_codes": [],
                    "next_action": "none",
                },
            }
        try:
            from repositories import get_manager_repo, get_metric_snapshot_repo

            manager_repo = get_manager_repo()
            manager_ids = fund_data.get("manager_ids") or []
            managers = []
            for manager_id in manager_ids:
                manager = manager_repo.get_manager(manager_id) or {"manager_id": manager_id, "name": manager_id}
                managers.append(manager)
            manager_tenure_metrics = [
                item
                for item in get_metric_snapshot_repo().get_latest_panel("fund", wind_code)
                if item.get("metric_window") == "manager_tenure"
            ]
        except Exception as manager_err:
            logger.warning(f"Manager tenure evidence unavailable for report {wind_code}: {manager_err}")
            managers = []
            manager_tenure_metrics = []

        # 报告只使用已入库并达到最小数量门槛的持仓；不在报告链路临时调用易失败接口，不编造持仓结论。
        current_q = f"{datetime.now().year}Q{(datetime.now().month-1)//3+1}"
        holding_snapshot = _load_latest_local_holdings(wind_code)
        holdings = holding_snapshot["holdings"]
        sales_rule_snapshot = _load_local_sales_rules(wind_code)

        # 获取相关调研报告
        research_reports = []
        if include_research:
            try:
                query = {"fund_ids": wind_code}
                reports_cursor = db.research_reports.find(query).sort("report_date", -1).limit(5)
                for doc in reports_cursor:
                    research_reports.append({
                        "id": str(doc.get("_id", "")),
                        "title": doc.get("title"),
                        "report_date": doc.get("report_date"),
                        "summary": doc.get("summary", ""),
                        "content": doc.get("content", ""),
                        "tags": doc.get("tags", []),
                    })
            except:
                pass

        # 生成报告
        generator = get_report_generator()
        generation_mode = "llm"
        if generator.api_key:
            report_content = generator.generate_fund_analysis(
                fund_data=fund_data,
                performance_data=perf,
                risk_data=risk,
                holdings_data=holdings,
                style_data=style,
                scoring_result=scoring,
                research_reports=research_reports,
                purchase_plan=safe_purchase_plan,
            )
        else:
            report_content = ""
        if not report_content or _is_unusable_llm_report(report_content):
            report_content = build_fund_research_report(
                fund_data=fund_data,
                performance_data=perf,
                risk_data=risk,
                style_data=style,
                scoring_result=scoring,
                holdings_data=holdings,
                peer_percentiles=peer_percentiles,
                manager_data=managers,
                manager_tenure_metrics=manager_tenure_metrics,
                sales_rule_data=sales_rule_snapshot,
                purchase_plan=safe_purchase_plan,
            )
            generation_mode = "deterministic_evidence_backed"
        report_content = _ensure_peer_percentile_section(report_content, peer_percentiles)
        report_content = _ensure_manager_tenure_section(report_content, managers, manager_tenure_metrics)
        report_content = _ensure_sales_rule_cost_section(report_content, sales_rule_snapshot, safe_purchase_plan)
        report_content = _ensure_buy_before_decision_section(
            report_content,
            peer_percentiles,
            sales_rule_snapshot,
            holdings,
            manager_tenure_metrics,
            safe_purchase_plan,
        )
        report_content = _ensure_purchase_plan_notice(report_content, safe_purchase_plan, safe_planned_amount)
        buy_before_decision = build_buy_before_decision_summary(
            peer_percentiles,
            sales_rule_snapshot,
            holdings,
            manager_tenure_metrics,
            safe_purchase_plan,
        )

        # 保存报告
        report_record = {
            "target_type": "fund",
            "target_id": wind_code,
            "report_type": f"fund_{report_depth}_analysis",
            "content": report_content,
            "data_sources": {
                "wind_code": wind_code,
                "performance": perf,
                "risk": risk,
                "style": style,
                "scoring": scoring,
                "holdings_quarter": holding_snapshot["quarter"] or current_q,
                "holdings_status": holding_snapshot["status"],
                "holdings_source": holding_snapshot["source"],
                "holdings_note": holding_snapshot["note"],
                "holdings_count": len(holdings),
                "peer_percentiles": peer_percentiles,
                "peer_percentile_status": peer_percentiles.get("sample_status"),
                "peer_usable_metric_count": peer_percentiles.get("usable_metric_count"),
                "manager_tenure_metrics_count": len(manager_tenure_metrics),
                "manager_tenure_status": "available" if manager_tenure_metrics else "unavailable",
                "managers": managers,
                "sales_rule_status": sales_rule_snapshot.get("status"),
                "sales_rule_source": sales_rule_snapshot.get("source"),
                "sales_rule_merged": sales_rule_snapshot.get("merged"),
                "buy_before_decision": buy_before_decision,
                "generation_mode": generation_mode,
                "research_reports_count": len(research_reports),
                "summary": {
                    "purchasePlan": safe_purchase_plan,
                    "plannedAmount": safe_planned_amount,
                    "buyBeforeGateStatus": buy_before_decision.get("status"),
                    "buyBeforeGateLabel": buy_before_decision.get("label"),
                },
            },
            "research_reports_used": [r["id"] for r in research_reports],
            "generation_params": {
                "depth": report_depth,
                "include_research": include_research,
                "purchasePlan": safe_purchase_plan,
                "plannedAmount": safe_planned_amount,
                "provider": generator.provider,
                "model": generator.model,
                "base_url": generator.base_url,
                "mode": generation_mode,
            },
            "created_at": datetime.utcnow(),
        }

        report_id = None
        try:
            report_id = _save_report_to_postgres(report_record)
        except Exception as pg_err:
            logger.warning(f"Failed to save report to PostgreSQL: {pg_err}")

        try:
            if db is not None:
                result = db.ai_analysis_reports.insert_one(report_record)
                report_record["mongo_id"] = str(result.inserted_id)
        except Exception as db_err:
            logger.debug(f"Mongo report save skipped: {db_err}")

        return {
            "id": report_id,
            "report": report_content,
            "metadata": {
                "target_type": "fund",
                "target_id": wind_code,
                "report_type": f"fund_{report_depth}_analysis",
                "report_id": report_id,
                "data_sources": report_record["data_sources"],
                "word_count": len(report_content),
                "purchasePlan": safe_purchase_plan,
                "plannedAmount": safe_planned_amount,
                "provider": generator.provider,
                "model": generator.model,
                "mode": generation_mode,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate fund report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manager/{manager_id}")
async def generate_manager_report(
    manager_id: str,
    include_profile: bool = True,
    depth: str = Query("standard", description="standard/deep/brief"),
):
    """生成基金经理分析报告"""
    from service_registry import get_data_service, get_scoring_engine, get_db
    data_svc = get_data_service(); scoring_engine = get_scoring_engine(); db = get_db()
    _reject_mock_data_source(data_svc, "基金经理")
    from services.ai_report import get_report_generator
    from services.search_service import get_search_service

    try:
        manager_data = data_svc.get_manager_info(manager_id)
        funds = data_svc.get_manager_funds(manager_id)

        # 汇总代表基金的业绩
        fund_details = []
        for fund in funds[:3]:
            code = fund.get("wind_code", "")
            if not code:
                continue
            p = data_svc.get_fund_performance(code)
            r = data_svc.get_fund_risk_metrics(code)
            s = data_svc.get_fund_style(code)
            score = scoring_engine.score_fund(p, r, s)
            fund_details.append({**fund, "performance": p, "risk": r, "style": s, "scoring": score})

        avg_perf = {
            "overall_score": sum(f["scoring"]["overall_score"] for f in fund_details) / len(fund_details)
            if fund_details
            else None,
        }
        manager_score = scoring_engine.score_manager(manager_data, avg_perf, {}, [])

        # 获取调研报告
        try:
            reports_cursor = db.research_reports.find({"manager_id": manager_id}).sort("report_date", -1).limit(10)
            reports = []
            for doc in reports_cursor:
                reports.append({
                    "id": str(doc.get("_id", "")),
                    "title": doc.get("title"),
                    "report_date": doc.get("report_date"),
                    "summary": doc.get("summary", ""),
                    "content": doc.get("content", ""),
                    "tags": doc.get("tags", []),
                })
        except:
            reports = []

        # 获取经理画像
        manager_profile = None
        if include_profile:
            try:
                profile = db.manager_profiles.find_one({"manager_id": manager_id})
                if profile:
                    manager_profile = {
                        "core_philosophy": profile.get("core_philosophy"),
                        "stock_selection_logic": profile.get("stock_selection_logic"),
                        "risk_philosophy": profile.get("risk_philosophy"),
                        "competence_advantages": profile.get("competence_advantages"),
                        "competence_boundaries": profile.get("competence_boundaries"),
                        "style_label": profile.get("style_label"),
                        "philosophy_behavior_consistency": profile.get("philosophy_behavior_consistency"),
                    }
            except:
                pass

        # 生成报告
        generator = get_report_generator()
        report_content = generator.generate_manager_analysis(
            manager_data=manager_data,
            fund_data={"funds": fund_details, "summary": avg_perf},
            performance_data=avg_perf,
            style_data=fund_details[0]["style"] if fund_details else {},
            scoring_result=manager_score,
            research_reports=reports,
            manager_profile=manager_profile,
        )
        if report_content.lstrip().startswith("## 报告生成失败") or "当前使用模拟数据" in report_content:
            raise HTTPException(status_code=503, detail="LLM 报告生成不可用，请检查 SiliconFlow API Key、模型名或供应商配额。")

        # 保存报告
        report_record = {
            "target_type": "manager",
            "target_id": manager_id,
            "report_type": f"manager_{depth}_analysis",
            "content": report_content,
            "data_sources": {
                "manager_data": manager_data,
                "funds_count": len(funds),
                "research_reports_count": len(reports),
                "profile_available": manager_profile is not None,
            },
            "research_reports_used": [r["id"] for r in reports],
            "generation_params": {
                "depth": depth,
                "include_profile": include_profile,
                "provider": generator.provider,
                "model": generator.model,
                "base_url": generator.base_url,
            },
            "created_at": datetime.utcnow(),
        }

        report_id = None
        try:
            report_id = _save_report_to_postgres(report_record)
        except Exception as pg_err:
            logger.warning(f"Failed to save manager report to PostgreSQL: {pg_err}")

        try:
            if db is not None:
                result = db.ai_analysis_reports.insert_one(report_record)
                report_record["mongo_id"] = str(result.inserted_id)
        except Exception as db_err:
            logger.debug(f"Mongo manager report save skipped: {db_err}")

        return {
            "id": report_id,
            "report": report_content,
            "metadata": {
                "target_type": "manager",
                "target_id": manager_id,
                "report_type": f"manager_{depth}_analysis",
                "report_id": report_id,
                "data_sources": report_record["data_sources"],
                "word_count": len(report_content),
                "provider": generator.provider,
                "model": generator.model,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate manager report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_report_history(
    target_type: str = Query(..., description="fund/manager"),
    target_id: str = Query(...),
    limit: int = Query(10, ge=1, le=50),
):
    """获取历史生成的报告列表"""
    from service_registry import get_db
    db = get_db()

    if db is None:
        return {"total": 0, "reports": []}

    try:
        cursor = db.ai_analysis_reports.find(
            {"target_type": target_type, "target_id": target_id}
        ).sort("created_at", -1).limit(limit)

        reports = []
        for doc in cursor:
            reports.append({
                "id": str(doc.get("_id", "")),
                "report_type": doc.get("report_type"),
                "content_preview": doc.get("content", "")[:200],
                "data_sources": doc.get("data_sources"),
                "created_at": doc.get("created_at"),
            })

        return {"total": len(reports), "reports": reports}
    except Exception as e:
        logger.error(f"Get report history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
@router.get("/")
async def list_analysis_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    target_type: Optional[str] = Query(None, description="fund/manager"),
):
    """获取 PostgreSQL 中已生成的研究报告列表"""
    from sqlalchemy import text
    from database import get_engine

    conditions = []
    params = {
        "limit": limit,
        "offset": (page - 1) * limit,
    }
    if target_type:
        conditions.append("target_type = :target_type")
        params["target_type"] = target_type

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    try:
        with get_engine().connect() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM ai_analysis_reports {where_clause}"), params).scalar()
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, target_type, target_id, report_type, content,
                           data_sources, generation_params, created_at
                    FROM ai_analysis_reports
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).fetchall()

        reports = []
        for row in rows:
            data = dict(row._mapping)
            reports.append({
                "id": _json_safe(data.get("id")),
                "report_type": data.get("report_type"),
                "target_type": data.get("target_type"),
                "target_id": data.get("target_id"),
                "content": data.get("content"),
                "content_preview": (data.get("content") or "")[:240],
                "data_sources": _json_safe(data.get("data_sources")),
                "generation_params": _json_safe(data.get("generation_params")),
                "created_at": _json_safe(data.get("created_at")),
            })

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "reports": reports,
        }
    except Exception as error:
        logger.error(f"List analysis reports error: {error}")
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/{report_id}")
async def get_report_detail(report_id: str):
    """获取报告详情"""
    try:
        from sqlalchemy import text
        from database import get_engine

        sql = """
            SELECT id, target_type, target_id, report_type, content, data_sources,
                   research_reports_used, generation_params, created_at
            FROM ai_analysis_reports
            WHERE id = CAST(:report_id AS UUID)
            LIMIT 1
        """
        with get_engine().connect() as conn:
            row = conn.execute(text(sql), {"report_id": report_id}).fetchone()
        if row:
            data = dict(row._mapping)
            return {
                "id": _json_safe(data.get("id")),
                "target_type": data.get("target_type"),
                "target_id": data.get("target_id"),
                "report_type": data.get("report_type"),
                "content": data.get("content"),
                "data_sources": _json_safe(data.get("data_sources")),
                "research_reports_used": _json_safe(data.get("research_reports_used") or []),
                "generation_params": _json_safe(data.get("generation_params")),
                "created_at": _json_safe(data.get("created_at")),
            }
    except Exception as pg_error:
        logger.debug(f"PostgreSQL report lookup skipped for {report_id}: {pg_error}")

    from bson import ObjectId
    from service_registry import get_db
    db = get_db()

    if db is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        doc = db.ai_analysis_reports.find_one({"_id": ObjectId(report_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        return {
            "id": str(doc["_id"]),
            "target_type": doc.get("target_type"),
            "target_id": doc.get("target_id"),
            "report_type": doc.get("report_type"),
            "content": doc.get("content"),
            "data_sources": doc.get("data_sources"),
            "created_at": doc.get("created_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get report detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
