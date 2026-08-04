"""
基金分类 Module。

把分散在评分、同类比较和页面调用方中的类型/关键词判断收口为一个可审计
Interface。显式策略族谱优先；基础类型与名称只作为带置信度的回退证据；无法
分类时明确返回证据不足，禁止默认归入主动权益。
"""
from typing import Any, Dict, List, Optional, Tuple


class FundClassificationService:
    """生成多层基金分类及其证据。"""

    METHODOLOGY_VERSION = "fund_classification_v2"

    FAMILY_META: Dict[str, Dict[str, Any]] = {
        "active_equity_core": {
            "asset_class": "equity",
            "active_passive": "active",
            "evaluation_profile_key": "active_equity",
            "compatible_fund_types": [
                "stock", "股票型", "普通股票型", "hybrid", "偏股混合型", "偏股混合",
            ],
        },
        "active_equity_sector": {
            "asset_class": "equity",
            "active_passive": "active",
            "evaluation_profile_key": "active_equity",
            "compatible_fund_types": [
                "stock", "股票型", "普通股票型", "hybrid", "偏股混合型", "偏股混合",
            ],
        },
        "fixed_income_credit": {
            "asset_class": "fixed_income",
            "active_passive": "active",
            "evaluation_profile_key": "fixed_income",
            "compatible_fund_types": [
                "bond", "债券型", "中长期纯债型", "短期纯债型", "混合债券型", "纯债",
            ],
        },
        "fixed_income_general": {
            "asset_class": "fixed_income",
            "active_passive": "active",
            "evaluation_profile_key": "fixed_income",
            "compatible_fund_types": [
                "bond", "债券型", "中长期纯债型", "短期纯债型", "混合债券型", "纯债",
            ],
        },
        "index_broad": {
            "asset_class": "index",
            "active_passive": "passive",
            "evaluation_profile_key": "index_fund",
            "compatible_fund_types": ["index", "指数型", "被动指数型", "ETF", "ETF联接"],
        },
        "index_enhanced": {
            "asset_class": "index",
            "active_passive": "active",
            "evaluation_profile_key": "index_enhanced",
            "compatible_fund_types": ["index", "指数型", "增强指数型", "指数增强"],
        },
        "qdii_global_theme": {
            "asset_class": "global",
            "active_passive": "active",
            "evaluation_profile_key": "qdii",
            "compatible_fund_types": ["qdii", "QDII", "国际(QDII)", "海外基金"],
        },
        "cash_management": {
            "asset_class": "money_market",
            "active_passive": "active",
            "evaluation_profile_key": "money_market",
            "compatible_fund_types": ["money", "货币型", "货币基金", "现金管理"],
        },
        "multi_asset_allocation": {
            "asset_class": "multi_asset",
            "active_passive": "active",
            "evaluation_profile_key": "multi_asset",
            "compatible_fund_types": ["hybrid", "混合型", "灵活配置型", "平衡混合型"],
        },
    }

    EXPLICIT_FAMILY_KEYS = (
        "strategy_family_key",
        "strategyFamilyKey",
        "strategy_family",
        "strategyFamily",
    )

    SECTOR_TERMS = (
        "行业", "主题", "医药", "医疗", "科技", "半导体", "芯片", "新能源", "消费",
        "军工", "传媒", "金融地产", "人工智能", "ai", "互联网",
    )

    def classify(
        self,
        fund: Dict[str, Any],
        profile: Optional[Dict[str, Any]] = None,
        standardized_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        profile = profile or {}
        standardized_context = standardized_context or {}
        if standardized_context.get("status") == "resolved":
            return self._classify_standardized(fund, standardized_context)

        evidence: List[Dict[str, Any]] = []
        fund_type = self._text(fund.get("type"))
        fund_name = self._text(fund.get("name") or fund.get("fund_name"))

        explicit_family = self._explicit_family(profile)
        if explicit_family:
            evidence.append(self._evidence("strategy_family_key", explicit_family, "research_profile", "显式策略族谱"))
            family_key = explicit_family if explicit_family in self.FAMILY_META else None
            if family_key:
                return self._classified_result(
                    fund,
                    profile,
                    family_key,
                    evidence,
                    confidence=0.98,
                    source="explicit_strategy_family",
                )
            return self._unavailable_result(
                fund,
                evidence,
                [f"策略族谱 {explicit_family} 尚未登记到分类方法中"],
            )

        family_key, matched_field, matched_value = self._infer_family(fund_type, fund_name, profile)
        if family_key:
            evidence.append(self._evidence(matched_field, matched_value, "fund_metadata", "基础类型/名称分类回退"))
            peer_group = self._text(profile.get("peer_group"))
            if peer_group:
                evidence.append(self._evidence("peer_group", peer_group, "research_profile", "现有同类组辅助验证"))
            confidence = 0.82 if fund_type else 0.58
            return self._classified_result(
                fund,
                profile,
                family_key,
                evidence,
                confidence=confidence,
                source="fund_metadata_fallback",
            )

        if fund_type:
            evidence.append(self._evidence("fund.type", fund_type, "fund_metadata", "未命中已登记分类规则"))
        if fund_name:
            evidence.append(self._evidence("fund.name", fund_name, "fund_metadata", "未命中已登记分类规则"))
        return self._unavailable_result(
            fund,
            evidence,
            ["缺少可确认的资产类别、策略族谱或主动/被动证据，不能进入分类内基金评价"],
        )

    def _classify_standardized(
        self,
        fund: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence = list(context.get("classification_evidence") or [])
        family_key = self._text(context.get("strategy_family_key"))
        if not family_key:
            return self._unavailable_result(
                fund,
                evidence,
                context.get("missing_items") or ["标准化基金实体缺少策略族谱"],
                standardized_context=context,
            )
        if family_key not in self.FAMILY_META:
            return self._unavailable_result(
                fund,
                evidence,
                [f"标准化策略族谱 {family_key} 尚未登记到基金评价方法中"],
                standardized_context=context,
            )

        meta = self.FAMILY_META[family_key]
        conflicts = []
        asset_class = self._text(context.get("asset_class"))
        active_passive = self._text(context.get("active_passive"))
        if asset_class and asset_class != meta["asset_class"]:
            conflicts.append(
                f"标准化资产类别 {asset_class} 与策略族谱 {family_key} 的 {meta['asset_class']} 冲突"
            )
        if active_passive and active_passive != meta["active_passive"]:
            conflicts.append(
                f"标准化主动/被动 {active_passive} 与策略族谱 {family_key} 的 {meta['active_passive']} 冲突"
            )
        if conflicts:
            return self._unavailable_result(
                fund,
                evidence,
                conflicts,
                standardized_context=context,
            )

        return self._classified_result(
            fund,
            {},
            family_key,
            evidence,
            confidence=self._confidence(context.get("classification_confidence"), 0.95),
            source="standardized_classification_adapter",
            standardized_context=context,
        )

    def _explicit_family(self, profile: Dict[str, Any]) -> Optional[str]:
        for key in self.EXPLICIT_FAMILY_KEYS:
            value = self._text(profile.get(key))
            if value:
                return value
        return None

    def _infer_family(
        self,
        fund_type: str,
        fund_name: str,
        profile: Dict[str, Any],
    ) -> Tuple[Optional[str], str, str]:
        combined = f"{fund_type} {fund_name} {self._text(profile.get('peer_group'))}".lower()

        if any(token in combined for token in ("qdii", "海外", "全球", "国际基金")):
            return "qdii_global_theme", "fund.type/name", combined.strip()
        if any(token in combined for token in ("货币", "money", "现金管理")):
            return "cash_management", "fund.type/name", combined.strip()
        if any(token in combined for token in ("指数增强", "增强指数", "enhanced index")):
            return "index_enhanced", "fund.type/name", combined.strip()
        if any(token in combined for token in ("指数", "index", "etf", "联接")):
            return "index_broad", "fund.type/name", combined.strip()
        if any(token in combined for token in ("债券", "纯债", "信用债", "产业债", "bond", "固收")):
            family = "fixed_income_credit" if any(token in combined for token in ("信用", "产业债")) else "fixed_income_general"
            return family, "fund.type/name", combined.strip()
        if any(token in combined for token in ("偏股混合", "偏股", "主动权益", "equity", "stock", "股票")):
            family = "active_equity_sector" if any(token in combined for token in self.SECTOR_TERMS) else "active_equity_core"
            return family, "fund.type/name", combined.strip()
        if any(token in combined for token in ("混合型", "hybrid", "灵活配置", "平衡混合")):
            return "multi_asset_allocation", "fund.type/name", combined.strip()
        return None, "", ""

    def _classified_result(
        self,
        fund: Dict[str, Any],
        profile: Dict[str, Any],
        family_key: str,
        evidence: List[Dict[str, Any]],
        confidence: float,
        source: str,
        standardized_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = self.FAMILY_META[family_key]
        context = standardized_context or {}
        benchmark_mapping = context.get("benchmark_mapping") or {}
        peer_group = context.get("peer_group_name") or context.get("peer_group_key") or profile.get("peer_group")
        primary_benchmark = benchmark_mapping.get("benchmark_name") or profile.get("primary_benchmark")
        missing_items = list(context.get("missing_items") or [])
        if not peer_group:
            missing_items.append("缺少显式同类组，不能形成完整的分类内基金评价")
        if not primary_benchmark:
            missing_items.append("缺少有效基准映射，不能形成完整的分类内基金评价")
        return {
            "status": "classified",
            "methodology_version": self.METHODOLOGY_VERSION,
            "fund_code": fund.get("wind_code") or fund.get("ts_code") or fund.get("id"),
            "legal_type": fund.get("type"),
            "entity_id": context.get("entity_id"),
            "canonical_code": context.get("canonical_code"),
            "canonical_name": context.get("canonical_name"),
            "asset_class": context.get("asset_class") or meta["asset_class"],
            "strategy_family_key": family_key,
            "strategy_family_name": context.get("strategy_family_name"),
            "active_passive": context.get("active_passive") or meta["active_passive"],
            "evaluation_profile_key": meta["evaluation_profile_key"],
            "peer_group": peer_group,
            "peer_group_id": context.get("peer_group_id"),
            "peer_group_key": context.get("peer_group_key"),
            "peer_group_name": context.get("peer_group_name"),
            "minimum_peer_count": context.get("minimum_peer_count"),
            "primary_benchmark": primary_benchmark,
            "benchmark_code": benchmark_mapping.get("benchmark_code"),
            "benchmark_mapping": benchmark_mapping or None,
            "compatible_fund_types": list(meta["compatible_fund_types"]),
            "confidence": round(confidence, 2),
            "source": source,
            "evidence": evidence,
            "missing_items": list(dict.fromkeys(missing_items)),
        }

    def _unavailable_result(
        self,
        fund: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        missing_items: List[str],
        standardized_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = standardized_context or {}
        benchmark_mapping = context.get("benchmark_mapping") or {}
        context_family_key = context.get("strategy_family_key")
        context_meta = self.FAMILY_META.get(str(context_family_key or ""), {})
        return {
            "status": "insufficient_evidence",
            "methodology_version": self.METHODOLOGY_VERSION,
            "fund_code": fund.get("wind_code") or fund.get("ts_code") or fund.get("id"),
            "legal_type": fund.get("type"),
            "entity_id": context.get("entity_id"),
            "canonical_code": context.get("canonical_code"),
            "canonical_name": context.get("canonical_name"),
            "asset_class": context.get("asset_class"),
            "strategy_family_key": context_family_key,
            "strategy_family_name": context.get("strategy_family_name"),
            "active_passive": context.get("active_passive"),
            "evaluation_profile_key": context_meta.get("evaluation_profile_key"),
            "peer_group": context.get("peer_group_name") or context.get("peer_group_key"),
            "peer_group_id": context.get("peer_group_id"),
            "peer_group_key": context.get("peer_group_key"),
            "peer_group_name": context.get("peer_group_name"),
            "minimum_peer_count": context.get("minimum_peer_count"),
            "primary_benchmark": benchmark_mapping.get("benchmark_name"),
            "benchmark_code": benchmark_mapping.get("benchmark_code"),
            "benchmark_mapping": benchmark_mapping or None,
            "compatible_fund_types": [],
            "confidence": 0.0,
            "source": "standardized_evidence_gate" if context else "evidence_gate",
            "evidence": evidence,
            "missing_items": list(dict.fromkeys(str(item) for item in missing_items if item)),
        }

    def _evidence(self, field: str, value: str, source: str, reason: str) -> Dict[str, str]:
        return {"field": field, "value": value, "source": source, "reason": reason}

    def _confidence(self, value: Any, default: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    def _text(self, value: Any) -> str:
        return str(value or "").strip()
