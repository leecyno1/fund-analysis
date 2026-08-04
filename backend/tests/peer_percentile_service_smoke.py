import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import init_database
from services.peer_comparison_service import PeerComparisonService


def main() -> int:
    init_database()

    result = PeerComparisonService().build_peer_percentiles("000002.OF", window="1y")
    metrics = result.get("metrics", {})

    if result.get("target_id") != "000002.OF":
        raise AssertionError(f"Unexpected target: {result}")
    if result.get("peer_count", 0) < 1:
        raise AssertionError(f"Expected non-empty peer universe: {result}")
    for metric_name in ["annualized_return", "max_drawdown", "sharpe_ratio"]:
        metric = metrics.get(metric_name)
        if not metric:
            raise AssertionError(f"Missing percentile metric {metric_name}: {result}")
        if metric.get("sample_status") != "insufficient_peer_sample":
            raise AssertionError(f"Explicit small peer group must remain insufficient: {metric}")
        if metric.get("percentile") is not None:
            raise AssertionError(f"Small peer group must not fabricate a percentile: {metric}")

    gap = result.get("peer_metric_gap", {})
    if gap.get("next_action") != "sync_peer_nav_and_rolling_metrics":
        raise AssertionError(f"Small peer group must expose a metric evidence gap: {gap}")
    if result.get("peer_group_source") != "standardized_peer_group_membership":
        raise AssertionError(f"Peer comparison must retain the explicit membership source: {result}")

    print("OK peer percentile service stops ranking when the explicit peer sample is insufficient")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
