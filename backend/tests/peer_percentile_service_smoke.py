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
        percentile = metric.get("percentile")
        if percentile is None or percentile < 0 or percentile > 100:
            raise AssertionError(f"Invalid percentile for {metric_name}: {metric}")

    print("OK peer percentile service returns same-peer ranks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
