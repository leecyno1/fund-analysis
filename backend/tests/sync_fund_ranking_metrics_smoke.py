import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.sync_fund_ranking_metrics import latest_nav_payload


def main() -> int:
    payload = latest_nav_payload([
        {"date": "2026-03-31", "unit_nav": 1.2, "net_asset": 1_250_000_000},
        {"date": "2026-04-01", "unit_nav": 1.21, "net_asset": None},
        {"date": "2026-04-02", "unit_nav": 1.22, "net_asset": None},
    ])
    if payload.get("nav") != 1.22 or payload.get("nav_date") != "2026-04-02":
        raise AssertionError(f"Latest NAV must remain the latest observation: {payload}")
    if payload.get("total_asset") != 12.5 or payload.get("total_asset_as_of") != "2026-03-31":
        raise AssertionError(f"AUM must use the latest reported non-null asset observation: {payload}")
    if payload.get("total_asset_source") != "tushare.fund_nav.latest_reported_net_asset":
        raise AssertionError(f"AUM source lineage must be explicit: {payload}")

    print("OK ranking sync keeps latest NAV and independently selects the latest reported AUM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
