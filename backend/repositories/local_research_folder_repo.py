"""MongoDB persistence for local research folder indexes and review proposals."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _document(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    serialized = _serialize(dict(doc))
    serialized["id"] = str(serialized.pop("_id"))
    return serialized


class LocalResearchFolderRepo:
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
