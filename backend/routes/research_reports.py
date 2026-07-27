"""
调研报告管理路由
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body
from typing import List, Optional
from datetime import datetime
import json
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research-reports", tags=["调研报告库"])


class ResearchReportCreate(BaseModel):
    manager_id: str = ""
    title: str
    report_date: str
    source: str
    content: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    fund_ids: List[str] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)


@router.get("/")
async def list_reports(
    manager_id: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="标签, 逗号分隔"),
    source: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    sort_by: str = Query("report_date"),
    sort_order: str = Query("desc"),
):
    """查询调研报告列表"""
    from service_registry import get_db
    db = get_db()

    if db is None:
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    try:
        query = {}
        if manager_id:
            query["manager_id"] = manager_id
        if keyword:
            query["$or"] = [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"summary": {"$regex": keyword, "$options": "i"}},
                {"content": {"$regex": keyword, "$options": "i"}},
            ]
        if source:
            query["source"] = {"$regex": source, "$options": "i"}
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            query["tags"] = {"$in": tag_list}
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query["report_date"] = date_filter

        sort_dir = -1 if sort_order == "desc" else 1
        cursor = db.research_reports.find(query).sort(sort_by, sort_dir).skip((page-1)*page_size).limit(page_size)
        total = db.research_reports.count_documents(query)

        reports = []
        for doc in cursor:
            reports.append({
                "id": str(doc.get("_id", "")),
                "manager_id": doc.get("manager_id"),
                "title": doc.get("title"),
                "report_date": doc.get("report_date"),
                "source": doc.get("source"),
                "summary": doc.get("summary", "")[:300],
                "tags": doc.get("tags", []),
                "key_points": doc.get("key_points", [])[:3],
            })

        return {"total": total, "page": page, "page_size": page_size, "data": reports}
    except Exception as e:
        logger.error(f"List reports error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_report(payload: ResearchReportCreate = Body(...)):
    """新增调研报告"""
    from service_registry import get_db
    db = get_db()
    from services.search_service import get_search_service

    if db is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        # 提取摘要（如果没有提供）
        manager_id = payload.manager_id or ""
        title = payload.title
        report_date = payload.report_date
        source = payload.source
        content = payload.content
        summary = payload.summary
        if not summary:
            summary = content[:500] if content else ""

        # 生成真实向量；模型/API 不可用时不写入假 embedding，报告仍可通过关键词检索。
        search_service = get_search_service()
        embedding = search_service.compute_report_embedding({
            "title": title, "summary": summary, "content": content[:2000]
        })

        report_doc = {
            "manager_id": manager_id,
            "title": title,
            "report_date": report_date,
            "source": source,
            "content": content,
            "summary": summary,
            "tags": payload.tags,
            "fund_ids": payload.fund_ids,
            "key_points": payload.key_points,
            "embedding": embedding,
            "embedding_status": "available" if embedding else "unavailable",
            "embedding_source": "openai_compatible" if embedding else "keyword_only_no_mock",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        result = db.research_reports.insert_one(report_doc)
        return {
            "id": str(result.inserted_id),
            "status": "created",
            "report": {
                "id": str(result.inserted_id),
                "manager_id": manager_id,
                "title": title,
                "report_date": report_date,
                "source": source,
                "summary": summary,
                "tags": payload.tags,
                "fund_ids": payload.fund_ids,
                "key_points": payload.key_points,
                "embedding_status": report_doc["embedding_status"],
                "embedding_source": report_doc["embedding_source"],
                "created_at": report_doc["created_at"],
            },
        }
    except Exception as e:
        logger.error(f"Create report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}")
async def get_report(report_id: str):
    """获取报告详情"""
    from bson import ObjectId
    from service_registry import get_db
    db = get_db()

    if db is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        doc = db.research_reports.find_one({"_id": ObjectId(report_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        return {
            "id": str(doc["_id"]),
            "manager_id": doc.get("manager_id"),
            "title": doc.get("title"),
            "report_date": doc.get("report_date"),
            "source": doc.get("source"),
            "content": doc.get("content"),
            "summary": doc.get("summary"),
            "tags": doc.get("tags", []),
            "fund_ids": doc.get("fund_ids", []),
            "key_points": doc.get("key_points", []),
            "created_at": doc.get("created_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{report_id}")
async def update_report(
    report_id: str,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    tags: Optional[List[str]] = None,
    content: Optional[str] = None,
):
    """更新报告"""
    from bson import ObjectId
    from service_registry import get_db
    db = get_db()

    if db is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        update_fields = {"updated_at": datetime.utcnow()}
        if title is not None:
            update_fields["title"] = title
        if summary is not None:
            update_fields["summary"] = summary
        if tags is not None:
            update_fields["tags"] = tags
        if content is not None:
            update_fields["content"] = content

        result = db.research_reports.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="报告不存在")

        return {"status": "updated", "id": report_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{report_id}")
async def delete_report(report_id: str):
    """删除报告"""
    from bson import ObjectId
    from service_registry import get_db
    db = get_db()

    if db is None:
        raise HTTPException(status_code=503, detail="数据库不可用")

    try:
        result = db.research_reports.delete_one({"_id": ObjectId(report_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="报告不存在")
        return {"status": "deleted", "id": report_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-import")
async def batch_import_reports(files: List[UploadFile] = File(...)):
    """批量导入调研报告（支持 PDF, DOCX, TXT, MD）"""
    from services.vector_db_service import get_vector_db
    import uuid

    try:
        vector_db = get_vector_db()
        imported_count = 0
        errors = []

        for file in files:
            try:
                # 读取文件内容
                content = await file.read()
                text_content = content.decode('utf-8', errors='ignore')

                # 提取标题（使用文件名）
                title = file.filename.rsplit('.', 1)[0]

                # 生成唯一ID
                report_id = str(uuid.uuid4())

                # 添加到向量数据库
                vector_db.add_report(
                    report_id=report_id,
                    title=title,
                    content=text_content,
                    metadata={
                        "source": "batch_import",
                        "filename": file.filename,
                        "date": datetime.utcnow().strftime("%Y-%m-%d")
                    }
                )

                imported_count += 1
            except Exception as e:
                logger.error(f"Failed to import {file.filename}: {e}")
                errors.append({"filename": file.filename, "error": str(e)})

        return {
            "status": "completed",
            "imported": imported_count,
            "total": len(files),
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Batch import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/status")
async def get_semantic_search_status():
    """Return vector DB and embedding model status without loading the model."""
    from services.vector_db_service import get_vector_db

    try:
        vector_db = get_vector_db()
        info = vector_db.get_collection_info()
        return {
            "available": bool(info),
            "collection": info.get("name"),
            "points_count": info.get("points_count", 0),
            "vectors_count": info.get("vectors_count", 0),
            "qdrant_status": str(info.get("status")),
            "model_loaded": info.get("model_loaded", False),
            "model_name": info.get("model_name"),
            "vector_size": info.get("vector_size"),
        }
    except Exception as e:
        logger.error(f"Semantic search status error: {e}")
        return {"available": False, "model_loaded": False, "error": str(e)}


@router.post("/search/warmup")
async def warm_up_semantic_search():
    """Load the embedding model explicitly so the first user search is fast."""
    from services.vector_db_service import get_vector_db

    try:
        vector_db = get_vector_db()
        warmup = vector_db.warm_up()
        info = vector_db.get_collection_info()
        return {
            "status": "ready",
            **warmup,
            "collection": info.get("name"),
            "points_count": info.get("points_count", 0),
            "vectors_count": info.get("vectors_count", 0),
            "qdrant_status": str(info.get("status")),
        }
    except Exception as e:
        logger.error(f"Semantic search warmup error: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/search/similar")
async def search_similar_reports(
    content: Optional[str] = Query(None),
    top_k: int = Query(5),
    manager_name: Optional[str] = None,
    payload: Optional[dict] = Body(None),
):
    """语义搜索相似报告（使用向量数据库）"""
    from services.vector_db_service import get_vector_db

    try:
        if payload:
            content = payload.get("content", content)
            top_k = payload.get("top_k", top_k)
            manager_name = payload.get("manager_name", manager_name)

        if not content:
            raise HTTPException(status_code=422, detail="content is required")

        vector_db = get_vector_db()

        # 构建过滤条件
        filter_dict = None
        if manager_name:
            filter_dict = {"manager_name": manager_name}

        # 搜索相似报告
        results = vector_db.search_similar(
            query=content,
            top_k=top_k,
            filter_dict=filter_dict
        )

        return {
            "query": content,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Search similar reports error: {e}")
        # 如果向量数据库不可用，返回空结果
        return {"query": content, "results": [], "count": 0}
