"""标准化基金分类数据库 Adapter。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:
    from backend.database import get_engine
except ModuleNotFoundError:
    from database import get_engine


REQUIRED_TABLES = (
    "fund_entities",
    "fund_share_classes",
    "strategy_families",
    "peer_group_members",
    "peer_groups",
    "benchmark_mappings",
)


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return {str(key): _serialize(value) for key, value in dict(row._mapping).items()}


class FundClassificationRepo:
    """从标准化实体、族谱、同类组和基准表解析基金分类上下文。"""

    def __init__(self, engine: Optional[Any] = None):
        self._engine = engine
        self._schema_ready_cache = False

    @property
    def engine(self):
        if self._engine is None:
            self._engine = get_engine()
        return self._engine

    def get_classification_context(
        self,
        fund_code: str,
        as_of_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """解析一个基金份额对应的基金实体、分类、同类组与有效基准。"""
        normalized_code = str(fund_code or "").strip()
        if not normalized_code:
            return self._unavailable("invalid_identifier", normalized_code, ["基金代码为空"])
        if not self._schema_ready():
            return self._unavailable(
                "schema_unavailable",
                normalized_code,
                ["标准化基金分类表尚未完整部署"],
            )

        from sqlalchemy import text

        evaluation_date = as_of_date or date.today()
        sql = """
            WITH selected_share AS (
                SELECT
                    fsc.wind_code AS fund_code,
                    fsc.share_class,
                    fsc.source AS share_class_source,
                    fsc.entity_id,
                    fe.canonical_code,
                    fe.canonical_name,
                    fe.strategy_family_id,
                    fe.asset_class AS entity_asset_class,
                    fe.active_passive AS entity_active_passive,
                    fe.source AS entity_source,
                    fe.source_updated_at AS entity_source_updated_at
                FROM fund_share_classes fsc
                JOIN fund_entities fe ON fe.id = fsc.entity_id
                WHERE (fsc.wind_code = :fund_code OR fe.canonical_code = :fund_code)
                  AND fsc.status = 'active'
                ORDER BY
                    CASE WHEN fsc.wind_code = :fund_code THEN 0 ELSE 1 END,
                    fsc.is_primary DESC,
                    fsc.wind_code ASC
                LIMIT 1
            )
            SELECT
                ss.fund_code,
                ss.entity_id,
                ss.canonical_code,
                ss.canonical_name,
                ss.entity_source,
                ss.entity_source_updated_at,
                ss.share_class,
                ss.share_class_source,
                sf.key AS strategy_family_key,
                sf.name AS strategy_family_name,
                COALESCE(ss.entity_asset_class, sf.asset_class) AS asset_class,
                COALESCE(ss.entity_active_passive, sf.active_passive) AS active_passive,
                sf.source AS strategy_family_source,
                peer.peer_group_id,
                peer.peer_group_key,
                peer.peer_group_name,
                peer.minimum_peer_count,
                peer.peer_group_source,
                peer.membership_role,
                peer.matched_rules,
                peer.excluded_rules,
                peer.sample_as_of_date,
                peer.membership_confidence,
                peer.membership_source,
                peer.peer_group_membership_count,
                benchmark.benchmark_code,
                benchmark.benchmark_name,
                benchmark.benchmark_type,
                benchmark.mapping_method,
                benchmark.benchmark_confidence,
                benchmark.benchmark_rationale,
                benchmark.benchmark_evidence_refs,
                benchmark.effective_from,
                benchmark.effective_to,
                benchmark.benchmark_source
            FROM selected_share ss
            LEFT JOIN strategy_families sf ON sf.id = ss.strategy_family_id
            LEFT JOIN LATERAL (
                SELECT
                    pg.id AS peer_group_id,
                    pg.key AS peer_group_key,
                    pg.name AS peer_group_name,
                    pg.minimum_peer_count,
                    pg.source AS peer_group_source,
                    pgm.role AS membership_role,
                    pgm.matched_rules,
                    pgm.excluded_rules,
                    pgm.sample_as_of_date,
                    pgm.confidence AS membership_confidence,
                    pgm.source AS membership_source,
                    COUNT(*) OVER () AS peer_group_membership_count
                FROM peer_group_members pgm
                JOIN peer_groups pg ON pg.id = pgm.peer_group_id
                WHERE pgm.entity_id = ss.entity_id
                  AND (pgm.sample_as_of_date IS NULL OR pgm.sample_as_of_date <= :as_of_date)
                ORDER BY
                    CASE pgm.role WHEN 'primary' THEN 0 WHEN 'target' THEN 1 ELSE 2 END,
                    pgm.sample_as_of_date DESC NULLS LAST,
                    pgm.confidence DESC NULLS LAST,
                    pg.updated_at DESC
                LIMIT 1
            ) peer ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    bm.benchmark_code,
                    bm.benchmark_name,
                    bm.benchmark_type,
                    bm.mapping_method,
                    bm.confidence AS benchmark_confidence,
                    bm.rationale AS benchmark_rationale,
                    bm.evidence_refs AS benchmark_evidence_refs,
                    bm.effective_from,
                    bm.effective_to,
                    bm.source AS benchmark_source
                FROM benchmark_mappings bm
                WHERE bm.entity_id = ss.entity_id
                  AND bm.status = 'active'
                  AND (bm.effective_from IS NULL OR bm.effective_from <= :as_of_date)
                  AND (bm.effective_to IS NULL OR bm.effective_to >= :as_of_date)
                ORDER BY
                    (bm.peer_group_id = peer.peer_group_id) DESC NULLS LAST,
                    bm.confidence DESC NULLS LAST,
                    bm.effective_from DESC NULLS LAST,
                    bm.updated_at DESC
                LIMIT 1
            ) benchmark ON TRUE
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text(sql),
                {"fund_code": normalized_code, "as_of_date": evaluation_date},
            ).fetchone()
        if not row:
            return self._unavailable(
                "not_found",
                normalized_code,
                ["基金代码尚未归一到 fund_entities / fund_share_classes"],
            )
        return self._build_context(_row_to_dict(row))

    def list_peer_funds(
        self,
        peer_group_id: str,
        target_wind_code: Optional[str] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """按显式同类组成员关系返回每个基金实体的代表份额。"""
        normalized_group = str(peer_group_id or "").strip()
        if not normalized_group or not self._schema_ready():
            return []

        from sqlalchemy import text

        sql = """
            SELECT *
            FROM (
                SELECT DISTINCT ON (fe.id)
                    COALESCE(f.wind_code, fsc.wind_code) AS wind_code,
                    COALESCE(f.name, fe.canonical_name) AS name,
                    COALESCE(f.type, fe.asset_class) AS type,
                    f.performance_data,
                    f.risk_metrics,
                    fe.id AS entity_id,
                    fe.canonical_code,
                    fsc.share_class
                FROM peer_group_members pgm
                JOIN peer_groups pg ON pg.id = pgm.peer_group_id
                JOIN fund_entities fe ON fe.id = pgm.entity_id
                JOIN fund_share_classes fsc ON fsc.entity_id = fe.id AND fsc.status = 'active'
                LEFT JOIN funds f ON f.id = fsc.fund_id
                WHERE pgm.peer_group_id = :peer_group_id
                  AND pgm.role <> 'excluded'
                ORDER BY
                    fe.id,
                    CASE WHEN fsc.wind_code = :target_wind_code THEN 0 ELSE 1 END,
                    fsc.is_primary DESC,
                    fsc.wind_code ASC
            ) peer_funds
            ORDER BY wind_code ASC
            LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                {
                    "peer_group_id": normalized_group,
                    "target_wind_code": str(target_wind_code or "").strip(),
                    "limit": max(1, min(int(limit), 5000)),
                },
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def _schema_ready(self) -> bool:
        if self._schema_ready_cache:
            return True

        from sqlalchemy import text

        checks = " AND ".join(
            f"to_regclass('public.{table_name}') IS NOT NULL"
            for table_name in REQUIRED_TABLES
        )
        with self.engine.connect() as conn:
            row = conn.execute(text(f"SELECT ({checks}) AS schema_ready")).fetchone()
        ready = bool(row and dict(row._mapping).get("schema_ready"))
        self._schema_ready_cache = ready
        return ready

    def _build_context(self, row: Dict[str, Any]) -> Dict[str, Any]:
        benchmark_mapping = None
        if row.get("benchmark_code"):
            benchmark_mapping = {
                "benchmark_code": row.get("benchmark_code"),
                "benchmark_name": row.get("benchmark_name"),
                "benchmark_type": row.get("benchmark_type"),
                "mapping_method": row.get("mapping_method"),
                "confidence": row.get("benchmark_confidence"),
                "rationale": row.get("benchmark_rationale"),
                "evidence_refs": row.get("benchmark_evidence_refs"),
                "effective_from": row.get("effective_from"),
                "effective_to": row.get("effective_to"),
                "source": row.get("benchmark_source"),
            }

        missing_items = []
        if not row.get("strategy_family_key"):
            missing_items.append("基金实体缺少有效策略族谱")
        if not row.get("peer_group_id"):
            missing_items.append("基金实体缺少显式同类组成员关系")
        if not benchmark_mapping:
            missing_items.append("基金实体缺少评价时点有效的基准映射")

        evidence = [
            {
                "field": "fund_entity",
                "value": row.get("canonical_code"),
                "source": "fund_entities",
                "reason": "基金实体归一结果",
                "source_record": row.get("entity_source"),
                "source_updated_at": row.get("entity_source_updated_at"),
            },
            {
                "field": "fund_share_class.wind_code",
                "value": row.get("fund_code"),
                "source": "fund_share_classes",
                "reason": "基金份额到基金实体映射",
                "source_record": row.get("share_class_source"),
            },
        ]
        if row.get("strategy_family_key"):
            evidence.append({
                "field": "strategy_family.key",
                "value": row.get("strategy_family_key"),
                "source": "strategy_families",
                "reason": "标准化策略族谱",
                "source_record": row.get("strategy_family_source"),
            })
        if row.get("peer_group_id"):
            evidence.append({
                "field": "peer_group_members.peer_group_id",
                "value": row.get("peer_group_id"),
                "source": "peer_group_members",
                "reason": "显式同类组成员关系",
                "role": row.get("membership_role"),
                "matched_rules": row.get("matched_rules"),
                "excluded_rules": row.get("excluded_rules"),
                "sample_as_of_date": row.get("sample_as_of_date"),
                "confidence": row.get("membership_confidence"),
                "source_record": row.get("membership_source"),
            })
        if benchmark_mapping:
            evidence.append({
                "field": "benchmark_mappings.benchmark_code",
                "value": benchmark_mapping.get("benchmark_code"),
                "source": "benchmark_mappings",
                "reason": benchmark_mapping.get("rationale"),
                "mapping_method": benchmark_mapping.get("mapping_method"),
                "confidence": benchmark_mapping.get("confidence"),
                "effective_from": benchmark_mapping.get("effective_from"),
                "effective_to": benchmark_mapping.get("effective_to"),
                "source_record": benchmark_mapping.get("source"),
            })

        membership_confidence = row.get("membership_confidence")
        classification_confidence = membership_confidence if membership_confidence is not None else 0.95
        return {
            "status": "resolved",
            "fund_code": row.get("fund_code"),
            "entity_id": row.get("entity_id"),
            "canonical_code": row.get("canonical_code"),
            "canonical_name": row.get("canonical_name"),
            "share_class": row.get("share_class"),
            "strategy_family_key": row.get("strategy_family_key"),
            "strategy_family_name": row.get("strategy_family_name"),
            "asset_class": row.get("asset_class"),
            "active_passive": row.get("active_passive"),
            "peer_group_id": row.get("peer_group_id"),
            "peer_group_key": row.get("peer_group_key"),
            "peer_group_name": row.get("peer_group_name"),
            "minimum_peer_count": row.get("minimum_peer_count"),
            "peer_group_membership_count": row.get("peer_group_membership_count") or 0,
            "benchmark_mapping": benchmark_mapping,
            "classification_confidence": classification_confidence,
            "classification_evidence": evidence,
            "missing_items": missing_items,
        }

    def _unavailable(self, status: str, fund_code: str, missing_items: List[str]) -> Dict[str, Any]:
        return {
            "status": status,
            "fund_code": fund_code or None,
            "classification_evidence": [],
            "missing_items": missing_items,
        }
