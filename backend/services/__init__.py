"""
服务包初始化
"""
from .scoring_engine import FundScoringEngine
from .ai_report import get_report_generator
from .search_service import get_search_service

__all__ = [
    "WindDataService",
    "FundScoringEngine",
    "get_report_generator",
    "get_search_service",
]


def __getattr__(name):
    if name == "WindDataService":
        from .wind_service import WindDataService
        return WindDataService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
