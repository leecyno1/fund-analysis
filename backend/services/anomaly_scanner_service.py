"""异常筛查器 (Anomaly Scanner) — 主动发现值得关注的基金变化。

扫描四类异常：
1. 规模异动：30 天内规模变化 > 30%（要求最新规模 >= 1 亿元，过滤微基金噪声）
2. 回撤异常：近 3 月回撤接近或超过近 3 年回撤（严格对齐同一 as_of_date）
3. 经理变更：manager_fund_tenures 中近 30 天的离任/上任
4. 集中度突变：前十大持仓占比季度变动 > 10pct（要求两期披露完整度可比）

设计原则：
- 只扫描主动基金（排除 ETF/指数/货币），被动代码在截断前过滤
- 每条异常带证据引用
- 扫描结果不自动触发任何操作；单类失败不再伪装成"0 异常"，scan() 输出 status/errors
"""
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from backend.database import get_engine
except ModuleNotFoundError:
    from database import get_engine

# ETF/LOF 指数代码前缀。'159' 只保留一次；主动 LOF（如 161xxx）不能被误排除。
_PASSIVE_CODE_PREFIXES = (
    '159', '510', '511', '512', '513', '515', '516', '518', '560', '561', '562', '563', '588',
)

_MIN_SCALE_AUM_YI = 1.0        # 规模异动最小规模（亿元）
_MIN_HOLDING_ROWS = 10         # 集中度比较：两期各自至少披露行数
_MIN_DISCLOSURE_RATIO = 0.5    # 集中度比较：两期披露完整度之比下限


def _is_passive_code(wind_code: str) -> bool:
    """判断是否为被动基金代码（ETF/LOF 指数类）。"""
    code = wind_code.split('.')[0] if '.' in wind_code else wind_code
    return any(code.startswith(p) for p in _PASSIVE_CODE_PREFIXES)


