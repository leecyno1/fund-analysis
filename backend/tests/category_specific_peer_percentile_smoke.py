import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.peer_comparison_service import PeerComparisonService


class CategoryPeerService(PeerComparisonService):
    def __init__(self, classification: dict, metric_map: dict):
        super().__init__()
        self.classification = classification
        self.metric_map = metric_map

    def _peer_universe(self, wind_code: str):
        peers = [
            {"wind_code": code, "name": code, "type": "测试类型"}
            for code in self.metric_map
        ]
        target = next(fund for fund in peers if fund["wind_code"] == wind_code)
        target["classification"] = self.classification
        target["research_profile"] = {}
        return target, peers, "standardized_peer_group_membership"

    def _metric_map(self, wind_codes, fund_rows=None):
        return {code: self.metric_map[code] for code in wind_codes}


def _index_panel(offset: int) -> dict:
    return {
        "1y": {
            "annualized_return": 0.08 + offset * 0.01,
            "max_drawdown": -0.12,
            "sharpe_ratio": 1.0,
            "tracking_error": 0.004 + offset * 0.001,
            "excess_return": (-1 if offset % 2 else 1) * (0.001 + offset * 0.001),
        },
        "latest": {"expense_ratio": 0.003 + offset * 0.0005, "aum": 20.0 + offset * 10},
    }


def _money_panel(offset: int) -> dict:
    return {
        "1y": {
            "annualized_return": 0.016 + offset * 0.001,
            "max_drawdown": -0.0005 + offset * 0.00005,
            "sharpe_ratio": -20.0 + offset,
        },
        "latest": {
            "seven_day_annualized_yield": 0.015 + offset * 0.001,
            "benchmark_yield_spread": -0.002 + offset * 0.0005,
            "aum": 30.0 + offset * 20,
        },
    }


def main() -> int:
    index_map = {f"INDEX.{index}": _index_panel(index) for index in range(5)}
    index = CategoryPeerService(
        {
            "status": "classified",
            "evaluation_profile_key": "index_fund",
            "peer_group": "沪深300同指数",
            "primary_benchmark": "沪深300",
            "minimum_peer_count": 5,
        },
        index_map,
    ).build_peer_percentiles("INDEX.0")
    if index.get("sample_status") != "sufficient":
        raise AssertionError(f"Complete index evidence should support category percentiles: {index}")
    if set(index.get("metrics", {})) != {
        "tracking_error",
        "absolute_tracking_difference",
        "expense_ratio",
        "aum",
        "professional_score",
    }:
        raise AssertionError(f"Index peers must use tracking, cost and scale evidence: {index}")
    if "annualized_return" in index.get("metrics", {}):
        raise AssertionError(f"Index peers must not reuse active-return ranking: {index}")
    if index.get("valid_metric_peer_count") != 5:
        raise AssertionError(f"Index valid sample count must reflect metric coverage: {index}")

    money_map = {f"MONEY.{index}": _money_panel(index) for index in range(5)}
    money = CategoryPeerService(
        {
            "status": "classified",
            "evaluation_profile_key": "money_market",
            "peer_group": "货币-现金管理",
            "primary_benchmark": "DR007",
            "minimum_peer_count": 5,
        },
        money_map,
    ).build_peer_percentiles("MONEY.0")
    if money.get("sample_status") != "sufficient":
        raise AssertionError(f"Complete money-market evidence should support category percentiles: {money}")
    if "seven_day_annualized_yield" not in money.get("metrics", {}):
        raise AssertionError(f"Money-market peers must compare seven-day yield: {money}")
    if "sharpe_ratio" in money.get("metrics", {}):
        raise AssertionError(f"Money-market peers must not rank unstable Sharpe proxies: {money}")
    if money.get("peer_methodology_version") != "category_peer_percentiles_v2":
        raise AssertionError(f"Peer methodology must be versioned: {money}")

    print("OK peer percentiles use category-specific core evidence and explicit metric coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
