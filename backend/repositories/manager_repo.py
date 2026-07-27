"""
基金经理 Repository - PostgreSQL 数据访问层
"""
import os
import json
from typing import List, Dict, Any, Optional
import logging

try:
    from backend.database import get_database_url
except ModuleNotFoundError:
    from database import get_database_url

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        pg_url = get_database_url()
        _engine = create_engine(pg_url, pool_pre_ping=True, pool_size=20, max_overflow=30, pool_recycle=3600)
    return _engine


def _json_ser(obj):
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, dict)):
        return [str(x) for x in obj]
    if isinstance(obj, float) and (obj != obj or abs(obj) == float('inf')):
        return None
    return obj


class ManagerRepo:
    """基金经理数据访问层"""

    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = _get_engine()
        return self._engine

    def upsert_manager(self, manager_id: str, data: Dict[str, Any]) -> bool:
        """Upsert 基金经理数据"""
        try:
            from sqlalchemy import text

            sql = """
            INSERT INTO managers (wind_code, name, company, education, work_years,
                               management_years, current_funds, historical_performance, raw_data)
            VALUES (:manager_id, :name, :company, :education, :work_years,
                    :mgmt_years, :current_funds, CAST(:hist_perf AS jsonb), CAST(:raw_data AS jsonb))
            ON CONFLICT (wind_code) DO UPDATE SET
                name = EXCLUDED.name,
                company = EXCLUDED.company,
                education = EXCLUDED.education,
                work_years = EXCLUDED.work_years,
                management_years = EXCLUDED.management_years,
                current_funds = CASE
                    WHEN COALESCE(cardinality(EXCLUDED.current_funds), 0) = 0 THEN managers.current_funds
                    ELSE ARRAY(
                        SELECT DISTINCT fund_code
                        FROM unnest(COALESCE(managers.current_funds, '{}'::text[]) || EXCLUDED.current_funds) AS fund_code
                    )
                END,
                historical_performance = EXCLUDED.historical_performance,
                raw_data = EXCLUDED.raw_data,
                updated_at = NOW()
            """
            params = {
                "manager_id": manager_id,
                "name": data.get("name", ""),
                "company": data.get("company", ""),
                "education": data.get("education", ""),
                "work_years": data.get("experience_years", 0),
                "mgmt_years": data.get("management_years", 0),
                "current_funds": data.get("current_funds", []),
                "hist_perf": json.dumps(data.get("historical_performance", {}), default=_json_ser),
                "raw_data": json.dumps(data.get("raw_data", {}), default=_json_ser),
            }

            with self.engine.connect() as conn:
                conn.execute(text(sql), params)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"upsert_manager error for {manager_id}: {e}")
            return False

    def get_manager(self, manager_id: str) -> Optional[Dict[str, Any]]:
        """获取基金经理"""
        try:
            from sqlalchemy import text
            sql = "SELECT * FROM managers WHERE wind_code = :manager_id OR name = :manager_id LIMIT 1"
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"manager_id": manager_id})
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
                return None
        except Exception as e:
            logger.error(f"get_manager error: {e}")
            return None

    def get_managers_by_ids(self, manager_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """按 manager_id 批量获取经理。"""
        if not manager_ids:
            return {}
        try:
            from sqlalchemy import bindparam, text

            unique_ids = list(dict.fromkeys([manager_id for manager_id in manager_ids if manager_id]))
            if not unique_ids:
                return {}
            sql = text("SELECT * FROM managers WHERE wind_code IN :manager_ids OR name IN :manager_ids")
            sql = sql.bindparams(bindparam("manager_ids", expanding=True))
            with self.engine.connect() as conn:
                rows = conn.execute(sql, {"manager_ids": unique_ids}).fetchall()
            return {
                row._mapping.get("wind_code"): dict(row._mapping)
                for row in rows
                if row._mapping.get("wind_code")
            }
        except Exception as e:
            logger.error(f"get_managers_by_ids error: {e}")
            return {}

    def list_managers(
        self,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """列表查询基金经理"""
        try:
            from sqlalchemy import text

            where_clauses = []
            params = {}

            if keyword:
                where_clauses.append("(name ILIKE :keyword OR company ILIKE :keyword)")
                params["keyword"] = f"%{keyword}%"

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            offset = (page - 1) * page_size

            count_sql = f"SELECT COUNT(*) as total FROM managers WHERE {where_sql}"
            data_sql = f"""
                SELECT * FROM managers
                WHERE {where_sql}
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
            """

            with self.engine.connect() as conn:
                count_result = conn.execute(text(count_sql), params)
                total = count_result.fetchone()[0]

                params["limit"] = page_size
                params["offset"] = offset
                data_result = conn.execute(text(data_sql), params)
                rows = data_result.fetchall()

            return {
                "total": total,
                "managers": [dict(r._mapping) for r in rows]
            }
        except Exception as e:
            logger.error(f"list_managers error: {e}")
            return {"total": 0, "managers": []}

    def upsert_profile(self, manager_id: str, profile: Dict[str, Any]) -> bool:
        """Upsert 基金经理画像"""
        try:
            from sqlalchemy import text

            sql = """
            INSERT INTO manager_profiles (
                manager_id, core_philosophy, stock_selection_logic, risk_philosophy,
                focus_industries, competence_advantages, competence_boundaries,
                style_label, concentration, turnover, style_stability,
                philosophy_score, competence_score, style_score, overall_quality_score,
                philosophy_behavior_consistency, valuation_consistency, quality_consistency,
                industry_consistency, key_insights, red_flags, interviews_analyzed, last_interview_date
            )
            VALUES (
                :manager_id, :philosophy, :stock_logic, :risk_philosophy,
                :focus_industries, :advantages, :boundaries,
                :style_label, :concentration, :turnover, :style_stability,
                :phil_score, :comp_score, :style_score, :overall_score,
                :phil_consistency, :val_consistency, :qual_consistency, :ind_consistency,
                :key_insights, :red_flags, :interviews, :last_interview
            )
            ON CONFLICT (manager_id) DO UPDATE SET
                core_philosophy = EXCLUDED.core_philosophy,
                stock_selection_logic = EXCLUDED.stock_selection_logic,
                risk_philosophy = EXCLUDED.risk_philosophy,
                focus_industries = EXCLUDED.focus_industries,
                competence_advantages = EXCLUDED.competence_advantages,
                competence_boundaries = EXCLUDED.competence_boundaries,
                style_label = EXCLUDED.style_label,
                concentration = EXCLUDED.concentration,
                turnover = EXCLUDED.turnover,
                style_stability = EXCLUDED.style_stability,
                philosophy_score = EXCLUDED.philosophy_score,
                competence_score = EXCLUDED.competence_score,
                style_score = EXCLUDED.style_score,
                overall_quality_score = EXCLUDED.overall_quality_score,
                philosophy_behavior_consistency = EXCLUDED.philosophy_behavior_consistency,
                valuation_consistency = EXCLUDED.valuation_consistency,
                quality_consistency = EXCLUDED.quality_consistency,
                industry_consistency = EXCLUDED.industry_consistency,
                key_insights = EXCLUDED.key_insights,
                red_flags = EXCLUDED.red_flags,
                interviews_analyzed = EXCLUDED.interviews_analyzed,
                last_interview_date = EXCLUDED.last_interview_date,
                last_updated = NOW()
            """
            params = {
                "manager_id": manager_id,
                "philosophy": profile.get("core_philosophy"),
                "stock_logic": profile.get("stock_selection_logic"),
                "risk_philosophy": profile.get("risk_philosophy"),
                "focus_industries": profile.get("focus_industries", []),
                "advantages": profile.get("competence_advantages"),
                "boundaries": profile.get("competence_boundaries"),
                "style_label": profile.get("style_label"),
                "concentration": profile.get("concentration"),
                "turnover": profile.get("turnover"),
                "style_stability": profile.get("style_stability"),
                "phil_score": profile.get("philosophy_score"),
                "comp_score": profile.get("competence_score"),
                "style_score": profile.get("style_score"),
                "overall_score": profile.get("overall_quality_score"),
                "phil_consistency": profile.get("philosophy_behavior_consistency"),
                "val_consistency": profile.get("valuation_consistency"),
                "qual_consistency": profile.get("quality_consistency"),
                "ind_consistency": profile.get("industry_consistency"),
                "key_insights": profile.get("key_insights", []),
                "red_flags": profile.get("red_flags", []),
                "interviews": profile.get("interviews_analyzed", 0),
                "last_interview": profile.get("last_interview_date"),
            }

            with self.engine.connect() as conn:
                conn.execute(text(sql), params)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"upsert_profile error for {manager_id}: {e}")
            return False

    def get_profile(self, manager_id: str) -> Optional[Dict[str, Any]]:
        """获取基金经理画像"""
        try:
            from sqlalchemy import text
            sql = "SELECT * FROM manager_profiles WHERE manager_id = :manager_id"
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), {"manager_id": manager_id})
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
                return None
        except Exception as e:
            logger.error(f"get_profile error: {e}")
            return None
