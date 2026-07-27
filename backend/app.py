"""
FastAPI 主应用
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from service_registry import init_services, get_wind_service, get_tushare_service, get_scoring_engine, get_db
from services.wind_service import WindDataService
from services.tushare_service import TushareDataService
from services.scoring_engine import FundScoringEngine
from routes import funds, managers, scoring, reports, research_reports, research_memos, screening, barra, brinson, export, data_sync, ai_reports, investment_analysis

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Fund Analysis API...")

    # 初始化服务
    tushare_svc = TushareDataService()
    wind_svc = WindDataService()
    scoring_eng = FundScoringEngine()
    db_conn = get_db()

    init_services(wind_svc=wind_svc, tushare_svc=tushare_svc, scoring_eng=scoring_eng, mongo_db=db_conn)

    logger.info("Services initialized successfully")
    yield

    logger.info("Shutting down Fund Analysis API...")


# 创建 FastAPI 应用
app = FastAPI(
    title="基金分析系统 API",
    description="基金经理评价、基金筛选、AI分析报告生成系统",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(funds.router)
app.include_router(managers.router)
app.include_router(scoring.router)
app.include_router(reports.router)
app.include_router(research_reports.router)
app.include_router(research_memos.router)
app.include_router(screening.router)
app.include_router(barra.router)
app.include_router(brinson.router)
app.include_router(export.router)
app.include_router(data_sync.router)
app.include_router(ai_reports.router)
app.include_router(investment_analysis.router)


@app.get("/")
async def root():
    return {
        "name": "基金分析系统",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "funds": "/api/funds",
            "managers": "/api/managers",
            "scoring": "/api/scoring",
            "reports": "/api/reports",
            "research_reports": "/api/research-reports",
            "screening": "/api/screening",
        },
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    wind_svc = get_wind_service()
    db_conn = get_db()
    return {
        "status": "healthy",
        "wind_service": "mock_mode" if wind_svc.mock_mode else "connected",
        "scoring_engine": "ready",
        "db": "connected" if db_conn is not None else "mock",
    }


@app.get("/api/config")
async def get_config():
    """获取系统配置和环境信息"""
    wind_svc = get_wind_service()
    return {
        "anthropic_api_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai_embedding_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "wind_api_available": wind_svc.mock_mode == False if wind_svc else "unknown",
        "embedding_model": os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
    }
