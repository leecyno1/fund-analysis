"""基金净值证据 Module。

把货币基金短周期收益派生、标准化基准映射和基准净值对齐收口到
一个可审计 Interface；没有真实基准数据时不生成相对指标输入。
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class FundNavEvidenceService:
    """从已取得的净值序列中生成评价事实。"""

    MONEY_MARKET_SOURCE = "derived:tushare.fund_nav.adj_nav"

    def derive_money_market_facts(
        self,
        nav_series: List[Dict[str, Any]],
        fund_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从货币基金累计收益序列派生七日年化与最新万份收益。"""
        points = self._money_market_points(nav_series, fund_type)
        if len(points) < 4:
            return {}

        end_date, end_value, _ = points[-1]
        target_date = end_date - timedelta(days=7)
        candidates = [point for point in points[:-1] if point[0] <= target_date + timedelta(days=2)]
        if not candidates:
            return {}
        start_date, start_value, _ = min(
            candidates,
            key=lambda point: abs((point[0] - target_date).days),
        )
        span_days = (end_date - start_date).days
        if span_days < 5 or span_days > 9 or start_value <= 0 or end_value <= 0:
            return {}

        total_return = end_value / start_value - 1.0
        if total_return <= -1.0 or abs(total_return) > 0.10:
            return {}
        annualized_yield = (1.0 + total_return) ** (365.0 / span_days) - 1.0
        window_observations = sum(1 for item_date, _, _ in points if start_date <= item_date <= end_date)

        result: Dict[str, Any] = {
            "seven_day_annualized_yield": round(annualized_yield, 8),
            "seven_day_yield_source": self.MONEY_MARKET_SOURCE,
            "seven_day_yield_as_of": end_date.isoformat(),
            "seven_day_yield_window_days": span_days,
            "seven_day_yield_observations": window_observations,
        }
        previous_date, previous_value, _ = points[-2]
        if 0 < (end_date - previous_date).days <= 3:
            result["income_per_10000"] = round(end_value - previous_value, 6)
            result["income_per_10000_as_of"] = end_date.isoformat()
        return result

    def attach_benchmark_nav(
        self,
        nav_series: List[Dict[str, Any]],
        benchmark_series: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """仅按真实共同日期对齐基准净值，不前值填充、不伪造覆盖率。"""
        benchmark_by_date = {
            normalized_date: value
            for item in benchmark_series
            if (normalized_date := self._date_text(item.get("date") or item.get("trade_date")))
            if (value := self._positive_number(item.get("nav") or item.get("close"))) is not None
        }
        enriched = []
        matched = 0
        for item in nav_series:
            copied = dict(item)
            item_date = self._date_text(item.get("date") or item.get("trade_date"))
            benchmark_nav = benchmark_by_date.get(item_date)
            if benchmark_nav is not None:
                copied["benchmark_nav"] = benchmark_nav
                matched += 1
            else:
                copied.pop("benchmark_nav", None)
            enriched.append(copied)
        return enriched, matched

    def _money_market_points(
        self,
        nav_series: List[Dict[str, Any]],
        fund_type: Optional[str],
    ) -> List[Tuple[date, float, Optional[float]]]:
        points = []
        reported_accum_values = []
        unit_values = []
        for item in nav_series:
            item_date = self._parse_date(item.get("date") or item.get("trade_date"))
            cumulative = self._positive_number(item.get("adj_nav") or item.get("accum_nav"))
            if item_date is None or cumulative is None:
                continue
            reported_accum = self._number(item.get("reported_accum_nav"))
            unit_nav = self._number(item.get("unit_nav") or item.get("nav"))
            points.append((item_date, cumulative, unit_nav))
            reported_accum_values.append(reported_accum)
            if unit_nav is not None:
                unit_values.append(unit_nav)
        points.sort(key=lambda point: point[0])
        if not points:
            return []

        normalized_type = str(fund_type or "").strip().lower()
        explicitly_money_market = "货币" in normalized_type or "money" in normalized_type
        source_shape_is_money_market = (
            points[-1][1] > 100.0
            and bool(unit_values)
            and sum(1 for value in unit_values if 0.9 <= value <= 1.1) / len(unit_values) >= 0.8
            and sum(1 for value in reported_accum_values if value is None) / len(reported_accum_values) >= 0.8
        )
        return points if explicitly_money_market or source_shape_is_money_market else []

    @staticmethod
    def _date_text(value: Any) -> Optional[str]:
        parsed = FundNavEvidenceService._parse_date(value)
        return parsed.isoformat() if parsed else None

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if len(text) == 8 and text.isdigit():
            text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        try:
            return datetime.fromisoformat(text[:10]).date()
        except ValueError:
            return None

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed != parsed or parsed in {float("inf"), float("-inf")}:
            return None
        return parsed

    @classmethod
    def _positive_number(cls, value: Any) -> Optional[float]:
        parsed = cls._number(value)
        return parsed if parsed is not None and parsed > 0 else None


class FundNavDataEnrichmentService:
    """组合标准化基准映射、Tushare 基准 Adapter 和净值证据派生。"""

    def __init__(
        self,
        market_data_adapter: Any,
        classification_adapter: Optional[Any] = None,
        evidence_service: Optional[FundNavEvidenceService] = None,
    ):
        self.market_data_adapter = market_data_adapter
        self._classification_adapter = classification_adapter
        self.evidence_service = evidence_service or FundNavEvidenceService()

    def enrich(
        self,
        wind_code: str,
        fund_type: Optional[str],
        nav_series: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        context = self._classification_context(wind_code)
        benchmark_mapping = context.get("benchmark_mapping") or {}
        benchmark_code = str(benchmark_mapping.get("benchmark_code") or "").strip() or None
        enriched_series = list(nav_series)
        benchmark_points = 0
        benchmark_status = "mapping_missing"

        if benchmark_code:
            benchmark_status = "data_unavailable"
            try:
                benchmark_series = self.market_data_adapter.get_benchmark_nav(
                    benchmark_code,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception:
                benchmark_series = []
            enriched_series, benchmark_points = self.evidence_service.attach_benchmark_nav(
                nav_series,
                benchmark_series,
            )
            if benchmark_points >= 2:
                benchmark_status = "available"

        performance_facts = self.evidence_service.derive_money_market_facts(
            enriched_series,
            fund_type=fund_type,
        )
        return {
            "nav_series": enriched_series,
            "performance_facts": performance_facts,
            "benchmark_code": benchmark_code,
            "benchmark_mapping": benchmark_mapping or None,
            "benchmark_data_status": benchmark_status,
            "benchmark_observations": benchmark_points,
            "benchmark_source": "tushare.index_daily" if benchmark_status == "available" else None,
            "money_market_metric_status": "available" if performance_facts else "not_available",
        }

    def _classification_context(self, wind_code: str) -> Dict[str, Any]:
        try:
            return self._get_classification_adapter().get_classification_context(wind_code) or {}
        except Exception:
            return {}

    def _get_classification_adapter(self):
        if self._classification_adapter is None:
            from repositories import get_fund_classification_repo

            self._classification_adapter = get_fund_classification_repo()
        return self._classification_adapter
