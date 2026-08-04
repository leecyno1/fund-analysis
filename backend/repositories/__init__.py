"""
Repository 包初始化
"""
from .fund_repo import FundRepo
from .manager_repo import ManagerRepo
from .holding_repo import HoldingRepo
from .nav_repo import NavRepo
from .factor_repo import FactorRepo
from .data_snapshot_repo import DataSourceSnapshotRepo
from .metric_snapshot_repo import MetricSnapshotRepo
from .report_chunk_repo import ReportChunkRepo
from .fund_pool_repo import FundPoolRepo
from .alert_repo import AlertRepo
from .research_profile_repo import ResearchProfileRepo
from .fund_classification_repo import FundClassificationRepo

# 全局单例
_fund_repo = None
_manager_repo = None
_holding_repo = None
_nav_repo = None
_factor_repo = None
_data_snapshot_repo = None
_metric_snapshot_repo = None
_report_chunk_repo = None
_fund_pool_repo = None
_alert_repo = None
_research_profile_repo = None
_fund_classification_repo = None


def get_fund_repo() -> FundRepo:
    global _fund_repo
    if _fund_repo is None:
        _fund_repo = FundRepo()
    return _fund_repo


def get_manager_repo() -> ManagerRepo:
    global _manager_repo
    if _manager_repo is None:
        _manager_repo = ManagerRepo()
    return _manager_repo


def get_holding_repo() -> HoldingRepo:
    global _holding_repo
    if _holding_repo is None:
        _holding_repo = HoldingRepo()
    return _holding_repo


def get_nav_repo() -> NavRepo:
    global _nav_repo
    if _nav_repo is None:
        _nav_repo = NavRepo()
    return _nav_repo


def get_factor_repo() -> FactorRepo:
    global _factor_repo
    if _factor_repo is None:
        _factor_repo = FactorRepo()
    return _factor_repo


def get_data_snapshot_repo() -> DataSourceSnapshotRepo:
    global _data_snapshot_repo
    if _data_snapshot_repo is None:
        _data_snapshot_repo = DataSourceSnapshotRepo()
    return _data_snapshot_repo


def get_metric_snapshot_repo() -> MetricSnapshotRepo:
    global _metric_snapshot_repo
    if _metric_snapshot_repo is None:
        _metric_snapshot_repo = MetricSnapshotRepo()
    return _metric_snapshot_repo


def get_report_chunk_repo() -> ReportChunkRepo:
    global _report_chunk_repo
    if _report_chunk_repo is None:
        _report_chunk_repo = ReportChunkRepo()
    return _report_chunk_repo


def get_fund_pool_repo() -> FundPoolRepo:
    global _fund_pool_repo
    if _fund_pool_repo is None:
        _fund_pool_repo = FundPoolRepo()
    return _fund_pool_repo


def get_alert_repo() -> AlertRepo:
    global _alert_repo
    if _alert_repo is None:
        _alert_repo = AlertRepo()
    return _alert_repo


def get_research_profile_repo() -> ResearchProfileRepo:
    global _research_profile_repo
    if _research_profile_repo is None:
        _research_profile_repo = ResearchProfileRepo()
    return _research_profile_repo


def get_fund_classification_repo() -> FundClassificationRepo:
    global _fund_classification_repo
    if _fund_classification_repo is None:
        _fund_classification_repo = FundClassificationRepo()
    return _fund_classification_repo
