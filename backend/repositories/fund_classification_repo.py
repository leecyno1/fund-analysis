"""标准化基金分类数据库 Adapter。"""
import hashlib
import json
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
                    (
                        SELECT COUNT(*)
                        FROM peer_group_members group_member
                        WHERE group_member.peer_group_id = pg.id
                          AND group_member.role <> 'excluded'
                    ) AS peer_group_membership_count
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
                    f.total_asset,
                    f.performance_data,
                    f.risk_metrics,
                    f.raw_data,
                    fe.id AS entity_id,
                    fe.canonical_code,
                    fsc.share_class
                FROM peer_group_members pgm
                JOIN peer_groups pg ON pg.id = pgm.peer_group_id
                JOIN fund_entities fe ON fe.id = pgm.entity_id
                JOIN fund_share_classes fsc ON fsc.entity_id = fe.id AND fsc.status = 'active'
                LEFT JOIN funds f ON f.wind_code = fsc.wind_code
                WHERE pgm.peer_group_id = :peer_group_id
                  AND pgm.role <> 'excluded'
                  AND fe.lifecycle_stage = 'active'
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

    def list_peer_group_inventory(self, limit: int = 100) -> List[Dict[str, Any]]:
        """返回标准化同类组清单，供分类内评价和推荐入口使用。"""
        if not self._schema_ready():
            return []

        from sqlalchemy import text

        sql = """
            SELECT
                pg.id,
                pg.key,
                pg.name,
                pg.minimum_peer_count,
                COUNT(DISTINCT pgm.entity_id) FILTER (WHERE pgm.role <> 'excluded')::int AS fund_count
            FROM peer_groups pg
            LEFT JOIN peer_group_members pgm ON pgm.peer_group_id = pg.id
            GROUP BY pg.id, pg.key, pg.name, pg.minimum_peer_count
            HAVING COUNT(DISTINCT pgm.entity_id) FILTER (WHERE pgm.role <> 'excluded') >= pg.minimum_peer_count
            ORDER BY fund_count DESC, pg.name ASC
            LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"limit": max(1, min(int(limit), 200))}).fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_fund_peer_group_map(self, wind_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量返回基金份额的标准同类组，避免列表页逐只查询分类上下文。"""
        normalized_codes = list(dict.fromkeys(
            str(code or "").strip() for code in wind_codes if str(code or "").strip()
        ))
        if not normalized_codes or not self._schema_ready():
            return {}

        from sqlalchemy import text

        sql = """
            SELECT DISTINCT ON (fsc.wind_code)
                fsc.wind_code,
                pg.id AS peer_group_id,
                pg.key AS peer_group_key,
                pg.name AS peer_group_name,
                pg.minimum_peer_count,
                pgm.confidence,
                pgm.source,
                pgm.sample_as_of_date
            FROM fund_share_classes fsc
            JOIN fund_entities fe ON fe.id = fsc.entity_id
            LEFT JOIN peer_group_members pgm
              ON pgm.entity_id = fe.id
             AND pgm.role <> 'excluded'
            LEFT JOIN peer_groups pg ON pg.id = pgm.peer_group_id
            WHERE fsc.status = 'active'
              AND fsc.wind_code = ANY(:wind_codes)
            ORDER BY
                fsc.wind_code,
                CASE pgm.role WHEN 'primary' THEN 0 WHEN 'target' THEN 1 ELSE 2 END,
                pgm.sample_as_of_date DESC NULLS LAST,
                pgm.confidence DESC NULLS LAST,
                pg.updated_at DESC NULLS LAST
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {"wind_codes": normalized_codes}).fetchall()
        return {
            row["wind_code"]: row
            for item in rows
            if (row := _row_to_dict(item)).get("wind_code") and row.get("peer_group_id")
        }

    def list_recommendation_funds(
        self,
        peer_group: str,
        limit: int = 50,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按标准化同类组返回每个基金实体的代表份额及完整基础数据。"""
        normalized_group = str(peer_group or "").strip()
        if not normalized_group or not self._schema_ready():
            return []

        from sqlalchemy import text

        sql = """
            SELECT *
            FROM (
                SELECT DISTINCT ON (fe.id)
                    f.*,
                    fe.id AS entity_id,
                    fe.canonical_code,
                    fe.canonical_name,
                    sf.key AS strategy_family_key,
                    sf.name AS strategy_family_name,
                    COALESCE(fe.asset_class, sf.asset_class) AS asset_class,
                    COALESCE(fe.active_passive, sf.active_passive) AS active_passive,
                    pg.id AS standardized_peer_group_id,
                    pg.key AS standardized_peer_group_key,
                    pg.name AS standardized_peer_group_name,
                    pg.minimum_peer_count,
                    pg.benchmark_code,
                    pg.benchmark_name
                FROM peer_groups pg
                JOIN peer_group_members pgm ON pgm.peer_group_id = pg.id
                JOIN fund_entities fe ON fe.id = pgm.entity_id
                LEFT JOIN strategy_families sf ON sf.id = fe.strategy_family_id
                JOIN fund_share_classes fsc ON fsc.entity_id = fe.id AND fsc.status = 'active'
                JOIN funds f ON f.wind_code = fsc.wind_code
                WHERE (pg.name = :peer_group OR pg.key = :peer_group)
                  AND pgm.role <> 'excluded'
                  AND fe.lifecycle_stage = 'active'
                  AND (
                    :keyword = ''
                    OR f.name ILIKE :keyword_pattern
                    OR f.wind_code ILIKE :keyword_pattern
                  )
                ORDER BY
                    fe.id,
                    fsc.is_primary DESC,
                    CASE WHEN f.performance_data IS NULL OR f.performance_data = '{}'::jsonb THEN 1 ELSE 0 END,
                    CASE WHEN f.risk_metrics IS NULL OR f.risk_metrics = '{}'::jsonb THEN 1 ELSE 0 END,
                    f.nav_date DESC NULLS LAST,
                    fsc.wind_code ASC
            ) peer_funds
            ORDER BY
                CASE WHEN performance_data IS NULL OR performance_data = '{}'::jsonb THEN 1 ELSE 0 END,
                CASE WHEN risk_metrics IS NULL OR risk_metrics = '{}'::jsonb THEN 1 ELSE 0 END,
                nav_date DESC NULLS LAST,
                wind_code ASC
            LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(sql),
                {
                    "peer_group": normalized_group,
                    "keyword": str(keyword or "").strip(),
                    "keyword_pattern": f"%{str(keyword or '').strip()}%",
                    "limit": max(1, min(int(limit), 2000)),
                },
            ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def count_recommendation_funds(self, peer_group: str, keyword: Optional[str] = None) -> int:
        """统计同类组可浏览的基金实体数，与候选列表使用相同过滤口径。"""
        normalized_group = str(peer_group or "").strip()
        if not normalized_group or not self._schema_ready():
            return 0

        from sqlalchemy import text

        sql = """
            SELECT COUNT(DISTINCT fe.id)::int AS fund_count
            FROM peer_groups pg
            JOIN peer_group_members pgm ON pgm.peer_group_id = pg.id
            JOIN fund_entities fe ON fe.id = pgm.entity_id
            JOIN fund_share_classes fsc ON fsc.entity_id = fe.id AND fsc.status = 'active'
            JOIN funds f ON f.wind_code = fsc.wind_code
            WHERE (pg.name = :peer_group OR pg.key = :peer_group)
              AND pgm.role <> 'excluded'
              AND fe.lifecycle_stage = 'active'
              AND (
                :keyword = ''
                OR f.name ILIKE :keyword_pattern
                OR f.wind_code ILIKE :keyword_pattern
              )
        """
        normalized_keyword = str(keyword or "").strip()
        with self.engine.connect() as conn:
            value = conn.execute(text(sql), {
                "peer_group": normalized_group,
                "keyword": normalized_keyword,
                "keyword_pattern": f"%{normalized_keyword}%",
            }).scalar()
        return int(value or 0)

    def ensure_catalog(
        self,
        strategy_families: List[Dict[str, Any]],
        peer_groups: List[Dict[str, Any]],
        source: str,
    ) -> Dict[str, Any]:
        """幂等初始化正式分类目录，不写入演示基金。"""
        if not self._schema_ready():
            raise RuntimeError("标准化基金分类表尚未完整部署")

        from sqlalchemy import text

        with self.engine.begin() as conn:
            for family in strategy_families:
                benchmark_policy = family.get("benchmark_policy") or {
                    "catalogVersion": source,
                    "rule": "explicit_benchmark_mapping_required",
                }
                peer_policy = family.get("peer_policy") or {
                    "catalogVersion": source,
                    "rule": "same_strategy_and_benchmark_only",
                }
                conn.execute(text("""
                    INSERT INTO strategy_families (
                        id, key, name, asset_class, active_passive, style_tags,
                        benchmark_policy, peer_policy, source, updated_at
                    ) VALUES (
                        :id, :key, :name, :asset_class, :active_passive, :style_tags,
                        CAST(:benchmark_policy AS jsonb), CAST(:peer_policy AS jsonb), :source, NOW()
                    )
                    ON CONFLICT (key) DO UPDATE SET
                        name = EXCLUDED.name,
                        asset_class = EXCLUDED.asset_class,
                        active_passive = EXCLUDED.active_passive,
                        style_tags = EXCLUDED.style_tags,
                        benchmark_policy = EXCLUDED.benchmark_policy,
                        peer_policy = EXCLUDED.peer_policy,
                        source = EXCLUDED.source,
                        updated_at = NOW()
                """), {
                    "id": family.get("id"),
                    "key": family.get("key"),
                    "name": family.get("name"),
                    "asset_class": family.get("asset_class"),
                    "active_passive": family.get("active_passive"),
                    "style_tags": family.get("style_tags") or [],
                    "benchmark_policy": json.dumps(benchmark_policy, ensure_ascii=False),
                    "peer_policy": json.dumps(peer_policy, ensure_ascii=False),
                    "source": source,
                })

            for peer_group in peer_groups:
                strategy = conn.execute(text("""
                    SELECT id, asset_class, active_passive
                    FROM strategy_families
                    WHERE key = :strategy_family_key
                    LIMIT 1
                """), {
                    "strategy_family_key": peer_group.get("strategy_family_key"),
                }).fetchone()
                if not strategy:
                    raise ValueError("catalog_strategy_family_missing")
                strategy_row = dict(strategy._mapping)
                if strategy_row.get("asset_class") != peer_group.get("asset_class"):
                    raise ValueError("catalog_peer_asset_class_conflict")
                if strategy_row.get("active_passive") != peer_group.get("active_passive"):
                    raise ValueError("catalog_peer_active_passive_conflict")

                conn.execute(text("""
                    INSERT INTO peer_groups (
                        id, key, name, strategy_family_id, asset_class, active_passive,
                        benchmark_code, benchmark_name, inclusion_rules, exclusion_rules,
                        minimum_peer_count, source, source_updated_at, updated_at
                    ) VALUES (
                        :id, :key, :name, :strategy_family_id, :asset_class, :active_passive,
                        :benchmark_code, :benchmark_name, CAST(:inclusion_rules AS jsonb),
                        CAST(:exclusion_rules AS jsonb), :minimum_peer_count, :source,
                        :source_updated_at, NOW()
                    )
                    ON CONFLICT (key) DO UPDATE SET
                        name = EXCLUDED.name,
                        strategy_family_id = EXCLUDED.strategy_family_id,
                        asset_class = EXCLUDED.asset_class,
                        active_passive = EXCLUDED.active_passive,
                        benchmark_code = EXCLUDED.benchmark_code,
                        benchmark_name = EXCLUDED.benchmark_name,
                        inclusion_rules = EXCLUDED.inclusion_rules,
                        exclusion_rules = EXCLUDED.exclusion_rules,
                        minimum_peer_count = EXCLUDED.minimum_peer_count,
                        source = EXCLUDED.source,
                        source_updated_at = EXCLUDED.source_updated_at,
                        updated_at = NOW()
                """), {
                    "id": peer_group.get("id"),
                    "key": peer_group.get("key"),
                    "name": peer_group.get("name"),
                    "strategy_family_id": strategy_row["id"],
                    "asset_class": peer_group.get("asset_class"),
                    "active_passive": peer_group.get("active_passive"),
                    "benchmark_code": peer_group.get("benchmark_code"),
                    "benchmark_name": peer_group.get("benchmark_name"),
                    "inclusion_rules": json.dumps(peer_group.get("inclusion_rules") or {}, ensure_ascii=False),
                    "exclusion_rules": json.dumps(peer_group.get("exclusion_rules") or {}, ensure_ascii=False),
                    "minimum_peer_count": peer_group.get("minimum_peer_count") or 5,
                    "source": source,
                    "source_updated_at": date.today(),
                })

        self._schema_ready_cache = True
        return {
            "catalog_strategy_families": len(strategy_families),
            "catalog_peer_groups": len(peer_groups),
            "catalog_version": source,
        }

    def apply_ingestion_plan(
        self,
        groups: List[Dict[str, Any]],
        source: str = "tushare_classification_ingestion",
        reconcile: bool = False,
    ) -> Dict[str, Any]:
        """幂等写入高置信度实体、份额、同类组成员关系与基准映射。"""
        if not groups and not reconcile:
            return {
                "applied_groups": 0,
                "applied_shares": 0,
                "created_entities": 0,
                "reused_entities": 0,
                "deactivated_shares": 0,
                "deactivated_entities": 0,
                "conflicts": [],
            }
        if not self._schema_ready():
            raise RuntimeError("标准化基金分类表尚未完整部署")

        from sqlalchemy import text

        applied_groups = 0
        applied_shares = 0
        created_entities = 0
        reused_entities = 0
        deactivated_shares = 0
        deactivated_entities = 0
        conflicts: List[Dict[str, Any]] = []
        active_share_codes = [
            str(share.get("wind_code"))
            for group in groups
            for share in group.get("shares") or []
            if share.get("wind_code")
        ]

        with self.engine.begin() as conn:
            for group in groups:
                try:
                    with conn.begin_nested():
                        strategy = conn.execute(text("""
                            SELECT id, key, asset_class, active_passive
                            FROM strategy_families
                            WHERE key = :strategy_family_key
                            LIMIT 1
                        """), {"strategy_family_key": group.get("strategy_family_key")}).fetchone()
                        peer_group = conn.execute(text("""
                            SELECT id, key, benchmark_code
                            FROM peer_groups
                            WHERE key = :peer_group_key
                            LIMIT 1
                        """), {"peer_group_key": group.get("peer_group_key")}).fetchone()
                        if not strategy or not peer_group:
                            raise ValueError("strategy_family_or_peer_group_missing")

                        strategy_row = dict(strategy._mapping)
                        peer_row = dict(peer_group._mapping)
                        if strategy_row.get("asset_class") != group.get("asset_class"):
                            raise ValueError("strategy_family_asset_class_conflict")
                        if strategy_row.get("active_passive") != group.get("active_passive"):
                            raise ValueError("strategy_family_active_passive_conflict")
                        if peer_row.get("benchmark_code") != group.get("benchmark_code"):
                            raise ValueError("peer_group_benchmark_conflict")

                        share_codes = [str(share.get("wind_code")) for share in group.get("shares") or []]
                        existing_rows = conn.execute(text("""
                            SELECT DISTINCT
                                fe.id,
                                fe.source,
                                fe.strategy_family_id,
                                fe.normalized_name
                            FROM fund_share_classes fsc
                            JOIN fund_entities fe ON fe.id = fsc.entity_id
                            WHERE fsc.wind_code = ANY(:share_codes)
                        """), {"share_codes": share_codes}).fetchall()
                        if len(existing_rows) > 1:
                            raise ValueError("share_codes_resolve_to_multiple_entities")

                        existing = existing_rows[0] if existing_rows else conn.execute(text("""
                            SELECT id, source, strategy_family_id, normalized_name
                            FROM fund_entities
                            WHERE canonical_code = :canonical_code
                               OR (
                                    normalized_name = :normalized_name
                                    AND strategy_family_id = :strategy_family_id
                               )
                            ORDER BY CASE WHEN canonical_code = :canonical_code THEN 0 ELSE 1 END
                            LIMIT 1
                        """), {
                            "canonical_code": group.get("canonical_code"),
                            "normalized_name": group.get("normalized_name"),
                            "strategy_family_id": strategy_row["id"],
                        }).fetchone()

                        entity_id = str(existing.id) if existing else str(group.get("entity_id"))
                        if existing and existing.strategy_family_id not in {None, strategy_row["id"]}:
                            raise ValueError("existing_entity_strategy_family_conflict")
                        entity_created = not bool(existing)

                        entity_payload = {
                            "source": source,
                            "classificationRule": group.get("mapping_method"),
                            "classificationConfidence": group.get("classification_confidence"),
                            "benchmarkConfidence": group.get("benchmark_confidence"),
                            "evidenceRefs": group.get("evidence_refs") or {},
                        }
                        if existing:
                            if existing.source == source:
                                conn.execute(text("""
                                    UPDATE fund_entities
                                    SET canonical_code = :canonical_code,
                                        canonical_name = :canonical_name,
                                        normalized_name = :normalized_name,
                                        strategy_family_id = :strategy_family_id,
                                        asset_class = :asset_class,
                                        active_passive = :active_passive,
                                        lifecycle_stage = 'active',
                                        established_at = COALESCE(:established_at, established_at),
                                        source_updated_at = :source_updated_at,
                                        raw_data = COALESCE(raw_data, '{}'::jsonb) || CAST(:raw_data AS jsonb),
                                        updated_at = NOW()
                                    WHERE id = :entity_id
                                """), {
                                    "entity_id": entity_id,
                                    "canonical_code": group.get("canonical_code"),
                                    "canonical_name": group.get("canonical_name"),
                                    "normalized_name": group.get("normalized_name"),
                                    "strategy_family_id": strategy_row["id"],
                                    "asset_class": group.get("asset_class"),
                                    "active_passive": group.get("active_passive"),
                                    "established_at": group.get("established_at"),
                                    "source_updated_at": group.get("source_updated_at"),
                                    "raw_data": json.dumps(entity_payload, ensure_ascii=False),
                                })
                        else:
                            conn.execute(text("""
                                INSERT INTO fund_entities (
                                    id, canonical_code, canonical_name, normalized_name,
                                    strategy_family_id, asset_class, active_passive,
                                    lifecycle_stage, established_at, source, source_updated_at,
                                    raw_data, updated_at
                                ) VALUES (
                                    :entity_id, :canonical_code, :canonical_name, :normalized_name,
                                    :strategy_family_id, :asset_class, :active_passive,
                                    'active', :established_at, :source, :source_updated_at,
                                    CAST(:raw_data AS jsonb), NOW()
                                )
                            """), {
                                "entity_id": entity_id,
                                "canonical_code": group.get("canonical_code"),
                                "canonical_name": group.get("canonical_name"),
                                "normalized_name": group.get("normalized_name"),
                                "strategy_family_id": strategy_row["id"],
                                "asset_class": group.get("asset_class"),
                                "active_passive": group.get("active_passive"),
                                "established_at": group.get("established_at"),
                                "source": source,
                                "source_updated_at": group.get("source_updated_at"),
                                "raw_data": json.dumps(entity_payload, ensure_ascii=False),
                            })

                        group_share_count = 0
                        for share in group.get("shares") or []:
                            share_payload = {
                                "source": "funds",
                                "fundType": share.get("fund_type"),
                                "investType": share.get("invest_type"),
                                "contractType": share.get("contract_type"),
                                "declaredBenchmark": share.get("declared_benchmark"),
                                "normalizationRule": "trailing_share_class_suffix",
                            }
                            share_id = "share-auto-" + hashlib.sha1(
                                str(share.get("wind_code")).encode("utf-8")
                            ).hexdigest()[:20]
                            conn.execute(text("""
                                INSERT INTO fund_share_classes (
                                    id, entity_id, fund_id, wind_code, share_class, fee_class,
                                    currency, is_primary, status, source, source_updated_at,
                                    raw_data, updated_at
                                ) VALUES (
                                    :id, :entity_id, :fund_id, :wind_code, :share_class, NULL,
                                    :currency, :is_primary, 'active', :source, :source_updated_at,
                                    CAST(:raw_data AS jsonb), NOW()
                                )
                                ON CONFLICT (wind_code) DO UPDATE SET
                                    entity_id = CASE
                                        WHEN fund_share_classes.source = :source THEN EXCLUDED.entity_id
                                        ELSE fund_share_classes.entity_id
                                    END,
                                    fund_id = COALESCE(fund_share_classes.fund_id, EXCLUDED.fund_id),
                                    share_class = COALESCE(fund_share_classes.share_class, EXCLUDED.share_class),
                                    currency = COALESCE(fund_share_classes.currency, EXCLUDED.currency),
                                    is_primary = CASE
                                        WHEN fund_share_classes.source = :source THEN EXCLUDED.is_primary
                                        ELSE fund_share_classes.is_primary
                                    END,
                                    status = CASE
                                        WHEN fund_share_classes.source = :source THEN 'active'
                                        ELSE fund_share_classes.status
                                    END,
                                    source_updated_at = GREATEST(fund_share_classes.source_updated_at, EXCLUDED.source_updated_at),
                                    raw_data = COALESCE(fund_share_classes.raw_data, '{}'::jsonb) || EXCLUDED.raw_data,
                                    updated_at = NOW()
                            """), {
                                "id": share_id,
                                "entity_id": entity_id,
                                "fund_id": share.get("fund_id"),
                                "wind_code": share.get("wind_code"),
                                "share_class": share.get("share_class"),
                                "currency": share.get("currency") or "CNY",
                                "is_primary": bool(share.get("is_primary")),
                                "source": source,
                                "source_updated_at": share.get("source_updated_at"),
                                "raw_data": json.dumps(share_payload, ensure_ascii=False),
                            })
                            group_share_count += 1

                        curated_membership = conn.execute(text("""
                            SELECT 1
                            FROM peer_group_members
                            WHERE entity_id = :entity_id
                              AND source <> :source
                            LIMIT 1
                        """), {"entity_id": entity_id, "source": source}).fetchone()
                        if not curated_membership:
                            if reconcile:
                                conn.execute(text("""
                                    DELETE FROM peer_group_members
                                    WHERE entity_id = :entity_id
                                      AND source = :source
                                      AND peer_group_id <> :peer_group_id
                                """), {
                                    "entity_id": entity_id,
                                    "source": source,
                                    "peer_group_id": peer_row["id"],
                                })
                            member_id = "peer-member-auto-" + hashlib.sha1(
                                f"{peer_row['id']}|{entity_id}".encode("utf-8")
                            ).hexdigest()[:20]
                            matched_rules = {
                                "strategyFamily": group.get("strategy_family_key"),
                                "benchmarkCode": group.get("benchmark_code"),
                                "normalization": "high_confidence_ingestion",
                                "shareCodes": share_codes,
                            }
                            conn.execute(text("""
                                INSERT INTO peer_group_members (
                                    id, peer_group_id, entity_id, role, matched_rules,
                                    excluded_rules, sample_as_of_date, confidence, source, updated_at
                                ) VALUES (
                                    :id, :peer_group_id, :entity_id, 'member', CAST(:matched_rules AS jsonb),
                                    NULL, :sample_as_of_date, :confidence, :source, NOW()
                                )
                                ON CONFLICT (peer_group_id, entity_id) DO UPDATE SET
                                    matched_rules = EXCLUDED.matched_rules,
                                    sample_as_of_date = EXCLUDED.sample_as_of_date,
                                    confidence = EXCLUDED.confidence,
                                    updated_at = NOW()
                                WHERE peer_group_members.source = :source
                            """), {
                                "id": member_id,
                                "peer_group_id": peer_row["id"],
                                "entity_id": entity_id,
                                "matched_rules": json.dumps(matched_rules, ensure_ascii=False),
                                "sample_as_of_date": group.get("source_updated_at"),
                                "confidence": group.get("classification_confidence"),
                                "source": source,
                            })

                        effective_from = group.get("established_at") or "1900-01-01"
                        curated_mapping = conn.execute(text("""
                            SELECT 1
                            FROM benchmark_mappings
                            WHERE entity_id = :entity_id
                              AND status = 'active'
                              AND source <> :source
                            LIMIT 1
                        """), {"entity_id": entity_id, "source": source}).fetchone()
                        if not curated_mapping:
                            if reconcile:
                                conn.execute(text("""
                                    UPDATE benchmark_mappings
                                    SET status = 'inactive', updated_at = NOW()
                                    WHERE entity_id = :entity_id
                                      AND source = :source
                                      AND benchmark_code <> :benchmark_code
                                      AND status = 'active'
                                """), {
                                    "entity_id": entity_id,
                                    "source": source,
                                    "benchmark_code": group.get("benchmark_code"),
                                })
                            mapping_id = "benchmark-auto-" + hashlib.sha1(
                                f"{entity_id}|{group.get('benchmark_code')}|{effective_from}".encode("utf-8")
                            ).hexdigest()[:20]
                            conn.execute(text("""
                                INSERT INTO benchmark_mappings (
                                    id, entity_id, peer_group_id, benchmark_code, benchmark_name,
                                    benchmark_type, mapping_method, confidence, rationale,
                                    evidence_refs, effective_from, effective_to, status, source, updated_at
                                ) VALUES (
                                    :id, :entity_id, :peer_group_id, :benchmark_code, :benchmark_name,
                                    :benchmark_type, :mapping_method, :confidence, :rationale,
                                    CAST(:evidence_refs AS jsonb), :effective_from, NULL, 'active', :source, NOW()
                                )
                                ON CONFLICT (entity_id, benchmark_code, effective_from) DO UPDATE SET
                                    peer_group_id = EXCLUDED.peer_group_id,
                                    benchmark_name = EXCLUDED.benchmark_name,
                                    benchmark_type = EXCLUDED.benchmark_type,
                                    mapping_method = EXCLUDED.mapping_method,
                                    confidence = EXCLUDED.confidence,
                                    rationale = EXCLUDED.rationale,
                                    evidence_refs = EXCLUDED.evidence_refs,
                                    status = 'active',
                                    updated_at = NOW()
                                WHERE benchmark_mappings.source = :source
                            """), {
                                "id": mapping_id,
                                "entity_id": entity_id,
                                "peer_group_id": peer_row["id"],
                                "benchmark_code": group.get("benchmark_code"),
                                "benchmark_name": group.get("benchmark_name"),
                                "benchmark_type": group.get("benchmark_type"),
                                "mapping_method": group.get("mapping_method"),
                                "confidence": group.get("benchmark_confidence"),
                                "rationale": group.get("rationale"),
                                "evidence_refs": json.dumps(group.get("evidence_refs") or {}, ensure_ascii=False),
                                "effective_from": effective_from,
                                "source": source,
                            })
                        if entity_created:
                            created_entities += 1
                        else:
                            reused_entities += 1
                        applied_shares += group_share_count
                        applied_groups += 1
                except Exception as error:
                    conflicts.append({
                        "canonical_code": group.get("canonical_code"),
                        "normalized_name": group.get("normalized_name"),
                        "reason": str(error),
                    })

            if reconcile:
                deactivated_shares = conn.execute(text("""
                    UPDATE fund_share_classes
                    SET status = 'inactive', updated_at = NOW()
                    WHERE source = :source
                      AND status = 'active'
                      AND wind_code <> ALL(:active_share_codes)
                """), {
                    "source": source,
                    "active_share_codes": active_share_codes,
                }).rowcount
                deactivated_entities = conn.execute(text("""
                    UPDATE fund_entities fe
                    SET lifecycle_stage = 'inactive', updated_at = NOW()
                    WHERE fe.source = :source
                      AND fe.lifecycle_stage = 'active'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM fund_share_classes fsc
                          WHERE fsc.entity_id = fe.id
                            AND fsc.status = 'active'
                      )
                """), {"source": source}).rowcount
                conn.execute(text("""
                    DELETE FROM peer_group_members pgm
                    USING fund_entities fe
                    WHERE pgm.entity_id = fe.id
                      AND pgm.source = :source
                      AND fe.source = :source
                      AND fe.lifecycle_stage = 'inactive'
                """), {"source": source})
                conn.execute(text("""
                    UPDATE benchmark_mappings bm
                    SET status = 'inactive', updated_at = NOW()
                    FROM fund_entities fe
                    WHERE bm.entity_id = fe.id
                      AND bm.source = :source
                      AND fe.source = :source
                      AND fe.lifecycle_stage = 'inactive'
                      AND bm.status = 'active'
                """), {"source": source})

        self._schema_ready_cache = True
        return {
            "applied_groups": applied_groups,
            "applied_shares": applied_shares,
            "created_entities": created_entities,
            "reused_entities": reused_entities,
            "deactivated_shares": deactivated_shares,
            "deactivated_entities": deactivated_entities,
            "conflicts": conflicts,
        }

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
