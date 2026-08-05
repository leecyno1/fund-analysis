import hashlib
import os
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.local_research_folder_service import (  # noqa: E402
    FolderValidationError,
    LocalResearchFolderService,
)


class MemoryResearchFolderRepo:
    def __init__(self):
        self.folders = {}
        self.documents = {}
        self.reports = {}
        self._sequence = 0

    def create_folder(self, folder):
        self._sequence += 1
        folder_id = f"folder-{self._sequence}"
        saved = {**deepcopy(folder), "id": folder_id}
        self.folders[folder_id] = saved
        return deepcopy(saved)

    def list_folders(self):
        return [deepcopy(folder) for folder in self.folders.values()]

    def get_folder(self, folder_id):
        folder = self.folders.get(folder_id)
        return deepcopy(folder) if folder else None

    def update_folder(self, folder_id, fields):
        self.folders[folder_id].update(deepcopy(fields))
        return deepcopy(self.folders[folder_id])

    def get_document(self, folder_id, relative_path):
        document = self.documents.get((folder_id, relative_path))
        return deepcopy(document) if document else None

    def find_document_by_hash(self, content_hash, exclude_folder_id=None, exclude_relative_path=None):
        for (folder_id, relative_path), document in self.documents.items():
            if folder_id == exclude_folder_id and relative_path == exclude_relative_path:
                continue
            if document.get("content_hash") == content_hash and document.get("report_id"):
                return deepcopy(document)
        return None

    def upsert_document(self, document):
        key = (document["folder_id"], document["relative_path"])
        saved = {**deepcopy(self.documents.get(key, {})), **deepcopy(document)}
        self.documents[key] = saved
        return deepcopy(saved)

    def create_report(self, report):
        self._sequence += 1
        report_id = f"report-{self._sequence}"
        saved = {**deepcopy(report), "id": report_id}
        self.reports[report_id] = saved
        return deepcopy(saved)

    def update_report(self, report_id, fields):
        self.reports[report_id].update(deepcopy(fields))
        return deepcopy(self.reports[report_id])

    def get_report(self, report_id):
        report = self.reports.get(report_id)
        return deepcopy(report) if report else None

    def list_pending_reviews(self, folder_id=None):
        pending = []
        for report in self.reports.values():
            if folder_id and report.get("local_folder_id") != folder_id:
                continue
            for proposal in report.get("review_proposals", []):
                if proposal.get("review_status") == "pending":
                    pending.append({
                        "report_id": report["id"],
                        "report_title": report["title"],
                        **deepcopy(proposal),
                    })
        return pending


