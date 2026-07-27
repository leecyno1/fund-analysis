"""
基金池 Repository
"""
import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

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


def _json(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _row_to_dict(row) -> Dict[str, Any]:
    data = dict(row._mapping)
    for key, value in list(data.items()):
        if isinstance(value, (datetime, date)):
            data[key] = value.isoformat()
    return data


class FundPoolRepo:
    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = _get_engine()
        return self._engine

    def create_pool(
        self,
        name: str,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        from sqlalchemy import text
        from database import init_database

        init_database()
        sql = """
            INSERT INTO fund_pools (name, description, created_by, is_default)
            VALUES (:name, :description, :created_by, :is_default)
            RETURNING *
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {
                "name": name,
                "description": description,
                "created_by": created_by,
                "is_default": is_default,
            }).fetchone()
            conn.commit()
        return _row_to_dict(row)

    def list_pools(self) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        sql = """
            SELECT * FROM fund_pools
            WHERE COALESCE(created_by, '') NOT IN ('smoke-test', 'portfolio-smoke')
              AND name NOT ILIKE '%组合%'
              AND name NOT ILIKE '%治理%'
            ORDER BY is_default DESC, updated_at DESC, created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return [_row_to_dict(row) for row in rows]

    def add_fund_to_pool(
        self,
        pool_id: str,
        fund_id: str,
        status: str,
        reason: Optional[str] = None,
        latest_conclusion: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
        risk_notes: Optional[str] = None,
        next_review_date: Optional[date] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import text
        from database import init_database

        init_database()
        existing_sql = """
            SELECT * FROM pool_members
            WHERE pool_id = CAST(:pool_id AS UUID) AND fund_id = :fund_id
            LIMIT 1
        """
        update_existing_sql = """
            UPDATE pool_members
            SET reason = CASE
                    WHEN :reason IS NULL OR :reason = '' THEN reason
                    WHEN reason IS NULL OR reason = '' THEN :reason
                    ELSE reason || '；' || :reason
                END,
                evidence = CASE
                    WHEN :evidence IS NULL THEN evidence
                    ELSE jsonb_strip_nulls(jsonb_build_object('previousEvidence', evidence)) || CAST(:evidence AS JSONB)
                END,
                risk_notes = CASE
                    WHEN :risk_notes IS NULL OR :risk_notes = '' THEN risk_notes
                    WHEN risk_notes IS NULL OR risk_notes = '' THEN :risk_notes
                    ELSE risk_notes || '；' || :risk_notes
                END,
                updated_by = :updated_by,
                updated_at = NOW()
            WHERE id = CAST(:member_id AS UUID)
            RETURNING *
        """
        insert_sql = """
            INSERT INTO pool_members (
                pool_id, fund_id, status, reason, latest_conclusion, evidence,
                risk_notes, next_review_date, created_by, updated_by
            ) VALUES (
                CAST(:pool_id AS UUID), :fund_id, :status, :reason, :latest_conclusion,
                CAST(:evidence AS JSONB), :risk_notes, :next_review_date, :created_by, :updated_by
            )
            RETURNING *
        """
        with self.engine.connect() as conn:
            existing = conn.execute(text(existing_sql), {"pool_id": pool_id, "fund_id": fund_id}).fetchone()
            if existing:
                row = conn.execute(text(update_existing_sql), {
                    "member_id": existing._mapping["id"],
                    "reason": reason,
                    "evidence": _json(evidence),
                    "risk_notes": risk_notes,
                    "updated_by": created_by,
                }).fetchone()
                conn.commit()
                return _row_to_dict(row)
            row = conn.execute(text(insert_sql), {
                "pool_id": pool_id,
                "fund_id": fund_id,
                "status": status,
                "reason": reason,
                "latest_conclusion": latest_conclusion,
                "evidence": _json(evidence),
                "risk_notes": risk_notes,
                "next_review_date": next_review_date,
                "created_by": created_by,
                "updated_by": created_by,
            }).fetchone()
            conn.commit()
        return _row_to_dict(row)

    def update_member_status(
        self,
        member_id: str,
        status: str,
        latest_conclusion: Optional[str] = None,
        updated_by: Optional[str] = None,
        next_review_date: Optional[date] = None,
        evidence: Optional[Dict[str, Any]] = None,
        risk_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        from sqlalchemy import text

        sql = """
            UPDATE pool_members
            SET status = :status,
                latest_conclusion = COALESCE(:latest_conclusion, latest_conclusion),
                evidence = COALESCE(CAST(:evidence AS JSONB), evidence),
                risk_notes = COALESCE(:risk_notes, risk_notes),
                updated_by = :updated_by,
                next_review_date = COALESCE(:next_review_date, next_review_date),
                updated_at = NOW()
            WHERE id = CAST(:member_id AS UUID)
            RETURNING *
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {
                "member_id": member_id,
                "status": status,
                "latest_conclusion": latest_conclusion,
                "evidence": _json(evidence),
                "risk_notes": risk_notes,
                "updated_by": updated_by,
                "next_review_date": next_review_date,
            }).fetchone()
            conn.commit()
        return _row_to_dict(row)

    def list_members(self, pool_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        clauses = ["pool_id = CAST(:pool_id AS UUID)"]
        params = {"pool_id": pool_id}
        if status:
            clauses.append("status = :status")
            params["status"] = status
        sql = f"""
            SELECT
                pool_members.*,
                funds.wind_code AS fund_wind_code,
                funds.name AS fund_name,
                funds.type AS fund_type,
                funds.nav AS fund_nav,
                funds.nav_date AS fund_nav_date,
                funds.total_asset AS fund_total_asset,
                funds.establishment_date AS fund_establishment_date
            FROM pool_members
            LEFT JOIN funds
              ON pool_members.fund_id = funds.id::text
              OR pool_members.fund_id = funds.wind_code
            WHERE {' AND '.join(clauses)}
            ORDER BY pool_members.updated_at DESC, pool_members.created_at DESC
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [_row_to_dict(row) for row in rows]
