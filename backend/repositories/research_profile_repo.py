"""
基金研究画像 Repository
"""
import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

try:
    from backend.database import get_database_url
except ModuleNotFoundError:
    from database import get_database_url

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        pg_url = get_database_url()
        _engine = create_engine(pg_url, pool_pre_ping=True, pool_size=20, max_overflow=30, pool_recycle=3600)
    return _engine


def _json(value: Optional[Any]) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _row_to_dict(row) -> Dict[str, Any]:
    data = dict(row._mapping)
    for key, value in list(data.items()):
        if isinstance(value, (datetime, date)):
            data[key] = value.isoformat()
    return data


class ResearchProfileRepo:
    @property
    def engine(self):
        return _get_engine()

    def upsert_profile(
        self,
        wind_code: str,
        primary_benchmark: str,
        peer_group: str,
        style_label: str,
        secondary_benchmark: Optional[str] = None,
        strategy_tags: Optional[List[str]] = None,
        manager_tenure_start: Optional[str] = None,
        capacity_notes: Optional[str] = None,
        data_quality_notes: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import text
        from database import init_database

        init_database()
        sql = """
            INSERT INTO fund_research_profiles (
                wind_code, primary_benchmark, secondary_benchmark, peer_group, style_label,
                strategy_tags, manager_tenure_start, capacity_notes, data_quality_notes,
                evidence, updated_by, updated_at
            ) VALUES (
                :wind_code, :primary_benchmark, :secondary_benchmark, :peer_group, :style_label,
                :strategy_tags, :manager_tenure_start, :capacity_notes, :data_quality_notes,
                CAST(:evidence AS JSONB), :updated_by, NOW()
            )
            ON CONFLICT (wind_code) DO UPDATE SET
                primary_benchmark = EXCLUDED.primary_benchmark,
                secondary_benchmark = EXCLUDED.secondary_benchmark,
                peer_group = EXCLUDED.peer_group,
                style_label = EXCLUDED.style_label,
                strategy_tags = EXCLUDED.strategy_tags,
                manager_tenure_start = EXCLUDED.manager_tenure_start,
                capacity_notes = EXCLUDED.capacity_notes,
                data_quality_notes = EXCLUDED.data_quality_notes,
                evidence = EXCLUDED.evidence,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            RETURNING *
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {
                "wind_code": wind_code,
                "primary_benchmark": primary_benchmark,
                "secondary_benchmark": secondary_benchmark,
                "peer_group": peer_group,
                "style_label": style_label,
                "strategy_tags": strategy_tags or [],
                "manager_tenure_start": manager_tenure_start,
                "capacity_notes": capacity_notes,
                "data_quality_notes": data_quality_notes,
                "evidence": _json(evidence),
                "updated_by": updated_by,
            }).fetchone()
            conn.commit()
        return _row_to_dict(row)

    def get_profile(self, wind_code: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        sql = "SELECT * FROM fund_research_profiles WHERE wind_code = :wind_code LIMIT 1"
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {"wind_code": wind_code}).fetchone()
        return _row_to_dict(row) if row else None

    def list_profiles(self, wind_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        from sqlalchemy import text

        if not wind_codes:
            return {}
        sql = "SELECT * FROM fund_research_profiles WHERE wind_code = ANY(:wind_codes)"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"wind_codes": wind_codes}).fetchall()
        return {row.wind_code: _row_to_dict(row) for row in rows}

    def list_funds_by_peer_group(self, peer_group: str, limit: int = 50) -> List[Dict[str, Any]]:
        """从全库返回已归入指定同类组的基金，并兼容尚未建立画像的基础类别。"""
        from sqlalchemy import text

        normalized_group = str(peer_group or "").strip()
        if not normalized_group:
            return []
        sql = """
            SELECT f.*
            FROM funds f
            LEFT JOIN fund_research_profiles profile ON profile.wind_code = f.wind_code
            WHERE profile.peer_group = :peer_group
               OR (
                    COALESCE(profile.peer_group, '') = ''
                    AND f.type = :peer_group
               )
            ORDER BY
                CASE WHEN f.performance_data IS NULL OR f.performance_data = '{}'::jsonb THEN 1 ELSE 0 END,
                CASE WHEN f.risk_metrics IS NULL OR f.risk_metrics = '{}'::jsonb THEN 1 ELSE 0 END,
                f.nav_date DESC NULLS LAST,
                f.updated_at DESC NULLS LAST,
                f.wind_code ASC
            LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                {
                    "peer_group": normalized_group,
                    "limit": max(1, min(int(limit), 100)),
                },
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_peer_groups(self, limit: int = 100) -> List[Dict[str, Any]]:
        """汇总全库已确认的研究同类组，以及尚未建画像的基础类别。"""
        from sqlalchemy import text

        sql = """
            WITH category_rows AS (
                SELECT profile.peer_group AS name, COUNT(*)::int AS fund_count, 'research_profile' AS source
                FROM fund_research_profiles profile
                WHERE COALESCE(profile.peer_group, '') <> ''
                GROUP BY profile.peer_group
                UNION ALL
                SELECT f.type AS name, COUNT(*)::int AS fund_count, 'fund_type' AS source
                FROM funds f
                LEFT JOIN fund_research_profiles profile ON profile.wind_code = f.wind_code
                WHERE COALESCE(profile.peer_group, '') = ''
                  AND COALESCE(f.type, '') <> ''
                GROUP BY f.type
            )
            SELECT name, SUM(fund_count)::int AS fund_count, MIN(source) AS source
            FROM category_rows
            GROUP BY name
            ORDER BY fund_count DESC, name ASC
            LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"limit": max(1, min(int(limit), 200))}).fetchall()
        return [_row_to_dict(row) for row in rows]
