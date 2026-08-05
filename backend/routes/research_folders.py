"""Local research folder configuration, scanning and human review API."""

from functools import lru_cache
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.local_research_folder_service import FolderValidationError, LocalResearchFolderService


router = APIRouter(prefix="/api/research-folders", tags=["本地调研纪要文件夹"])


class FolderConnectRequest(BaseModel):
    path: str = Field(min_length=1, max_length=2048)


class ReviewDecisionRequest(BaseModel):
    action: Literal["confirmed", "rejected"]


@lru_cache(maxsize=1)
def _get_service() -> LocalResearchFolderService:
    from repositories.local_research_folder_repo import LocalResearchFolderRepo
    from services.research_memo_metadata_extractor import get_research_memo_metadata_extractor
    from service_registry import get_db

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="调研纪要数据库不可用")
    repo = LocalResearchFolderRepo(db)
    repo.ensure_indexes()
    extractor = get_research_memo_metadata_extractor()
    return LocalResearchFolderService(repo=repo, metadata_extractor=extractor.extract)


@router.get("/")
async def list_folders():
    return {"data": _get_service().list_folders()}


@router.post("/", status_code=201)
async def connect_folder(payload: FolderConnectRequest):
    try:
        return {"status": "connected", "folder": _get_service().add_folder(payload.path)}
    except FolderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{folder_id}/scan")
async def scan_folder(folder_id: str):
    try:
        return _get_service().scan_folder(folder_id)
    except FolderValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reviews")
async def list_pending_reviews(folder_id: Optional[str] = Query(None)):
    data = _get_service().list_pending_reviews(folder_id)
    return {"total": len(data), "data": data}


@router.patch("/reviews/{report_id}/{proposal_id}")
async def review_proposal(report_id: str, proposal_id: str, payload: ReviewDecisionRequest):
    try:
        return _get_service().review_proposal(report_id, proposal_id, payload.action)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
