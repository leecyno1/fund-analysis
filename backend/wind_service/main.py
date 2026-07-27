from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Fund Analysis Wind Service",
    description="Wind API 数据采集服务",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 响应模型
class FundInfoResponse(BaseModel):
    wind_code: str
    name: str
    setup_date: Optional[str]
    company: Optional[str]
    manager: Optional[str]
    raw_data: Dict[str, Any]

class ManagerInfoResponse(BaseModel):
    name: str
    company: Optional[str]
    education: Optional[str]
    work_years: Optional[int]
    funds: List[str]
    raw_data: Dict[str, Any]

@app.get("/")
async def root():
    return {
        "service": "Wind API Service",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "unavailable",
        "data_source": "wind",
        "mock_mode": False,
        "detail": "Wind 独立采集服务尚未接入真实 Wind API；不会返回模拟基金或经理数据。",
    }

@app.get("/api/funds/{fund_code}", response_model=FundInfoResponse)
async def get_fund_info(fund_code: str):
    """获取基金基本信息"""
    raise HTTPException(
        status_code=501,
        detail="Wind 独立采集服务尚未接入真实 Wind API，已阻止返回模拟基金数据。",
    )

@app.get("/api/managers/{manager_name}", response_model=ManagerInfoResponse)
async def get_manager_info(manager_name: str):
    """获取基金经理信息"""
    raise HTTPException(
        status_code=501,
        detail="Wind 独立采集服务尚未接入真实 Wind API，已阻止返回模拟基金经理数据。",
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
