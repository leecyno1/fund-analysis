"""基金浏览器路由。"""
from typing import Optional

from fastapi import APIRouter, Query

from services.fund_browser_service import FundBrowserService


router = APIRouter(prefix="/api/fund-browser", tags=["基金浏览器"])


@router.get("")
async def browse_funds(
    keyword: Optional[str] = Query(None),
    peer_group: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    return FundBrowserService().browse(
        keyword=keyword,
        peer_group=peer_group,
        page=page,
        page_size=page_size,
    )
