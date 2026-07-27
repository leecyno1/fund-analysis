"""
数据健康检查 API
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from repositories import get_data_snapshot_repo

router = APIRouter(prefix="/api/data-health", tags=["数据健康"])


@router.get("/summary")
def get_data_health_summary(stale_hours: int = Query(24, ge=1, le=24 * 30)) -> Dict[str, Any]:
    """返回各数据集最新同步状态、近期失败数和过期数据集。"""
    repo = get_data_snapshot_repo()
    try:
        latest_snapshots = repo.list_latest_by_dataset()
        recent_failed_count = repo.count_recent_failures(hours=stale_hours)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Data health store unavailable: {exc.__class__.__name__}") from exc

    cutoff = datetime.now() - timedelta(hours=stale_hours)
    stale_datasets: List[Dict[str, Any]] = []
    for snapshot in latest_snapshots:
        finished_at = snapshot.get("finished_at") or snapshot.get("started_at")
        status = snapshot.get("status")
        is_stale = False
        if finished_at:
            try:
                is_stale = datetime.fromisoformat(finished_at) < cutoff
            except ValueError:
                is_stale = False
        if status != "success" or is_stale:
            stale_datasets.append({
                "dataset": snapshot.get("dataset"),
                "source": snapshot.get("source"),
                "status": status,
                "last_seen_at": finished_at,
            })

    return {
        "latest_snapshots": latest_snapshots,
        "recent_failed_count": recent_failed_count,
        "stale_datasets": stale_datasets,
        "stale_threshold_hours": stale_hours,
    }
