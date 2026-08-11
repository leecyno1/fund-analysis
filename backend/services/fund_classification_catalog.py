"""基金分类目录 Module。

集中定义策略族谱、同类组和可核验的指数别名；不包含任何演示基金。
"""
import re
from typing import Any, Dict, List, Optional


class FundClassificationCatalog:
    """标准分类定义的唯一来源。"""

    VERSION = "fund_classification_catalog_v5"

    STRATEGY_FAMILIES: List[Dict[str, Any]] = [
        {
            "id": "strategy-family-active-equity-core",
            "key": "active_equity_core",
            "name": "主动权益-宽基参考",
            "asset_class": "equity",
            "active_passive": "active",
            "evaluation_profile_key": "active_equity",
            "compatible_fund_types": ["stock", "股票型", "普通股票型"],
            "style_tags": ["主动权益", "宽基参考"],
        },
        {
            "id": "strategy-family-active-equity-sector",
            "key": "active_equity_sector",
            "name": "主动权益-行业/主题",
            "asset_class": "equity",
            "active_passive": "active",
            "evaluation_profile_key": "active_equity",
            "compatible_fund_types": ["stock", "股票型", "普通股票型", "hybrid", "偏股混合型", "偏股混合"],
            "style_tags": ["主动权益", "行业", "主题"],
        },
        {
            "id": "strategy-family-fixed-income-credit",
            "key": "fixed_income_credit",
            "name": "固收-信用债/产业债",
            "asset_class": "fixed_income",
            "active_passive": "active",
            "evaluation_profile_key": "fixed_income",
            "compatible_fund_types": ["bond", "债券型", "中长期纯债型", "短期纯债型", "混合债券型", "纯债"],
            "style_tags": ["固收", "信用债", "产业债"],
        },
        {
            "id": "strategy-family-fixed-income-general",
            "key": "fixed_income_general",
            "name": "固收-综合债券",
            "asset_class": "fixed_income",
            "active_passive": "active",
            "evaluation_profile_key": "fixed_income",
            "compatible_fund_types": ["bond", "债券型", "中长期纯债型", "短期纯债型", "混合债券型", "纯债"],
            "style_tags": ["固收", "纯债", "综合债券"],
        },
        {
            "id": "strategy-family-fixed-income-equity-allocation",
            "key": "fixed_income_equity_allocation",
            "name": "债券型-含权益配置",
            "asset_class": "fixed_income",
            "active_passive": "active",
            "evaluation_profile_key": "fixed_income_plus",
            "compatible_fund_types": ["bond", "债券型", "混合债券型", "强化收益型", "稳健增长型"],
            "style_tags": ["固收", "含权益配置", "收益增强"],
        },
        {
            "id": "strategy-family-index-broad",
            "key": "index_broad",
            "name": "指数-权益宽基",
            "asset_class": "index",
            "active_passive": "passive",
            "evaluation_profile_key": "index_fund",
            "compatible_fund_types": ["index", "指数型", "被动指数型", "ETF", "ETF联接"],
            "style_tags": ["指数", "宽基", "被动"],
        },
        {
            "id": "strategy-family-index-fixed-income",
            "key": "index_fixed_income",
            "name": "指数-固定收益",
            "asset_class": "fixed_income",
            "active_passive": "passive",
            "evaluation_profile_key": "index_fund",
            "compatible_fund_types": ["指数型", "被动指数型", "债券指数", "同业存单指数"],
            "style_tags": ["指数", "固定收益", "被动"],
        },
        {
            "id": "strategy-family-index-enhanced",
            "key": "index_enhanced",
            "name": "指数-增强",
            "asset_class": "index",
            "active_passive": "active",
            "evaluation_profile_key": "index_enhanced",
            "compatible_fund_types": ["index", "指数型", "增强指数型", "指数增强"],
            "style_tags": ["指数", "增强", "主动"],
        },
        {
            "id": "strategy-family-qdii-global-theme",
            "key": "qdii_global_theme",
            "name": "QDII-全球/区域主题",
            "asset_class": "global",
            "active_passive": "active",
            "evaluation_profile_key": "qdii",
            "compatible_fund_types": ["qdii", "QDII", "国际(QDII)", "海外基金"],
            "style_tags": ["QDII", "全球", "区域", "汇率"],
        },
        {
            "id": "strategy-family-cash-management",
            "key": "cash_management",
            "name": "货币-现金管理",
            "asset_class": "money_market",
            "active_passive": "active",
            "evaluation_profile_key": "money_market",
            "compatible_fund_types": ["money", "货币型", "货币基金", "现金管理"],
            "style_tags": ["货币", "现金管理", "流动性"],
        },
        {
            "id": "strategy-family-multi-asset-allocation",
            "key": "multi_asset_allocation",
            "name": "多资产-配置",
            "asset_class": "multi_asset",
            "active_passive": "active",
            "evaluation_profile_key": "multi_asset",
            "compatible_fund_types": ["hybrid", "混合型", "灵活配置型", "平衡混合型"],
            "style_tags": ["多资产", "配置", "平衡"],
        },
        {
            "id": "strategy-family-mixed-equity-allocation",
            "key": "mixed_equity_allocation",
            "name": "混合型-偏股配置",
            "asset_class": "multi_asset",
            "active_passive": "active",
            "evaluation_profile_key": "multi_asset_equity",
            "compatible_fund_types": ["hybrid", "混合型", "灵活配置型", "偏股混合型"],
            "style_tags": ["混合型", "偏股", "权益配置"],
        },
        {
            "id": "strategy-family-mixed-balanced-allocation",
            "key": "mixed_balanced_allocation",
            "name": "混合型-平衡配置",
            "asset_class": "multi_asset",
            "active_passive": "active",
            "evaluation_profile_key": "multi_asset_balanced",
            "compatible_fund_types": ["hybrid", "混合型", "灵活配置型", "平衡混合型"],
            "style_tags": ["混合型", "平衡", "股债配置"],
        },
        {
            "id": "strategy-family-mixed-bond-allocation",
            "key": "mixed_bond_allocation",
            "name": "混合型-偏债配置",
            "asset_class": "multi_asset",
            "active_passive": "active",
            "evaluation_profile_key": "multi_asset_bond",
            "compatible_fund_types": ["hybrid", "混合型", "灵活配置型", "偏债混合型"],
            "style_tags": ["混合型", "偏债", "稳健配置"],
        },
    ]

    TRACKED_INDEX_RULES: List[Dict[str, Any]] = [
        {
            "aliases": ["沪深300指数"],
            "benchmark_code": "000300.SH",
            "benchmark_name": "沪深300",
            "peer_group_key": "peer-index-hs300",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证500指数", "中证小盘500指数"],
            "benchmark_code": "000905.SH",
            "benchmark_name": "中证500",
            "peer_group_key": "peer-index-csi500",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证A500指数"],
            "benchmark_code": "000510.SH",
            "benchmark_name": "中证A500",
            "peer_group_key": "peer-index-csi-a500",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证1000指数"],
            "benchmark_code": "000852.SH",
            "benchmark_name": "中证1000",
            "peer_group_key": "peer-index-csi1000",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证2000指数"],
            "benchmark_code": "932000.CSI",
            "benchmark_name": "中证2000",
            "peer_group_key": "peer-index-csi2000",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证800指数"],
            "benchmark_code": "000906.SH",
            "benchmark_name": "中证800",
            "peer_group_key": "peer-index-csi800",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证A50指数"],
            "benchmark_code": "930050.CSI",
            "benchmark_name": "中证A50",
            "peer_group_key": "peer-index-csi-a50",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["创业板指数", "创业板指"],
            "benchmark_code": "399006.SZ",
            "benchmark_name": "创业板指",
            "peer_group_key": "peer-index-chinext",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["上证科创板50成份指数", "科创50指数"],
            "benchmark_code": "000688.SH",
            "benchmark_name": "科创50",
            "peer_group_key": "peer-index-star50",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["上证180指数", "上海证券交易所180指数"],
            "benchmark_code": "000010.SH",
            "benchmark_name": "上证180",
            "peer_group_key": "peer-index-sse180",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["上证50指数", "上海证券交易所50成份指数"],
            "benchmark_code": "000016.SH",
            "benchmark_name": "上证50",
            "peer_group_key": "peer-index-sse50",
            "strategy_family_key": "index_broad",
            "asset_class": "index",
        },
        {
            "aliases": ["中证同业存单AAA指数"],
            "benchmark_code": "931059.CSI",
            "benchmark_name": "中证同业存单AAA",
            "peer_group_key": "peer-index-cd-aaa",
            "strategy_family_key": "index_fixed_income",
            "asset_class": "fixed_income",
            "required_contract_term": "债券",
        },
    ]

    ACTIVE_EQUITY_REFERENCE_RULES: List[Dict[str, Any]] = [
        {
            "aliases": ["沪深300指数"],
            "benchmark_code": "000300.SH",
            "benchmark_name": "沪深300",
            "peer_group_key": "peer-active-equity-stock-hs300",
        },
        {
            "aliases": ["中证500指数", "中证小盘500指数"],
            "benchmark_code": "000905.SH",
            "benchmark_name": "中证500",
            "peer_group_key": "peer-active-equity-stock-csi500",
        },
        {
            "aliases": ["中证800指数"],
            "benchmark_code": "000906.SH",
            "benchmark_name": "中证800",
            "peer_group_key": "peer-active-equity-stock-csi800",
        },
        {
            "aliases": ["中证1000指数"],
            "benchmark_code": "000852.SH",
            "benchmark_name": "中证1000",
            "peer_group_key": "peer-active-equity-stock-csi1000",
        },
    ]

    ACTIVE_EQUITY_SECTOR_RULES: List[Dict[str, Any]] = [
        {
            "aliases": ["中证上游资源产业指数"],
            "benchmark_code": "SECTOR-RESOURCE",
            "benchmark_name": "资源产业",
            "peer_group_key": "peer-active-equity-sector-resource",
        },
        {
            "aliases": ["中证全指信息技术指数", "中证全指电信业务指数"],
            "benchmark_code": "SECTOR-TECH-MEDIA",
            "benchmark_name": "信息技术/传媒",
            "peer_group_key": "peer-active-equity-sector-tech-media",
        },
        {
            "aliases": ["中证内地消费主题指数"],
            "benchmark_code": "SECTOR-CONSUMPTION",
            "benchmark_name": "消费主题",
            "peer_group_key": "peer-active-equity-sector-consumption",
        },
        {
            "aliases": ["中证新能源指数", "中证新能源汽车指数", "中证港股通能源综合指数"],
            "benchmark_code": "SECTOR-NEW-ENERGY",
            "benchmark_name": "新能源",
            "peer_group_key": "peer-active-equity-sector-new-energy",
        },
    ]

    ACTIVE_FIXED_INCOME_REFERENCE_RULES: List[Dict[str, Any]] = [
        {
            "aliases": ["中证全债指数"],
            "benchmark_code": "H11001.CSI",
            "benchmark_name": "中证全债",
            "peer_group_key": "peer-fixed-income-csi-total-bond",
        },
        {
            "aliases": ["中证综合债指数", "中证综合债券指数"],
            "benchmark_code": "H11009.CSI",
            "benchmark_name": "中证综合债",
            "peer_group_key": "peer-fixed-income-csi-composite-bond",
        },
    ]

    @classmethod
    def resolve_declared_equity_benchmark(cls, declared_benchmark: str) -> Optional[Dict[str, Any]]:
        """从合同复合基准中提取唯一可核验的权益指数成分，供行业归因使用。"""
        text = str(declared_benchmark or "").strip()
        if not text:
            return None

        matches = []
        for rule in cls.TRACKED_INDEX_RULES:
            if rule.get("asset_class") != "index":
                continue
            matched_alias = next((alias for alias in rule.get("aliases", []) if alias in text), None)
            if not matched_alias:
                continue
            weight_match = re.search(
                rf"{re.escape(matched_alias)}(?:收益率)?\s*[×xX*]\s*(\d+(?:\.\d+)?)\s*%",
                text,
            )
            matches.append({
                "benchmark_code": rule["benchmark_code"],
                "benchmark_name": rule["benchmark_name"],
                "declared_weight": float(weight_match.group(1)) / 100 if weight_match else None,
                "declared_benchmark": text,
            })

        unique = {item["benchmark_code"]: item for item in matches}
        return next(iter(unique.values())) if len(unique) == 1 else None

    @classmethod
    def family_meta(cls) -> Dict[str, Dict[str, Any]]:
        return {
            item["key"]: {
                "asset_class": item["asset_class"],
                "active_passive": item["active_passive"],
                "evaluation_profile_key": item["evaluation_profile_key"],
                "compatible_fund_types": list(item["compatible_fund_types"]),
            }
            for item in cls.STRATEGY_FAMILIES
        }

    @classmethod
    def peer_groups(cls) -> List[Dict[str, Any]]:
        groups = [
            {
                "id": "peer-money-cash-management",
                "key": "peer-money-cash-management",
                "name": "货币-现金管理",
                "strategy_family_key": "cash_management",
                "asset_class": "money_market",
                "active_passive": "active",
                "benchmark_code": "DR007",
                "benchmark_name": "DR007",
                "inclusion_rules": {"legalType": "money_market", "currency": "CNY"},
                "exclusion_rules": {"exclude": ["非货币基金"]},
                "minimum_peer_count": 5,
            }
        ]
        groups.extend([
            {
                "id": "peer-fixed-income-equity-allocation",
                "key": "peer-fixed-income-equity-allocation",
                "name": "债券型-含权益配置",
                "strategy_family_key": "fixed_income_equity_allocation",
                "asset_class": "fixed_income",
                "active_passive": "active",
                "benchmark_code": "FIXED-INCOME-EQUITY-20",
                "benchmark_name": "合同基准权益权重>0%且≤20%",
                "inclusion_rules": {"legalType": "债券型", "equityBenchmarkWeightRange": [0, 20], "declaredBenchmarkRequired": True},
                "exclusion_rules": {"exclude": ["可转债主题", "权重不完整", "无法识别资产类别"]},
                "minimum_peer_count": 5,
            },
            {
                "id": "peer-mixed-equity-allocation",
                "key": "peer-mixed-equity-allocation",
                "name": "混合型-偏股配置",
                "strategy_family_key": "mixed_equity_allocation",
                "asset_class": "multi_asset",
                "active_passive": "active",
                "benchmark_code": "MIXED-EQUITY-60",
                "benchmark_name": "合同基准权益权重≥60%",
                "inclusion_rules": {"legalType": "混合型", "minimumEquityBenchmarkWeight": 60, "declaredBenchmarkRequired": True},
                "exclusion_rules": {"exclude": ["权重不完整", "无法识别资产类别"]},
                "minimum_peer_count": 5,
            },
            {
                "id": "peer-mixed-balanced-allocation",
                "key": "peer-mixed-balanced-allocation",
                "name": "混合型-平衡配置",
                "strategy_family_key": "mixed_balanced_allocation",
                "asset_class": "multi_asset",
                "active_passive": "active",
                "benchmark_code": "MIXED-BALANCED-30-60",
                "benchmark_name": "合同基准权益权重>30%且<60%",
                "inclusion_rules": {"legalType": "混合型", "equityBenchmarkWeightRange": [30, 60], "declaredBenchmarkRequired": True},
                "exclusion_rules": {"exclude": ["权重不完整", "无法识别资产类别"]},
                "minimum_peer_count": 5,
            },
            {
                "id": "peer-mixed-bond-allocation",
                "key": "peer-mixed-bond-allocation",
                "name": "混合型-偏债配置",
                "strategy_family_key": "mixed_bond_allocation",
                "asset_class": "multi_asset",
                "active_passive": "active",
                "benchmark_code": "MIXED-BOND-30",
                "benchmark_name": "合同基准权益权重≤30%",
                "inclusion_rules": {"legalType": "混合型", "maximumEquityBenchmarkWeight": 30, "declaredBenchmarkRequired": True},
                "exclusion_rules": {"exclude": ["权重不完整", "无法识别资产类别"]},
                "minimum_peer_count": 5,
            },
        ])
        for rule in cls.TRACKED_INDEX_RULES:
            groups.append({
                "id": rule["peer_group_key"],
                "key": rule["peer_group_key"],
                "name": f"指数-{rule['benchmark_name']}",
                "strategy_family_key": rule["strategy_family_key"],
                "asset_class": rule["asset_class"],
                "active_passive": "passive",
                "benchmark_code": rule["benchmark_code"],
                "benchmark_name": rule["benchmark_name"],
                "inclusion_rules": {
                    "sameIndex": rule["benchmark_code"],
                    "tracking": "passive",
                    "declaredBenchmarkRequired": True,
                },
                "exclusion_rules": {"exclude": ["指数增强", "非同指数"]},
                "minimum_peer_count": 5,
            })
        for rule in cls.ACTIVE_EQUITY_REFERENCE_RULES:
            groups.append({
                "id": rule["peer_group_key"],
                "key": rule["peer_group_key"],
                "name": f"主动权益-{rule['benchmark_name']}参考",
                "strategy_family_key": "active_equity_core",
                "asset_class": "equity",
                "active_passive": "active",
                "benchmark_code": rule["benchmark_code"],
                "benchmark_name": rule["benchmark_name"],
                "inclusion_rules": {
                    "legalType": "股票型",
                    "primaryEquityReference": rule["benchmark_code"],
                    "minimumPrimaryWeight": 80,
                    "declaredBenchmarkRequired": True,
                },
                "exclusion_rules": {
                    "exclude": ["指数基金", "指数增强", "行业主题", "多权益市场基准"],
                },
                "minimum_peer_count": 5,
            })
        for rule in cls.ACTIVE_EQUITY_SECTOR_RULES:
            groups.append({
                "id": rule["peer_group_key"],
                "key": rule["peer_group_key"],
                "name": f"主动权益-行业/{rule['benchmark_name']}",
                "strategy_family_key": "active_equity_sector",
                "asset_class": "equity",
                "active_passive": "active",
                "benchmark_code": rule["benchmark_code"],
                "benchmark_name": rule["benchmark_name"],
                "inclusion_rules": {"legalType": "股票型", "minimumSectorBenchmarkWeight": 70},
                "exclusion_rules": {"exclude": ["行业基准权重不足", "跨行业基准无法归一"]},
                "minimum_peer_count": 5,
            })
        for rule in cls.ACTIVE_FIXED_INCOME_REFERENCE_RULES:
            groups.append({
                "id": rule["peer_group_key"],
                "key": rule["peer_group_key"],
                "name": f"固收-{rule['benchmark_name']}参考",
                "strategy_family_key": "fixed_income_general",
                "asset_class": "fixed_income",
                "active_passive": "active",
                "benchmark_code": rule["benchmark_code"],
                "benchmark_name": rule["benchmark_name"],
                "inclusion_rules": {
                    "legalType": "债券型",
                    "bondReference": rule["benchmark_code"],
                    "requiredWeight": 100,
                    "declaredBenchmarkRequired": True,
                },
                "exclusion_rules": {
                    "exclude": ["可转债", "二级债", "含权益基准", "复合基准"],
                },
                "minimum_peer_count": 5,
            })
        return groups
