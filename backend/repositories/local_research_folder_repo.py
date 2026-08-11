"""Persistence adapters for local research folder indexes and review proposals."""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any, Dict, List, Optional
from uuid import UUID


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _document(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    serialized = _serialize(dict(doc))
    serialized["id"] = str(serialized.pop("_id"))
    return serialized


class LocalResearchFolderRepo:
    """Legacy MongoDB adapter retained for old report consumers."""

    def __init__(self, db: Any):
        self.db = db

    def ensure_indexes(self) -> None:
        self.db.local_research_folders.create_index("path", unique=True)
        self.db.local_research_documents.create_index(
            [("folder_id", 1), ("relative_path", 1)], unique=True
        )
        self.db.local_research_documents.create_index("content_hash")
        self.db.research_reports.create_index("fund_ids")

    def create_folder(self, folder: Dict[str, Any]) -> Dict[str, Any]:
        result = self.db.local_research_folders.insert_one(dict(folder))
        return {**_serialize(folder), "id": str(result.inserted_id)}

    def list_folders(self) -> List[Dict[str, Any]]:
        return [_document(item) for item in self.db.local_research_folders.find({}).sort("created_at", -1)]

    def get_folder(self, folder_id: str) -> Optional[Dict[str, Any]]:
        from bson import ObjectId

        return _document(self.db.local_research_folders.find_one({"_id": ObjectId(folder_id)}))

    def update_folder(self, folder_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from bson import ObjectId
        from pymongo import ReturnDocument

        doc = self.db.local_research_folders.find_one_and_update(
            {"_id": ObjectId(folder_id)},
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
        return _document(doc)

    def get_document(self, folder_id: str, relative_path: str) -> Optional[Dict[str, Any]]:
        return _document(self.db.local_research_documents.find_one({
            "folder_id": folder_id,
            "relative_path": relative_path,
        }))

    def find_document_by_hash(
        self,
        content_hash: str,
        exclude_folder_id: Optional[str] = None,
        exclude_relative_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        query: Dict[str, Any] = {"content_hash": content_hash, "report_id": {"$nin": [None, ""]}}
        if exclude_folder_id and exclude_relative_path:
            query["$nor"] = [{"folder_id": exclude_folder_id, "relative_path": exclude_relative_path}]
        return _document(self.db.local_research_documents.find_one(query))

    def upsert_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        from pymongo import ReturnDocument

        doc = self.db.local_research_documents.find_one_and_update(
            {"folder_id": document["folder_id"], "relative_path": document["relative_path"]},
            {"$set": dict(document)},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return _document(doc)

    def create_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        result = self.db.research_reports.insert_one(dict(report))
        return {**_serialize(report), "id": str(result.inserted_id)}

    def update_report(self, report_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from bson import ObjectId
        from pymongo import ReturnDocument

        doc = self.db.research_reports.find_one_and_update(
            {"_id": ObjectId(report_id)},
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
        return _document(doc)

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        from bson import ObjectId

        return _document(self.db.research_reports.find_one({"_id": ObjectId(report_id)}))

    def list_reports_for_fund(self, wind_code: str) -> List[Dict[str, Any]]:
        cursor = self.db.research_reports.find({"fund_ids": wind_code}).sort([
            ("report_date", -1),
            ("updated_at", -1),
        ])
        return [_document(item) for item in cursor]

    def list_pending_reviews(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"review_proposals": {"$elemMatch": {"review_status": "pending"}}}
        if folder_id:
            query["local_folder_id"] = folder_id
        pending: List[Dict[str, Any]] = []
        for report in self.db.research_reports.find(query).sort("updated_at", -1):
            for proposal in report.get("review_proposals", []):
                if proposal.get("review_status") != "pending":
                    continue
                pending.append({
                    "report_id": str(report["_id"]),
                    "report_title": report.get("title") or "无标题纪要",
                    **_serialize(proposal),
                })
        return pending


class PostgresLocalResearchFolderRepo:
    """PostgreSQL-backed local memo index used by the main application."""

    REPORT_FIELDS = {
        "manager_id", "manager_name", "fund_ids", "title", "report_date", "source",
        "content", "summary", "key_points", "tags", "classifications", "style_labels",
        "review_proposals", "review_status", "local_folder_id", "local_relative_path",
        "local_source_path", "source_hash", "extraction_status", "extraction_provider",
        "extraction_model", "llm_extraction_status", "llm_extraction_error", "created_at",
        "updated_at",
    }
    JSON_FIELDS = {"key_points", "review_proposals", "last_scan_counts"}

    def __init__(self, engine: Any = None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            try:
                from backend.database import get_engine
            except ModuleNotFoundError:
                from database import get_engine
            self._engine = get_engine()
        return self._engine

    @staticmethod
    def _row(row: Any) -> Optional[Dict[str, Any]]:
        return _serialize(dict(row._mapping)) if row else None

    @classmethod
    def _params(cls, fields: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: json.dumps(value, ensure_ascii=False, default=str) if key in cls.JSON_FIELDS else value
            for key, value in fields.items()
        }

    @classmethod
    def _assignments(cls, fields: Dict[str, Any]) -> str:
        return ", ".join(
            f"{key} = CAST(:{key} AS JSONB)" if key in cls.JSON_FIELDS else f"{key} = :{key}"
            for key in fields
        )

    def ensure_indexes(self) -> None:
        try:
            from backend.database import init_database
        except ModuleNotFoundError:
            from database import init_database
        init_database()

    def create_folder(self, folder: Dict[str, Any]) -> Dict[str, Any]:
        from sqlalchemy import text

        fields = {key: folder.get(key) for key in (
            "path", "name", "status", "last_scan_at", "last_scan_counts", "created_at", "updated_at"
        )}
        sql = f"""
            INSERT INTO local_research_folders ({', '.join(fields)})
            VALUES ({', '.join(f'CAST(:{key} AS JSONB)' if key in self.JSON_FIELDS else f':{key}' for key in fields)})
            RETURNING *
        """
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), self._params(fields)).fetchone()
        return self._row(row) or {}

    def list_folders(self) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM local_research_folders ORDER BY created_at DESC")).fetchall()
        return [self._row(row) or {} for row in rows]

    def get_folder(self, folder_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM local_research_folders WHERE id = CAST(:id AS UUID)"), {"id": folder_id}).fetchone()
        return self._row(row)

    def update_folder(self, folder_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        allowed = {key: value for key, value in fields.items() if key in {
            "path", "name", "status", "last_scan_at", "last_scan_counts", "updated_at"
        }}
        if not allowed:
            return self.get_folder(folder_id)
        sql = f"UPDATE local_research_folders SET {self._assignments(allowed)} WHERE id = CAST(:id AS UUID) RETURNING *"
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), {**self._params(allowed), "id": folder_id}).fetchone()
        return self._row(row)

    def get_document(self, folder_id: str, relative_path: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            row = conn.execute(text("""
                SELECT * FROM local_research_documents
                WHERE folder_id = CAST(:folder_id AS UUID) AND relative_path = :relative_path
            """), {"folder_id": folder_id, "relative_path": relative_path}).fetchone()
        return self._row(row)

    def find_document_by_hash(
        self,
        content_hash: str,
        exclude_folder_id: Optional[str] = None,
        exclude_relative_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        sql = """
            SELECT * FROM local_research_documents
            WHERE content_hash = :content_hash AND report_id IS NOT NULL
              AND NOT (
                CAST(:exclude_folder_id AS UUID) IS NOT NULL
                AND folder_id = CAST(:exclude_folder_id AS UUID)
                AND relative_path = :exclude_relative_path
              )
            LIMIT 1
        """
        with self.engine.connect() as conn:
            row = conn.execute(text(sql), {
                "content_hash": content_hash,
                "exclude_folder_id": exclude_folder_id,
                "exclude_relative_path": exclude_relative_path,
            }).fetchone()
        return self._row(row)

    def upsert_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        from sqlalchemy import text

        fields = {key: document.get(key) for key in (
            "folder_id", "relative_path", "source_path", "size", "mtime_ns", "content_hash",
            "report_id", "index_status", "error", "updated_at",
        )}
        sql = """
            INSERT INTO local_research_documents (
                folder_id, relative_path, source_path, size, mtime_ns, content_hash,
                report_id, index_status, error, updated_at
            ) VALUES (
                CAST(:folder_id AS UUID), :relative_path, :source_path, :size, :mtime_ns, :content_hash,
                CAST(:report_id AS UUID), :index_status, :error, :updated_at
            )
            ON CONFLICT (folder_id, relative_path) DO UPDATE SET
                source_path = EXCLUDED.source_path,
                size = EXCLUDED.size,
                mtime_ns = EXCLUDED.mtime_ns,
                content_hash = EXCLUDED.content_hash,
                report_id = EXCLUDED.report_id,
                index_status = EXCLUDED.index_status,
                error = EXCLUDED.error,
                updated_at = EXCLUDED.updated_at
            RETURNING *
        """
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), fields).fetchone()
        return self._row(row) or {}

    def create_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        from sqlalchemy import text

        fields = {key: value for key, value in report.items() if key in self.REPORT_FIELDS}
        columns = ", ".join(fields)
        values = ", ".join(
            f"CAST(:{key} AS JSONB)" if key in self.JSON_FIELDS else f":{key}"
            for key in fields
        )
        with self.engine.begin() as conn:
            row = conn.execute(
                text(f"INSERT INTO research_reports ({columns}) VALUES ({values}) RETURNING *"),
                self._params(fields),
            ).fetchone()
        return self._row(row) or {}

    def update_report(self, report_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        allowed = {key: value for key, value in fields.items() if key in self.REPORT_FIELDS and key != "created_at"}
        if not allowed:
            return self.get_report(report_id)
        sql = f"UPDATE research_reports SET {self._assignments(allowed)} WHERE id = CAST(:id AS UUID) RETURNING *"
        with self.engine.begin() as conn:
            row = conn.execute(text(sql), {**self._params(allowed), "id": report_id}).fetchone()
        return self._row(row)

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM research_reports WHERE id = CAST(:id AS UUID)"), {"id": report_id}).fetchone()
        return self._row(row)

    def list_reports_for_fund(self, wind_code: str) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT * FROM research_reports
                WHERE :wind_code = ANY(COALESCE(fund_ids, ARRAY[]::TEXT[]))
                ORDER BY report_date DESC NULLS LAST, updated_at DESC
            """), {"wind_code": wind_code}).fetchall()
        return [self._row(row) or {} for row in rows]

    def list_pending_reviews(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        where = "review_proposals @> '[{\"review_status\":\"pending\"}]'::jsonb"
        params: Dict[str, Any] = {}
        if folder_id:
            where += " AND local_folder_id = CAST(:folder_id AS UUID)"
            params["folder_id"] = folder_id
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"SELECT * FROM research_reports WHERE {where} ORDER BY updated_at DESC"), params).fetchall()
        pending: List[Dict[str, Any]] = []
        for row in rows:
            report = self._row(row) or {}
            for proposal in report.get("review_proposals") or []:
                if proposal.get("review_status") == "pending":
                    pending.append({
                        "report_id": report.get("id"),
                        "report_title": report.get("title") or "无标题纪要",
                        **proposal,
                    })
        return pending
