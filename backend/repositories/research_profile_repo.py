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
