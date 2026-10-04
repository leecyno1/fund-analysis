"""目标经理与同行必须使用同一覆盖门禁；离线加载真实 service，无 DB/网络/包初始化。"""
import importlib.util
import unittest
from pathlib import Path


SERVICES = Path(__file__).resolve().parents[1] / "services"


def _load_service():
    path = SERVICES / "manager_tenure_peer_ranking_service.py"
    spec = importlib.util.spec_from_file_location("mtp_peer_ranking_offline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ManagerTenurePeerRankingService


Service = _load_service()


class FakeRepo:
    def __init__(self, summaries):
        self._summaries = summaries
        self.peer_summary_calls = 0

    def get_classification_context(self, code):
        return {
            "status": "resolved", "entity_id": "target-entity", "peer_group_id": "peer-active",
            "peer_group_name": "主动权益-测试组", "peer_group_membership_count": 7, "minimum_peer_count": 5,
        }

    def list_peer_period_nav_summaries(self, peer_group_id, start_date, end_date):
        self.peer_summary_calls += 1
        return list(self._summaries)


def _peer(code, entity, observations, last_nav):
    return {
        "entity_id": entity, "wind_code": code, "first_date": "2025-01-02", "last_date": "2025-12-31",
        "observations": observations, "first_nav": 1.0, "last_nav": last_nav,
        "record_breaking_days_ratio": 0.6, "max_drawdown": -0.1, "sharpe_ratio": 0.5,
    }


# 四个稠密同行（obs=249，覆盖达标），total_return 分别 0.5/0.4/0.2/0.1。
DENSE_PEERS = [
    _peer("PEER1.OF", "peer-1", 249, 1.5), _peer("PEER2.OF", "peer-2", 249, 1.4),
    _peer("PEER3.OF", "peer-3", 249, 1.2), _peer("PEER4.OF", "peer-4", 249, 1.1),
]


def _tenure(**over):
    tenure = {
        "fund_code": "TARGET.OF", "entity_id": "target-entity", "start_date": "2025-01-01",
        "metric_as_of_date": "2025-12-31", "metric_observations": 250, "tenure_return": 0.30,
        "annualized_return": 0.31, "record_breaking_days_ratio": 0.75, "max_drawdown": -0.15,
        "sharpe_ratio": 0.8,
    }
    tenure.update(over)
    return tenure


class TargetCoverageGateTests(unittest.TestCase):
    def rank(self, tenure, peers=DENSE_PEERS):
        return Service(FakeRepo(peers)).rank(tenure)

    def test_target_meeting_peer_gate_still_ranks(self):
        result = self.rank(_tenure())
        self.assertEqual(result["status"], "sufficient")
        self.assertEqual(result["metrics"]["total_return"]["rank"], 3)
        self.assertEqual(result["valid_peer_count"], 5)

    def test_target_below_min_observations_is_gated(self):
        result = self.rank(_tenure(metric_observations=10))
        self.assertEqual(result["status"], "target_insufficient_coverage")
        self.assertEqual(result["metrics"], {})
        self.assertEqual(result["minimum_observations"], Service.MIN_OBSERVATIONS)

    def test_target_low_observation_coverage_is_gated(self):
        # 一年任期 expected≈252，obs=100 → coverage≈0.40 < 0.80
        result = self.rank(_tenure(metric_observations=100))
        self.assertEqual(result["status"], "target_insufficient_coverage")
        self.assertLess(result["observation_coverage"], Service.MIN_OBSERVATION_COVERAGE)

    def test_missing_observations_is_not_ranked(self):
        for observations in (None, 0):
            with self.subTest(observations=observations):
                result = self.rank(_tenure(metric_observations=observations))
                self.assertEqual(result["status"], "target_insufficient_coverage")
                self.assertEqual(result["metrics"], {})

    def test_target_held_to_same_threshold_as_peers(self):
        # obs=249 达标（与同行同阈值），obs=19 低于 MIN_OBSERVATIONS 被拒
        self.assertEqual(self.rank(_tenure(metric_observations=249))["status"], "sufficient")
        self.assertEqual(self.rank(_tenure(metric_observations=19))["status"], "target_insufficient_coverage")

    def test_partial_tenure_coverage_gate_still_precedes(self):
        result = self.rank(_tenure(tenure_coverage_status="partial_since_data_start",
                                   tenure_coverage_ratio=0.48, metric_observations=10))
        self.assertEqual(result["status"], "partial_tenure_coverage")

    def test_gate_return_includes_peer_context(self):
        result = self.rank(_tenure(metric_observations=10))
        self.assertEqual(result["peer_group_id"], "peer-active")
        self.assertEqual(result["peer_group_name"], "主动权益-测试组")
        self.assertEqual(result["minimum_peer_count"], 5)
        self.assertEqual(result["expected_observations"], 252)

    def test_missing_metadata_and_sparse_nav_have_distinct_reasons(self):
        missing = self.rank(_tenure(metric_observations=None))
        sparse = self.rank(_tenure(metric_observations=10))
        self.assertEqual(missing["status"], "target_insufficient_coverage")
        self.assertEqual(sparse["status"], "target_insufficient_coverage")
        self.assertEqual(missing["highlight_reason"], "target_observation_metadata_missing")
        self.assertEqual(sparse["highlight_reason"], "target_tenure_nav_coverage_below_peer_threshold")

    def test_gate_precedes_peer_summary_sql(self):
        repo = FakeRepo(DENSE_PEERS)
        result = Service(repo).rank(_tenure(metric_observations=10))
        self.assertEqual(result["status"], "target_insufficient_coverage")
        self.assertEqual(repo.peer_summary_calls, 0)
        dense_repo = FakeRepo(DENSE_PEERS)
        Service(dense_repo).rank(_tenure())
        self.assertEqual(dense_repo.peer_summary_calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
