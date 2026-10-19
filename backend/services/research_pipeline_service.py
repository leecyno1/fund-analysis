"""研究动线（research pipeline）：把画像→业绩→归因→持仓→同类→异常→结论串成有序步骤。

build_pipeline_steps 是纯函数（不依赖 services，可离线测）：给定事实包输出每步就绪度。
缺失一律降级（partial/blocked）并给出缺口，不冒充证据。归因步骤遵守 ADR-0004：只解释不评分。
"""
from typing import Any, Dict, List, Optional

# 就绪阈值（解释见各步）。
_NAV_READY = 240   # 约 1 年日频净值
_NAV_PARTIAL = 60
_PEER_READY = 30   # 同类可比样本下限
_BENCHMARK_MIN = 20

_STEP_DEFS = [
    ("identity", "身份识别", "先定基金画像与理论收益来源，再谈业绩"),
    ("performance", "业绩拆解", "绝对/相对收益、回撤修复、上下行捕获"),
    ("attribution", "收益来源", "配置/选择/风格贡献拆解（仅解释，不进评分）"),
    ("holdings", "持仓追踪", "连续期持仓变化：仓位不撒谎"),
    ("peer", "同类定位", "同类组内分位与比较基准"),
    ("anomalies", "异常点", "值得深挖的异常值，带着问题看资料"),
    ("conclusion", "结论", "靠什么赚/能否重复/何时失效"),
]


def _step(order: int, key: str, status: str, summary: str, evidence: Dict[str, Any],
          gap: Optional[str], link: str) -> Dict[str, Any]:
    label = next(lbl for k, lbl, _ in _STEP_DEFS if k == key)
    return {
        "order": order,
        "key": key,
        "label": label,
        "status": status,
        "summary": summary,
        "evidence": evidence,
        "gap": gap,
        "link": link,
    }