class AnomalyScannerService:
    def __init__(self, engine=None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            self._engine = get_engine()
        return self._engine

    def scan(self, limit: int = 50, wind_code: Optional[str] = None) -> Dict[str, Any]:
        """执行异常扫描，返回按类型分组的异常列表。

        wind_code 为空时扫全库并过滤被动基金；指定时只扫该基金（用于研究问题清单）。
        单类失败会被记录到 errors 并标记 status=partial，而不是静默返回 0 条。
        """
        filtered_code = str(wind_code or "").strip().upper() or None
        scanners = [
            ("scale_anomaly", self._scan_scale_anomaly),
            ("drawdown_anomaly", self._scan_drawdown_anomaly),
            ("manager_change", self._scan_manager_changes),
            ("concentration_change", self._scan_concentration_change),
        ]
        results: Dict[str, List[Dict[str, Any]]] = {}
        errors: Dict[str, str] = {}
        for key, scanner in scanners:
            try:
                # 多取再过滤，避免被动基金占满 LIMIT 额度而漏掉主动基金异常。
                items = scanner(limit * 3, wind_code=filtered_code)
                if filtered_code:
                    results[key] = items[:limit]
                else:
                    results[key] = [
                        item for item in items
                        if not _is_passive_code(str(item.get("wind_code") or ""))
                    ][:limit]
            except Exception as exc:
                results[key] = []
                errors[key] = f"{type(exc).__name__}: {exc}"
        total = sum(len(v) for v in results.values())
        return {
            "scan_date": date.today().isoformat(),
            "status": "ok" if not errors else "partial",
            "errors": errors,
            "total_anomalies": total,
            "by_type": {k: len(v) for k, v in results.items()},
            "anomalies": results,
        }

    def scan_fund(self, wind_code: str, limit: int = 50) -> Dict[str, Any]:
        """只扫单只基金，返回扁平异常列表（供研究问题清单使用）。"""
        code = str(wind_code or "").strip().upper()
        if not code:
            return {"status": "ok", "errors": {}, "wind_code": "", "anomalies": [], "by_type": {}}
        result = self.scan(limit=limit, wind_code=code)
        anomalies = [item for items in result["anomalies"].values() for item in items]
        return {
            "status": result["status"],
            "errors": result["errors"],
            "wind_code": code,
            "anomalies": anomalies,
            "by_type": result["by_type"],
        }

    def _scan_scale_anomaly(self, limit: int, wind_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """规模异动：最新 AUM 与上一可比快照差异 > 30%（AUM 单位为亿元）。

        AUM 来自季度净资产，逐日快照常为同一季度值；因此取"至少 20 天前、400 天内"
        的最近一次快照作为对比基准，并按季度节奏工作，同时输出实际对比日期。
        """
        from sqlalchemy import text
        code_clause = "" if wind_code is None else " AND target_id = :wind_code"
        code_clause_m = "" if wind_code is None else " AND m.target_id = :wind_code"
        sql = text(f"""
            WITH ranked AS (
                SELECT target_id AS wind_code, metric_value, as_of_date,
                       ROW_NUMBER() OVER (PARTITION BY target_id ORDER BY as_of_date DESC) AS rn
                FROM metric_snapshots
                WHERE target_type = 'fund' AND metric_name = 'aum' AND metric_window = 'latest'{code_clause}
            ),
            latest AS MATERIALIZED (
                SELECT wind_code, metric_value AS aum_now, as_of_date AS now_date
                FROM ranked WHERE rn = 1
            ),
            prev AS MATERIALIZED (
                SELECT wind_code, aum_prev, prev_date FROM (
                    SELECT m.target_id AS wind_code, m.metric_value AS aum_prev, m.as_of_date AS prev_date,
                           ROW_NUMBER() OVER (PARTITION BY m.target_id ORDER BY m.as_of_date DESC) AS rn
                    FROM metric_snapshots m
                    JOIN latest l ON l.wind_code = m.target_id AND m.metric_value <> l.aum_now
                    WHERE m.target_type = 'fund' AND m.metric_name = 'aum' AND m.metric_window = 'latest'
                      AND m.as_of_date <= CURRENT_DATE - INTERVAL '20 days'
                      AND m.as_of_date >= CURRENT_DATE - INTERVAL '400 days'{code_clause_m}
                ) t WHERE rn = 1
            )
            SELECT l.wind_code, l.aum_now, p.aum_prev, l.now_date, p.prev_date,
                   ROUND(((l.aum_now - p.aum_prev) / NULLIF(p.aum_prev, 0)) * 100, 1) AS change_pct
            FROM latest l JOIN prev p ON l.wind_code = p.wind_code
            WHERE p.aum_prev > 0 AND l.aum_now >= :min_aum_yi AND p.aum_prev >= :min_aum_yi
              AND ABS(l.aum_now - p.aum_prev) >= :min_aum_yi
              AND ABS((l.aum_now - p.aum_prev) / p.aum_prev) > 0.30
            ORDER BY ABS((l.aum_now - p.aum_prev) / p.aum_prev) DESC, l.wind_code
            LIMIT :limit
        """)
        params = {"limit": limit, "min_aum_yi": _MIN_SCALE_AUM_YI}
        if wind_code is not None:
            params["wind_code"] = wind_code
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {"type": "scale_anomaly", "wind_code": str(r[0]),
             "aum_now": float(r[1]) if r[1] else None,
             "aum_prev": float(r[2]) if r[2] else None,
             "as_of_date": str(r[3]) if r[3] else None,
             "prev_date": str(r[4]) if r[4] else None,
             "change_pct": float(r[5]) if r[5] else None,
             "description": (
                 f"规模较 {r[4]} 变动 {float(r[5]):+.1f}%"
                 f"（{float(r[2]):.2f} → {float(r[1]):.2f} 亿元）"
             )}
            for r in rows
        ]

    def _scan_drawdown_anomaly(self, limit: int, wind_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """回撤异常：近 3 月回撤 >= 近 3 年回撤的 80%（对齐同一 as_of_date）。"""
        from sqlalchemy import text
        code_clause = "" if wind_code is None else " AND target_id = :wind_code"
        sql = text(f"""
            WITH dd_3m AS (
                SELECT target_id AS wind_code, as_of_date, metric_value AS dd_3m FROM (
                    SELECT target_id, as_of_date, metric_value,
                           ROW_NUMBER() OVER (PARTITION BY target_id ORDER BY as_of_date DESC) AS rn
                    FROM metric_snapshots
                    WHERE target_type='fund' AND metric_name='max_drawdown' AND metric_window='3m' AND metric_value < 0{code_clause}
                ) t WHERE rn = 1
            ),
            dd_3y AS (
                SELECT target_id AS wind_code, as_of_date, metric_value AS dd_3y FROM (
                    SELECT target_id, as_of_date, metric_value,
                           ROW_NUMBER() OVER (PARTITION BY target_id ORDER BY as_of_date DESC) AS rn
                    FROM metric_snapshots
                    WHERE target_type='fund' AND metric_name='max_drawdown' AND metric_window='3y' AND metric_value < 0{code_clause}
                ) t WHERE rn = 1
            )
            SELECT d3.wind_code, d3.dd_3m, d3y.dd_3y,
                   ROUND((d3.dd_3m / NULLIF(d3y.dd_3y, 0)) * 100, 1) AS ratio_pct
            FROM dd_3m d3
            JOIN dd_3y d3y ON d3.wind_code = d3y.wind_code AND d3.as_of_date = d3y.as_of_date
            WHERE d3y.dd_3y < 0 AND (d3.dd_3m / d3y.dd_3y) >= 0.80
              AND d3.dd_3m < -0.05
            ORDER BY (d3.dd_3m / d3y.dd_3y) DESC, ABS(d3.dd_3m) DESC, d3.wind_code
            LIMIT :limit
        """)
        params = {"limit": limit}
        if wind_code is not None:
            params["wind_code"] = wind_code
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {"type": "drawdown_anomaly", "wind_code": str(r[0]),
             "dd_3m": float(r[1]) if r[1] else None,
             "dd_3y": float(r[2]) if r[2] else None,
             "ratio_pct": float(r[3]) if r[3] else None,
             "description": f"近3月回撤 {float(r[1])*100:.1f}% 已达近3年的 {float(r[3]):.0f}%"}
            for r in rows
        ]

    def _scan_manager_changes(self, limit: int, wind_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """经理变更：近 30 天的离任/上任（来源 manager_fund_tenures）。"""
        from sqlalchemy import text
        code_clause = "" if wind_code is None else " AND fund_code = :wind_code"
        sql = text(f"""
            WITH changes AS (
                SELECT fund_code AS wind_code, 'manager_removed' AS change_type,
                       manager_id, end_date AS changed_at
                FROM manager_fund_tenures
                WHERE end_date BETWEEN CURRENT_DATE - INTERVAL '30 days' AND CURRENT_DATE{code_clause}
                UNION ALL
                SELECT fund_code, 'manager_added', manager_id, start_date
                FROM manager_fund_tenures
                WHERE start_date >= CURRENT_DATE - INTERVAL '30 days' AND start_date <= CURRENT_DATE{code_clause}
            )
            SELECT wind_code, change_type, manager_id, changed_at
            FROM changes
            WHERE wind_code IS NOT NULL AND wind_code <> ''
            ORDER BY changed_at DESC, wind_code, manager_id
            LIMIT :limit
        """)
        params = {"limit": limit}
        if wind_code is not None:
            params["wind_code"] = wind_code
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        items = []
        for r in rows:
            name = str(r[2] or "").split("|")[0]
            action = "离任" if str(r[1]) == "manager_removed" else "上任"
            items.append({
                "type": "manager_change",
                "wind_code": str(r[0]),
                "change_type": str(r[1]),
                "manager_name": name,
                "changed_at": str(r[3]) if r[3] else None,
                "description": f"经理变更：{name} {action}（{r[3]}）",
            })
        return items

    def _scan_concentration_change(self, limit: int, wind_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """集中度突变：前十大占比季度变动 > 10pct。

        仅比较 weight_basis='fund_nav'；两期披露行数均 >= 10 且完整度之比 >= 0.5，
        避免"仅披露前十大 vs 全量披露"造成的假突变。
        """
        from sqlalchemy import text
        code_clause = "" if wind_code is None else " AND wind_code = :wind_code"
        sql = text(f"""
            WITH ranked AS (
                SELECT wind_code, quarter, weight,
                       ROW_NUMBER() OVER (PARTITION BY wind_code, quarter ORDER BY weight DESC) AS rn,
                       COUNT(*) OVER (PARTITION BY wind_code, quarter) AS total_rows
                FROM holdings
                WHERE weight_basis = 'fund_nav' AND weight IS NOT NULL AND weight > 0{code_clause}
            ),
            quarterly_top10 AS (
                SELECT wind_code, quarter, SUM(weight) AS top10_weight, MAX(total_rows) AS total_rows
                FROM ranked WHERE rn <= 10
                GROUP BY wind_code, quarter
            ),
            q_list AS (SELECT DISTINCT quarter FROM quarterly_top10 ORDER BY quarter DESC LIMIT 2),
            q_latest AS (SELECT quarter FROM q_list ORDER BY quarter DESC LIMIT 1),
            q_prev AS (SELECT quarter FROM q_list ORDER BY quarter ASC LIMIT 1)
            SELECT l.wind_code, l.top10_weight AS latest_w, p.top10_weight AS prev_w,
                   ROUND((l.top10_weight - p.top10_weight) * 100, 1) AS change_pct,
                   l.total_rows AS latest_rows, p.total_rows AS prev_rows
            FROM quarterly_top10 l
            JOIN quarterly_top10 p ON l.wind_code = p.wind_code
            JOIN q_latest ql ON l.quarter = ql.quarter
            JOIN q_prev qp ON p.quarter = qp.quarter
            WHERE ABS(l.top10_weight - p.top10_weight) > 0.10
              AND l.total_rows >= :min_rows AND p.total_rows >= :min_rows
              AND LEAST(l.total_rows, p.total_rows)::numeric / GREATEST(l.total_rows, p.total_rows) >= :min_ratio
            ORDER BY ABS(l.top10_weight - p.top10_weight) DESC, l.wind_code
            LIMIT :limit
        """)
        params = {
            "limit": limit,
            "min_rows": _MIN_HOLDING_ROWS,
            "min_ratio": _MIN_DISCLOSURE_RATIO,
        }
        if wind_code is not None:
            params["wind_code"] = wind_code
        with self.engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {"type": "concentration_change", "wind_code": str(r[0]),
             "latest_weight": float(r[1]) if r[1] else None,
             "prev_weight": float(r[2]) if r[2] else None,
             "change_pct": float(r[3]) if r[3] else None,
             "latest_rows": int(r[4]) if r[4] else None,
             "prev_rows": int(r[5]) if r[5] else None,
             "description": f"前十大集中度变动 {float(r[3]):+.1f}pct"}
            for r in rows
        ]
