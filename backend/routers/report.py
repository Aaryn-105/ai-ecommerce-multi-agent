"""Report router — query stored reports and trigger exports."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.deps import get_db_session
from backend.models.report import Report
from backend.models.schemas import ExportRequest
from pydantic import BaseModel
from backend.services.report_document import build_report_document, normalize_report_document
from backend.services.report_export import ReportExportService

router = APIRouter(prefix="/api/v1/report", tags=["report"])

_export_svc = ReportExportService()

# ── Content type mapping ─────────────────────────────────
_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_FILE_EXTENSIONS = {
    "pdf": ".pdf",
    "docx": ".docx",
}

@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve a stored analysis report by ID."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Report #{report_id} not found")
    return {
        "id": report.id,
        "conversation_id": report.conversation_id,
        "title": report.title,
        "summary": report.summary,
        "sections": report.sections,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }

@router.get("/")
async def list_reports(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """List stored reports with pagination."""
    reports = (
        db.query(Report)
        .order_by(Report.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "summary": r.summary[:100] if r.summary else "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]

@router.delete("/{report_id}", status_code=200)
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db_session),
) -> dict:
    """Delete a stored analysis report by ID."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Report #{report_id} not found")
    db.delete(report)
    db.commit()
    return {"deleted": True, "id": report_id}

class BatchDeleteRequest(BaseModel):
    ids: list[int]

@router.post("/batch-delete", status_code=200)
async def batch_delete_reports(
    body: BatchDeleteRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """批量删除多个报告。"""
    if not body.ids:
        return {"deleted": False, "ids": [], "count": 0}
    deleted_ids: list[int] = []
    for rid in body.ids:
        report = db.query(Report).filter(Report.id == rid).first()
        if report:
            db.delete(report)
            deleted_ids.append(rid)
    db.commit()
    return {"deleted": True, "ids": deleted_ids, "count": len(deleted_ids)}

@router.post("/export")
async def export_report(
    body: ExportRequest,
    db: Session = Depends(get_db_session),
) -> Any:
    """Export a report as PDF or DOCX and return the file as a download stream.

    The ``sections`` field in the request body can be used to provide
    live analysis data directly. If omitted, stored sections are used.
    """
    report = db.query(Report).filter(Report.id == body.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Report #{body.report_id} not found")

    # Resolve sections: handle both wrapped ({_agent_sections: ...}) and flat formats.
    stored_raw = report.sections if isinstance(report.sections, dict) else {}
    raw = body.sections if body.sections else stored_raw
    report_document = None
    if isinstance(raw, dict) and "_agent_sections" in raw:
        sections = raw["_agent_sections"] or {}
        report_document = raw.get("_report_document")
        content_md = raw.get("_report_markdown") or ""
    else:
        sections = raw if isinstance(raw, dict) else {}
        report_document = stored_raw.get("_report_document")
        content_md = stored_raw.get("_report_markdown") or ""

    if report_document:
        report_document = normalize_report_document(
            report_document,
            title=report.title or "Analysis Report",
            summary=report.summary or "",
        )
    else:
        report_document = build_report_document(
            content_md,
            title=report.title or "Analysis Report",
            summary=report.summary or "",
        )
        if stored_raw:
            migrated_sections = dict(stored_raw)
            migrated_sections["_report_document"] = report_document
            report.sections = migrated_sections
            db.commit()
    fmt = body.format

    if fmt == "pdf":
        file_bytes = _export_svc.to_pdf(
            report.title or "Analysis Report",
            report.summary or "",
            sections,
            content_md=content_md,
            report_document=report_document,
        )
    elif fmt == "docx":
        file_bytes = _export_svc.to_docx(
            report.title or "Analysis Report",
            report.summary or "",
            sections,
            content_md=content_md,
            report_document=report_document,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    content_type = _CONTENT_TYPES.get(fmt, "application/octet-stream")
    ext = _FILE_EXTENSIONS.get(fmt, ".bin")
    filename = f"report_{body.report_id}{ext}"

    return StreamingResponse(
        iter([file_bytes]),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_bytes)),
        },
    )