def build_pipeline_steps(facts: Dict[str, Any]) -> Dict[str, Any]:
    """把基金事实包映射为 7 步研究动线的就绪度。"""
    facts = facts or {}
    peer_group = facts.get("peer_group")
    style_label = facts.get("style_label")
    style_snapshots = int(facts.get("style_snapshots") or 0)
    nav_obs = int(facts.get("nav_observations") or 0)
    bench_obs = int(facts.get("benchmark_observations") or 0)
    capture = facts.get("capture")
    regime = facts.get("regime_performance")
    return_source = facts.get("return_source")
    holdings_count = int(facts.get("holdings_count") or 0)
    holding_quarters = int(facts.get("holding_quarters") or 0)
    peer_size = int(facts.get("peer_group_size") or 0)
    peer_ready = bool(facts.get("peer_percentile_ready"))
    anomaly_status = str(facts.get("anomaly_status") or "unknown")
    anomaly_open = facts.get("anomaly_open")
    has_score = bool(facts.get("has_score"))
    has_report = bool(facts.get("has_report"))

    steps: List[Dict[str, Any]] = []

    # 1 身份识别
    if peer_group and style_snapshots >= 1:
        steps.append(_step(1, "identity", "ready",
                           f"{peer_group} / {style_label or '风格待定'}，可比基准已锚定",
                           {"peer_group": peer_group, "benchmark_code": facts.get("benchmark_code"),
                            "style_label": style_label, "style_snapshots": style_snapshots},
                           None, "#fund-identity"))
    elif peer_group:
        steps.append(_step(1, "identity", "partial",
                           f"{peer_group}，缺风格快照",
                           {"peer_group": peer_group, "benchmark_code": facts.get("benchmark_code")},
                           "缺风格快照，标签漂移暂不可判", "#fund-identity"))
    else:
        steps.append(_step(1, "identity", "blocked", "缺同类分类，身份未定",
                           {}, "缺同类分类，后续比较无基准", "#fund-identity"))

    # 2 业绩拆解
    perf_evidence: Dict[str, Any] = {"nav_observations": nav_obs}
    perf_gap: Optional[str] = None
    if isinstance(capture, dict) and capture.get("up_capture_ratio") is not None:
        perf_evidence["capture"] = {
            "up_capture_ratio": capture.get("up_capture_ratio"),
            "down_capture_ratio": capture.get("down_capture_ratio"),
        }
    if isinstance(regime, dict) and regime.get("status") == "available":
        perf_evidence["regime_performance"] = {
            "bull_win_rate": (regime.get("regimes") or {}).get("bull", {}).get("win_rate"),
            "bear_win_rate": (regime.get("regimes") or {}).get("bear", {}).get("win_rate"),
            "range_win_rate": (regime.get("regimes") or {}).get("range", {}).get("win_rate"),
            "bull_periods": (regime.get("regimes") or {}).get("bull", {}).get("period_count"),
            "bear_periods": (regime.get("regimes") or {}).get("bear", {}).get("period_count"),
        }
    if isinstance(return_source, dict) and return_source.get("status") == "available":
        perf_evidence["return_source"] = {
            "classification": return_source.get("classification"),
            "classification_label": return_source.get("classification_label"),
            "beta": return_source.get("beta"),
            "alpha_annualized": return_source.get("alpha_annualized"),
            "alpha_t_stat": return_source.get("alpha_t_stat"),
            "r_squared": return_source.get("r_squared"),
            "alpha_replicability": return_source.get("alpha_replicability"),
            "alpha_replicability_label": return_source.get("alpha_replicability_label"),
        }
    if nav_obs >= _NAV_READY:
        perf_status = "ready"
        if bench_obs < _BENCHMARK_MIN:
            perf_gap = "基准覆盖不足，捕获率/相对指标不可算"
    elif nav_obs >= _NAV_PARTIAL:
        perf_status = "partial"
        perf_gap = "净值不足一年，长期业绩与回撤修复不可靠"
    else:
        perf_status = "blocked"
        perf_gap = "净值观测过少，无法拆解业绩"
    perf_summary = f"净值观测 {nav_obs} 天"
    if perf_evidence.get("regime_performance"):
        regime_evidence = perf_evidence["regime_performance"]
        def _pct(value):
            return "—" if value is None else f"{round(float(value) * 100)}%"
        perf_summary += (
            f"；牛市胜率 {_pct(regime_evidence.get('bull_win_rate'))}"
            f" / 熊市胜率 {_pct(regime_evidence.get('bear_win_rate'))}"
        )
    if perf_evidence.get("return_source"):
        perf_summary += f"；收益来源：{perf_evidence['return_source'].get('classification_label') or '—'}"
    steps.append(_step(2, "performance", perf_status,
                       perf_summary, perf_evidence, perf_gap, "#fund-performance"))

    # 3 收益来源（归因，仅解释）
    if holdings_count >= 5:
        steps.append(_step(3, "attribution", "ready",
                           "有最近持仓，可做配置/选择归因（仅解释）",
                           {"holdings_count": holdings_count}, None, "#fund-attribution"))
    else:
        steps.append(_step(3, "attribution", "blocked", "缺持仓，无法归因",
                           {}, "需持仓数据；按 ADR-0004 归因只解释不进评分", "#fund-attribution"))

    # 4 持仓追踪
    if holdings_count >= 5 and holding_quarters >= 2:
        steps.append(_step(4, "holdings", "ready",
                           f"{holding_quarters} 期连续持仓可追踪",
                           {"holdings_count": holdings_count, "holding_quarters": holding_quarters},
                           None, "#fund-holdings"))
    elif holdings_count >= 5:
        steps.append(_step(4, "holdings", "partial", "仅单期持仓",
                           {"holdings_count": holdings_count, "holding_quarters": holding_quarters},
                           "单期持仓，无法追踪变化与行为一致性", "#fund-holdings"))
    else:
        steps.append(_step(4, "holdings", "blocked", "缺持仓",
                           {"holdings_count": holdings_count}, "持仓缺失", "#fund-holdings"))

    # 5 同类定位
    if peer_size >= _PEER_READY and peer_ready:
        steps.append(_step(5, "peer", "ready", f"同类 {peer_size} 只，分位已就绪",
                           {"peer_group_size": peer_size, "percentile_ready": True}, None, "#fund-peer"))
    elif peer_size >= _PEER_READY:
        steps.append(_step(5, "peer", "partial", f"同类 {peer_size} 只，分位未就绪",
                           {"peer_group_size": peer_size, "percentile_ready": False},
                           "同类分位未计算，相对比较暂缺", "#fund-peer"))
    else:
        steps.append(_step(5, "peer", "blocked", f"同类样本 {peer_size} 只",
                           {"peer_group_size": peer_size}, "同类样本不足，比较无意义", "#fund-peer"))

    # 6 异常点
    questions = facts.get("research_questions")
    anomaly_evidence: Dict[str, Any] = {"open": anomaly_open}
    anomaly_summary = f"{anomaly_open if anomaly_open is not None else 0} 项未决异常"
    if isinstance(questions, dict):
        anomaly_evidence["research_questions"] = questions
        if questions.get("count"):
            anomaly_summary += f"；{questions['count']} 个待查问题"
            if questions.get("evidence_count"):
                anomaly_summary += f"（关联纪要 {questions['evidence_count']} 条）"
    if anomaly_status == "ok":
        steps.append(_step(6, "anomalies", "ready", anomaly_summary,
                           anomaly_evidence, None, "#fund-anomalies"))
    elif anomaly_status == "partial":
        steps.append(_step(6, "anomalies", "partial", "异常扫描部分可用",
                           anomaly_evidence, "扫描子系统部分失效，结果需复核", "#fund-anomalies"))
    else:
        steps.append(_step(6, "anomalies", "blocked", "异常扫描不可用",
                           anomaly_evidence, "扫描子系统不可用（见 §18.5 已知缺陷）", "#fund-anomalies"))

    # 7 结论
    if has_score or has_report:
        steps.append(_step(7, "conclusion", "ready", "已有评价/报告可收口",
                           {"has_score": has_score, "has_report": has_report}, None, "#fund-conclusion"))
    else:
        steps.append(_step(7, "conclusion", "blocked", "缺评价与报告",
                           {}, "缺评价/报告，无法回答靠什么赚/能否重复/何时失效", "#fund-conclusion"))

    ready_count = sum(1 for s in steps if s["status"] == "ready")
    blocked = any(s["status"] == "blocked" for s in steps)
    first = next((s for s in steps if s["status"] != "ready"), None)
    return {
        "status": "complete" if ready_count == len(steps) else ("blocked" if blocked else "partial"),
        "ready_count": ready_count,
        "total": len(steps),
        "first_gap": ({"key": first["key"], "label": first["label"], "gap": first["gap"]} if first else None),
        "steps": steps,
        "methodology": "research_pipeline_v1",
    }


class FundResearchPipelineService:
    """读取基金事实包并产出研究动线（只读组装现有数据，不新算评分）。"""

    def __init__(self, repos: Optional[Dict[str, Any]] = None):
        self._repos = repos

    def _repo(self, name: str):
        if self._repos and name in self._repos:
            return self._repos[name]
        import repositories
        return getattr(repositories, f"get_{name}_repo")()

    def build(self, wind_code: str) -> Dict[str, Any]:
        from services.fund_research_pipeline_facts import gather_pipeline_facts
        facts = gather_pipeline_facts(str(wind_code or "").strip().upper(), self._repo)
        result = build_pipeline_steps(facts)
        result["wind_code"] = str(wind_code or "").strip().upper()
        result["product_scope"] = {"fund_evaluation": "supporting_evidence", "investment_decision": "excluded"}
        return result
