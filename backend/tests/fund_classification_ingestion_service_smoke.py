import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fund_classification_ingestion_service import FundClassificationIngestionService


def main() -> int:
    service = FundClassificationIngestionService()
    plan = service.build_plan([
        {
            "id": "money-a",
            "wind_code": "980001.OF",
            "name": "审计现金宝货币A",
            "type": "货币型",
            "establishment_date": "2020-01-01",
        },
        {
            "id": "money-b",
            "wind_code": "980002.OF",
            "name": "审计现金宝货币B类",
            "type": "货币型",
            "establishment_date": "2020-02-01",
        },
        {
            "id": "index-a",
            "wind_code": "980003.OF",
            "name": "审计沪深300ETF联接A",
            "type": "指数型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数收益率*95%+银行活期存款利率*5%",
                "invest_type": "被动指数型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980007.OF",
            "name": "审计中证A500ETF联接A",
            "type": "指数型",
            "raw_data": {"universe": {
                "benchmark": "中证A500指数收益率×95%+银行活期存款利率(税后)×5%",
                "invest_type": "被动指数型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980008.OF",
            "name": "审计同业存单AAA指数A",
            "type": "指数型",
            "raw_data": {"universe": {
                "benchmark": "中证同业存单AAA指数收益率×95%+银行人民币一年定期存款利率(税后)×5%",
                "invest_type": "被动指数型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980004.OF",
            "name": "审计沪深300指数增强A",
            "type": "指数型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数收益率*95%+银行活期存款利率*5%",
                "invest_type": "增强指数型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980005.OF",
            "name": "审计沪深300红利低波ETF",
            "type": "指数型",
            "raw_data": {"info": {"benchmark": "沪深300红利低波指数收益率"}},
        },
        {
            "wind_code": "980006.OF",
            "name": "审计信用债基金A",
            "type": "债券型",
            "raw_data": {"universe": {
                "benchmark": "中证全债指数×100%",
                "invest_type": "债券型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980009.OF",
            "name": "审计价值股票A",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数×80%+中证全债指数×20%",
                "invest_type": "股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980010.OF",
            "name": "审计价值股票C",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数×80%+中证全债指数×20%",
                "invest_type": "股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "150003.SZ",
            "name": "审计价值股票",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数×80%+中证全债指数×20%",
                "invest_type": "股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980011.OF",
            "name": "审计成长股票A",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "中证1000指数收益率×95%+银行活期存款利率(税后)×5%",
                "invest_type": "普通股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980012.OF",
            "name": "审计医药股票A",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数×80%+中证全债指数×20%",
                "invest_type": "股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980013.OF",
            "name": "审计多元股票A",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数×80%+恒生指数×10%+中证全债指数×10%",
                "invest_type": "股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980014.OF",
            "name": "审计均衡股票A",
            "type": "股票型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数×45%+恒生指数×45%+中证全债指数×10%",
                "invest_type": "股票型",
                "contract_type": "股票型",
            }},
        },
        {
            "wind_code": "980015.OF",
            "name": "审计稳健纯债A",
            "type": "债券型",
            "raw_data": {"universe": {
                "benchmark": "中证全债指数×100%",
                "invest_type": "债券型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980016.OF",
            "name": "审计稳健纯债C",
            "type": "债券型",
            "raw_data": {"universe": {
                "benchmark": "中证全债指数收益率×100%",
                "invest_type": "债券型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980017.OF",
            "name": "审计安心纯债A",
            "type": "债券型",
            "raw_data": {"universe": {
                "benchmark": "中证综合债券指数×100%",
                "invest_type": "债券型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980018.OF",
            "name": "审计可转债A",
            "type": "债券型",
            "raw_data": {"universe": {
                "benchmark": "中证全债指数×100%",
                "invest_type": "债券型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980019.OF",
            "name": "审计收益债券A",
            "type": "债券型",
            "raw_data": {"universe": {
                "benchmark": "中证综合债指数收益率×90%+沪深300指数收益率×10%",
                "invest_type": "债券型",
                "contract_type": "债券型",
            }},
        },
        {
            "wind_code": "980020.OF",
            "name": "审计偏股配置混合A",
            "type": "混合型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数收益率×65%+中证港股通综合指数收益率×15%+中债综合全价指数收益率×20%",
                "invest_type": "混合型",
                "contract_type": "混合型",
            }},
        },
        {
            "wind_code": "980021.OF",
            "name": "审计平衡配置混合A",
            "type": "混合型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数收益率×50%+中债综合指数收益率×50%",
                "invest_type": "灵活配置型",
                "contract_type": "混合型",
            }},
        },
        {
            "wind_code": "980022.OF",
            "name": "审计偏债配置混合A",
            "type": "混合型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数收益率×20%+中债综合财富指数收益率×80%",
                "invest_type": "混合型",
                "contract_type": "混合型",
            }},
        },
        {
            "wind_code": "980023.OF",
            "name": "审计权重缺失混合A",
            "type": "混合型",
            "raw_data": {"universe": {
                "benchmark": "沪深300指数收益率×60%+中债综合指数收益率×20%",
                "invest_type": "混合型",
                "contract_type": "混合型",
            }},
        },
        {
            "wind_code": "0000371.OF",
            "name": "审计脏代码货币A",
            "type": "货币型",
        },
    ])

    groups = plan.get("groups") or []
    if plan.get("summary", {}).get("eligible_funds") != 15 or len(groups) != 11:
        raise AssertionError(f"Only high-confidence standardized funds should be eligible: {plan}")
    money = next(group for group in groups if group.get("strategy_family_key") == "cash_management")
    if money.get("benchmark_code") != "DR007" or len(money.get("shares") or []) != 2:
        raise AssertionError(f"Money share classes must merge into one DR007 entity: {money}")
    if money.get("canonical_name") != "审计现金宝货币":
        raise AssertionError(f"Share suffix normalization failed: {money}")
    if sum(1 for share in money["shares"] if share.get("is_primary")) != 1:
        raise AssertionError(f"Entity must have exactly one primary share: {money}")

    index = next(group for group in groups if group.get("peer_group_key") == "peer-index-hs300")
    if index.get("benchmark_code") != "000300.SH" or index.get("peer_group_key") != "peer-index-hs300":
        raise AssertionError(f"Exact declared index benchmark mapping failed: {index}")
    a500 = next(group for group in groups if group.get("benchmark_code") == "000510.SH")
    if a500.get("peer_group_key") != "peer-index-csi-a500":
        raise AssertionError(f"A500 benchmark mapping failed: {a500}")
    deposit = next(group for group in groups if group.get("strategy_family_key") == "index_fixed_income")
    if deposit.get("benchmark_code") != "931059.CSI" or deposit.get("asset_class") != "fixed_income":
        raise AssertionError(f"Fixed-income index must not enter equity index peers: {deposit}")

    active_equity = next(group for group in groups if group.get("peer_group_key") == "peer-active-equity-stock-hs300")
    if len(active_equity.get("shares") or []) != 3 or active_equity.get("benchmark_weight") != 80:
        raise AssertionError(f"Active equity share classes and primary benchmark weight are wrong: {active_equity}")
    if active_equity.get("canonical_code") != "980009.OF":
        raise AssertionError(f"Open-end A share must take priority over legacy exchange shares: {active_equity}")
    if active_equity.get("benchmark_type") != "composite_primary_equity_reference":
        raise AssertionError(f"Composite benchmark must remain explicitly identified: {active_equity}")
    active_csi1000 = next(
        group for group in groups if group.get("peer_group_key") == "peer-active-equity-stock-csi1000"
    )
    if active_csi1000.get("benchmark_code") != "000852.SH":
        raise AssertionError(f"Active equity CSI1000 reference mapping failed: {active_csi1000}")

    total_bond = next(group for group in groups if group.get("benchmark_code") == "H11001.CSI")
    if len(total_bond.get("shares") or []) != 2 or total_bond.get("benchmark_weight") != 100:
        raise AssertionError(f"Total-bond share classes and benchmark mapping are wrong: {total_bond}")
    composite_bond = next(group for group in groups if group.get("benchmark_code") == "H11009.CSI")
    if composite_bond.get("strategy_family_key") != "fixed_income_general":
        raise AssertionError(f"Composite bond must enter general fixed-income peers: {composite_bond}")

    mixed_groups = {group.get("strategy_family_key"): group for group in groups if group.get("asset_class") == "multi_asset"}
    if mixed_groups.get("mixed_equity_allocation", {}).get("benchmark_weight") != 80:
        raise AssertionError(f"Equity-oriented mixed fund weight bucket failed: {mixed_groups}")
    if mixed_groups.get("mixed_balanced_allocation", {}).get("benchmark_weight") != 50:
        raise AssertionError(f"Balanced mixed fund weight bucket failed: {mixed_groups}")
    if mixed_groups.get("mixed_bond_allocation", {}).get("benchmark_weight") != 20:
        raise AssertionError(f"Bond-oriented mixed fund weight bucket failed: {mixed_groups}")

    reasons = plan.get("summary", {}).get("skipped_by_reason") or {}
    if reasons.get("unsupported_index_enhanced") != 1:
        raise AssertionError(f"Enhanced index must remain outside passive-index auto mapping: {plan}")
    if reasons.get("unsupported_or_ambiguous_index_benchmark") != 1:
        raise AssertionError(f"Theme index must not collapse into HS300: {plan}")
    if reasons.get("unsupported_active_equity_sector_or_index_style") != 1:
        raise AssertionError(f"Sector equity funds must not enter broad-reference peers: {plan}")
    if reasons.get("unsupported_active_equity_secondary_reference") != 1:
        raise AssertionError(f"Multiple equity market references must remain outside the catalog: {plan}")
    if reasons.get("active_equity_reference_weight_below_80") != 1:
        raise AssertionError(f"Low-weight equity references must remain outside the catalog: {plan}")
    if reasons.get("unsupported_fixed_income_style") != 2:
        raise AssertionError(f"Credit and convertible bond funds must remain outside general bond peers: {plan}")
    if reasons.get("fixed_income_reference_not_100_percent") != 1:
        raise AssertionError(f"Bond benchmarks containing equity exposure must remain outside the catalog: {plan}")
    if reasons.get("mixed_benchmark_weights_incomplete") != 1:
        raise AssertionError(f"Incomplete mixed benchmark weights must remain unclassified: {plan}")
    if reasons.get("invalid_fund_code_format") != 1:
        raise AssertionError(f"Malformed fund codes must not enter standardized entities: {plan}")

    print("OK classification ingestion only materializes high-confidence entities and share classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
