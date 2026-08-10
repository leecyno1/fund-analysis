import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.investment_analysis_service import InvestmentAnalysisService  # noqa: E402
from services.performance_attribution_service import PerformanceAttributionService  # noqa: E402


class FakeMarketDataAdapter:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_benchmark_nav(self, benchmark_code, start_date, end_date):
        self.calls.append((benchmark_code, start_date, end_date))
        return list(self.rows)


def main() -> int:
    attribution = PerformanceAttributionService()
    mapped_code, mapped_source = attribution._resolve_benchmark(
        None,
        {"benchmark_mapping": {"benchmark_code": "000905.SH"}},
    )
    if (mapped_code, mapped_source) != ("000905.SH", "fund_classification_catalog"):
        raise AssertionError(f"Default attribution benchmark must come from classification: {(mapped_code, mapped_source)}")

    override_code, override_source = attribution._resolve_benchmark("000852", {})
    if (override_code, override_source) != ("000852.SH", "user_override"):
        raise AssertionError(f"Explicit benchmark override should be normalized and disclosed: {(override_code, override_source)}")

    missing_code, missing_source = attribution._resolve_benchmark(None, {})
    if missing_code is not None or missing_source != "missing_classification_benchmark":
        raise AssertionError(f"Missing classification benchmark must remain unavailable: {(missing_code, missing_source)}")

    market = FakeMarketDataAdapter([
        {"date": "2026-07-01", "nav": 100.0},
        {"date": "2026-07-02", "nav": 101.0},
        {"date": "2026-07-03", "nav": 100.5},
    ])
    nav_analysis = InvestmentAnalysisService(market_data_adapter=market)
    nav_analysis._returns = lambda *_args, **_kwargs: {}
    returns, label, source = nav_analysis._benchmark_returns(
        {"wind_code": "000001.OF", "type": "stock"},
        "000905.SH",
        "2026-07-01",
        "2026-07-03",
    )
    if label != "000905.SH" or source != "market_data_adapter" or len(returns) != 2:
        raise AssertionError(f"Mapped benchmark must use a real benchmark series: {(returns, label, source)}")
    if market.calls != [("000905.SH", "2026-07-01", "2026-07-03")]:
        raise AssertionError(f"Benchmark adapter received the wrong request: {market.calls}")

    empty_market = FakeMarketDataAdapter([])
    unavailable = InvestmentAnalysisService(market_data_adapter=empty_market)
    unavailable._returns = lambda *_args, **_kwargs: {}
    returns, label, source = unavailable._benchmark_returns(
        {"wind_code": "000001.OF", "type": "stock"},
        "000905.SH",
        "2026-07-01",
        "2026-07-03",
    )
    if returns or label != "000905.SH" or source != "benchmark_series_unavailable":
        raise AssertionError(f"Explicit benchmark failure must not fall back to a broad peer average: {(returns, label, source)}")

    print("OK attribution uses classification benchmarks and never disguises peer averages as explicit indexes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
