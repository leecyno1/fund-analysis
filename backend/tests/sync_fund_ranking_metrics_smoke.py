import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.sync_fund_ranking_metrics import latest_nav_payload, save_latest_fund_facts


class FakeMetricRepo:
    def __init__(self):
        self.saved = []

    def upsert_metric(self, **payload):
        self.saved.append(payload)


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

    metric_repo = FakeMetricRepo()
    saved = save_latest_fund_facts(
        metric_repo,
        "000051.OF",
        {
            "total_asset": 115.57,
            "raw_data": {
                "source": "tushare",
                "universe": {"management_fee": 0.15, "custodian_fee": 0.05},
            },
        },
        date(2026, 8, 11),
    )
    saved_values = {item["metric_name"]: float(item["metric_value"]) for item in metric_repo.saved}
    if saved != 2 or saved_values != {"expense_ratio": 0.002, "aum": 115.57}:
        raise AssertionError(f"Ranking sync must persist real fee and AUM facts: {metric_repo.saved}")
    if any(item.get("details", {}).get("source") != "funds.total_asset+funds.raw_data.tushare" for item in metric_repo.saved):
        raise AssertionError(f"Static evaluation metrics need explicit source lineage: {metric_repo.saved}")

    print("OK ranking sync keeps latest NAV and persists real AUM and fee snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
