import math
import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tushare_service import TushareDataService


NAV_VALUES = [
    1.0000, 1.0200, 0.9900, 1.0150, 1.0050, 0.9800, 1.0100, 1.0300,
    1.0000, 0.9700, 1.0050, 1.0250, 0.9950, 1.0150, 1.0400, 1.0100,
    0.9850, 1.0200, 1.0350, 1.0050, 0.9750, 1.0150, 1.0300, 1.0500,
    1.0200, 1.0000, 1.0250, 1.0450, 1.0150, 1.0350,
]


class FakePro:
    def fund_nav(self, **kwargs):
        start = date.today() - timedelta(days=len(NAV_VALUES) - 1)
        return pd.DataFrame([
            {
                "ts_code": "000001.OF",
                "nav_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
                "unit_nav": value,
                "accum_nav": value,
            }
            for offset, value in enumerate(NAV_VALUES)
        ])


def expected_sortino() -> float:
    daily_returns = [
        NAV_VALUES[index] / NAV_VALUES[index - 1] - 1
        for index in range(1, len(NAV_VALUES))
    ]
    annual_return = (sum(daily_returns) / len(daily_returns)) * 252
    downside_returns = [min(value, 0.0) for value in daily_returns]
    mean = sum(downside_returns) / len(downside_returns)
    variance = sum((value - mean) ** 2 for value in downside_returns) / (len(downside_returns) - 1)
    downside_deviation = math.sqrt(variance) * math.sqrt(252)
    return annual_return / downside_deviation


def main() -> int:
    service = TushareDataService(token="test", mock_mode=True)
    service.mock_mode = False
    service._pro = FakePro()

    performance = service.get_fund_performance("000001.OF")
    sortino = performance.get("sortino")
    sharpe = performance.get("sharpe_ratio")

    real_sortino = expected_sortino()
    if sortino is None or abs(sortino - real_sortino) > 1e-4:
        raise AssertionError(
            f"sortino must be derived from downside deviation, expected {real_sortino}, got {sortino}"
        )
    if abs(sortino - round(sharpe * 1.2, 4)) < 1e-9:
        raise AssertionError(f"sortino must not be fabricated as sharpe*1.2: {sortino}")

    print("OK Tushare fund performance derives sortino from downside deviation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
