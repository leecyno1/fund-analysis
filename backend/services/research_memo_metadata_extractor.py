"""Evidence-bound LLM metadata extraction for local research memos."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


class ResearchMemoMetadataExtractor:
    FIELD_KINDS = {
        "manager_names": "manager",
        "fund_ids": "fund",
        "classifications": "classification",
        "style_labels": "style_label",
    }

    def __init__(self, generator: Optional[Any] = None):
        self.generator = generator

    def extract(self, content: str, filename: str) -> Dict[str, Any]:
        if not self.generator:
            return {"status": "unavailable", "provider": None, "model": None, "proposals": []}
        try:
            raw = self.generator.extract_research_memo_metadata(content, filename)
            data = self._parse_json(raw)
            proposals = self._validated_proposals(data, content)
            return {
                "status": "complete",
                "provider": getattr(self.generator, "provider", None),
                "model": getattr(self.generator, "model", None),
                "proposals": proposals,
            }
        except Exception as exc:
            return {
                "status": "failed",
                "provider": getattr(self.generator, "provider", None),
                "model": getattr(self.generator, "model", None),
                "proposals": [],
                "error": str(exc),
            }

    @staticmethod
    def _parse_json(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        text = str(raw or "").strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()
        else:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                raise ValueError("模型没有返回 JSON 对象")
            text = match.group(0)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("模型结果必须是 JSON 对象")
        return parsed

    def _validated_proposals(self, data: Dict[str, Any], content: str) -> List[Dict[str, Any]]:
        proposals: List[Dict[str, Any]] = []
        seen = set()
        for field, kind in self.FIELD_KINDS.items():
            items = data.get(field, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = str(item.get("value") or "").strip()[:120]
                excerpt = re.sub(r"\s+", " ", str(item.get("excerpt") or "")).strip()[:240]
                normalized_content = re.sub(r"\s+", " ", content)
                if not value or not excerpt or excerpt not in normalized_content:
                    continue
                if kind == "fund" and not re.fullmatch(r"\d{6}\.(?:OF|SH|SZ|BJ|HK)", value.upper()):
                    continue
                if kind == "fund":
                    value = value.upper()
                try:
                    confidence = min(1.0, max(0.0, float(item.get("confidence", 0))))
                except (TypeError, ValueError):
                    continue
                identity = (kind, value)
                if identity in seen:
                    continue
                seen.add(identity)
                proposals.append({
                    "kind": kind,
                    "value": value,
                    "confidence": confidence,
                    "excerpt": excerpt,
                    "extraction_source": "llm",
                })
        return proposals


def get_research_memo_metadata_extractor() -> ResearchMemoMetadataExtractor:
    try:
        from services.ai_report import get_report_generator

        generator = get_report_generator()
        if not generator.api_key:
            return ResearchMemoMetadataExtractor(generator=None)
        return ResearchMemoMetadataExtractor(generator=generator)
    except Exception:
        return ResearchMemoMetadataExtractor(generator=None)
