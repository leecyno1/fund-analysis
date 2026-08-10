"""Read-only, incremental indexing for local research memo folders."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class FolderValidationError(ValueError):
    """Raised when a folder cannot be indexed safely."""


class LocalResearchFolderService:
    SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}
    STYLE_LABELS = (
        "成长",
        "价值",
        "均衡",
        "质量",
        "红利",
        "大盘",
        "中盘",
        "小盘",
        "低换手",
        "高换手",
        "低波",
        "行业轮动",
        "主题",
        "量化",
        "指数增强",
        "固收+",
        "信用",
        "利率",
    )
    CLASSIFICATIONS = (
        "主动权益",
        "被动指数",
        "指数增强",
        "偏股混合",
        "灵活配置",
        "纯债",
        "一级债基",
        "二级债基",
        "货币基金",
        "QDII",
        "FOF",
        "商品",
    )

    def __init__(
        self,
        repo: Any,
        manager_resolver: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        metadata_extractor: Optional[Callable[[str, str], Dict[str, Any]]] = None,
        profile_projector: Optional[Callable[[Dict[str, Any], List[str]], Dict[str, Any]]] = None,
        max_files: int = 5_000,
        max_file_bytes: int = 25 * 1024 * 1024,
    ):
        self.repo = repo
        self.manager_resolver = manager_resolver
        self.metadata_extractor = metadata_extractor
        self.profile_projector = profile_projector
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes

    def add_folder(self, raw_path: str) -> Dict[str, Any]:
        path = self._validate_folder(raw_path)
        now = self._now()
        existing = next((item for item in self.repo.list_folders() if item.get("path") == str(path)), None)
        if existing:
            return existing
        return self.repo.create_folder({
            "path": str(path),
            "name": path.name,
            "status": "ready",
            "last_scan_at": None,
            "last_scan_counts": None,
            "created_at": now,
            "updated_at": now,
        })

    def list_folders(self) -> List[Dict[str, Any]]:
        return self.repo.list_folders()

    def scan_folder(self, folder_id: str) -> Dict[str, Any]:
        folder = self.repo.get_folder(folder_id)
        if not folder:
            raise FolderValidationError("未找到已连接的调研文件夹")
        root = self._validate_folder(folder.get("path", ""))
        candidates = self._supported_files(root)
        if len(candidates) > self.max_files:
            raise FolderValidationError(f"可处理文件超过上限（{self.max_files} 份）")

        counts = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0, "supported": len(candidates)}
        results: List[Dict[str, Any]] = []
        for path in candidates:
            result = self._index_file(folder_id, root, path)
            counts[result["status"]] += 1
            results.append(result)

        scanned_at = self._now()
        self.repo.update_folder(folder_id, {
            "status": "ready" if not counts["failed"] else "completed_with_errors",
            "last_scan_at": scanned_at,
            "last_scan_counts": counts,
            "updated_at": scanned_at,
        })
        profile_projection = self._project_scan_results(results)
        return {
            "folder_id": folder_id,
            "folder_path": str(root),
            "scanned_at": scanned_at,
            "counts": counts,
            "results": results,
            "profile_projection": profile_projection,
        }

    def list_pending_reviews(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.repo.list_pending_reviews(folder_id)

    def review_proposal(self, report_id: str, proposal_id: str, action: str) -> Dict[str, Any]:
        if action not in {"confirmed", "rejected"}:
            raise ValueError("复核结果只能是 confirmed 或 rejected")
        report = self.repo.get_report(report_id)
        if not report:
            raise ValueError("未找到调研纪要")
        old_fund_ids = list(report.get("fund_ids", []))

        proposals = report.get("review_proposals", [])
        target = next((item for item in proposals if item.get("id") == proposal_id), None)
        if not target:
            raise ValueError("未找到待复核项")
        target["review_status"] = action
        target["reviewed_at"] = self._now()

        fields = {
            "manager_id": report.get("manager_id") or "",
            "manager_name": report.get("manager_name") or "",
            "classifications": list(report.get("classifications", [])),
            "style_labels": list(report.get("style_labels", [])),
            "tags": list(report.get("tags", [])),
            "fund_ids": list(report.get("fund_ids", [])),
        }
        self._apply_proposal(fields, target, confirmed=action == "confirmed")
        fields.update({
            "review_proposals": proposals,
            "review_status": "pending" if any(
                item.get("review_status") == "pending" for item in proposals
            ) else "reviewed",
            "updated_at": self._now(),
        })
        updated = self.repo.update_report(report_id, fields)
        affected_fund_ids = list(dict.fromkeys([
            *old_fund_ids,
            *(updated.get("fund_ids", []) if updated else []),
            *([target.get("value")] if target.get("kind") == "fund" else []),
        ]))
        projection = self.profile_projector(updated, affected_fund_ids) if self.profile_projector else None
        return {
            "status": action,
            "report": updated,
            "proposal": target,
            "profile_projection": projection,
        }

    def _project_scan_results(self, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not self.profile_projector:
            return None
        reports = []
        for report_id in dict.fromkeys(
            result.get("report_id") for result in results if result.get("report_id")
        ):
            report = self.repo.get_report(report_id)
            if report:
                reports.append(report)
        fund_ids = list(dict.fromkeys(
            fund_id
            for report in reports
            for fund_id in report.get("fund_ids", [])
            if fund_id
        ))
        if not fund_ids:
            return {
                "projected_count": 0,
                "deleted_count": 0,
                "skipped_count": 0,
                "funds": [],
            }
        return self.profile_projector(reports[0], fund_ids)

    def _index_file(self, folder_id: str, root: Path, path: Path) -> Dict[str, Any]:
        relative_path = path.relative_to(root).as_posix()
        try:
            resolved_path = path.resolve(strict=True)
            if not resolved_path.is_relative_to(root):
                raise ValueError("文件指向已连接文件夹之外")
            stat = resolved_path.stat()
            existing = self.repo.get_document(folder_id, relative_path)
            if existing and existing.get("size") == stat.st_size and existing.get("mtime_ns") == stat.st_mtime_ns:
                return {"relative_path": relative_path, "status": "unchanged", "report_id": existing.get("report_id")}
            if stat.st_size > self.max_file_bytes:
                raise ValueError(f"文件超过 {self.max_file_bytes // (1024 * 1024) or 1} MB 上限")

            raw = resolved_path.read_bytes()
            content_hash = hashlib.sha256(raw).hexdigest()
            if existing and existing.get("content_hash") == content_hash:
                document = self._document_record(folder_id, root, resolved_path, stat, content_hash, existing.get("report_id"), "indexed")
                self.repo.upsert_document(document)
                return {"relative_path": relative_path, "status": "unchanged", "report_id": existing.get("report_id")}

            duplicate = self.repo.find_document_by_hash(
                content_hash,
                exclude_folder_id=folder_id,
                exclude_relative_path=relative_path,
            )
            if duplicate:
                document = self._document_record(folder_id, root, resolved_path, stat, content_hash, duplicate.get("report_id"), "duplicate")
                self.repo.upsert_document(document)
                return {"relative_path": relative_path, "status": "unchanged", "report_id": duplicate.get("report_id"), "duplicate": True}

            content = self._extract_text(resolved_path, raw).strip()
            if not content:
                raise ValueError("未提取到可检索文字")
            extraction = self._extract_metadata(content, resolved_path.name)
            proposals = self._merge_proposals(
                self._extract_proposals(content, root, resolved_path),
                extraction.get("proposals", []),
                root,
                resolved_path,
            )
            now = self._now()
            report_payload = {
                "manager_id": "",
                "manager_name": "",
                "title": resolved_path.stem,
                "report_date": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).date().isoformat(),
                "source": "本地调研纪要文件夹",
                "content": content,
                "summary": self._summary(content),
                "tags": [],
                "classifications": [],
                "style_labels": [],
                "fund_ids": [],
                "key_points": self._key_points(content),
                "review_proposals": proposals,
                "review_status": "pending" if proposals else "needs_metadata",
                "local_folder_id": folder_id,
                "local_relative_path": relative_path,
                "local_source_path": str(resolved_path),
                "source_hash": content_hash,
                "extraction_status": "complete",
                "extraction_provider": extraction.get("provider") or "deterministic_rules",
                "extraction_model": extraction.get("model"),
                "llm_extraction_status": extraction.get("status") or "unavailable",
                "llm_extraction_error": extraction.get("error"),
                "created_at": now,
                "updated_at": now,
            }
            if existing and existing.get("report_id"):
                report = self.repo.update_report(existing["report_id"], self._merge_review_state(report_payload, self.repo.get_report(existing["report_id"])))
                status = "updated"
            else:
                report = self.repo.create_report(report_payload)
                status = "created"
            document = self._document_record(folder_id, root, resolved_path, stat, content_hash, report["id"], "indexed")
            self.repo.upsert_document(document)
            return {"relative_path": relative_path, "status": status, "report_id": report["id"]}
        except Exception as exc:
            try:
                stat = path.stat()
                failed = {
                    "folder_id": folder_id,
                    "relative_path": relative_path,
                    "source_path": str(path),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "content_hash": None,
                    "report_id": None,
                    "index_status": "failed",
                    "error": str(exc),
                    "updated_at": self._now(),
                }
                self.repo.upsert_document(failed)
            except OSError:
                pass
            return {"relative_path": relative_path, "status": "failed", "error": str(exc)}

    def _extract_text(self, path: Path, raw: bytes) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            for encoding in ("utf-8-sig", "gb18030"):
                try:
                    return raw.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        if suffix == ".pdf":
            from io import BytesIO
            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
        if suffix == ".docx":
            from io import BytesIO
            from docx import Document

            document = Document(BytesIO(raw))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        raise ValueError(f"不支持的文件格式：{suffix}")

    def _extract_proposals(self, content: str, root: Path, path: Path) -> List[Dict[str, Any]]:
        proposals: List[Dict[str, Any]] = []
        explicit_manager = re.search(r"基金经理\s*[：:]\s*([\u4e00-\u9fffA-Za-z·]{2,40})", content)
        if explicit_manager:
            value = explicit_manager.group(1).strip()
            candidate = self.manager_resolver(value) if self.manager_resolver else None
            proposals.append(self._proposal(
                "manager",
                value,
                path,
                root,
                self._line_excerpt(content, explicit_manager.start()),
                0.98 if candidate else 0.88,
                candidate_id=(candidate or {}).get("manager_id"),
            ))
        elif path.parent != root and 2 <= len(path.parent.name) <= 40:
            proposals.append(self._proposal(
                "manager",
                path.parent.name,
                path,
                root,
                f"文件夹：{path.parent.name}",
                0.55,
            ))

        for match in re.finditer(r"(?<!\d)(\d{6}\.(?:OF|SH|SZ|BJ|HK))(?![A-Z])", content, re.IGNORECASE):
            value = match.group(1).upper()
            proposals.append(self._proposal(
                "fund",
                value,
                path,
                root,
                self._line_excerpt(content, match.start()),
                0.92,
            ))

        for value in self.CLASSIFICATIONS:
            if value.lower() in content.lower():
                proposals.append(self._proposal(
                    "classification", value, path, root, self._excerpt_for_value(content, value), 0.78
                ))
        for value in self.STYLE_LABELS:
            if value.lower() in content.lower():
                proposals.append(self._proposal(
                    "style_label", value, path, root, self._excerpt_for_value(content, value), 0.76
                ))
        return proposals

    def _extract_metadata(self, content: str, filename: str) -> Dict[str, Any]:
        if not self.metadata_extractor:
            return {"status": "unavailable", "provider": None, "model": None, "proposals": []}
        try:
            result = self.metadata_extractor(content, filename)
            return result if isinstance(result, dict) else {"status": "failed", "proposals": [], "error": "模型提取结果格式无效"}
        except Exception as exc:
            return {"status": "failed", "provider": None, "model": None, "proposals": [], "error": str(exc)}

    def _merge_proposals(
        self,
        rule_proposals: List[Dict[str, Any]],
        model_proposals: List[Dict[str, Any]],
        root: Path,
        path: Path,
    ) -> List[Dict[str, Any]]:
        merged: Dict[tuple, Dict[str, Any]] = {
            (item.get("kind"), item.get("value")): item for item in rule_proposals
        }
        for candidate in model_proposals:
            kind = candidate.get("kind")
            value = str(candidate.get("value") or "").strip()
            if kind not in {"manager", "fund", "classification", "style_label", "tag"} or not value:
                continue
            key = (kind, value)
            proposal = self._proposal(
                kind,
                value,
                path,
                root,
                str(candidate.get("excerpt") or ""),
                float(candidate.get("confidence", 0)),
            )
            proposal["extraction_source"] = "llm"
            current = merged.get(key)
            if not current or proposal["confidence"] > current.get("confidence", 0):
                merged[key] = proposal
        return list(merged.values())

    def _proposal(
        self,
        kind: str,
        value: str,
        path: Path,
        root: Path,
        excerpt: str,
        confidence: float,
        candidate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        relative_path = path.relative_to(root).as_posix()
        identity = hashlib.sha256(f"{relative_path}\0{kind}\0{value}".encode("utf-8")).hexdigest()[:20]
        return {
            "id": identity,
            "kind": kind,
            "value": value,
            "candidate_id": candidate_id,
            "confidence": confidence,
            "review_status": "pending",
            "source_ref": {
                "relative_path": relative_path,
                "source_path": str(path),
                "excerpt": excerpt[:240],
            },
        }

    @staticmethod
    def _apply_proposal(fields: Dict[str, Any], proposal: Dict[str, Any], confirmed: bool) -> None:
        kind = proposal.get("kind")
        value = proposal.get("value")
        if kind == "manager":
            if confirmed:
                fields["manager_name"] = value
                fields["manager_id"] = proposal.get("candidate_id") or ""
            elif fields.get("manager_name") == value:
                fields["manager_name"] = ""
                fields["manager_id"] = ""
            return
        field_name = {
            "fund": "fund_ids",
            "classification": "classifications",
            "style_label": "style_labels",
            "tag": "tags",
        }.get(kind)
        if not field_name:
            return
        values = [item for item in fields.get(field_name, []) if item != value]
        if confirmed:
            values.append(value)
        fields[field_name] = list(dict.fromkeys(values))

    def _merge_review_state(self, fresh: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not existing:
            return fresh
        old_by_key = {
            (item.get("kind"), item.get("value")): item
            for item in existing.get("review_proposals", [])
            if item.get("review_status") in {"confirmed", "rejected"}
        }
        fields = {
            "manager_id": "",
            "manager_name": "",
            "classifications": [],
            "style_labels": [],
            "tags": [],
            "fund_ids": [],
        }
        for proposal in fresh["review_proposals"]:
            old = old_by_key.get((proposal.get("kind"), proposal.get("value")))
            if old:
                proposal["review_status"] = old["review_status"]
                proposal["reviewed_at"] = old.get("reviewed_at")
                proposal["candidate_id"] = old.get("candidate_id") or proposal.get("candidate_id")
            if proposal.get("review_status") == "confirmed":
                self._apply_proposal(fields, proposal, confirmed=True)
        fresh.update(fields)
        fresh["created_at"] = existing.get("created_at") or fresh["created_at"]
        fresh["review_status"] = "pending" if any(
            item.get("review_status") == "pending" for item in fresh["review_proposals"]
        ) else "reviewed"
        return fresh

    def _supported_files(self, root: Path) -> List[Path]:
        files = []
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
                continue
            files.append(path)
        return sorted(files, key=lambda item: item.relative_to(root).as_posix().casefold())

    def _validate_folder(self, raw_path: str) -> Path:
        if not str(raw_path or "").strip():
            raise FolderValidationError("请输入调研纪要文件夹路径")
        try:
            path = Path(raw_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise FolderValidationError("文件夹不存在或无法读取") from exc
        if not path.is_dir():
            raise FolderValidationError("所选路径不是文件夹")
        if path in {Path(path.anchor), Path.home().resolve()}:
            raise FolderValidationError("不能连接系统根目录或整个用户目录")
        return path

    def _document_record(
        self,
        folder_id: str,
        root: Path,
        path: Path,
        stat: Any,
        content_hash: str,
        report_id: str,
        index_status: str,
    ) -> Dict[str, Any]:
        return {
            "folder_id": folder_id,
            "relative_path": path.relative_to(root).as_posix(),
            "source_path": str(path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "content_hash": content_hash,
            "report_id": report_id,
            "index_status": index_status,
            "error": None,
            "updated_at": self._now(),
        }

    @staticmethod
    def _summary(content: str) -> str:
        return re.sub(r"\s+", " ", content).strip()[:500]

    @staticmethod
    def _key_points(content: str) -> List[str]:
        points = []
        for line in content.splitlines():
            clean = line.strip().lstrip("-•* ").strip()
            if line.strip().startswith(("-", "•", "*")) and 8 <= len(clean) <= 180:
                points.append(clean)
        return points[:5]

    @staticmethod
    def _line_excerpt(content: str, character_index: int) -> str:
        start = content.rfind("\n", 0, character_index) + 1
        end = content.find("\n", character_index)
        return content[start: end if end >= 0 else len(content)].strip()

    @classmethod
    def _excerpt_for_value(cls, content: str, value: str) -> str:
        index = content.lower().find(value.lower())
        return cls._line_excerpt(content, max(index, 0))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
