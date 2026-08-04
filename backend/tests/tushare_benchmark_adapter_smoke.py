import os
import sys
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tushare_service import TushareDataService


class FakePro:
    def __init__(self):
        self.calls = []
        self.repo_calls = []

    def index_daily(self, **kwargs):
        self.calls.append(kwargs)
        return pd.DataFrame([
            {"ts_code": "000300.SH", "trade_date": "20260702", "close": 4010.0},
            {"ts_code": "000300.SH", "trade_date": "20260701", "close": 4000.0},
        ])

    def fund_nav(self, **kwargs):
        start = date.today() - timedelta(days=19)
        return pd.DataFrame([
            {
                "ts_code": "000198.OF",
                "nav_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
                "unit_nav": 1.0,
                "accum_nav": None,
                "adj_nav": 13940.0 + offset * 0.4,
            }
            for offset in range(20)
        ])

    def repo_daily(self, **kwargs):
        self.repo_calls.append(kwargs)
        return pd.DataFrame([
            {
                "ts_code": "DR007.IB",
                "trade_date": "20260702",
                "repo_maturity": "DR007",
                "weight_r": 1.4551,
                "weight": 1.4548,
                "close": 1.4533,
            },
            {
                "ts_code": "DR007.IB",
                "trade_date": "20260701",
                "repo_maturity": "DR007",
                "weight_r": 1.4420,
                "weight": 1.4410,
                "close": 1.4400,
            },
        ])


def main() -> int:
    service = TushareDataService(token="test", mock_mode=True)
    fake_pro = FakePro()
    service.mock_mode = False
    service._pro = fake_pro

    series = service.get_benchmark_nav("000300.SH", "2026-07-01", "2026-07-02")
    if [item.get("date") for item in series] != ["2026-07-01", "2026-07-02"]:
        raise AssertionError(f"Tushare benchmark adapter must return sorted dates: {series}")
    if any(item.get("source") != "tushare.index_daily" for item in series):
        raise AssertionError(f"Benchmark rows must retain source lineage: {series}")
    if fake_pro.calls[0].get("fields") != "ts_code,trade_date,close":
        raise AssertionError(f"Benchmark adapter must request only necessary fields: {fake_pro.calls}")

    call_count = len(fake_pro.calls)
    if service.get_benchmark_nav("DR007", "2026-07-01", "2026-07-02") != []:
        raise AssertionError("Unsupported rate benchmark must remain unavailable instead of fabricated")
    if len(fake_pro.calls) != call_count:
        raise AssertionError("Unsupported benchmark code must not call the index endpoint")

    rates = service.get_benchmark_rate("DR007", "2026-07-01", "2026-07-02")
    if [item.get("date") for item in rates] != ["2026-07-01", "2026-07-02"]:
        raise AssertionError(f"DR007 rate evidence must be sorted: {rates}")
    if abs(rates[-1].get("annualized_rate") - 0.014551) > 1e-12:
        raise AssertionError(f"DR007 percentage points must normalize to decimal rates: {rates}")
    if fake_pro.repo_calls[0].get("ts_code") != "DR007.IB":
        raise AssertionError(f"DR007 mapping must request the interbank repo code: {fake_pro.repo_calls}")
    if service.get_benchmark_rate("CBA_CREDIT", "2026-07-01", "2026-07-02") != []:
        raise AssertionError("Unsupported rate benchmark must remain unavailable")

    performance = service.get_fund_performance("000198.OF")
    if performance.get("seven_day_annualized_yield") is None:
        raise AssertionError(f"Money-market performance must use adj_nav when accum_nav is empty: {performance}")
    if performance.get("seven_day_yield_source") != "derived:tushare.fund_nav.adj_nav":
        raise AssertionError(f"Money-market performance must retain derivation lineage: {performance}")

    nav_series = service.get_fund_nav("000198.OF", "2026-07-01", "2026-07-20")
    if any(item.get("metric_nav_source") != "tushare.fund_nav.adj_nav" for item in nav_series):
        raise AssertionError(f"Fund NAV must choose one consistent performance column: {nav_series}")

    print("OK Tushare adapter separates index NAV, DR007 rates and money-market NAV evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
