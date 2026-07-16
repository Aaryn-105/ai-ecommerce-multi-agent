"""Report router — query stored reports and trigger exports."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.deps import get_db_session
from backend.models.report import Report
from backend.models.schemas import ExportRequest
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

    sections = body.sections or report.sections
    fmt = body.format

    if fmt == "pdf":
        file_bytes = _export_svc.to_pdf(report.title or "Analysis Report", report.summary or "", sections)
    elif fmt == "docx":
        file_bytes = _export_svc.to_docx(report.title or "Analysis Report", report.summary or "", sections)
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
