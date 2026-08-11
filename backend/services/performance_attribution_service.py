"""统一基金业绩归因。

正式 Barra、Brinson 与净值行为解释分开输出，避免代理指标冒充专业模型。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


class PerformanceAttributionService:
    """面向基金详情与 AI 分析的统一归因入口。"""

    def __init__(self, classification_adapter: Optional[Any] = None):
        self._classification_adapter = classification_adapter

    def analyze(
        self,
        wind_code: str,
        benchmark: Optional[str] = None,
        quarter: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        from repositories import get_fund_repo
        from service_registry import get_data_service
        from services.investment_analysis_service import InvestmentAnalysisService

        fund = get_fund_repo().get_fund_by_identifier(wind_code)
        if not fund:
            raise ValueError(f"Fund not found: {wind_code}")

        fund_code = str(fund.get("wind_code") or wind_code)
        normalized_quarter = self._normalize_quarter(quarter)
        if quarter and not normalized_quarter:
            raise ValueError("quarter must use YYYYQ1-YYYYQ4, for example 2026Q2")
        attribution_quarter = normalized_quarter or self._latest_completed_quarter()
        holding_quarter = self._previous_quarter(attribution_quarter)
        classification_context = self._get_classification_adapter().get_classification_context(fund_code) or {}
        benchmark_code, benchmark_source, benchmark_detail = self._resolve_attribution_benchmark(
            benchmark,
            classification_context,
            fund,
        )
        data_service = get_data_service()
        holdings = data_service.get_fund_holdings(fund_code, holding_quarter)

        formal_style_factors: Dict[str, float] = {}
        if data_service.__class__.__name__ != "TushareDataService":
            try:
                style_payload = data_service.get_fund_style(fund_code) or {}
                formal_style_factors = {
                    key: float(value)
                    for key, value in style_payload.items()
                    if key in self._barra_factor_names() and value is not None
                }
            except Exception as exc:
                logger.warning("Formal style factors unavailable for %s: %s", fund_code, exc)

        barra = self._barra_evidence(fund, holdings, formal_style_factors, holding_quarter)
        brinson = self._brinson_evidence(
            data_service=data_service,
            fund=fund,
            holdings=holdings,
            benchmark_code=benchmark_code,
            benchmark_source=benchmark_source,
            benchmark_detail=benchmark_detail,
            attribution_quarter=attribution_quarter,
            holding_quarter=holding_quarter,
        )

        investment_analysis = InvestmentAnalysisService()
        nav_factor = self._safe_analysis(
            lambda: investment_analysis.factor_lens(fund_code, start_date, end_date),
            "净值行为因子证据不可用",
        )
        if benchmark_code:
            nav_attribution = self._safe_analysis(
                lambda: investment_analysis.advanced_attribution(
                    fund_code,
                    benchmark=benchmark_code,
                    start_date=start_date,
                    end_date=end_date,
                ),
                "净值主动收益解释不可用",
            )
        else:
            nav_attribution = {
                "status": "insufficient_evidence",
                "source": "standardized_classification_gate",
                "missing_items": ["基金分类目录缺少有效基准，不能计算主动收益。"],
            }
        nav_factor["method"] = "nav_behavior_factor_lens"
        nav_factor["is_barra"] = False
        nav_attribution["method"] = "nav_return_attribution"
        nav_attribution["is_brinson"] = False

        formal_statuses = {barra.get("status"), brinson.get("status")}
        if formal_statuses == {"ok"}:
            status = "ok"
        elif any(item in {"ok", "partial_evidence"} for item in formal_statuses) or nav_attribution.get("status") == "ok":
            status = "partial_evidence"
        else:
            status = "insufficient_evidence"

        return {
            "fund": {
                "id": str(fund.get("id") or fund_code),
                "wind_code": fund_code,
                "name": fund.get("name"),
                "type": fund.get("type"),
            },
            "status": status,
            "quarter": attribution_quarter,
            "holding_snapshot_quarter": holding_quarter,
            "benchmark": benchmark_code,
            "benchmark_source": benchmark_source,
            "benchmark_detail": benchmark_detail,
            "barra": barra,
            "brinson": brinson,
            "nav_factor_lens": nav_factor,
            "nav_return_attribution": nav_attribution,
            "methodology": {
                "formal_models": ["Barra style/risk exposure", "Brinson-Fachler industry attribution"],
                "supplementary_models": ["NAV behavior factor lens", "NAV active-return decomposition"],
                "rule": "净值行为解释不得标记为 Barra 或 Brinson。",
                "benchmark_rule": "默认基准只来自基金分类目录；用户可在单次分析中显式覆盖。",
            },
        }

    def _barra_evidence(
        self,
        fund: Dict[str, Any],
        holdings: List[Dict[str, Any]],
        style_factors: Dict[str, float],
        holding_quarter: str,
    ) -> Dict[str, Any]:
        fund_type = str(fund.get("type") or "").lower()
        if any(token in fund_type for token in ["money", "货币", "bond", "债"]):
            return {
                "method": "barra_style_risk_model",
                "status": "not_applicable",
                "formal_model_ready": False,
                "source": "methodology_scope",
                "quarter": holding_quarter,
                "factor_exposures": [],
                "industry_exposures": {},
                "risk_contributions": [],
                "r_squared": None,
                "holdings_count": 0,
                "holdings_disclosed_weight": 0.0,
                "missing_items": ["货币或债券基金不适用当前股票 Barra 风格与风险模型。"],
            }
        industry_exposures: Dict[str, float] = {}
        disclosed_weight = 0.0
        for holding in holdings:
            weight = self._number(holding.get("weight"))
            if weight is None or weight <= 0:
                continue
            industry = str(holding.get("industry") or "未知")
            disclosed_weight += weight
            industry_exposures[industry] = industry_exposures.get(industry, 0.0) + weight

        if style_factors:
            status = "partial_evidence"
            missing_items = ["已取得 Barra 风格因子暴露，但缺少可核验的因子协方差矩阵和特异风险，暂不输出正式风险贡献与 R²。"]
        elif industry_exposures:
            status = "partial_evidence"
            missing_items = ["已取得持仓行业暴露，但未接入正式 Barra 风格因子库，不能输出 SIZE、BETA、MOMENTUM 等因子结论。"]
        else:
            status = "insufficient_evidence"
            missing_items = ["持仓明细缺失，不能计算 Barra 风格或行业暴露。"]

        return {
            "method": "barra_style_risk_model",
            "status": status,
            "formal_model_ready": False,
            "source": "factor_exposure_input" if style_factors else "fund_portfolio_disclosure",
            "quarter": holding_quarter,
            "factor_exposures": [
                {
                    "factor": factor,
                    "exposure": exposure,
                }
                for factor, exposure in style_factors.items()
            ],
            "industry_exposures": dict(
                sorted(
                    ((key, round(value, 6)) for key, value in industry_exposures.items()),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ),
            "risk_contributions": [],
            "r_squared": None,
            "holdings_count": len(holdings),
            "holdings_disclosed_weight": round(disclosed_weight, 6),
            "missing_items": missing_items,
        }

    def _brinson_evidence(
        self,
        data_service: Any,
        fund: Dict[str, Any],
        holdings: List[Dict[str, Any]],
        benchmark_code: Optional[str],
        benchmark_source: str,
        benchmark_detail: Dict[str, Any],
        attribution_quarter: str,
        holding_quarter: str,
    ) -> Dict[str, Any]:
        fund_type = str(fund.get("type") or "").lower()
        if any(token in fund_type for token in ["money", "货币", "bond", "债"]):
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                ["货币或债券基金不适用当前股票行业 Brinson 归因。"],
                status="not_applicable",
            )
        if not benchmark_code:
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                ["基金分类目录缺少有效基准，不能计算 Brinson 行业归因。"],
            )
        if not holdings:
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                [f"缺少 {holding_quarter} 持仓，不能解释 {attribution_quarter} 的行业配置与选择效应。"],
            )
        if data_service.__class__.__name__ != "TushareDataService" or getattr(data_service, "mock_mode", False):
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                ["当前数据 adapter 未提供基金、基准、成分股和行业的同区间收益。"],
            )

        try:
            return self._tushare_brinson(
                data_service=data_service,
                fund=fund,
                holdings=holdings,
                benchmark_code=benchmark_code,
                benchmark_source=benchmark_source,
                benchmark_detail=benchmark_detail,
                attribution_quarter=attribution_quarter,
                holding_quarter=holding_quarter,
            )
        except Exception as exc:
            logger.exception("Brinson input preparation failed for %s", fund.get("wind_code"))
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                [f"Brinson 输入准备失败：{exc.__class__.__name__}"],
            )

    def _tushare_brinson(
        self,
        data_service: Any,
        fund: Dict[str, Any],
        holdings: List[Dict[str, Any]],
        benchmark_code: str,
        benchmark_source: str,
        benchmark_detail: Dict[str, Any],
        attribution_quarter: str,
        holding_quarter: str,
    ) -> Dict[str, Any]:
        from lib.brinson.attribution import BrinsonAttributor
        from services.tushare_service import _to_ts_code

        period_start, period_end = self._quarter_dates(attribution_quarter)
        pro = data_service.pro
        index_frame = pro.index_daily(ts_code=benchmark_code, start_date=period_start, end_date=period_end)
        if index_frame is None or index_frame.empty or len(index_frame) < 2:
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                ["基准指数区间行情缺失。"],
            )
        index_frame = index_frame.sort_values("trade_date")
        first_trade = str(index_frame.iloc[0]["trade_date"])
        last_trade = str(index_frame.iloc[-1]["trade_date"])
        benchmark_return = float(index_frame.iloc[-1]["close"]) / float(index_frame.iloc[0]["close"]) - 1

        fund_frame = pro.fund_nav(
            ts_code=_to_ts_code(str(fund.get("wind_code"))),
            start_date=period_start,
            end_date=period_end,
        )
        fund_return = self._frame_return(fund_frame, ("adj_nav", "accum_nav", "unit_nav"), "nav_date")
        if fund_return is None:
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                ["基金区间净值不足，不能计算主动收益。"],
            )

        weight_start = (datetime.strptime(first_trade, "%Y%m%d") - timedelta(days=220)).strftime("%Y%m%d")
        weight_frame = pro.index_weight(index_code=benchmark_code, start_date=weight_start, end_date=first_trade)
        if weight_frame is None or weight_frame.empty:
            return self._missing_brinson(
                benchmark_code,
                attribution_quarter,
                holding_quarter,
                ["基准成分权重缺失。"],
            )
        available_dates = [str(value) for value in weight_frame["trade_date"].dropna().tolist()]
        selected_weight_date = max((value for value in available_dates if value <= first_trade), default=max(available_dates))
        weight_frame = weight_frame[weight_frame["trade_date"].astype(str) == selected_weight_date]

        start_prices = pro.daily(trade_date=first_trade)
        end_prices = pro.daily(trade_date=last_trade)
        start_factors = pro.adj_factor(trade_date=first_trade)
        end_factors = pro.adj_factor(trade_date=last_trade)
        stock_returns = self._adjusted_stock_returns(start_prices, end_prices, start_factors, end_factors)
        stock_profiles = pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry")
        industries = {
            str(row["ts_code"]): str(row.get("industry") or "未知")
            for _, row in stock_profiles.iterrows()
        } if stock_profiles is not None and not stock_profiles.empty else {}

        portfolio_industries: Dict[str, Dict[str, float]] = {}
        disclosed_weight = 0.0
        return_weight = 0.0
        for holding in holdings:
            code = str(holding.get("stock_code") or "")
            weight = self._number(holding.get("weight"))
            if not code or weight is None or weight <= 0:
                continue
            disclosed_weight += weight
            industry = str(holding.get("industry") or industries.get(code) or "未知")
            bucket = portfolio_industries.setdefault(industry, {"weight": 0.0, "weighted_return": 0.0, "return_weight": 0.0})
            bucket["weight"] += weight
            stock_return = stock_returns.get(code)
            if stock_return is not None:
                bucket["weighted_return"] += weight * stock_return
                bucket["return_weight"] += weight
                return_weight += weight

        for bucket in portfolio_industries.values():
            covered_weight = bucket.pop("return_weight")
            weighted_return = bucket.pop("weighted_return")
            bucket["return"] = weighted_return / covered_weight if covered_weight > 0 else None

        benchmark_industries: Dict[str, Dict[str, float]] = {}
        benchmark_total_weight = 0.0
        benchmark_return_weight = 0.0
        for _, row in weight_frame.iterrows():
            code = str(row.get("con_code") or "")
            weight = (self._number(row.get("weight")) or 0) / 100.0
            if not code or weight <= 0:
                continue
            benchmark_total_weight += weight
            stock_return = stock_returns.get(code)
            if stock_return is None:
                continue
            benchmark_return_weight += weight
            industry = industries.get(code) or "未知"
            bucket = benchmark_industries.setdefault(industry, {"weight": 0.0, "weighted_return": 0.0})
            bucket["weight"] += weight
            bucket["weighted_return"] += weight * stock_return

        for bucket in benchmark_industries.values():
            weight = bucket["weight"]
            weighted_return = bucket.pop("weighted_return")
            bucket["return"] = weighted_return / weight if weight > 0 else None

        portfolio_coverage = min(disclosed_weight, 1.0)
        benchmark_coverage = benchmark_return_weight / benchmark_total_weight if benchmark_total_weight > 0 else 0.0
        holding_return_coverage = return_weight / disclosed_weight if disclosed_weight > 0 else 0.0
        attribution = BrinsonAttributor().calculate_from_industry_inputs(
            portfolio_industries=portfolio_industries,
            benchmark_industries=benchmark_industries,
            fund_return=fund_return,
            benchmark_return=benchmark_return,
            portfolio_coverage=portfolio_coverage,
            benchmark_coverage=benchmark_coverage,
            return_coverage=holding_return_coverage,
        )
        missing_items = list(attribution.get("missing_items") or [])
        if benchmark_source == "fund_declared_benchmark_equity_component":
            weight = benchmark_detail.get("declared_weight")
            weight_text = f"{float(weight):.0%}" if weight is not None else "部分"
            missing_items.append(
                f"基金合同复合基准中权益指数权重为 {weight_text}；"
                "本次仅以该指数作为权益行业参照，基金整体主动收益仍包含非权益资产和未披露持仓影响。"
            )
        return {
            "method": "brinson_fachler",
            "status": "partial_evidence" if missing_items and attribution.get("status") == "ok" else attribution.get("status", "insufficient_evidence"),
            "source": "tushare.fund_portfolio+index_weight+daily+adj_factor+fund_nav",
            "benchmark": benchmark_code,
            "benchmark_source": benchmark_source,
            "benchmark_detail": benchmark_detail,
            "period": {
                "quarter": attribution_quarter,
                "start": first_trade,
                "end": last_trade,
                "holding_snapshot_quarter": holding_quarter,
                "benchmark_weight_date": selected_weight_date,
            },
            "returns": {
                "fund": round(fund_return, 6),
                "benchmark": round(benchmark_return, 6),
                "active": round(fund_return - benchmark_return, 6),
            },
            "effects": [
                {"name": "allocation", "label": "行业配置效应", "value": attribution.get("allocation_effect")},
                {"name": "selection", "label": "行业内选择效应", "value": attribution.get("selection_effect")},
                {"name": "interaction", "label": "交互效应", "value": attribution.get("interaction_effect")},
                {"name": "residual", "label": "未披露持仓与残差", "value": attribution.get("residual")},
            ],
            "industry_detail": attribution.get("industry_details") or [],
            "coverage": attribution.get("coverage") or {},
            "missing_items": missing_items,
        }

    def _adjusted_stock_returns(self, start_prices: Any, end_prices: Any, start_factors: Any, end_factors: Any) -> Dict[str, float]:
        def values(frame: Any, field: str) -> Dict[str, float]:
            if frame is None or frame.empty:
                return {}
            return {
                str(row["ts_code"]): float(row[field])
                for _, row in frame.iterrows()
                if row.get("ts_code") and self._number(row.get(field)) is not None
            }

        start_close = values(start_prices, "close")
        end_close = values(end_prices, "close")
        start_factor = values(start_factors, "adj_factor")
        end_factor = values(end_factors, "adj_factor")
        returns = {}
        for code in set(start_close) & set(end_close):
            start_value = start_close[code] * start_factor.get(code, 1.0)
            end_value = end_close[code] * end_factor.get(code, 1.0)
            if start_value > 0:
                returns[code] = end_value / start_value - 1
        return returns

    def _frame_return(self, frame: Any, value_columns: Tuple[str, ...], date_column: str) -> Optional[float]:
        if frame is None or frame.empty:
            return None
        frame = frame.sort_values(date_column)
        for column in value_columns:
            if column not in frame.columns:
                continue
            values = frame[column].dropna()
            if len(values) >= 2 and float(values.iloc[0]) > 0:
                return float(values.iloc[-1]) / float(values.iloc[0]) - 1
        return None

    def _safe_analysis(self, call, message: str) -> Dict[str, Any]:
        try:
            return call()
        except Exception as exc:
            return {
                "status": "insufficient_evidence",
                "source": "evidence_gate",
                "missing_items": [f"{message}：{exc.__class__.__name__}"],
            }

    def _missing_brinson(
        self,
        benchmark_code: Optional[str],
        attribution_quarter: str,
        holding_quarter: str,
        missing_items: List[str],
        status: str = "insufficient_evidence",
    ) -> Dict[str, Any]:
        return {
            "method": "brinson_fachler",
            "status": status,
            "source": "evidence_gate",
            "benchmark": benchmark_code,
            "period": {
                "quarter": attribution_quarter,
                "holding_snapshot_quarter": holding_quarter,
            },
            "returns": {"fund": None, "benchmark": None, "active": None},
            "effects": [],
            "industry_detail": [],
            "coverage": {},
            "missing_items": missing_items,
        }

    def _resolve_benchmark(
        self,
        benchmark: Optional[str],
        classification_context: Dict[str, Any],
    ) -> Tuple[Optional[str], str]:
        value = str(benchmark or "").strip().upper()
        if not value:
            mapping = classification_context.get("benchmark_mapping") or {}
            value = str(mapping.get("benchmark_code") or "").strip().upper()
            source = "fund_classification_catalog" if value else "missing_classification_benchmark"
        else:
            source = "user_override"
        if re.fullmatch(r"\d{6}", value):
            suffix = ".SZ" if value.startswith("399") else ".SH"
            value = f"{value}{suffix}"
        return (value or None), source

    def _resolve_attribution_benchmark(
        self,
        benchmark: Optional[str],
        classification_context: Dict[str, Any],
        fund: Dict[str, Any],
    ) -> Tuple[Optional[str], str, Dict[str, Any]]:
        code, source = self._resolve_benchmark(benchmark, classification_context)
        if benchmark:
            return code, source, {
                "role": "user_override",
                "benchmark_code": code,
                "benchmark_name": code,
            }
        if code and re.fullmatch(r"[0-9A-Z]{6,12}\.(SH|SZ|CSI)", code):
            mapping = classification_context.get("benchmark_mapping") or {}
            return code, source, {
                "role": "classification_benchmark",
                "benchmark_code": code,
                "benchmark_name": mapping.get("benchmark_name") or classification_context.get("primary_benchmark") or code,
                "benchmark_type": mapping.get("benchmark_type"),
                "confidence": mapping.get("confidence"),
            }

        raw_data = fund.get("raw_data") if isinstance(fund.get("raw_data"), dict) else {}
        universe = raw_data.get("universe") if isinstance(raw_data.get("universe"), dict) else {}
        info = raw_data.get("info") if isinstance(raw_data.get("info"), dict) else {}
        declared_benchmark = (
            universe.get("benchmark")
            or info.get("benchmark")
            or fund.get("benchmark")
            or ""
        )
        from services.fund_classification_catalog import FundClassificationCatalog

        resolved = FundClassificationCatalog.resolve_declared_equity_benchmark(str(declared_benchmark))
        if resolved:
            return (
                str(resolved["benchmark_code"]),
                "fund_declared_benchmark_equity_component",
                {**resolved, "role": "equity_component_reference"},
            )
        return None, "missing_verifiable_attribution_benchmark", {
            "role": "unavailable",
            "classification_benchmark": code,
            "declared_benchmark": declared_benchmark or None,
        }

    def _get_classification_adapter(self):
        if self._classification_adapter is None:
            from repositories import get_fund_classification_repo

            self._classification_adapter = get_fund_classification_repo()
        return self._classification_adapter

    def _normalize_quarter(self, quarter: Optional[str]) -> Optional[str]:
        value = str(quarter or "").strip().upper()
        return value if re.fullmatch(r"\d{4}Q[1-4]", value) else None

    def _latest_completed_quarter(self) -> str:
        now = datetime.now()
        current_quarter = (now.month - 1) // 3 + 1
        if current_quarter == 1:
            return f"{now.year - 1}Q4"
        return f"{now.year}Q{current_quarter - 1}"

    def _previous_quarter(self, quarter: str) -> str:
        year = int(quarter[:4])
        number = int(quarter[-1])
        return f"{year - 1}Q4" if number == 1 else f"{year}Q{number - 1}"

    def _quarter_dates(self, quarter: str) -> Tuple[str, str]:
        year = int(quarter[:4])
        number = int(quarter[-1])
        starts = {1: "0101", 2: "0401", 3: "0701", 4: "1001"}
        ends = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}
        return f"{year}{starts[number]}", f"{year}{ends[number]}"

    def _barra_factor_names(self) -> set:
        from lib.barra.factor_calculation import BARRA_FACTORS

        return set(BARRA_FACTORS)

    def _number(self, value: Any) -> Optional[float]:
        try:
            number = float(value)
            return number if number == number else None
        except (TypeError, ValueError):
            return None
