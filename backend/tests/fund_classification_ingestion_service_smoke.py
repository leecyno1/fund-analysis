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
        },
        {
            "wind_code": "0000371.OF",
            "name": "审计脏代码货币A",
            "type": "货币型",
        },
    ])

    groups = plan.get("groups") or []
    if plan.get("summary", {}).get("eligible_funds") != 5 or len(groups) != 4:
        raise AssertionError(f"Only high-confidence money/passive-index funds should be eligible: {plan}")
    money = next(group for group in groups if group.get("strategy_family_key") == "cash_management")
    if money.get("benchmark_code") != "DR007" or len(money.get("shares") or []) != 2:
        raise AssertionError(f"Money share classes must merge into one DR007 entity: {money}")
    if money.get("canonical_name") != "审计现金宝货币":
        raise AssertionError(f"Share suffix normalization failed: {money}")
    if sum(1 for share in money["shares"] if share.get("is_primary")) != 1:
        raise AssertionError(f"Entity must have exactly one primary share: {money}")

    index = next(group for group in groups if group.get("benchmark_code") == "000300.SH")
    if index.get("benchmark_code") != "000300.SH" or index.get("peer_group_key") != "peer-index-hs300":
        raise AssertionError(f"Exact declared index benchmark mapping failed: {index}")
    a500 = next(group for group in groups if group.get("benchmark_code") == "000510.SH")
    if a500.get("peer_group_key") != "peer-index-csi-a500":
        raise AssertionError(f"A500 benchmark mapping failed: {a500}")
    deposit = next(group for group in groups if group.get("strategy_family_key") == "index_fixed_income")
    if deposit.get("benchmark_code") != "931059.CSI" or deposit.get("asset_class") != "fixed_income":
        raise AssertionError(f"Fixed-income index must not enter equity index peers: {deposit}")

    reasons = plan.get("summary", {}).get("skipped_by_reason") or {}
    if reasons.get("unsupported_index_enhanced") != 1:
        raise AssertionError(f"Enhanced index must remain outside passive-index auto mapping: {plan}")
    if reasons.get("unsupported_or_ambiguous_index_benchmark") != 1:
        raise AssertionError(f"Theme index must not collapse into HS300: {plan}")
    if reasons.get("unsupported_fund_type") != 1:
        raise AssertionError(f"Unsupported bond classification must remain explicit: {plan}")
    if reasons.get("invalid_fund_code_format") != 1:
        raise AssertionError(f"Malformed fund codes must not enter standardized entities: {plan}")

    print("OK classification ingestion only materializes high-confidence entities and share classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
