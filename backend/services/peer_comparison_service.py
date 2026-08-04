"""
同类分位与基金对比矩阵服务

面向投研筛选场景，把“绝对指标”翻译成“同类相对位置”和“横向优劣矩阵”。
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from services.fund_classification_service import FundClassificationService
from services.professional_scoring_service import ProfessionalScoringService


class PeerComparisonService:
    """同类分位与多基金对比入口。"""

    MIN_VALID_PEERS = 5

    METRIC_CONFIGS = [
        {"metric_name": "annualized_return", "label": "1Y 年化收益", "unit": "percent", "higher_is_better": True},
        {"metric_name": "max_drawdown", "label": "1Y 最大回撤", "unit": "percent", "higher_is_better": True},
        {"metric_name": "annualized_volatility", "label": "1Y 年化波动", "unit": "percent", "higher_is_better": False},
        {"metric_name": "sharpe_ratio", "label": "1Y 夏普比率", "unit": "number", "higher_is_better": True},
        {"metric_name": "calmar_ratio", "label": "1Y Calmar", "unit": "number", "higher_is_better": True},
        {"metric_name": "positive_return_ratio", "label": "1Y 正收益占比", "unit": "percent", "higher_is_better": True},
    ]

    def __init__(
        self,
        scoring_service: Optional[ProfessionalScoringService] = None,
        classification_service: Optional[FundClassificationService] = None,
        classification_adapter: Optional[Any] = None,
        fund_repo: Optional[Any] = None,
        profile_repo: Optional[Any] = None,
    ):
        self.scoring_service = scoring_service or ProfessionalScoringService()
        self.classification_service = classification_service or FundClassificationService()
        self._classification_adapter = classification_adapter
        self._fund_repo_adapter = fund_repo
        self._profile_repo_adapter = profile_repo

    def build_peer_percentiles(self, wind_code: str, window: str = "1y") -> Dict[str, Any]:
        target, peer_funds, peer_group_source = self._peer_universe(wind_code)
        target_id = target.get("wind_code") or wind_code
        peer_codes = [fund["wind_code"] for fund in peer_funds if fund.get("wind_code")]
        metric_map = self._metric_map(peer_codes, peer_funds)
        target_profile = target.get("research_profile") or {}
        classification = target.get("classification") or self.classification_service.classify(target, target_profile)
        minimum_peer_count = self._minimum_peer_count(classification.get("minimum_peer_count"))
        scoring_map = self._fast_peer_score_map(
            peer_codes,
            metric_map,
            window,
            classification.get("evaluation_profile_key"),
        )

        metrics: Dict[str, Any] = {}
        for config in self.METRIC_CONFIGS:
            metric_name = config["metric_name"]
            values = [
                (code, self._to_float(metric_map.get(code, {}).get(window, {}).get(metric_name)))
                for code in peer_codes
            ]
            metrics[metric_name] = self._rank_metric(
                target_id=target_id,
                values=values,
                higher_is_better=config["higher_is_better"],
                metric_name=metric_name,
                label=config["label"],
                unit=config["unit"],
                minimum_peer_count=minimum_peer_count,
            )

        professional_values = [
            (code, self._to_float(scoring_map.get(code, {}).get("overall_score")))
            for code in peer_codes
        ]
        metrics["professional_score"] = self._rank_metric(
            target_id=target_id,
            values=professional_values,
            higher_is_better=True,
            metric_name="professional_score",
            label="专业综合评分",
            unit="score",
            minimum_peer_count=minimum_peer_count,
        )

        return {
            "target_id": target_id,
            "name": target.get("name"),
            "fund_type": target.get("type"),
            "peer_group": classification.get("peer_group") or target_profile.get("peer_group"),
            "primary_benchmark": classification.get("primary_benchmark") or target_profile.get("primary_benchmark"),
            "peer_group_source": peer_group_source,
            "classification": classification,
            "evaluation_scope": "category_relative",
            "peer_count": len(peer_codes),
            "minimum_valid_peer_count": minimum_peer_count,
            "usable_metric_count": self._usable_metric_count(metrics),
            "insufficient_metric_count": self._insufficient_metric_count(metrics),
            "peer_metric_gap": self._peer_metric_gap(
                metrics,
                peer_funds,
                metric_map,
                window,
                target_id,
                minimum_peer_count,
            ),
            "sample_status": self._sample_status(metrics),
            "metric_window": window,
            "professional_score_source": "category_specific_peer_metric_proxy",
            "product_scope": {
                "fund_classification": "core",
                "fund_evaluation": "core",
                "investment_decision": "excluded",
            },
            "metrics": metrics,
        }

    def build_comparison_matrix(self, wind_codes: List[str], window: str = "1y") -> Dict[str, Any]:
        codes = []
        for code in wind_codes:
            normalized = str(code).strip()
            if normalized and normalized not in codes:
                codes.append(normalized)
        if len(codes) < 2:
            raise ValueError("至少需要两只基金进行对比")
        if len(codes) > 10:
            raise ValueError("单次最多对比 10 只基金")

        from repositories import get_metric_snapshot_repo

        fund_repo = self._get_fund_repo()
        profile_repo = self._get_profile_repo()
        metric_repo = get_metric_snapshot_repo()

        funds = []
        percentile_map = {}
        for code in codes:
            fund = fund_repo.get_fund_by_identifier(code)
            if not fund:
                continue
            wind_code = fund.get("wind_code")
            profile = profile_repo.get_profile(wind_code) or {}
            panel = self._merge_metric_windows(
                self._metrics_by_window(metric_repo.get_latest_panel("fund", wind_code)),
                self._fund_fallback_metrics(fund),
            )
            scoring = self._safe_score(wind_code)
            percentiles = self.build_peer_percentiles(wind_code, window=window)
            classification = percentiles.get("classification") or scoring.get("classification") or {}
            percentile_map[wind_code] = percentiles
            funds.append({
                "wind_code": wind_code,
                "name": fund.get("name"),
                "type": fund.get("type"),
                "peer_group": classification.get("peer_group") or profile.get("peer_group"),
                "primary_benchmark": classification.get("primary_benchmark") or profile.get("primary_benchmark"),
                "peer_count": percentiles.get("peer_count"),
                "metrics": panel.get(window, {}),
                "professional_score": scoring.get("overall_score"),
                "professional_grade": scoring.get("overall_grade"),
                "peer_percentiles": percentiles.get("metrics", {}),
            })

        if len(funds) < 2:
            raise ValueError("可用基金少于两只，无法生成对比矩阵")

        rows = [self._matrix_row(config, funds, window) for config in self.METRIC_CONFIGS]
        rows.append(self._matrix_row({
            "metric_name": "professional_score",
            "label": "专业综合评分",
            "unit": "score",
            "higher_is_better": True,
            "source": "professional_scoring",
        }, funds, window))
        observations = self._evaluation_observations(funds, rows)

        return {
            "metric_window": window,
            "funds": [
                {
                    "wind_code": fund["wind_code"],
                    "name": fund["name"],
                    "type": fund["type"],
                    "peer_group": fund["peer_group"],
                    "primary_benchmark": fund["primary_benchmark"],
                    "peer_count": fund["peer_count"],
                    "professional_score": fund["professional_score"],
                    "professional_grade": fund["professional_grade"],
                }
                for fund in funds
            ],
            "matrix_rows": rows,
            "evaluation_observations": observations,
            # 兼容旧前端字段；内容只描述评价事实，不输出候选、观察池或尽调处置。
            "recommendations": observations,
            "product_scope": {
                "fund_evaluation": "core",
                "investment_decision": "excluded",
            },
        }

    def _peer_universe(self, wind_code: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str]:
        fund_repo = self._get_fund_repo()
        profile_repo = self._get_profile_repo()
        target = fund_repo.get_fund_by_identifier(wind_code) or {"wind_code": wind_code}
        target_code = target.get("wind_code") or wind_code
        target_profile = profile_repo.get_profile(target_code) or {}
        target["research_profile"] = target_profile
        standardized_context = self._get_classification_adapter().get_classification_context(target_code)
        target["standardized_classification"] = standardized_context
        classification = self.classification_service.classify(target, target_profile, standardized_context)
        target["classification"] = classification

        if standardized_context.get("status") == "resolved":
            peer_group_id = classification.get("peer_group_id")
            if classification.get("status") == "classified" and peer_group_id:
                peers = self._get_classification_adapter().list_peer_funds(
                    peer_group_id,
                    target_wind_code=target_code,
                )
                source = "standardized_peer_group_membership"
            else:
                peers = []
                source = "standardized_peer_group_missing"
        else:
            peer_group = target_profile.get("peer_group")
            peers = self._query_peer_funds_by_profile(peer_group) if peer_group else []
            source = "research_profile_peer_group"

            if len(peers) < self.MIN_VALID_PEERS:
                compatible_types = classification.get("compatible_fund_types") or []
                if classification.get("status") == "classified" and compatible_types:
                    peers = self._query_peer_funds_by_types(compatible_types)
                    source = "classification_fund_type_fallback"
                else:
                    peers = []
                    source = "classification_insufficient_evidence"

        if not any(fund.get("wind_code") == target_code for fund in peers):
            peers.append(target)

        profile_map = profile_repo.list_profiles([fund.get("wind_code") for fund in peers if fund.get("wind_code")])
        for fund in peers:
            fund["research_profile"] = profile_map.get(fund.get("wind_code"), {})

        return target, peers, source

    def _get_classification_adapter(self):
        if self._classification_adapter is None:
            from repositories import get_fund_classification_repo

            self._classification_adapter = get_fund_classification_repo()
        return self._classification_adapter

    def _query_peer_funds_by_profile(self, peer_group: str) -> List[Dict[str, Any]]:
        if not peer_group:
            return []
        from sqlalchemy import text

        sql = """
            SELECT f.*
            FROM funds f
            JOIN fund_research_profiles p ON p.wind_code = f.wind_code
            WHERE p.peer_group = :peer_group
            ORDER BY f.wind_code ASC
            LIMIT 2000
        """
        with self._get_fund_repo().engine.connect() as conn:
            rows = conn.execute(text(sql), {"peer_group": peer_group}).fetchall()
        return [dict(row._mapping) for row in rows]

    def _query_peer_funds_by_types(self, fund_types: List[str]) -> List[Dict[str, Any]]:
        normalized_types = [str(item).strip() for item in fund_types if str(item or "").strip()]
        if not normalized_types:
            return []
        from sqlalchemy import text

        sql = """
            SELECT *
            FROM funds
            WHERE type = ANY(:fund_types)
            ORDER BY wind_code ASC
            LIMIT 2000
        """
        with self._get_fund_repo().engine.connect() as conn:
            rows = conn.execute(text(sql), {"fund_types": normalized_types}).fetchall()
        return [dict(row._mapping) for row in rows]

    def _get_fund_repo(self):
        if self._fund_repo_adapter is None:
            from repositories import get_fund_repo

            self._fund_repo_adapter = get_fund_repo()
        return self._fund_repo_adapter

    def _get_profile_repo(self):
        if self._profile_repo_adapter is None:
            from repositories import get_research_profile_repo

            self._profile_repo_adapter = get_research_profile_repo()
        return self._profile_repo_adapter

    def _metric_map(self, wind_codes: List[str], fund_rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
        from repositories import get_metric_snapshot_repo

        repo = get_metric_snapshot_repo()
        fund_map = {fund.get("wind_code"): fund for fund in (fund_rows or []) if fund.get("wind_code")}
        batch_panels = repo.get_latest_panels("fund", wind_codes)
        return {
            code: self._merge_metric_windows(
                self._metrics_by_window(batch_panels.get(code, [])),
                self._fund_fallback_metrics(fund_map.get(code, {})),
            )
            for code in wind_codes
        }

    def _merge_metric_windows(
        self,
        primary: Dict[str, Dict[str, float]],
        fallback: Dict[str, Dict[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        merged = {window: values.copy() for window, values in primary.items()}
        for window, values in fallback.items():
            target = merged.setdefault(window, {})
            for metric_name, value in values.items():
                if target.get(metric_name) is None and value is not None:
                    target[metric_name] = value
        return merged

    def _first_metric(self, source: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for key in keys:
            value = self._to_float(source.get(key))
            if value is not None:
                return value
        return None

    def _fund_fallback_metrics(self, fund: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        performance = fund.get("performance_data") or fund.get("performance") or {}
        risk = fund.get("risk_metrics") or {}
        one_year = {
            "annualized_return": self._first_metric(performance, ["annualized_return_1y", "return_1y", "annual_return"]),
            "max_drawdown": self._first_metric(risk, ["max_drawdown_1y", "max_drawdown_2y", "max_drawdown"])
                or self._first_metric(performance, ["max_drawdown"]),
            "annualized_volatility": self._first_metric(risk, ["annualized_volatility_1y", "volatility"])
                or self._first_metric(performance, ["volatility"]),
            "sharpe_ratio": self._first_metric(performance, ["sharpe_ratio", "sharpe"]),
            "calmar_ratio": self._first_metric(performance, ["calmar_ratio"]),
            "positive_return_ratio": self._first_metric(performance, ["positive_return_ratio", "win_rate_1y"]),
        }
        cleaned = {key: value for key, value in one_year.items() if value is not None}
        return {"1y": cleaned} if cleaned else {}

    def _metrics_by_window(self, panel: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        metrics: Dict[str, Dict[str, float]] = {}
        for item in panel:
            window = item.get("metric_window") or "latest"
            metric_name = item.get("metric_name")
            value = self._to_float(item.get("metric_value"))
            if metric_name and value is not None:
                metrics.setdefault(window, {})[metric_name] = value
        return metrics

    def _scoring_map(self, wind_codes: List[str]) -> Dict[str, Dict[str, Any]]:
        return {code: self._safe_score(code) for code in wind_codes}

    def _fast_peer_score_map(
        self,
        peer_codes: List[str],
        metric_map: Dict[str, Dict[str, Dict[str, float]]],
        window: str,
        evaluation_profile_key: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        return {
            code: {
                "overall_score": self._fast_peer_score(
                    metric_map.get(code, {}).get(window, {}),
                    evaluation_profile_key,
                )
            }
            for code in peer_codes
        }

    def _fast_peer_score(
        self,
        metrics: Dict[str, Any],
        evaluation_profile_key: Optional[str],
    ) -> Optional[float]:
        rule_profile = self.scoring_service.TYPE_PROFILES.get(evaluation_profile_key or "")
        if not rule_profile:
            return None
        return_low, return_high = rule_profile["return_range"]
        drawdown_low, drawdown_high = rule_profile["drawdown_range"]
        volatility_high, volatility_low = rule_profile["volatility_range"]
        pieces = [
            self._normalize_score(self._to_float(metrics.get("annualized_return")), return_low, return_high),
            self._normalize_score(self._drawdown_for_score(metrics.get("max_drawdown")), drawdown_low, drawdown_high),
            self._normalize_score(
                self._to_float(metrics.get("annualized_volatility")),
                volatility_high,
                volatility_low,
                higher_is_better=False,
            ),
            self._normalize_score(self._to_float(metrics.get("sharpe_ratio")), 0.0, 2.0),
            self._normalize_score(self._to_float(metrics.get("positive_return_ratio")), 0.45, 0.70),
        ]
        valid = [piece for piece in pieces if piece is not None]
        if len(valid) < 2:
            return None
        return round(sum(valid) / len(valid), 2)

    def _drawdown_for_score(self, value: Any) -> Optional[float]:
        drawdown = self._to_float(value)
        if drawdown is None:
            return None
        return -abs(drawdown)

    def _normalize_score(
        self,
        value: Optional[float],
        low: float,
        high: float,
        higher_is_better: bool = True,
    ) -> Optional[float]:
        if value is None:
            return None
        if low == high:
            return None
        minimum = min(low, high)
        maximum = max(low, high)
        clipped = min(max(value, minimum), maximum)
        if higher_is_better:
            ratio = (clipped - low) / (high - low)
        else:
            ratio = (low - clipped) / (low - high)
        return max(0.0, min(100.0, ratio * 100.0))

    def _safe_score(self, wind_code: str) -> Dict[str, Any]:
        try:
            return self.scoring_service.score_fund(wind_code)
        except Exception:
            return {"overall_score": None, "overall_grade": None}

    def _rank_metric(
        self,
        target_id: str,
        values: List[Tuple[str, Optional[float]]],
        higher_is_better: bool,
        metric_name: str,
        label: str,
        unit: str,
        minimum_peer_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        minimum = self._minimum_peer_count(minimum_peer_count)
        valid = [(code, value) for code, value in values if value is not None]
        target_value = next((value for code, value in valid if code == target_id), None)
        if len(valid) < minimum:
            return {
                "metric_name": metric_name,
                "label": label,
                "value": None if target_value is None else round(target_value, 6),
                "percentile": None,
                "rank": None,
                "peer_count": len(valid),
                "minimum_peer_count": minimum,
                "sample_status": "insufficient_peer_sample",
                "unit": unit,
                "direction": "higher" if higher_is_better else "lower",
            }
        if target_value is None:
            return {
                "metric_name": metric_name,
                "label": label,
                "value": None,
                "percentile": None,
                "rank": None,
                "peer_count": len(valid),
                "minimum_peer_count": minimum,
                "sample_status": "target_metric_missing",
                "unit": unit,
                "direction": "higher" if higher_is_better else "lower",
            }
        sorted_values = sorted(valid, key=lambda item: item[1], reverse=higher_is_better)
        rank = next(index + 1 for index, item in enumerate(sorted_values) if item[0] == target_id)
        peer_count = len(sorted_values)
        percentile = (peer_count - rank) / (peer_count - 1) * 100
        return {
            "metric_name": metric_name,
            "label": label,
            "value": round(target_value, 6),
            "percentile": round(percentile, 2),
            "rank": rank,
            "peer_count": peer_count,
            "minimum_peer_count": minimum,
            "sample_status": "sufficient",
            "unit": unit,
            "direction": "higher" if higher_is_better else "lower",
        }

    def _sample_status(self, metrics: Dict[str, Any]) -> str:
        metric_statuses = {metric.get("sample_status") for metric in metrics.values() if isinstance(metric, dict)}
        if "sufficient" in metric_statuses:
            return "partial_sufficient" if len(metric_statuses) > 1 else "sufficient"
        if "insufficient_peer_sample" in metric_statuses:
            return "insufficient_peer_sample"
        if "target_metric_missing" in metric_statuses:
            return "target_metric_missing"
        return "unavailable"

    def _usable_metric_count(self, metrics: Dict[str, Any]) -> int:
        return sum(
            1
            for metric in metrics.values()
            if isinstance(metric, dict)
            and metric.get("sample_status") == "sufficient"
            and metric.get("percentile") is not None
        )

    def _insufficient_metric_count(self, metrics: Dict[str, Any]) -> int:
        return sum(
            1
            for metric in metrics.values()
            if isinstance(metric, dict)
            and metric.get("sample_status") in {"insufficient_peer_sample", "target_metric_missing"}
        )

    def _peer_metric_gap(
        self,
        metrics: Dict[str, Any],
        peer_funds: Optional[List[Dict[str, Any]]] = None,
        metric_map: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
        window: str = "1y",
        target_id: Optional[str] = None,
        minimum_peer_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        minimum = self._minimum_peer_count(minimum_peer_count)
        blocking_metrics = []
        required_more_funds = 0
        for metric_name, metric in metrics.items():
            if not isinstance(metric, dict) or metric.get("sample_status") != "insufficient_peer_sample":
                continue
            peer_count = int(metric.get("peer_count") or 0)
            missing_count = max(0, minimum - peer_count)
            required_more_funds = max(required_more_funds, missing_count)
            blocking_metrics.append({
                "metric_name": metric_name,
                "label": metric.get("label") or metric_name,
                "peer_count": peer_count,
                "missing_count": missing_count,
            })
        suggested_funds = self._suggest_metric_sync_funds(
            blocking_metrics,
            peer_funds or [],
            metric_map or {},
            window,
            target_id,
            max(required_more_funds, 5),
        )
        return {
            "required_more_funds": required_more_funds,
            "blocking_metrics": blocking_metrics,
            "suggested_sync_codes": [fund["wind_code"] for fund in suggested_funds],
            "suggested_sync_funds": suggested_funds,
            "next_action": "sync_peer_nav_and_rolling_metrics" if blocking_metrics else "none",
        }

    def _minimum_peer_count(self, value: Any) -> int:
        try:
            return max(2, int(value))
        except (TypeError, ValueError):
            return self.MIN_VALID_PEERS

    def _suggest_metric_sync_funds(
        self,
        blocking_metrics: List[Dict[str, Any]],
        peer_funds: List[Dict[str, Any]],
        metric_map: Dict[str, Dict[str, Dict[str, float]]],
        window: str,
        target_id: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not blocking_metrics:
            return []
        blocking_metric_names = [item["metric_name"] for item in blocking_metrics]
        candidates = []
        for fund in peer_funds:
            code = fund.get("wind_code")
            if not code or code == target_id:
                continue
            missing_metrics = [
                metric_name
                for metric_name in blocking_metric_names
                if self._to_float(metric_map.get(code, {}).get(window, {}).get(metric_name)) is None
            ]
            if not missing_metrics:
                continue
            candidates.append({
                "wind_code": code,
                "name": fund.get("name"),
                "missing_metric_count": len(missing_metrics),
                "missing_metrics": missing_metrics,
            })
        candidates.sort(key=lambda item: (-item["missing_metric_count"], item["wind_code"]))
        return candidates[: max(0, min(limit, 10))]

    def _matrix_row(self, config: Dict[str, Any], funds: List[Dict[str, Any]], window: str) -> Dict[str, Any]:
        metric_name = config["metric_name"]
        values = {}
        ranking_values = []
        for fund in funds:
            if metric_name == "professional_score":
                raw_value = self._to_float(fund.get("professional_score"))
            else:
                raw_value = self._to_float(fund.get("metrics", {}).get(metric_name))
            percentile = fund.get("peer_percentiles", {}).get(metric_name, {}).get("percentile")
            values[fund["wind_code"]] = {
                "value": None if raw_value is None else round(raw_value, 6),
                "display": self._display_value(raw_value, config["unit"]),
                "peer_percentile": percentile,
            }
            ranking_score = percentile if percentile is not None else raw_value
            if ranking_score is not None:
                ranking_values.append((fund["wind_code"], ranking_score))

        best_code = None
        if ranking_values:
            best_code = sorted(ranking_values, key=lambda item: item[1], reverse=True)[0][0]

        return {
            "metric_name": metric_name,
            "label": config["label"],
            "unit": config["unit"],
            "direction": "higher" if config["higher_is_better"] else "lower",
            "window": window if metric_name != "professional_score" else None,
            "best_code": best_code,
            "values": values,
        }

    def _evaluation_observations(self, funds: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> List[str]:
        observations = []
        score_row = next((row for row in rows if row["metric_name"] == "professional_score"), None)
        if score_row and score_row.get("best_code"):
            winner = next((fund for fund in funds if fund["wind_code"] == score_row["best_code"]), None)
            if winner:
                observations.append(f"{winner['name']} 在当前分类口径的专业综合评分中相对较高。")
        drawdown_row = next((row for row in rows if row["metric_name"] == "max_drawdown"), None)
        if drawdown_row and drawdown_row.get("best_code"):
            winner = next((fund for fund in funds if fund["wind_code"] == drawdown_row["best_code"]), None)
            if winner:
                observations.append(f"{winner['name']} 的回撤控制在本次同类对比中相对较优。")
        peer_groups = {fund.get("peer_group") for fund in funds if fund.get("peer_group")}
        if len(peer_groups) > 1:
            observations.append("本次对比跨越多个同类组，绝对指标不应被解释为同一评价口径下的排名。")
        if not observations:
            observations.append("本次同类评价没有形成明显的单项相对优势。")
        return observations

    def _display_value(self, value: Optional[float], unit: str) -> str:
        if value is None:
            return "暂无"
        if unit == "percent":
            return f"{value * 100:.2f}%"
        if unit == "score":
            return f"{value:.1f}"
        return f"{value:.2f}"

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(Decimal(str(value)))
        except Exception:
            return None
