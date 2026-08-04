import os
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_database
from repositories import get_fund_repo, get_nav_repo, get_research_profile_repo
from services.manager_tenure_metric_service import ManagerTenureMetricService
from services.professional_scoring_service import ProfessionalScoringService
from services.rolling_metric_service import RollingMetricService


def _nav_series(start: date, days: int) -> list[dict]:
    nav = Decimal("1.0000")
    series = []
    for offset in range(days):
        trade_date = start + timedelta(days=offset)
        daily_change = Decimal("0.00075") if offset % 31 else Decimal("-0.0040")
        nav = max(Decimal("0.7000"), nav * (Decimal("1") + daily_change))
        series.append({"date": trade_date.isoformat(), "nav": float(nav), "accum_nav": float(nav)})
    return series


def main() -> int:
    init_database()

    fund_code = "PROSCORE.TEST"
    fund_repo = get_fund_repo()
    nav_repo = get_nav_repo()
    profile_repo = get_research_profile_repo()

    fund_repo.upsert_fund(fund_code, {
        "name": "专业评分测试基金",
        "type": "stock",
        "nav": 1.5678,
        "nav_date": "2026-05-29",
        "total_asset": 68.5,
        "establishment_date": "2022-01-01",
        "performance": {"return_1y": 0.18},
        "risk_metrics": {"max_drawdown": -0.16},
    })
    profile_repo.upsert_profile(
        wind_code=fund_code,
        primary_benchmark="沪深300",
        peer_group="主动权益-专业评分",
        style_label="均衡成长",
        manager_tenure_start="2024-01-01",
        capacity_notes="规模适中",
        data_quality_notes="专业评分 smoke 数据齐备",
        updated_by="professional-scoring-smoke",
    )
    nav_repo.delete_nav(fund_code)
    nav_repo.upsert_nav_series(fund_code, _nav_series(date(2023, 1, 1), 900))
    RollingMetricService().calculate_and_save_for_fund(fund_code)
    ManagerTenureMetricService().calculate_and_save_for_fund(fund_code)

    result = ProfessionalScoringService().score_fund(fund_code)
    if result.get("calculation_method") != "category_evaluation_methodology_v1:active_equity":
        raise AssertionError(f"Unexpected calculation method: {result}")
    if result.get("fund_type_profile") != "active_equity":
        raise AssertionError(f"Expected active_equity profile, got {result}")
    if result.get("overall_score", 0) <= 60:
        raise AssertionError(f"Expected usable professional evaluation score, got {result}")

    dimensions = result.get("dimension_scores", {})
    for dimension in {"return", "risk", "risk_adjusted", "consistency", "manager_tenure", "data_quality"}:
        if dimension not in dimensions:
            raise AssertionError(f"Missing professional dimension {dimension}: {result}")

    if result.get("data_quality", {}).get("status") != "complete":
        raise AssertionError(f"Expected complete data quality, got {result}")
    if not result.get("positive_factors"):
        raise AssertionError(f"Expected positive scoring factors, got {result}")

    print("OK professional scoring uses rolling, tenure and quality inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
