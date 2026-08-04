import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.data_quality_service import DataQualityService


def main() -> int:
    service = DataQualityService()
    standardized = {
        "status": "resolved",
        "strategy_family_key": "index_broad",
        "peer_group_key": "peer-index-hs300",
        "benchmark_mapping": {"benchmark_code": "000300.SH"},
    }
    context_check = service._check_research_context({}, standardized)
    if not context_check.get("passed") or context_check.get("source") != "standardized_classification":
        raise AssertionError(f"Standardized classification must replace duplicate profile fields: {context_check}")

    index_manager = service._check_manager_tenure(None, "index_broad")
    money_manager = service._check_manager_tenure(None, "cash_management")
    if not index_manager.get("not_applicable") or not money_manager.get("not_applicable"):
        raise AssertionError("Index and money-market quality must not require manager-tenure evidence")

    active_manager = service._check_manager_tenure(None, "active_equity_core")
    if active_manager.get("passed"):
        raise AssertionError("Active management quality must retain the manager-tenure requirement")

    print("OK data quality reuses standardized classification and applies category-aware tenure checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
