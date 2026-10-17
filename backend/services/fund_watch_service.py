"""观察项 (Fund Watches) — 任意基金+任意指标+阈值+夜扫。

用户可对任何一只基金的任何指标设置观察条件，例如：
- "如果 XX 基金规模突破 200 亿告诉我"  → metric_field=total_asset, operator=>=, threshold=200e8
- "如果 XX 基金最大回撤突破 -20% 告诉我" → metric_field=max_drawdown, operator=<=, threshold=-0.20
- "如果 XX 基金前十大集中度超过 70% 告诉我" → metric_field=top_ten_weight, operator=>=, threshold=0.70

夜扫逻辑由 /api/watches/scan 触发（可接入 scheduled_update.sh）。
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from backend.database import get_engine
except ModuleNotFoundError:
    from database import get_engine


VALID_OPERATORS = {">=", "<=", ">", "<", "=="}


# 支持的指标字段必须与 _get_current_value 的分支一致，否则会造出"永远静默"的 watch。
SUPPORTED_METRIC_FIELDS = {
    "total_asset",
    "max_drawdown",
    "annualized_return",
    "annualized_volatility",
    "sharpe_ratio",
    "institution_ratio",
    "top_ten_weight",
}


class FundWatchService:
    def __init__(self, engine=None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            self._engine = get_engine()
        return self._engine

    # ─── CRUD ───

    def list_watches(self, status: Optional[str] = None, fund_wind_code: Optional[str] = None) -> List[Dict[str, Any]]:
        from sqlalchemy import text
        where = []
        params: Dict[str, Any] = {}
        if status:
            where.append("status = :status")
            params["status"] = status
        if fund_wind_code:
            where.append("fund_wind_code = :wind_code")
            params["wind_code"] = fund_wind_code
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        sql = text(f"SELECT * FROM fund_watches{where_sql} ORDER BY created_at DESC")
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    def create_watch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from sqlalchemy import text
        wind_code = str(payload.get("fund_wind_code") or "").strip()
        metric_field = str(payload.get("metric_field") or "").strip()
        operator = str(payload.get("operator") or ">=").strip()
        threshold = payload.get("threshold")
        if not wind_code or not metric_field or threshold is None:
            raise ValueError("fund_wind_code, metric_field and threshold are required")
        if metric_field not in SUPPORTED_METRIC_FIELDS:
            raise ValueError(f"metric_field must be one of {sorted(SUPPORTED_METRIC_FIELDS)}")
        if operator not in VALID_OPERATORS:
            raise ValueError(f"operator must be one of {sorted(VALID_OPERATORS)}")
        threshold = self._normalize_threshold(metric_field, threshold)

        watch_id = str(uuid.uuid4())
        sql = text("""
            INSERT INTO fund_watches (id, fund_wind_code, metric_field, operator, threshold, note, status)
            VALUES (CAST(:id AS UUID), :wind_code, :metric_field, :operator, :threshold, :note, 'active')
        """)
        with self.engine.begin() as conn:
            conn.execute(sql, {
                "id": watch_id, "wind_code": wind_code, "metric_field": metric_field,
                "operator": operator, "threshold": float(threshold),
                "note": payload.get("note"),
            })
        return self.get_watch(watch_id) or {}

    def get_watch(self, watch_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM fund_watches WHERE id = CAST(:id AS UUID)"), {"id": watch_id}
            ).fetchone()
        return self._row(row) if row else None

    def update_status(self, watch_id: str, status: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text
        if status not in ("active", "triggered", "dismissed"):
            raise ValueError("invalid status")
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE fund_watches SET status = CAST(:status AS \"WatchStatus\"), updated_at = NOW() WHERE id = CAST(:id AS UUID)"),
                {"id": watch_id, "status": status},
            )
        return self.get_watch(watch_id)

    def delete_watch(self, watch_id: str) -> bool:
        from sqlalchemy import text
        with self.engine.begin() as conn:
            result = conn.execute(text("DELETE FROM fund_watches WHERE id = CAST(:id AS UUID)"), {"id": watch_id})
        return result.rowcount > 0

    # ─── 夜扫 ───

    def scan(self) -> Dict[str, Any]:
        """扫描所有 active 观察项，检查是否触发阈值。"""
        from sqlalchemy import text

        watches = self.list_watches(status="active")
        triggered: List[Dict[str, Any]] = []
        unevaluated: List[Dict[str, Any]] = []
        evaluated = 0

        for watch in watches:
            raw_value = self._get_current_value(watch["fund_wind_code"], watch["metric_field"])
            current_value = self._comparable_value(watch["metric_field"], raw_value)
            if current_value is None:
                unevaluated.append({
                    "id": watch["id"],
                    "fund_wind_code": watch["fund_wind_code"],
                    "metric_field": watch["metric_field"],
                    "reason": "unsupported_metric" if watch["metric_field"] not in SUPPORTED_METRIC_FIELDS else "metric_unavailable",
                })
                continue
            evaluated += 1
            if self._check_threshold(current_value, watch["operator"], watch["threshold"]):
                # 标记为 triggered
                with self.engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE fund_watches
                            SET status = 'triggered', triggered_at = NOW(), triggered_value = :val, updated_at = NOW()
                            WHERE id = CAST(:id AS UUID)
                        """),
                        {"id": watch["id"], "val": current_value},
                    )
                watch["triggered_value"] = current_value
                watch["status"] = "triggered"
                triggered.append(watch)

        return {
            "scanned_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "active_watches": len(watches),
            "evaluated_count": evaluated,
            "unevaluated_count": len(unevaluated),
            "unevaluated": unevaluated,
            "triggered_count": len(triggered),
            "triggered": triggered,
        }

    def _get_current_value(self, wind_code: str, metric_field: str) -> Optional[float]:
        """从数据库获取基金当前指标值。"""
        from sqlalchemy import text

        if metric_field == "total_asset":
            sql = text("SELECT total_asset FROM funds WHERE wind_code = :wc")
        elif metric_field in ("max_drawdown", "annualized_return", "annualized_volatility", "sharpe_ratio"):
            window = "1y"
            sql = text("""
                SELECT metric_value FROM metric_snapshots
                WHERE target_type='fund' AND target_id=:wc AND metric_name=:mn AND metric_window=:w
                ORDER BY as_of_date DESC LIMIT 1
            """)
            with self.engine.connect() as conn:
                row = conn.execute(sql, {"wc": wind_code, "mn": metric_field, "w": window}).fetchone()
            return float(row[0]) if row and row[0] is not None else None
        elif metric_field == "institution_ratio":
            sql = text("""
                SELECT institution_ratio FROM fund_holder_structures
                WHERE wind_code = :wc ORDER BY report_date DESC LIMIT 1
            """)
        elif metric_field == "top_ten_weight":
            sql = text("""
                SELECT SUM(weight) FROM (
                    SELECT weight FROM holdings WHERE wind_code = :wc AND quarter = (
                        SELECT MAX(quarter) FROM holdings WHERE wind_code = :wc
                    ) ORDER BY weight DESC LIMIT 10
                ) t
            """)
        else:
            return None

        try:
            with self.engine.connect() as conn:
                row = conn.execute(sql, {"wc": wind_code}).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        except Exception:
            pass
        return None

    @staticmethod
    def _normalize_threshold(metric_field: str, threshold: Any) -> float:
        """total_asset 阈值统一为元。

        funds.total_asset 以亿元存储，前端 formatThreshold 按 value/1e8 显示"亿"，
        故规范比较单位是元。历史/手工输入若小于 1e6（如 200），视为亿元并换算。
        """
        value = float(threshold)
        if metric_field == "total_asset" and 0 < value < 1_000_000:
            return value * 1e8
        return value

    @staticmethod
    def _comparable_value(metric_field: str, raw_value: Any) -> Optional[float]:
        if raw_value is None:
            return None
        value = float(raw_value)
        if metric_field == "total_asset":
            return value * 1e8  # 亿元 → 元
        return value

    @staticmethod
    def _check_threshold(value: float, operator: str, threshold: float) -> bool:
        if operator == ">=":
            return value >= threshold
        if operator == "<=":
            return value <= threshold
        if operator == ">":
            return value > threshold
        if operator == "<":
            return value < threshold
        if operator == "==":
            return abs(value - threshold) < 1e-9
        return False

    @staticmethod
    def _row(row) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        d = dict(row._mapping)
        d["id"] = str(d.get("id") or "")
        for tf in ("created_at", "updated_at", "triggered_at"):
            v = d.get(tf)
            if hasattr(v, "isoformat"):
                d[tf] = v.isoformat()
        return d
