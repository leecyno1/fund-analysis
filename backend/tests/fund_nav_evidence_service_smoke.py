import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fund_nav_evidence_service import FundNavDataEnrichmentService, FundNavEvidenceService


class FakeClassificationAdapter:
    def __init__(self, benchmark_code=None):
        self.benchmark_code = benchmark_code

    def get_classification_context(self, wind_code: str):
        return {
            "status": "resolved",
            "fund_code": wind_code,
            "benchmark_mapping": (
                {
                    "benchmark_code": self.benchmark_code,
                    "source": "benchmark_mappings",
                    "mapping_method": "test_mapping",
                }
                if self.benchmark_code
                else None
            ),
        }


class FakeMarketDataAdapter:
    def __init__(self, benchmark_series):
        self.benchmark_series = benchmark_series
        self.calls = []

    def get_benchmark_nav(self, benchmark_code: str, start_date: str, end_date: str):
        self.calls.append((benchmark_code, start_date, end_date))
        return list(self.benchmark_series)


def _money_nav_series():
    start = date(2026, 7, 20)
    cumulative = 13940.0
    result = []
    for offset in range(16):
        cumulative += 0.4
        result.append({
            "date": (start + timedelta(days=offset)).isoformat(),
            "nav": 1.0,
            "unit_nav": 1.0,
            "accum_nav": cumulative,
            "adj_nav": cumulative,
            "reported_accum_nav": None,
        })
    return result


def main() -> int:
    evidence_service = FundNavEvidenceService()
    money_facts = evidence_service.derive_money_market_facts(_money_nav_series(), fund_type="货币型")
    if money_facts.get("seven_day_annualized_yield") is None:
        raise AssertionError(f"Money-market NAV must derive a seven-day annualized yield: {money_facts}")
    if money_facts.get("seven_day_yield_source") != "derived:tushare.fund_nav.adj_nav":
        raise AssertionError(f"Derived yield must retain source lineage: {money_facts}")
    if money_facts.get("income_per_10000") is None:
        raise AssertionError(f"Money-market NAV must expose latest income per 10,000 units: {money_facts}")

    normal_fund = [
        {"date": item["date"], "unit_nav": 1.2, "accum_nav": 2.0 + index * 0.01, "reported_accum_nav": 2.0}
        for index, item in enumerate(_money_nav_series())
    ]
    if evidence_service.derive_money_market_facts(normal_fund):
        raise AssertionError("Ordinary fund NAV must not be mislabeled as a money-market yield series")

    fund_series = [
        {"date": f"2026-07-{day:02d}", "nav": 1.0 + day / 1000}
        for day in range(1, 11)
    ]
    benchmark_series = [
        {"date": f"2026-07-{day:02d}", "nav": 4000 + day}
        for day in range(1, 11)
    ]
    market = FakeMarketDataAdapter(benchmark_series)
    enrichment = FundNavDataEnrichmentService(
        market,
        classification_adapter=FakeClassificationAdapter("000300.SH"),
    ).enrich(
        wind_code="INDEX.EVIDENCE",
        fund_type="指数型",
        nav_series=fund_series,
        start_date="2026-07-01",
        end_date="2026-07-10",
    )
    if enrichment.get("benchmark_data_status") != "available":
        raise AssertionError(f"Mapped real benchmark series must become available: {enrichment}")
    if enrichment.get("benchmark_observations") != 10:
        raise AssertionError(f"Benchmark alignment count is not auditable: {enrichment}")
    if any(item.get("benchmark_nav") is None for item in enrichment.get("nav_series", [])):
        raise AssertionError(f"Shared benchmark dates must be attached exactly: {enrichment}")

    no_mapping_market = FakeMarketDataAdapter(benchmark_series)
    no_mapping = FundNavDataEnrichmentService(
        no_mapping_market,
        classification_adapter=FakeClassificationAdapter(),
    ).enrich(
        wind_code="INDEX.NO.MAPPING",
        fund_type="指数型",
        nav_series=fund_series,
        start_date="2026-07-01",
        end_date="2026-07-10",
    )
    if no_mapping.get("benchmark_data_status") != "mapping_missing" or no_mapping_market.calls:
        raise AssertionError(f"Missing benchmark mapping must block benchmark fetching: {no_mapping}")
    if any(item.get("benchmark_nav") is not None for item in no_mapping.get("nav_series", [])):
        raise AssertionError("Missing mapping must never fabricate benchmark NAV")

    print("OK NAV evidence derives money-market facts and aligns only mapped real benchmarks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
