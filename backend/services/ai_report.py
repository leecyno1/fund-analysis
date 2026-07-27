"""
基金研究报告生成服务 - 支持 Anthropic 与 OpenAI-compatible API
"""
import os
import json
import logging
import urllib.error
import urllib.request
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一位专业的基金研究分析师，擅长深度分析基金经理的投资能力、风格特征和业绩归因。
你的分析报告应当:
1. 数据驱动: 结合具体数据指标进行分析
2. 深入洞察: 不仅描述现象，更挖掘背后原因
3. 客观中立: 既有亮点也有风险提示
4. 结构清晰: 使用分级标题，逻辑递进
5. 严守边界: 只输出基金研究观点和后续跟踪问题，不输出买卖建议、仓位建议、组合配置建议或下游结论
6. 证据克制: 对标记为 unavailable、missing、待补的数据，必须说明证据缺口，不能自行编造持仓、行业或风格结论

报告语言: 中文
报告格式: Markdown"""

REPORT_TYPES = {
    "fund_analysis": "分析一只基金，需要包含以下部分:\n1. 基金概况: 基本信息、规模、成立时间\n2. 业绩分析: 分年度收益、跑赢基准情况、同类排名\n3. 风险分析: 回撤控制、波动率、风险调整收益\n4. 持仓分析: 重仓股特征、行业配置、风格暴露\n5. 归因分析: 收益来源、超额收益分解\n6. 综合评价: 优势、劣势、研究建议",
    "manager_analysis": "分析一位基金经理，需要包含以下部分:\n1. 基金经理概况: 背景、从业年限、管理规模\n2. 投资理念: 投资哲学、选股逻辑、组合管理方式\n3. 风格特征: 基于持仓和净值数据的风格判断\n4. 业绩归因: 历史业绩分析、超额收益来源\n5. 行为一致性: 理念与实际操作的一致性程度\n6. 能力边界: 擅长场景、劣势场景\n7. 综合评价: 核心优势、主要风险点",
    "comparative_analysis": "对比分析多只基金或基金经理，需要包含:\n1. 整体对比: 关键指标对比表格\n2. 收益维度: 各维度收益表现对比\n3. 风险维度: 风险特征对比\n4. 风格对比: 投资风格差异\n5. 综合结论: 各有优劣、适用场景",
    "screening_report": "基于筛选条件生成的基金推荐报告，需要包含:\n1. 筛选概况: 条件说明、筛选结果统计\n2. 推荐列表: 基金名称、评分、一句话推荐理由\n3. 重点推荐: 2-3只基金的深度分析\n4. 风险提示: 筛选结果的局限性",
}


class ClaudeReportGenerator:
    """生成基金/经理研究报告"""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-7-20250514"):
        self.provider = self._resolve_provider()
        self.api_key = api_key or self._resolve_api_key()
        self.model = os.environ.get("LLM_MODEL") or self._resolve_model(model)
        self.base_url = os.environ.get("LLM_BASE_URL") or self._resolve_base_url()
        self._client = None

    def _resolve_provider(self) -> str:
        configured = os.environ.get("LLM_PROVIDER")
        if configured:
            return configured.strip().lower()

        base_url = (
            os.environ.get("LLM_BASE_URL")
            or os.environ.get("SILICONFLOW_BASE_URL")
            or os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or ""
        ).lower()
        model = (
            os.environ.get("LLM_MODEL")
            or os.environ.get("SILICONFLOW_MODEL")
            or os.environ.get("OPENAI_COMPATIBLE_MODEL")
            or ""
        ).lower()
        if os.environ.get("SILICONFLOW_API_KEY") or "siliconflow" in base_url or "deepseek-ai/" in model:
            return "siliconflow"
        if os.environ.get("OPENAI_COMPATIBLE_API_KEY") or os.environ.get("OPENAI_BASE_URL"):
            return "openai-compatible"
        return "anthropic"

    def _resolve_api_key(self) -> Optional[str]:
        if self.provider in {"siliconflow", "deepseek", "openai-compatible"}:
            for key_name in ("LLM_API_KEY", "SILICONFLOW_API_KEY", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_API_KEY"):
                value = (os.environ.get(key_name) or "").strip()
                if len(value) >= 30:
                    return value
            return None
        return os.environ.get("ANTHROPIC_API_KEY")

    def _resolve_model(self, anthropic_default: str) -> str:
        if self.provider in {"siliconflow", "deepseek", "openai-compatible"}:
            return (
                os.environ.get("SILICONFLOW_MODEL")
                or os.environ.get("OPENAI_COMPATIBLE_MODEL")
                or "deepseek-ai/DeepSeek-V4-Flash"
            )
        return anthropic_default

    def _resolve_base_url(self) -> Optional[str]:
        if self.provider in {"siliconflow", "deepseek", "openai-compatible"}:
            return (
                os.environ.get("SILICONFLOW_BASE_URL")
                or os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
                or os.environ.get("OPENAI_BASE_URL")
                or "https://api.siliconflow.cn"
            )
        return None

    @property
    def client(self):
        if self.provider in {"siliconflow", "deepseek", "openai-compatible"}:
            return None
        if self._client is None and self.api_key:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("Anthropic SDK not available. Install with: pip install anthropic")
        return self._client

    def generate_fund_analysis(
        self,
        fund_data: Dict[str, Any],
        performance_data: Dict[str, Any],
        risk_data: Dict[str, Any],
        holdings_data: List[Dict],
        style_data: Dict[str, Any],
        scoring_result: Dict[str, Any],
        research_reports: List[Dict] = None,
        purchase_plan: str = "sip",
    ) -> str:
        """生成基金分析报告"""
        prompt = self._build_fund_prompt(
            fund_data,
            performance_data,
            risk_data,
            holdings_data,
            style_data,
            scoring_result,
            research_reports,
            purchase_plan,
        )
        return self._call_llm(prompt, "fund_analysis")

    def generate_manager_analysis(
        self,
        manager_data: Dict[str, Any],
        fund_data: Dict[str, Any],
        performance_data: Dict[str, Any],
        style_data: Dict[str, Any],
        scoring_result: Dict[str, Any],
        research_reports: List[Dict],
        manager_profile: Dict[str, Any] = None,
    ) -> str:
        """生成基金经理分析报告"""
        prompt = self._build_manager_prompt(manager_data, fund_data, performance_data, style_data, scoring_result, research_reports, manager_profile)
        return self._call_llm(prompt, "manager_analysis")

    def generate_comparative_analysis(
        self,
        targets: List[Dict[str, Any]],
        comparison_type: str = "fund",
    ) -> str:
        """生成对比分析报告"""
        prompt = self._build_comparison_prompt(targets, comparison_type)
        return self._call_llm(prompt, "comparative_analysis")

    def _to_json(self, data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def _build_fund_prompt(
        self, fund_data, performance, risk, holdings, style, scoring, reports, purchase_plan="sip"
    ) -> str:
        parts = []

        # 基金名称（避免在字符串中使用 ** 语法）
        fund_name = fund_data.get("name", "N/A")
        fund_code = fund_data.get("wind_code", "")
        safe_purchase_plan = "lump_sum" if purchase_plan == "lump_sum" else "sip"
        purchase_plan_label = "一次性买入" if safe_purchase_plan == "lump_sum" else "定投"
        purchase_plan_fields = (
            "申购状态、起购金额、限购、赎回规则、费率、销售风险等级（R1-R5）"
            if safe_purchase_plan == "lump_sum"
            else "申购状态、定投支持、定投起点、限购、赎回规则、费率、销售风险等级（R1-R5）"
        )
        parts.append("请根据以下数据，为基金 [{}] ({}) 生成一份深度分析报告。".format(fund_name, fund_code))
        parts.append(
            "\n## 买前研究口径\n"
            "- 买入方式口径：{}\n"
            "- 进入正式买前判断前必须补齐：{}\n"
            "- 评分、收益风险指标和模型分析只作为研究信号，不能输出正式买前结论；缺失销售证据不得视为中性或默认通过。".format(
                purchase_plan_label,
                purchase_plan_fields,
            )
        )

        parts.append("\n## 基金基本信息\n```json\n" + self._to_json(fund_data) + "\n```")
        parts.append("\n## 业绩数据\n```json\n" + self._to_json(performance) + "\n```")
        parts.append("\n## 风险数据\n```json\n" + self._to_json(risk) + "\n```")
        parts.append("\n## 风格数据 (Barra因子暴露)\n```json\n" + self._to_json(style) + "\n```")
        parts.append("\n## 评分结果\n```json\n" + self._to_json(scoring) + "\n```")

        # 持仓
        if holdings:
            parts.append("\n## 重仓股")
            for h in holdings[:10]:
                sname = h.get("stock_name", "")
                scode = h.get("stock_code", "")
                w = h.get("weight", 0)
                ind = h.get("industry", "N/A")
                parts.append("- {}({}): {:.2%}, 行业:{}".format(sname, scode, w, ind))

        # 调研纪要
        if reports:
            parts.append("\n## 相关调研纪要")
            for r in reports[:3]:
                title = r.get("title", "无标题")
                date = r.get("report_date", "")
                summary = r.get("summary", r.get("content", "")[:500] or "N/A")
                parts.append("\n### {} ({})\n{}\n".format(title, date, summary))

        parts.append("\n请按报告格式要求，生成一份专业、深入、数据驱动的基金分析报告。")
        return "\n".join(parts)

    def _build_manager_prompt(
        self, manager_data, fund_data, performance, style, scoring, reports, profile
    ) -> str:
        parts = []

        # 经理名称
        mgr_name = manager_data.get("name", "N/A")
        parts.append("请根据以下数据，为基金经理 [{}] 生成一份深度分析报告。".format(mgr_name))

        parts.append("\n## 基金经理信息\n```json\n" + self._to_json(manager_data) + "\n```")
        parts.append("\n## 管理的代表基金\n```json\n" + self._to_json(fund_data) + "\n```")
        parts.append("\n## 业绩数据\n```json\n" + self._to_json(performance) + "\n```")
        parts.append("\n## 风格数据\n```json\n" + self._to_json(style) + "\n```")
        parts.append("\n## 评分结果\n```json\n" + self._to_json(scoring) + "\n```")

        if reports:
            parts.append("\n## 调研纪要汇总")
            for r in reports:
                title = r.get("title", "无标题")
                date = r.get("report_date", "")
                summary = r.get("summary", "N/A")
                content = r.get("content", "")
                tags = r.get("tags", [])
                content_snippet = content[:300] + "..." if content else "N/A"
                parts.append("\n### {} ({})\n- 摘要: {}\n- 要点: {}\n- 关键词: {}".format(
                    title, date, summary, content_snippet, ", ".join(tags) if tags else "N/A"))

        if profile:
            parts.append("\n## 经理画像摘要")
            parts.append("- 核心投资理念: {}".format(profile.get("core_philosophy", "N/A")))
            parts.append("- 选股逻辑: {}".format(profile.get("stock_selection_logic", "N/A")))
            parts.append("- 能力优势: {}".format(profile.get("competence_advantages", "N/A")))
            parts.append("- 能力边界: {}".format(profile.get("competence_boundaries", "N/A")))
            parts.append("- 风格标签: {}".format(profile.get("style_label", "N/A")))
            cons = profile.get("philosophy_behavior_consistency", "N/A")
            parts.append("- 理念-行为一致性: {}%".format(cons))

        parts.append("\n请按报告格式要求，生成一份专业、深入、有洞察力的基金经理分析报告。重点关注:")
        parts.append("1. 从调研纪要中提取投资理念和风格特征")
        parts.append("2. 结合数据和纪要对业绩进行归因分析")
        parts.append("3. 评估理念与实际操作的一致性")
        parts.append("4. 给出客观的能力边界和风险提示")
        return "\n".join(parts)

    def _build_comparison_prompt(self, targets: List[Dict], comparison_type: str) -> str:
        parts = ["请对以下{}进行对比分析:\n".format(comparison_type)]
        for i, t in enumerate(targets):
            name = t.get("name", t.get("fund_name", "N/A"))
            parts.append("### {}. {}\n```json\n{}\n```".format(i + 1, name, self._to_json(t)))
        parts.append("\n请生成一份对比分析报告，包含整体对比表格、各维度分析、以及综合结论。")
        return "\n".join(parts)

    def _call_llm(self, prompt: str, report_type: str) -> str:
        """调用模型 API"""
        if self.provider in {"siliconflow", "deepseek", "openai-compatible"}:
            if not self.api_key:
                logger.warning("OpenAI-compatible API key not configured. Refusing to generate mock report.")
                return "## 报告生成失败\n\n模型 API Key 未配置；系统已阻止输出模拟研究报告，请配置真实模型服务或使用本地确定性证据报告。"
            return self._call_openai_compatible(prompt)

        if not self.client:
            logger.warning("Anthropic client not available. Refusing to generate mock report.")
            return "## 报告生成失败\n\nAnthropic 客户端或 API Key 不可用；系统已阻止输出模拟研究报告，请配置真实模型服务或使用本地确定性证据报告。"

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error("Anthropic API error: {}".format(e))
            return "## 报告生成失败\n\n错误: {}\n\n请检查API配置后重试。".format(e)

    def _call_openai_compatible(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        timeout = int(os.environ.get("LLM_TIMEOUT_SECONDS", "240"))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="ignore")
            logger.error("OpenAI-compatible API HTTP error %s: %s", error.code, detail[:500])
            return "## 报告生成失败\n\n模型服务返回错误，请检查 API Key、模型名和供应商配额。"
        except Exception as error:
            logger.error("OpenAI-compatible API error: %s", error)
            return "## 报告生成失败\n\n错误: {}\n\n请检查模型服务配置后重试。".format(error)

# 全局单例
_report_generator: Optional[ClaudeReportGenerator] = None


def get_report_generator() -> ClaudeReportGenerator:
    global _report_generator
    if _report_generator is None:
        _report_generator = ClaudeReportGenerator()
    return _report_generator
