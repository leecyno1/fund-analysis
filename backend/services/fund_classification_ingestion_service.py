"""高置信度基金分类标准化 Module。

只把能够由基金法定类型或合同基准明确确认的对象写入标准化分类表；
模糊、增强、主题和缺少合同基准的对象保留为证据不足。
"""
import hashlib
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.fund_classification_catalog import FundClassificationCatalog


class FundClassificationIngestionService:
    """生成可审计的基金实体、份额、同类组和基准映射写入计划。"""

    SOURCE = "tushare_classification_ingestion"
    SHARE_CLASSES = {"A", "B", "C", "D", "E", "F", "H", "I", "R", "Y"}
    PRIMARY_SHARE_PRIORITY = {"A": 0, None: 1, "I": 2, "B": 3, "C": 4, "D": 5, "E": 6, "F": 7, "H": 8, "R": 9, "Y": 10}
    ENHANCED_INDEX_TERMS = ("增强", "量化", "主动", "策略增强")
    TERMINATED_TERMS = ("清算", "终止", "退市")
    ACTIVE_EQUITY_NAME_EXCLUSIONS = (
        "etf", "fof", "联接", "指数", "增强", "量化", "行业", "主题", "医药", "医疗",
        "健康", "科技", "半导体", "芯片", "集成电路", "新能源", "消费", "军工", "传媒",
        "金融", "地产", "人工智能", "互联网", "农业", "制造", "环保", "绿色", "资源",
        "能源", "材料", "低碳", "创新药", "新经济", "改革", "产业", "养老", "文化",
        "文体", "沪港深", "港股", "全球", "外向", "专精特新", "内需", "国策", "智造",
        "事件驱动", "大数据",
    )
    ACTIVE_FIXED_INCOME_NAME_EXCLUSIONS = (
        "可转债", "转债", "二级债", "信用", "产业债", "双债", "增强", "混合",
    )
    ACTIVE_EQUITY_ALLOWED_SECONDARY_TERMS = (
        "存款", "利率", "中债", "全债", "综合债", "国债", "债券", "同业存单",
    )
    MIXED_DEFENSIVE_BENCHMARK_TERMS = ("债", "国债", "存款", "利率", "现金", "DR007", "同业存单")
    MIXED_EQUITY_BENCHMARK_TERMS = (
        "沪深", "中证", "上证", "上海证券交易所", "深证", "创业板", "恒生", "港股", "国证", "股票",
        "金融", "地产", "消费", "产业", "科技", "互联网", "数字经济", "战略新兴",
    )
    FUND_CODE_PATTERN = re.compile(r"^[0-9]{6}\.(OF|SH|SZ|BJ)$", re.IGNORECASE)

    INDEX_RULES = tuple(FundClassificationCatalog.TRACKED_INDEX_RULES)
    ACTIVE_EQUITY_RULES = tuple(FundClassificationCatalog.ACTIVE_EQUITY_REFERENCE_RULES)
    ACTIVE_FIXED_INCOME_RULES = tuple(FundClassificationCatalog.ACTIVE_FIXED_INCOME_REFERENCE_RULES)

    def __init__(self, repository: Optional[Any] = None):
        self._repository = repository

    def build_plan(self, funds: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        skipped: List[Dict[str, Any]] = []
        seen_codes = set()

        for fund in funds:
            wind_code = self._text(fund.get("wind_code") or fund.get("ts_code")).upper()
            if not wind_code or wind_code in seen_codes:
                skipped.append({"wind_code": wind_code or None, "reason": "invalid_or_duplicate_code"})
                continue
            seen_codes.add(wind_code)
            if not self.FUND_CODE_PATTERN.fullmatch(wind_code):
                skipped.append({"wind_code": wind_code, "reason": "invalid_fund_code_format"})
                continue
            candidate, reason = self._candidate(fund, wind_code)
            if candidate is None:
                skipped.append({"wind_code": wind_code, "reason": reason})
                continue

            key = (
                candidate["strategy_family_key"],
                candidate["normalized_name"],
                candidate["benchmark_code"],
            )
            group = grouped.setdefault(key, {
                "strategy_family_key": candidate["strategy_family_key"],
                "asset_class": candidate["asset_class"],
                "active_passive": candidate["active_passive"],
                "peer_group_key": candidate["peer_group_key"],
                "benchmark_code": candidate["benchmark_code"],
                "benchmark_name": candidate["benchmark_name"],
                "benchmark_type": candidate["benchmark_type"],
                "mapping_method": candidate["mapping_method"],
                "classification_confidence": candidate["classification_confidence"],
                "benchmark_confidence": candidate["benchmark_confidence"],
                "benchmark_weight": candidate.get("benchmark_weight"),
                "rationale": candidate["rationale"],
                "automatic_rule_scope": candidate["automatic_rule_scope"],
                "normalized_name": candidate["normalized_name"],
                "shares": [],
            })
            group["shares"].append(candidate["share"])

        groups = [self._finalize_group(group) for group in grouped.values()]
        groups.sort(key=lambda group: (group["strategy_family_key"], group["canonical_code"]))
        skipped_by_reason: Dict[str, int] = {}
        for item in skipped:
            reason = str(item.get("reason") or "unknown")
            skipped_by_reason[reason] = skipped_by_reason.get(reason, 0) + 1
        eligible_by_family: Dict[str, int] = {}
        eligible_by_benchmark: Dict[str, int] = {}
        for group in groups:
            family = str(group.get("strategy_family_key") or "unknown")
            benchmark = str(group.get("benchmark_code") or "unknown")
            share_count = len(group.get("shares") or [])
            eligible_by_family[family] = eligible_by_family.get(family, 0) + share_count
            eligible_by_benchmark[benchmark] = eligible_by_benchmark.get(benchmark, 0) + share_count
        return {
            "groups": groups,
            "skipped": skipped,
            "summary": {
                "input_funds": len(seen_codes),
                "eligible_funds": sum(len(group["shares"]) for group in groups),
                "entity_groups": len(groups),
                "skipped_funds": len(skipped),
                "skipped_by_reason": skipped_by_reason,
                "eligible_by_family": eligible_by_family,
                "eligible_by_benchmark": eligible_by_benchmark,
            },
        }

    def apply_plan(self, plan: Dict[str, Any], reconcile: bool = False) -> Dict[str, Any]:
        repository = self._get_repository()
        catalog_result = repository.ensure_catalog(
            FundClassificationCatalog.STRATEGY_FAMILIES,
            FundClassificationCatalog.peer_groups(),
            source=FundClassificationCatalog.VERSION,
        )
        result = repository.apply_ingestion_plan(
            plan.get("groups") or [],
            source=self.SOURCE,
            reconcile=reconcile,
        )
        return {**plan.get("summary", {}), **catalog_result, **result}

    def _candidate(self, fund: Dict[str, Any], wind_code: str) -> Tuple[Optional[Dict[str, Any]], str]:
        name = self._display_text(fund.get("name") or fund.get("fund_name"))
        if not name:
            return None, "missing_name"
        if any(term in name for term in self.TERMINATED_TERMS):
            return None, "inactive_or_terminated"

        normalized_name, share_class = self._share_identity(name)
        fund_type = self._text(fund.get("type") or fund.get("fund_type")).lower()
        declared_benchmark = self._declared_benchmark(fund)
        invest_type = self._raw_classification_value(fund, "invest_type")
        contract_type = self._raw_classification_value(fund, "contract_type")

        if "货币" in fund_type or fund_type == "money":
            classification, reason = self._money_market_candidate()
        elif "指数" in fund_type or fund_type == "index":
            classification, reason = self._passive_index_candidate(
                name,
                declared_benchmark,
                invest_type,
                contract_type,
            )
        elif fund_type in {"混合型", "hybrid"} or contract_type == "混合型":
            classification, reason = self._mixed_allocation_candidate(
                declared_benchmark,
                invest_type,
                contract_type,
            )
        elif fund_type in {"股票型", "stock"}:
            classification, reason = self._active_equity_candidate(
                name,
                declared_benchmark,
                invest_type,
                contract_type,
            )
        elif fund_type in {"债券型", "bond"}:
            classification, reason = self._active_fixed_income_candidate(
                name,
                declared_benchmark,
                invest_type,
                contract_type,
            )
        else:
            return None, "unsupported_fund_type"
        if classification is None:
            return None, reason

        established_at = self._date_text(fund.get("establishment_date") or fund.get("found_date"))
        return {
            **classification,
            "normalized_name": normalized_name,
            "share": {
                "wind_code": wind_code,
                "fund_id": self._text(fund.get("id")) or None,
                "name": name,
                "share_class": share_class,
                "currency": "CNY",
                "established_at": established_at,
                "declared_benchmark": declared_benchmark or None,
                "fund_type": fund.get("type") or fund.get("fund_type"),
                "invest_type": invest_type or None,
                "contract_type": contract_type or None,
                "source_updated_at": self._date_text(fund.get("nav_date")) or date.today().isoformat(),
            },
        }, "eligible"

    def _money_market_candidate(self) -> Tuple[Dict[str, Any], str]:
        return {
            "strategy_family_key": "cash_management",
            "asset_class": "money_market",
            "active_passive": "active",
            "peer_group_key": "peer-money-cash-management",
            "benchmark_code": "DR007",
            "benchmark_name": "DR007",
            "benchmark_type": "money_market_rate",
            "mapping_method": "legal_type_cash_rate_policy",
            "classification_confidence": 0.97,
            "benchmark_confidence": 0.86,
            "benchmark_weight": None,
            "automatic_rule_scope": "legal_money_market",
            "rationale": "基金法定类型明确为货币基金；DR007 仅作为资金利率参照，不生成净值跟踪误差。",
        }, "eligible"

    def _passive_index_candidate(
        self,
        name: str,
        declared_benchmark: str,
        invest_type: str,
        contract_type: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        combined = f"{name} {declared_benchmark} {invest_type}"
        if any(term in combined for term in self.ENHANCED_INDEX_TERMS):
            return None, "unsupported_index_enhanced"
        if invest_type and invest_type != "被动指数型":
            return None, "unsupported_index_investment_type"
        matched = [rule for rule in self.INDEX_RULES if self._matches_index_rule(rule, declared_benchmark)]
        if len(matched) != 1:
            return None, "unsupported_or_ambiguous_index_benchmark"
        rule = matched[0]
        required_contract_term = rule.get("required_contract_term")
        if required_contract_term and required_contract_term not in contract_type:
            return None, "index_contract_type_conflict"
        if rule["asset_class"] == "index" and "债券" in contract_type:
            return None, "index_contract_type_conflict"
        return {
            "strategy_family_key": rule["strategy_family_key"],
            "asset_class": rule["asset_class"],
            "active_passive": "passive",
            "peer_group_key": rule["peer_group_key"],
            "benchmark_code": rule["benchmark_code"],
            "benchmark_name": rule["benchmark_name"],
            "benchmark_type": "tracked_index",
            "mapping_method": "declared_benchmark_exact_alias",
            "classification_confidence": 0.99,
            "benchmark_confidence": 0.99,
            "benchmark_weight": None,
            "automatic_rule_scope": "exact_supported_passive_index",
            "rationale": f"投资类型为被动指数型，合同业绩比较基准明确引用{rule['benchmark_name']}指数。",
        }, "eligible"

    def _active_equity_candidate(
        self,
        name: str,
        declared_benchmark: str,
        invest_type: str,
        contract_type: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        if invest_type not in {"股票型", "普通股票型"}:
            return None, "unsupported_active_equity_investment_type"
        if contract_type != "股票型":
            return None, "active_equity_contract_type_conflict"
        if not declared_benchmark:
            return None, "missing_declared_benchmark"
        lower_name = name.lower()
        if any(term in lower_name for term in self.ACTIVE_EQUITY_NAME_EXCLUSIONS):
            return None, "unsupported_active_equity_sector_or_index_style"

        matched = self._weighted_rule_matches(self.ACTIVE_EQUITY_RULES, declared_benchmark)
        if len(matched) != 1:
            return None, "unsupported_or_ambiguous_active_equity_benchmark"
        match = matched[0]
        if match["weight"] < 80:
            return None, "active_equity_reference_weight_below_80"
        if self._has_unsupported_equity_secondary(declared_benchmark, match["alias"]):
            return None, "unsupported_active_equity_secondary_reference"

        rule = match["rule"]
        return {
            "strategy_family_key": "active_equity_core",
            "asset_class": "equity",
            "active_passive": "active",
            "peer_group_key": rule["peer_group_key"],
            "benchmark_code": rule["benchmark_code"],
            "benchmark_name": rule["benchmark_name"],
            "benchmark_type": "composite_primary_equity_reference",
            "mapping_method": "declared_benchmark_primary_equity_alias_and_weight",
            "classification_confidence": 0.96,
            "benchmark_confidence": 0.96,
            "benchmark_weight": match["weight"],
            "automatic_rule_scope": "active_stock_single_broad_equity_reference",
            "rationale": (
                f"基金法定、投资与合同类型均为股票型；合同组合基准以{rule['benchmark_name']}"
                f"为主权益参考（权重{match['weight']:g}%）。基准代码仅表示主权益参考，不代表完整复合基准。"
            ),
        }, "eligible"

    def _active_fixed_income_candidate(
        self,
        name: str,
        declared_benchmark: str,
        invest_type: str,
        contract_type: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        if invest_type != "债券型":
            return None, "unsupported_fixed_income_investment_type"
        if contract_type != "债券型":
            return None, "fixed_income_contract_type_conflict"
        if not declared_benchmark:
            return None, "missing_declared_benchmark"
        if any(term in name for term in self.ACTIVE_FIXED_INCOME_NAME_EXCLUSIONS):
            return None, "unsupported_fixed_income_style"

        matched = self._weighted_rule_matches(self.ACTIVE_FIXED_INCOME_RULES, declared_benchmark)
        if len(matched) != 1:
            return None, "unsupported_or_ambiguous_fixed_income_benchmark"
        match = matched[0]
        if match["weight"] != 100 or "+" in unicodedata.normalize("NFKC", declared_benchmark):
            return None, "fixed_income_reference_not_100_percent"

        rule = match["rule"]
        return {
            "strategy_family_key": "fixed_income_general",
            "asset_class": "fixed_income",
            "active_passive": "active",
            "peer_group_key": rule["peer_group_key"],
            "benchmark_code": rule["benchmark_code"],
            "benchmark_name": rule["benchmark_name"],
            "benchmark_type": "declared_bond_index",
            "mapping_method": "declared_benchmark_exact_bond_alias_and_weight",
            "classification_confidence": 0.98,
            "benchmark_confidence": 0.99,
            "benchmark_weight": match["weight"],
            "automatic_rule_scope": "active_bond_exact_supported_100_percent_reference",
            "rationale": (
                f"基金法定、投资与合同类型均为债券型；合同业绩比较基准为"
                f"{rule['benchmark_name']}指数100%，且未混入权益或转债基准。"
            ),
        }, "eligible"

    def _mixed_allocation_candidate(
        self,
        declared_benchmark: str,
        invest_type: str,
        contract_type: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        if contract_type != "混合型":
            return None, "mixed_contract_type_conflict"
        if invest_type not in {"混合型", "灵活配置型", "稳健增长型", "股债配置型", ""}:
            return None, "unsupported_mixed_investment_type"
        if not declared_benchmark:
            return None, "missing_declared_benchmark"

        components = re.findall(r"([^+＋]+?)[×xX*]\s*(\d+(?:\.\d+)?)\s*%", declared_benchmark)
        if not components:
            return None, "mixed_benchmark_weights_unavailable"
        total_weight = sum(float(weight) for _, weight in components)
        if total_weight < 95 or total_weight > 105:
            return None, "mixed_benchmark_weights_incomplete"

        equity_weight = 0.0
        for component, raw_weight in components:
            weight = float(raw_weight)
            if any(term.lower() in component.lower() for term in self.MIXED_DEFENSIVE_BENCHMARK_TERMS):
                continue
            if any(term.lower() in component.lower() for term in self.MIXED_EQUITY_BENCHMARK_TERMS):
                equity_weight += weight
                continue
            return None, "mixed_benchmark_asset_class_ambiguous"

        if equity_weight >= 60:
            family_key = "mixed_equity_allocation"
            peer_group_key = "peer-mixed-equity-allocation"
            benchmark_code = "MIXED-EQUITY-60"
            benchmark_name = "合同基准权益权重≥60%"
        elif equity_weight <= 30:
            family_key = "mixed_bond_allocation"
            peer_group_key = "peer-mixed-bond-allocation"
            benchmark_code = "MIXED-BOND-30"
            benchmark_name = "合同基准权益权重≤30%"
        else:
            family_key = "mixed_balanced_allocation"
            peer_group_key = "peer-mixed-balanced-allocation"
            benchmark_code = "MIXED-BALANCED-30-60"
            benchmark_name = "合同基准权益权重>30%且<60%"
        return {
            "strategy_family_key": family_key,
            "asset_class": "multi_asset",
            "active_passive": "active",
            "peer_group_key": peer_group_key,
            "benchmark_code": benchmark_code,
            "benchmark_name": benchmark_name,
            "benchmark_type": "declared_allocation_bucket",
            "mapping_method": "declared_benchmark_asset_weight_bucket",
            "classification_confidence": 0.96,
            "benchmark_confidence": 0.96,
            "benchmark_weight": round(equity_weight, 4),
            "automatic_rule_scope": "mixed_fund_explicit_contract_allocation",
            "rationale": f"合同基准各资产权重合计{total_weight:g}%，其中权益类权重{equity_weight:g}%，据此进入配置同类组。",
        }, "eligible"

    def _finalize_group(self, group: Dict[str, Any]) -> Dict[str, Any]:
        shares = sorted(
            group["shares"],
            key=lambda share: (
                0 if str(share.get("wind_code") or "").upper().endswith(".OF") else 1,
                self.PRIMARY_SHARE_PRIORITY.get(share.get("share_class"), 99),
                share.get("established_at") or "9999-12-31",
                share["wind_code"],
            ),
        )
        primary = shares[0]
        for share in shares:
            share["is_primary"] = share is primary
        established_dates = [share["established_at"] for share in shares if share.get("established_at")]
        stable_key = f"{group['strategy_family_key']}|{group['normalized_name']}|{group['benchmark_code']}"
        digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()[:20]
        return {
            **group,
            "entity_id": f"entity-auto-{digest}",
            "canonical_code": primary["wind_code"],
            "canonical_name": group["normalized_name"],
            "established_at": min(established_dates) if established_dates else None,
            "source_updated_at": max(share["source_updated_at"] for share in shares),
            "shares": shares,
            "evidence_refs": {
                "source": "funds.raw_data.info/universe",
                "fundType": primary.get("fund_type"),
                "investType": primary.get("invest_type"),
                "contractType": primary.get("contract_type"),
                "declaredBenchmark": primary.get("declared_benchmark"),
                "shareCodes": [share["wind_code"] for share in shares],
                "catalogVersion": FundClassificationCatalog.VERSION,
                "primaryReferenceWeight": group.get("benchmark_weight"),
                "automaticRuleScope": group.get("automatic_rule_scope"),
            },
        }

    def _weighted_rule_matches(
        self,
        rules: Iterable[Dict[str, Any]],
        benchmark: str,
    ) -> List[Dict[str, Any]]:
        matches: List[Dict[str, Any]] = []
        normalized = unicodedata.normalize("NFKC", benchmark)
        operator = r"(?:\*|×|x|X)"
        suffix = r"(?:收益率|涨跌幅)?"
        for rule in rules:
            for alias in rule.get("aliases") or []:
                after = re.compile(
                    re.escape(alias) + suffix + r"\s*" + operator + r"\s*(\d+(?:\.\d+)?)\s*%",
                    re.IGNORECASE,
                )
                before = re.compile(
                    r"(\d+(?:\.\d+)?)\s*%\s*" + operator + r"\s*" + re.escape(alias) + suffix,
                    re.IGNORECASE,
                )
                for pattern in (after, before):
                    for item in pattern.finditer(normalized):
                        matches.append({
                            "rule": rule,
                            "alias": alias,
                            "weight": float(item.group(1)),
                        })
        return matches

    def _has_unsupported_equity_secondary(self, benchmark: str, primary_alias: str) -> bool:
        components = re.split(r"\s*\+\s*", unicodedata.normalize("NFKC", benchmark))
        for component in components:
            if primary_alias in component:
                continue
            if any(term in component for term in ("可转债", "可转换债券", "可交换债")):
                return True
            if any(term in component for term in self.ACTIVE_EQUITY_ALLOWED_SECONDARY_TERMS):
                continue
            return True
        return False

    def _matches_index_rule(self, rule: Dict[str, Any], benchmark: str) -> bool:
        if not benchmark or benchmark.count("指数") > 1:
            return False
        suffix = r"(?:收益率|涨跌幅)?(?=\s*(?:\*|×|x|X|\+|$))"
        return any(
            re.search(re.escape(alias) + suffix, benchmark, re.IGNORECASE)
            for alias in rule.get("aliases") or []
        )

    def _raw_classification_value(self, fund: Dict[str, Any], field: str) -> str:
        direct = self._display_text(fund.get(field))
        if direct:
            return direct
        raw_data = fund.get("raw_data") or {}
        if not isinstance(raw_data, dict):
            return ""
        for key in ("universe", "info"):
            section = raw_data.get(key) or {}
            if isinstance(section, dict):
                value = self._display_text(section.get(field))
                if value:
                    return value
        return ""

    def _share_identity(self, name: str) -> Tuple[str, Optional[str]]:
        compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", name)).strip()
        upper = compact.upper()
        if upper.endswith(("ETF", "LOF", "QDII")):
            return compact, None
        match = re.search(r"([A-Z])(?:类|份额)?$", upper)
        if match and match.group(1) in self.SHARE_CLASSES:
            return compact[:match.start()].rstrip("-_ /"), match.group(1)
        return compact, None

    def _declared_benchmark(self, fund: Dict[str, Any]) -> str:
        direct = self._display_text(fund.get("benchmark"))
        if direct:
            return direct
        raw_data = fund.get("raw_data") or {}
        if not isinstance(raw_data, dict):
            return ""
        for key in ("info", "universe"):
            section = raw_data.get(key) or {}
            if isinstance(section, dict):
                value = self._display_text(section.get("benchmark"))
                if value:
                    return value
        return ""

    def _get_repository(self):
        if self._repository is None:
            from repositories import get_fund_classification_repo

            self._repository = get_fund_classification_repo()
        return self._repository

    @staticmethod
    def _date_text(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value or "").strip()
        if len(text) == 8 and text.isdigit():
            text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        try:
            return datetime.fromisoformat(text[:10]).date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _display_text(value: Any) -> str:
        return unicodedata.normalize("NFKC", str(value or "")).strip()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()
