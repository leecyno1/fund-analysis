"""AI 报告落库的 NaN/Inf 清洗：绩效数据含零波动基金的 NaN 指标时必须仍可写入 PG jsonb。"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.reports import _json_safe, _save_report_to_postgres


def main() -> int:
    # _json_safe 必须把 NaN/Inf 递归替换为 None（PG jsonb 拒收裸 NaN token）
    dirty = {
        "annualized_volatility_2y": float("nan"),
        "sharpe_ratio": float("inf"),
        "nested": {"max_drawdown": float("-inf"), "ok": 1.5},
        "items": [float("nan"), 2.0],
    }
    cleaned = _json_safe(dirty)
    import json
    serialized = json.dumps(cleaned)  # 若残留 NaN，allow_nan 默认 True 会静默通过，需显式断言
    assert "NaN" not in serialized and "Infinity" not in serialized, serialized
    assert cleaned["annualized_volatility_2y"] is None
    assert cleaned["sharpe_ratio"] is None
    assert cleaned["nested"]["max_drawdown"] is None
    assert cleaned["nested"]["ok"] == 1.5
    assert cleaned["items"][0] is None and cleaned["items"][1] == 2.0

    # 端到端：含 NaN 指标的真实记录必须能落库并返回 UUID
    record = {
        "target_type": "fund",
        "target_id": "TEST.NAN.SMOKE",
        "report_type": "fund_nan_smoke",
        "content": "smoke: report persistence must survive NaN metrics",
        "data_sources": {"wind_code": "TEST.NAN.SMOKE", "performance": {"sharpe_ratio": float("nan")}},
        "research_reports_used": [],
        "generation_params": {"depth": "smoke"},
    }
    try:
        report_id = _save_report_to_postgres(record)
        assert report_id, "save must return a UUID for a NaN-carrying record"
    finally:
        from sqlalchemy import text
        from database import get_engine
        with get_engine().begin() as conn:
            conn.execute(
                text("DELETE FROM ai_analysis_reports WHERE target_id = :tid AND report_type = 'fund_nan_smoke'"),
                {"tid": "TEST.NAN.SMOKE"},
            )

    print("OK report persistence survives NaN/Inf metrics via json-safe cleaning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
