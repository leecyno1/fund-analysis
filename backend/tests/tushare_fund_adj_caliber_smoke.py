import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tushare_service import TushareDataService

DAYS = 25
EX_DIV_OFFSET = 10


class FakeProWithAdj:
    """分红基金：除息日单位净值 1.05→1.00，复权因子 1.00→1.05。"""

    def __init__(self):
        self.adj_calls = []

    def fund_nav(self, **kwargs):
        start = date.today() - timedelta(days=DAYS - 1)
        rows = []
        for offset in range(DAYS):
            if offset < EX_DIV_OFFSET:
                unit_nav = 1.05
                accum_nav = 1.05
            else:
                unit_nav = 1.00 + (offset - EX_DIV_OFFSET) * 0.001
                accum_nav = unit_nav + 0.05
            rows.append({
                "ts_code": "000001.OF",
                "nav_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
                "unit_nav": unit_nav,
                "accum_nav": accum_nav,
            })
        return pd.DataFrame(rows)

    def fund_adj(self, **kwargs):
        self.adj_calls.append(kwargs)
        start = date.today() - timedelta(days=DAYS - 1)
        return pd.DataFrame([
            {
                "ts_code": "000001.OF",
                "trade_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
                "adj_factor": 1.0 if offset < EX_DIV_OFFSET else 1.05,
            }
            for offset in range(DAYS)
        ])


class FakeProWithoutAdj:
    def fund_nav(self, **kwargs):
        start = date.today() - timedelta(days=DAYS - 1)
        return pd.DataFrame([
            {
                "ts_code": "000002.OF",
                "nav_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
                "unit_nav": 1.0 + offset * 0.001,
                "accum_nav": 1.0 + offset * 0.001,
            }
            for offset in range(DAYS)
        ])


def build_service(fake_pro) -> TushareDataService:
    service = TushareDataService(token="test", mock_mode=True)
    service.mock_mode = False
    service._pro = fake_pro
    return service


def main() -> int:
    fake_pro = FakeProWithAdj()
    service = build_service(fake_pro)
    series = service.get_fund_nav("000001.OF", "2020-01-01", "2099-01-01")

    if not fake_pro.adj_calls:
        raise AssertionError("get_fund_nav must query tushare fund_adj for adjustment factors")

    for item in series:
        expected_adj = round(item.get("unit_nav") * (1.0 if item.get("date") <= series[EX_DIV_OFFSET - 1].get("date") else 1.05), 6)
        if item.get("adj_nav") is None or abs(item.get("adj_nav") - expected_adj) > 1e-4:
            raise AssertionError(f"adj_nav must equal unit_nav x adj_factor: {item} vs {expected_adj}")
        if item.get("metric_nav_source") != "tushare.fund_adj.adj_factor":
            raise AssertionError(f"metric nav must prefer adjusted caliber with lineage: {item.get('metric_nav_source')}")
        if item.get("unit_nav") is None or item.get("nav") is None:
            raise AssertionError(f"unit nav must remain available for display: {item}")

    ex_div_row = series[EX_DIV_OFFSET]
    artificial_drop = 1.00 / 1.05 - 1
    if ex_div_row.get("daily_return") is None or abs(ex_div_row["daily_return"] - artificial_drop) < 1e-6:
        raise AssertionError(f"daily_return must not contain the artificial ex-dividend drop: {ex_div_row}")
    if abs(ex_div_row["daily_return"]) > 0.005:
        raise AssertionError(f"adjusted daily_return at ex-dividend must stay continuous: {ex_div_row}")

    fallback = build_service(FakeProWithoutAdj())
    fallback_series = fallback.get_fund_nav("000002.OF", "2020-01-01", "2099-01-01")
    if any(item.get("metric_nav_source") != "tushare.fund_nav.accum_nav" for item in fallback_series):
        raise AssertionError(f"without fund_adj the caliber must fall back to accum_nav: {fallback_series[0]}")

    performance_service = build_service(fake_pro)
    performance = performance_service.get_fund_performance("000001.OF")
    if len(fake_pro.adj_calls) < 2:
        raise AssertionError("get_fund_performance must also query fund_adj for the adjusted caliber")
    adjusted_ret_1y = round((1.00 + (DAYS - 1 - EX_DIV_OFFSET) * 0.001) * 1.05 / 1.05 - 1, 4)
    accum_ret_1y = round(((1.00 + (DAYS - 1 - EX_DIV_OFFSET) * 0.001) + 0.05) / 1.05 - 1, 4)
    if performance.get("annualized_return_1y") != adjusted_ret_1y:
        raise AssertionError(
            f"performance returns must use the adjusted caliber: expected {adjusted_ret_1y}, got {performance.get('annualized_return_1y')}"
        )
    if performance.get("annualized_return_1y") == accum_ret_1y:
        raise AssertionError(f"performance returns must not stay on the accum_nav caliber: {performance}")

    print("OK Tushare fund NAV uses fund_adj adjusted caliber with lineage and fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
