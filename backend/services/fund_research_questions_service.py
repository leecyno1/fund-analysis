"""研究问题清单：把异常信号转成"带着问题去看资料"的待查问题，并挂接相关纪要/报告。

只读、不自动下结论。没有相关纪要时如实标注证据缺口，不虚构资料。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MAX_EVIDENCE_PER_QUESTION = 3

_ACTION_LABELS = {"manager_removed": "离任", "manager_added": "上任"}


def _fmt_pct(value: Any, digits: int = 1) -> Optional[str]:
    try:
        return f"{float(value):+.{digits}f}%"
    except (TypeError, ValueError):
        return None


def _fmt_ratio(value: Any) -> Optional[str]:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return None


def _fmt_plain_pct(value: Any, digits: int = 0) -> Optional[str]:
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return None


def _fmt_yi(value: Any) -> Optional[str]:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return None


def _question_text(anomaly: Dict[str, Any]) -> str:
    anomaly_type = str(anomaly.get("type") or "")
    description = str(anomaly.get("description") or "").strip()
    if anomaly_type == "scale_anomaly":
        change = _fmt_pct(anomaly.get("change_pct"))
        prev, now = _fmt_yi(anomaly.get("aum_prev")), _fmt_yi(anomaly.get("aum_now"))
        prev_date = anomaly.get("prev_date") or "上一可比期"
        if change and prev and now:
            return (
                f"规模较 {prev_date} 变动 {change}（{prev}→{now} 亿元），"
                "查最近纪要与季报是否解释申赎、策略容量或机构行为。"
            )
    elif anomaly_type == "drawdown_anomaly":
        dd = _fmt_ratio(anomaly.get("dd_3m"))
        ratio = _fmt_plain_pct(anomaly.get("ratio_pct"), 0)
        if dd and ratio:
            return f"近3月回撤 {dd} 已达近3年的 {ratio}，查经理在纪要中是否讨论回撤控制、市场判断与仓位应对。"
    elif anomaly_type == "concentration_change":
        change = _fmt_pct(anomaly.get("change_pct"), 1)
        prev_rows = anomaly.get("prev_rows")
        latest_rows = anomaly.get("latest_rows")
        if change:
            rows_text = (
                f"（披露 {prev_rows}→{latest_rows} 只）"
                if prev_rows is not None and latest_rows is not None else ""
            )
            return f"前十大集中度变动 {change}{rows_text}，查季报/纪要是否解释调仓逻辑与集中度取舍。"
    elif anomaly_type == "manager_change":
        name = str(anomaly.get("manager_name") or "经理")
        action = _ACTION_LABELS.get(str(anomaly.get("change_type") or ""), "变更")
        changed_at = anomaly.get("changed_at") or ""
        return f"经理 {name} {action}（{changed_at}），查交接说明、团队变化与既有结论是否需要复核。"
    return f"{description}；查相关纪要/季报是否有解释。" if description else "异常信号待解释，查相关纪要/季报。"


def _question_for(anomaly: Dict[str, Any], reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    anomaly_type = str(anomaly.get("type") or "")
    evidence: List[Dict[str, Any]] = []
    evidence_gap: Optional[str] = None
    if anomaly_type == "manager_change":
        manager_name = str(anomaly.get("manager_name") or "")
        matched = [
            report for report in reports
            if manager_name and str(report.get("manager_name") or "") == manager_name
        ]
        if matched:
            evidence = matched[:MAX_EVIDENCE_PER_QUESTION]
        else:
            evidence_gap = (
                f"暂无 {manager_name} 的相关纪要/报告，建议补充访谈或核对季报。"
                if manager_name else "暂无相关纪要/报告，建议补充访谈或核对季报。"
            )
    elif reports:
        evidence = reports[:MAX_EVIDENCE_PER_QUESTION]
    else:
        evidence_gap = "暂无相关纪要/报告，建议补充访谈或季报核对。"

    evidence = [
        {
            "report_id": str(report.get("report_id") or report.get("id") or ""),
            "title": str(report.get("title") or ""),
            "report_date": str(report.get("report_date") or ""),
            "manager_name": str(report.get("manager_name") or ""),
        }
        for report in evidence
    ]
    return {
        "key": f"{anomaly_type}:{anomaly.get('wind_code') or ''}",
        "anomaly_type": anomaly_type,
        "wind_code": str(anomaly.get("wind_code") or ""),
        "question": _question_text(anomaly),
        "evidence": evidence,
        "evidence_gap": evidence_gap,
        "anomaly": anomaly,
    }


def build_research_questions(
    anomalies: List[Dict[str, Any]],
    reports: List[Dict[str, Any]],
    fund_code: str,
) -> Dict[str, Any]:
    if not anomalies:
        return {
            "status": "no_anomalies",
            "wind_code": fund_code,
            "question_count": 0,
            "questions": [],
            "methodology": "anomaly_to_research_questions_v1",
            "limitations": [
                "没有异常不等于没有风险；本清单只把已触发的异常转成待查问题。",
                "问题不自动下结论，需结合纪要、季报和访谈人工判断。",
            ],
        }
    questions = [_question_for(anomaly, reports) for anomaly in anomalies]
    return {
        "status": "available",
        "wind_code": fund_code,
        "question_count": len(questions),
        "questions": questions,
        "methodology": "anomaly_to_research_questions_v1",
        "limitations": [
            "问题由异常信号模板化生成，只提示核查方向，不构成结论或建议。",
            "证据仅匹配本地纪要/报告；无匹配时标注缺口，不虚构资料。",
        ],
    }


class FundResearchQuestionsService:
    """单只基金的异常→研究问题清单（只读）。"""

    def __init__(self, scanner: Optional[Any] = None, fund_repo: Optional[Any] = None):
        self._scanner = scanner
        self._fund_repo = fund_repo

    @property
    def scanner(self):
        if self._scanner is None:
            from services.anomaly_scanner_service import AnomalyScannerService

            self._scanner = AnomalyScannerService()
        return self._scanner

    @property
    def fund_repo(self):
        if self._fund_repo is None:
            from repositories import get_fund_repo

            self._fund_repo = get_fund_repo()
        return self._fund_repo

    def get(self, wind_code: str) -> Dict[str, Any]:
        code = str(wind_code or "").strip().upper()
        if not code:
            raise ValueError("wind_code is required")
        fund = self.fund_repo.get_fund_by_identifier(code)
        if not fund:
            raise ValueError(f"Fund not found: {code}")
        scan = self.scanner.scan_fund(code)
        manager_ids = [
            str(item) for item in (fund.get("manager_ids") or []) if str(item).strip()
        ]
        reports: List[Dict[str, Any]] = []
        report_error: Optional[str] = None
        try:
            reports = self._reports(code, manager_ids)
        except Exception as exc:
            report_error = f"{type(exc).__name__}: {exc}"
        result = build_research_questions(scan.get("anomalies") or [], reports, code)
        result.update({
            "scan_status": scan.get("status"),
            "scan_errors": scan.get("errors") or {},
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "local.postgres.anomaly_scan+research_reports",
            "simulation_used": False,
            "product_scope": {"fund_evaluation": "supporting_evidence", "investment_decision": "excluded"},
        })
        if report_error:
            result["report_error"] = report_error
        return result

    def _reports(self, code: str, manager_ids: List[str]) -> List[Dict[str, Any]]:
        from database import get_engine
        from sqlalchemy import text

        sql = text("""
            SELECT id, title, report_date, manager_name
            FROM research_reports
            WHERE (:code = ANY(COALESCE(fund_ids, ARRAY[]::TEXT[])))
               OR (
                    :has_managers
                    AND manager_id = ANY(CAST(:manager_ids AS TEXT[]))
               )
            ORDER BY report_date DESC NULLS LAST, updated_at DESC
            LIMIT 8
        """)
        with get_engine().connect() as conn:
            rows = conn.execute(sql, {
                "code": code,
                "has_managers": bool(manager_ids),
                "manager_ids": manager_ids or [""],
            }).fetchall()
        return [
            {
                "report_id": str(row[0]),
                "title": row[1],
                "report_date": str(row[2]) if row[2] else "",
                "manager_name": row[3],
            }
            for row in rows
        ]
