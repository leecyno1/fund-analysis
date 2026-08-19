"""基金组合构建服务 (Portfolio Construction Service)。

研究型组合：目标配置 → 候选准入（推荐就绪池）→ 等权/自定义权重 → 组合穿透。
边界：组合是研究工具，不执行交易、不做适当性判断、不生成销售规则；
穿透分析只解释公开披露证据，覆盖率不足时披露残差。
"""
import math
from typing import Any, Dict, List, Optional

from repositories.portfolio_repo import PortfolioRepo

try:
    from backend.database import get_engine
except ModuleNotFoundError:
    from database import get_engine


MAX_SINGLE_WEIGHT = 0.40
WEIGHT_SUM_TOLERANCE = 0.005
CORRELATION_MIN_DAYS = 60
CORRELATION_LOOKBACK_DAYS = 500


class PortfolioService:
    def __init__(
        self,
        repo: Optional[PortfolioRepo] = None,
        similarity_service: Optional[Any] = None,
        style_repo: Optional[Any] = None,
    ):
        self.repo = repo or PortfolioRepo()
        if similarity_service is None:
            from services.fund_holding_similarity_service import FundHoldingSimilarityService
            similarity_service = FundHoldingSimilarityService()
        self.similarity_service = similarity_service
        if style_repo is None:
            from repositories import get_holding_style_snapshot_repo
            style_repo = get_holding_style_snapshot_repo()
        self.style_repo = style_repo

    # ─────────────── 组合 CRUD ───────────────

    def create_portfolio(self, name: str, objective: Optional[str] = None, targets: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        normalized = str(name or "").strip()
        if not normalized:
            raise ValueError("组合名称不能为空")
        portfolio = self.repo.create_portfolio({"name": normalized, "objective": objective})
        if targets:
            portfolio["targets"] = self._replace_targets(portfolio["id"], targets)
        else:
            portfolio["targets"] = []
        return portfolio

    def list_portfolios(self, status: Optional[str] = None) -> Dict[str, Any]:
        rows = self.repo.list_portfolios(status=status)
        return {
            "data": rows,
            "total": len(rows),
            "boundary": "组合为研究工具，不构成投资建议，不执行交易。",
        }

    def get_portfolio(self, portfolio_id: str) -> Dict[str, Any]:
        portfolio = self.repo.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError("组合不存在")
        holdings = self.repo.list_holdings(portfolio_id)
        portfolio["targets"] = self.repo.list_targets(portfolio_id)
        portfolio["holdings"] = [self._with_evaluation_summary(item) for item in holdings]
        portfolio["weight_summary"] = self._weight_summary(holdings)
        return portfolio

    def update_portfolio(
        self,
        portfolio_id: str,
        *,
        name: Optional[str] = None,
        objective: Optional[str] = None,
        status: Optional[str] = None,
        targets: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        existing = self.repo.get_portfolio(portfolio_id)
        if not existing:
            raise ValueError("组合不存在")
        fields: Dict[str, Any] = {}
        if name is not None:
            normalized = str(name).strip()
            if not normalized:
                raise ValueError("组合名称不能为空")
            fields["name"] = normalized
        if objective is not None:
            fields["objective"] = objective
        if status is not None:
            fields["status"] = status
        if fields:
            self.repo.update_portfolio(portfolio_id, fields)
        if targets is not None:
            self._replace_targets(portfolio_id, targets)
        return self.get_portfolio(portfolio_id)

    # ─────────────── 持仓与权重 ───────────────

    def add_holding(self, portfolio_id: str, wind_code: str, note: Optional[str] = None) -> Dict[str, Any]:
        portfolio = self.repo.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError("组合不存在")
        normalized = str(wind_code or "").strip().upper()
        admission = self.check_admission(normalized)
        if not admission["admitted"]:
            raise ValueError(admission["reason"])
        self.repo.add_holding(portfolio_id, normalized, note)
        return self.get_portfolio(portfolio_id)

    def remove_holding(self, portfolio_id: str, wind_code: str) -> Dict[str, Any]:
        if not self.repo.get_portfolio(portfolio_id):
            raise ValueError("组合不存在")
        removed = self.repo.remove_holding(portfolio_id, str(wind_code).strip().upper())
        if not removed:
            raise ValueError("持仓不存在")
        return self.get_portfolio(portfolio_id)

    def set_weights(self, portfolio_id: str, items: List[Dict[str, Any]], source: str = "custom") -> Dict[str, Any]:
        if not self.repo.get_portfolio(portfolio_id):
            raise ValueError("组合不存在")
        holdings = self.repo.list_holdings(portfolio_id)
        holding_codes = {item["wind_code"] for item in holdings}
        normalized: List[Dict[str, Any]] = []
        for item in items or []:
            code = str(item.get("wind_code") or "").strip().upper()
            weight = item.get("weight")
            if code not in holding_codes:
                raise ValueError(f"基金不在组合持仓中: {code}")
            if weight is None or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)):
                raise ValueError(f"权重必须是数字: {code}")
            weight_value = float(weight)
            if weight_value <= 0:
                raise ValueError(f"权重必须为正数: {code}")
            if weight_value > MAX_SINGLE_WEIGHT + 1e-9:
                raise ValueError(f"单只基金权重不得超过 {MAX_SINGLE_WEIGHT:.0%}: {code}")
            normalized.append({"wind_code": code, "weight": weight_value})
        if not normalized:
            raise ValueError("权重清单不能为空")
        total = sum(item["weight"] for item in normalized)
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"权重合计必须为 100%（当前 {total:.1%}）")
        self.repo.set_weights(portfolio_id, normalized, source)
        return self.get_portfolio(portfolio_id)

    def equal_weights(self, portfolio_id: str) -> Dict[str, Any]:
        holdings = self.repo.list_holdings(portfolio_id)
        if not holdings:
            raise ValueError("组合暂无持仓，无法等权")
        codes = [item["wind_code"] for item in holdings]
        if 1.0 / len(codes) > MAX_SINGLE_WEIGHT + 1e-9:
            raise ValueError(f"持仓数过少（{len(codes)} 只），等权将突破单只 {MAX_SINGLE_WEIGHT:.0%} 上限")
        weight = round(1.0 / len(codes), 6)
        items = [{"wind_code": code, "weight": weight} for code in codes]
        self.repo.set_weights(portfolio_id, items, "equal")
        return self.get_portfolio(portfolio_id)

    def check_admission(self, wind_code: str) -> Dict[str, Any]:
        """候选准入：基金必须存在于基金库且有滚动指标面板（推荐就绪口径）。"""
        from sqlalchemy import text

        normalized = str(wind_code or "").strip().upper()
        engine = get_engine()
        with engine.connect() as conn:
            fund_row = conn.execute(
                text("SELECT wind_code, name FROM funds WHERE wind_code = :code"),
                {"code": normalized},
            ).fetchone()
            if not fund_row:
                return {
                    "admitted": False,
                    "reason": f"基金不存在于本地基金库: {normalized}",
                    "wind_code": normalized,
                }
            metric_row = conn.execute(
                text(
                    """
                    SELECT MAX(as_of_date)
                    FROM metric_snapshots
                    WHERE target_type = 'fund' AND target_id = :code
                    """
                ),
                {"code": normalized},
            ).fetchone()
        latest_metric_date = metric_row[0] if metric_row else None
        if not latest_metric_date:
            return {
                "admitted": False,
                "reason": f"{normalized} 尚无滚动指标面板，不满足推荐就绪口径；请先补齐净值与滚动指标。",
                "wind_code": normalized,
            }
        return {
            "admitted": True,
            "reason": "基金存在且有滚动指标面板（推荐就绪口径）。",
            "wind_code": normalized,
            "fund_name": str(fund_row[1]) if fund_row else None,
            "latest_metric_date": str(latest_metric_date),
        }

    # ─────────────── 组合穿透分析 ───────────────

    def analyze(self, portfolio_id: str) -> Dict[str, Any]:
        portfolio = self.get_portfolio(portfolio_id)
        holdings = portfolio["holdings"]
        codes = [item["wind_code"] for item in holdings]
        weights = self._effective_weights(holdings)

        overlap = self.similarity_service.build(codes) if len(codes) >= 2 else {
            "status": "insufficient",
            "reason": "至少两只持仓才能比较重仓股重叠。",
        }
        style_aggregate = self._style_aggregate(codes, weights)
        correlation = self._correlation_matrix(codes, weights)

        return {
            "portfolio_id": portfolio_id,
            "name": portfolio["name"],
            "holding_count": len(codes),
            "codes": codes,
            "weights": weights,
            "weight_summary": portfolio["weight_summary"],
            "overlap": overlap,
            "style_aggregate": style_aggregate,
            "correlation": correlation,
            "boundary": "组合穿透只基于公开披露持仓与历史净值；覆盖率不足的结论以残差披露，不构成完整组合画像或投资建议。",
        }

    # ─────────────── 内部工具 ───────────────

    def _replace_targets(self, portfolio_id: str, targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        total = 0.0
        for item in targets or []:
            key = str(item.get("peer_group_key") or "").strip()
            if not key:
                raise ValueError("目标配置的同类组不能为空")
            weight = item.get("target_weight")
            if weight is None or not isinstance(weight, (int, float)) or float(weight) <= 0:
                raise ValueError(f"目标权重必须为正数: {key}")
            total += float(weight)
            normalized.append({
                "peer_group_key": key,
                "peer_group_name": item.get("peer_group_name"),
                "target_weight": float(weight),
                "note": item.get("note"),
            })
        if normalized and abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"目标配置权重合计必须为 100%（当前 {total:.1%}）")
        return self.repo.replace_targets(portfolio_id, normalized)

    def _with_evaluation_summary(self, holding: Dict[str, Any]) -> Dict[str, Any]:
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT overall_score, overall_grade, evaluation_window, created_at
                    FROM fund_evaluation_snapshots
                    WHERE wind_code = :code
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"code": holding["wind_code"]},
            ).fetchone()
        summary = {
            "overall_score": float(row[0]) if row and row[0] is not None else None,
            "grade": row[1] if row else None,
            "evaluation_window": row[2] if row else None,
            "evaluated_at": str(row[3].date()) if row and row[3] else None,
        }
        return {**holding, "evaluation": summary}

    @staticmethod
    def _weight_summary(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        weighted = [item for item in holdings if item.get("weight") is not None]
        total = sum(float(item["weight"]) for item in weighted)
        return {
            "holding_count": len(holdings),
            "weighted_count": len(weighted),
            "total_weight": round(total, 6),
            "is_complete": abs(total - 1.0) <= WEIGHT_SUM_TOLERANCE if weighted else False,
        }

    @staticmethod
    def _effective_weights(holdings: List[Dict[str, Any]]) -> Dict[str, float]:
        weighted = {
            item["wind_code"]: float(item["weight"])
            for item in holdings
            if item.get("weight") is not None
        }
        if weighted and abs(sum(weighted.values()) - 1.0) <= 0.05:
            return weighted
        # 未设置完整权重时按等权聚合并披露
        equal = 1.0 / len(holdings) if holdings else 0.0
        return {item["wind_code"]: equal for item in holdings}

    def _style_aggregate(self, codes: List[str], weights: Dict[str, float]) -> Dict[str, Any]:
        if not codes:
            return {"status": "insufficient", "reason": "组合暂无持仓。"}
        snapshots = self.style_repo.get_latest_map(codes)
        covered_weight = sum(weights.get(code, 0.0) for code in codes if code in snapshots)
        if not snapshots:
            return {
                "status": "insufficient",
                "reason": "组合持仓均无公开持仓风格快照，暂不能聚合风格暴露。",
                "coverage": 0.0,
            }
        factor_totals: Dict[str, Dict[str, float]] = {}
        for code in codes:
            snapshot = snapshots.get(code)
            if not snapshot:
                continue
            weight = weights.get(code, 0.0)
            for descriptor in snapshot.get("descriptors") or []:
                if not isinstance(descriptor, dict):
                    continue
                factor = str(descriptor.get("factor") or "").strip()
                exposure = descriptor.get("exposure")
                if not factor or not isinstance(exposure, (int, float)):
                    continue
                bucket = factor_totals.setdefault(factor, {
                    "label": str(descriptor.get("label") or factor),
                    "unit": descriptor.get("unit"),
                    "weighted_exposure": 0.0,
                })
                bucket["weighted_exposure"] += float(exposure) * weight
        factors = [
            {
                "factor": factor,
                "label": bucket["label"],
                "unit": bucket["unit"],
                "weighted_exposure": round(bucket["weighted_exposure"], 6),
            }
            for factor, bucket in sorted(factor_totals.items())
        ]
        return {
            "status": "available" if factors else "insufficient",
            "quarter_basis": "各持仓最新已披露季度（可能不完全一致）",
            "coverage": round(covered_weight, 6),
            "coverage_note": f"风格聚合覆盖 {covered_weight:.1%} 权重的持仓；未覆盖部分为残差。",
            "factors": factors,
        }

    def _correlation_matrix(self, codes: List[str], weights: Dict[str, float]) -> Dict[str, Any]:
        if len(codes) < 2:
            return {"status": "insufficient", "reason": "至少两只持仓才能计算净值相关性。"}
        from sqlalchemy import text

        engine = get_engine()
        returns_map: Dict[str, Dict[str, float]] = {}
        with engine.connect() as conn:
            for code in codes:
                rows = conn.execute(
                    text(
                        """
                        SELECT trade_date,
                               COALESCE(NULLIF(accum_nav, 0), NULLIF(unit_nav, 0), NULLIF(nav, 0)) AS nav_value
                        FROM fund_nav
                        WHERE wind_code = :code
                        ORDER BY trade_date DESC
                        LIMIT :limit
                        """
                    ),
                    {"code": code, "limit": CORRELATION_LOOKBACK_DAYS},
                ).fetchall()
                series: Dict[str, float] = {}
                ordered: List[Any] = list(reversed(rows))
                previous: Optional[float] = None
                for row in ordered:
                    nav_value = float(row[1]) if row[1] is not None else None
                    if nav_value is None:
                        continue
                    if previous is not None and previous != 0:
                        date_key = str(row[0])
                        series[date_key] = nav_value / previous - 1.0
                    previous = nav_value
                returns_map[code] = series
        pairs = []
        for i, code_a in enumerate(codes):
            for code_b in codes[i + 1:]:
                common = sorted(set(returns_map.get(code_a, {})) & set(returns_map.get(code_b, {})))
                if len(common) < CORRELATION_MIN_DAYS:
                    pairs.append({
                        "fund_a": code_a,
                        "fund_b": code_b,
                        "correlation": None,
                        "overlap_days": len(common),
                        "status": "insufficient_overlap",
                    })
                    continue
                values_a = [returns_map[code_a][day] for day in common]
                values_b = [returns_map[code_b][day] for day in common]
                pairs.append({
                    "fund_a": code_a,
                    "fund_b": code_b,
                    "correlation": round(self._pearson(values_a, values_b), 4),
                    "overlap_days": len(common),
                    "status": "ok",
                })
        return {
            "status": "available" if any(pair["status"] == "ok" for pair in pairs) else "insufficient",
            "lookback_days": CORRELATION_LOOKBACK_DAYS,
            "min_overlap_days": CORRELATION_MIN_DAYS,
            "pairs": pairs,
            "note": "相关性基于历史日收益率（复权净值优先）；重叠不足的配对不输出结论。",
        }

    @staticmethod
    def _pearson(xs: List[float], ys: List[float]) -> float:
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        var_x = sum((x - mean_x) ** 2 for x in xs)
        var_y = sum((y - mean_y) ** 2 for y in ys)
        if var_x == 0 or var_y == 0:
            return 0.0
        return cov / math.sqrt(var_x * var_y)