def _write_pdf(path: Path, text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(bytes(output))


def _write_docx(path: Path, text: str) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    document.save(path)


def _proposal(report, kind, value):
    return next(
        proposal
        for proposal in report.get("review_proposals", [])
        if proposal.get("kind") == kind and proposal.get("value") == value
    )


def main() -> int:
    repo = MemoryResearchFolderRepo()
    service = LocalResearchFolderService(repo=repo, max_files=20, max_file_bytes=2_000_000)

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "调研纪要"
        manager_folder = root / "张三"
        manager_folder.mkdir(parents=True)

        markdown_content = "# 访谈纪要\n基金经理：张三\n风格：成长、大盘、低换手\n基金分类：主动权益\n- 重视现金流与长期竞争力\n"
        markdown_path = manager_folder / "2026-08-01-访谈.md"
        duplicate_path = manager_folder / "重复内容.txt"
        notes_path = root / "李四-补充.txt"
        pdf_path = root / "英文纪要.pdf"
        docx_path = root / "Word纪要.docx"

        markdown_path.write_text(markdown_content, encoding="utf-8")
        duplicate_path.write_text(markdown_content, encoding="utf-8")
        notes_path.write_text("基金经理：李四\n风格：价值、小盘\n关注回撤与估值。", encoding="utf-8")
        _write_pdf(pdf_path, "PDF research memo for parser verification")
        _write_docx(docx_path, "DOCX research memo for parser verification")
        (root / "不支持.csv").write_text("ignored", encoding="utf-8")

        original_bytes = {path: path.read_bytes() for path in (markdown_path, duplicate_path, notes_path, pdf_path, docx_path)}

        folder = service.add_folder(str(root))
        if folder.get("path") != str(root.resolve()):
            raise AssertionError(f"Folder path should be canonical: {folder}")

        first = service.scan_folder(folder["id"])
        expected_first = {"created": 4, "updated": 0, "unchanged": 1, "failed": 0, "supported": 5}
        if first.get("counts") != expected_first:
            raise AssertionError(f"Unexpected first scan counts: {first}")
        if len(repo.reports) != 4 or len(repo.documents) != 5:
            raise AssertionError(f"Content deduplication failed: reports={len(repo.reports)} documents={len(repo.documents)}")

        for path, before in original_bytes.items():
            if path.read_bytes() != before:
                raise AssertionError(f"Scanner rewrote source file: {path}")

        for document in repo.documents.values():
            if not document.get("relative_path") or not document.get("content_hash"):
                raise AssertionError(f"Document lacks audit identity: {document}")
            if document.get("size", 0) <= 0 or document.get("mtime_ns", 0) <= 0:
                raise AssertionError(f"Document lacks file metadata: {document}")

        parsed_contents = "\n".join(report.get("content", "") for report in repo.reports.values())
        if "PDF research memo" not in parsed_contents or "DOCX research memo" not in parsed_contents:
            raise AssertionError("PDF and DOCX files must be parsed into searchable text")

        manager_report = next(report for report in repo.reports.values() if "基金经理：张三" in report.get("content", ""))
        manager_proposal = _proposal(manager_report, "manager", "张三")
        style_proposal = _proposal(manager_report, "style_label", "成长")
        for proposal in (manager_proposal, style_proposal):
            source_ref = proposal.get("source_ref", {})
            if proposal.get("review_status") != "pending":
                raise AssertionError(f"Extracted conclusions must await review: {proposal}")
            if not source_ref.get("relative_path") or not source_ref.get("excerpt"):
                raise AssertionError(f"Proposal lacks source evidence: {proposal}")
            confidence = proposal.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise AssertionError(f"Proposal confidence is invalid: {proposal}")

        service.review_proposal(manager_report["id"], manager_proposal["id"], "confirmed")
        service.review_proposal(manager_report["id"], style_proposal["id"], "rejected")
        reviewed = repo.get_report(manager_report["id"])
        if reviewed.get("manager_name") != "张三":
            raise AssertionError(f"Confirmed manager should control grouping: {reviewed}")
        if "成长" in reviewed.get("style_labels", []):
            raise AssertionError(f"Rejected style must not enter confirmed labels: {reviewed}")

        pending = service.list_pending_reviews(folder["id"])
        if any(item.get("id") in {manager_proposal["id"], style_proposal["id"]} for item in pending):
            raise AssertionError(f"Reviewed proposals must leave pending queue: {pending}")

        second = service.scan_folder(folder["id"])
        if second.get("counts") != {"created": 0, "updated": 0, "unchanged": 5, "failed": 0, "supported": 5}:
            raise AssertionError(f"Unchanged files should not be reparsed: {second}")

        time.sleep(0.002)
        notes_path.write_text("基金经理：李四\n风格：均衡、大盘\n更新后的风险控制记录。", encoding="utf-8")
        os.utime(notes_path, None)
        third = service.scan_folder(folder["id"])
        if third.get("counts") != {"created": 0, "updated": 1, "unchanged": 4, "failed": 0, "supported": 5}:
            raise AssertionError(f"Changed file should update only one indexed memo: {third}")

        updated_document = repo.get_document(folder["id"], "李四-补充.txt")
        expected_hash = hashlib.sha256(notes_path.read_bytes()).hexdigest()
        if updated_document.get("content_hash") != expected_hash:
            raise AssertionError(f"Updated hash was not stored: {updated_document}")

    for unsafe in ("/", str(Path.home()), "/path/that/does/not/exist"):
        try:
            service.add_folder(unsafe)
        except FolderValidationError:
            pass
        else:
            raise AssertionError(f"Unsafe or missing path should be rejected: {unsafe}")

    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "too-large"
        root.mkdir()
        (root / "oversize.txt").write_bytes(b"x" * 33)
        strict_service = LocalResearchFolderService(repo=MemoryResearchFolderRepo(), max_file_bytes=32)
        folder = strict_service.add_folder(str(root))
        result = strict_service.scan_folder(folder["id"])
        if result.get("counts", {}).get("failed") != 1:
            raise AssertionError(f"Oversized file should fail without being read: {result}")

    print("OK local research folders scan incrementally with auditable, reviewable extraction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
