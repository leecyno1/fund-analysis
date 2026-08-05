import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fund_recommendation_service import FundRecommendationService


class FakeClassificationRepo:
    def __init__(self, rows):
        self.rows = rows
        self.requested_limit = None

    def list_recommendation_funds(self, peer_group, limit=50, keyword=None):
        self.requested_limit = limit
        return list(self.rows)

    def count_recommendation_funds(self, peer_group, keyword=None):
        return len(self.rows)


class FakeMetricRepo:
    def __init__(self, panels):
        self.panels = panels

    def get_latest_panels(self, target_type, target_ids):
        assert target_type == "fund"
        return {code: list(self.panels.get(code, [])) for code in target_ids}


class FakeProfileRepo:
    def __init__(self, profiles):
        self.profiles = profiles

    def list_profiles(self, wind_codes):
        return {code: dict(self.profiles.get(code, {})) for code in wind_codes}


def _panel(index):
    values = {
        "tracking_error": 0.002 + index * 0.0001,
        "tracking_difference": 0.001 + index * 0.00005,
        "expense_ratio": 0.002 + index * 0.00002,
        "aum": 200.0 - index,
    }
    return [
        {
            "metric_window": "1y" if name in {"tracking_error", "tracking_difference"} else "latest",
            "metric_name": name,
            "metric_value": value,
            "as_of_date": "2026-08-04",
        }
        for name, value in values.items()
    ]


def _row(index, peer_group="指数-沪深300"):
    code = f"{index:06d}.OF"
    return {
        "id": code,
        "wind_code": code,
        "name": f"测试沪深300基金{index}",
        "type": "指数型",
        "nav": 1.0 + index / 100,
        "nav_date": "2026-08-04",
        "total_asset": 200.0 - index,
        "establishment_date": "2018-01-01",
        "performance_data": {"tracking_difference": 0.001 + index * 0.00005},
        "risk_metrics": {"tracking_error": 0.002 + index * 0.0001},
        "raw_data": {"info": {"management_fee": 0.15, "custodian_fee": 0.05}},
        "standardized_peer_group_id": "peer-index-hs300" if peer_group == "指数-沪深300" else "peer-index-csi500",
        "standardized_peer_group_key": "peer-index-hs300" if peer_group == "指数-沪深300" else "peer-index-csi500",
        "standardized_peer_group_name": peer_group,
        "strategy_family_key": "index_broad",
        "asset_class": "index",
        "active_passive": "passive",
        "minimum_peer_count": 5,
        "benchmark_code": "000300.SH",
        "benchmark_name": "沪深300",
    }


def main() -> int:
    rows = [_row(index) for index in range(35)]
    rows.append(_row(99, peer_group="指数-中证500"))
    panels = {row["wind_code"]: _panel(index) for index, row in enumerate(rows)}
    panels["000005.OF"] = [
        item for item in panels["000005.OF"] if item["metric_name"] != "tracking_error"
    ]
    rows[5]["risk_metrics"] = {}
    profiles = {
        row["wind_code"]: {
            "peer_group": row["standardized_peer_group_name"],
            "primary_benchmark": row["benchmark_name"],
            "style_label": "大盘成长" if index < 12 else "价值",
            "strategy_tags": ["成长"] if index < 12 else ["价值"],
        }
        for index, row in enumerate(rows)
    }
    profiles["000005.OF"]["style_label"] = "仅缺证基金拥有的风格"
    profiles["000005.OF"]["strategy_tags"] = ["仅缺证风格"]

    classification_repo = FakeClassificationRepo(rows)
    service = FundRecommendationService(
        classification_repo=classification_repo,
        metric_repo=FakeMetricRepo(panels),
        profile_repo=FakeProfileRepo(profiles),
    )
    result = service.build_candidate_group("指数-沪深300", style="成长", limit=50)

    candidates = result.get("candidates") or []
    if classification_repo.requested_limit < 35:
        raise AssertionError(f"Recommendation service truncated the peer universe: {classification_repo.requested_limit}")
    if len(candidates) != 10:
        raise AssertionError(f"Candidate group must be capped at ten funds: {result}")
    if result.get("peer_universe_count") != 35:
        raise AssertionError(f"Only the exact requested peer group may be counted: {result}")
    if result.get("evidence_eligible_count") != 34:
        raise AssertionError(f"Funds missing required category evidence must be excluded: {result}")
    if result.get("style_matched_count") != 11:
        raise AssertionError(f"Style filtering must run across the full eligible peer group: {result}")
    if "仅缺证基金拥有的风格" in (result.get("available_styles") or []):
        raise AssertionError(f"Style options must only come from evidence-eligible funds: {result}")
    if any(item.get("research_profile", {}).get("peer_group") != "指数-沪深300" for item in candidates):
        raise AssertionError(f"Cross-category fund leaked into candidate group: {result}")
    if any("成长" not in " ".join(item.get("research_profile", {}).get("strategy_tags") or []) for item in candidates):
        raise AssertionError(f"Selected style must be backed by profile tags: {result}")
    if any(item.get("wind_code") == "000005.OF" for item in candidates):
        raise AssertionError(f"Fund with missing tracking evidence entered candidates: {result}")

    scores = [item["professional_scoring"]["overall_score"] for item in candidates]
    if scores != sorted(scores, reverse=True):
        raise AssertionError(f"Candidates must be ordered by category-specific score: {scores}")
    for item in candidates:
        evidence = item.get("recommendation_evidence") or {}
        if not evidence.get("reasons") or not evidence.get("risks"):
            raise AssertionError(f"Every candidate needs plain-language reasons and risks: {item}")
        if evidence.get("data_as_of") != "2026-08-04":
            raise AssertionError(f"Candidate evidence needs an auditable data date: {item}")
        if evidence.get("methodology_version") != "fund_candidate_group_v1":
            raise AssertionError(f"Candidate method must be versioned: {item}")
        percentile = (item.get("peer_percentiles") or {}).get("metrics", {}).get("professional_score", {}).get("percentile")
        if percentile is None:
            raise AssertionError(f"Category score percentile is missing: {item}")

    if result.get("limit") != 10 or result.get("returned") != 10:
        raise AssertionError(f"Public candidate group contract must enforce the ten-fund cap: {result}")
    if result.get("source") != "full_peer_group_category_evaluation":
        raise AssertionError(f"Candidate source must disclose full peer-group evaluation: {result}")
    if any(key in result for key in ["purchase_amount", "suitability", "position", "trade_action"]):
        raise AssertionError(f"Candidate group leaked out-of-scope decision fields: {result}")

    print("OK recommendation service scans the full peer group and returns at most ten evidence-backed style candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
