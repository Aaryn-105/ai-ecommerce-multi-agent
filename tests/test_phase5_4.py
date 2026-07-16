# -*- coding: utf-8 -*-
"""Phase 5.4 — Report List & Detail API tests with real data."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import create_app
from backend.core.database import init_db, get_db
from backend.models.report import Report


@pytest.fixture(scope="module")
def client():
    init_db()
    app = create_app()
    return TestClient(app)


@pytest.fixture
def seed_reports(client: TestClient):
    """Insert test reports directly into DB for real-data testing."""
    db: Session = next(get_db())
    reports_data = [
        Report(title="\u7535\u5b50\u4ea7\u54c1\u9009\u54c1\u5206\u6790\u62a5\u544a",
               summary="\u5bf9\u7535\u5b50\u4ea7\u54c1\u7c7b\u76ee\u8fdb\u884c\u6df1\u5165\u7684\u9009\u54c1\u5206\u6790\uff0c\u5305\u62ec\u4ef7\u683c\u533a\u95f4\u3001\u8bc4\u5206\u5206\u5e03\u548c\u7ade\u54c1\u5bf9\u6bd4\u3002",
               sections={"product_analysis": {"summary": "test"}, "trend_forecast": {"trend": "up"}}),
        Report(title="\u5973\u88c5\u7c7b\u76ee\u8d8b\u52bf\u9884\u6d4b\u62a5\u544a",
               summary="\u57fa\u4e8e\u5386\u53f2\u9500\u552e\u6570\u636e\u548c\u5e02\u573a\u8d8b\u52bf\uff0c\u9884\u6d4b\u5973\u88c5\u7c7b\u76ee\u672a\u676530\u5929\u7684\u70ed\u9500\u54c1\u7c7b\u3002",
               sections={"trend": {"direction": "up"}}),
        Report(title="\u7efc\u5408\u8425\u9500\u7b56\u7565\u62a5\u544a",
               summary="\u7ed3\u5408\u9009\u54c1\u5206\u6790\u3001\u8d8b\u52bf\u9884\u6d4b\u548c\u7ade\u54c1\u5bf9\u6bd4\uff0c\u5236\u5b9a\u7efc\u5408\u8425\u9500\u65b9\u6848\u3002",
               sections={"marketing": {"strategy": "test"}}),
    ]
    for r in reports_data:
        db.add(r)
    db.commit()
    ids = [r.id for r in reports_data]
    yield ids
    # cleanup
    for rid in ids:
        db.query(Report).filter(Report.id == rid).delete()
    db.commit()
    db.close()


class TestReportAPI:

    def test_list_reports_empty(self, client: TestClient):
        """Initially no reports exist, should return empty list."""
        resp = client.get("/api/v1/report/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_reports_with_data(self, client: TestClient, seed_reports):
        """After seeding, list returns the reports with correct schema."""
        resp = client.get("/api/v1/report/?skip=0&limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        ids = [r["id"] for r in data]
        for sid in seed_reports:
            assert sid in ids, f"Seeded report {sid} not in list"
        item = data[0]
        assert "id" in item and "title" in item and "summary" in item and "created_at" in item

    def test_list_reports_pagination(self, client: TestClient, seed_reports):
        """Pagination limit parameter works correctly."""
        resp = client.get("/api/v1/report/?skip=0&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2
        resp2 = client.get("/api/v1/report/?skip=2&limit=2")
        assert resp2.status_code == 200
        ids1 = [r["id"] for r in resp.json()]
        ids2 = [r["id"] for r in resp2.json()]
        assert len(set(ids1) & set(ids2)) == 0, "Overlapping IDs across pages"

    def test_get_report_detail(self, client: TestClient, seed_reports):
        """Fetch a single report by ID returns full detail."""
        rid = seed_reports[0]
        resp = client.get(f"/api/v1/report/{rid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rid
        assert data["summary"] is not None and len(data["summary"]) > 5
        assert "sections" in data and isinstance(data["sections"], dict)
        assert "created_at" in data and "updated_at" in data

    def test_get_report_not_found(self, client: TestClient):
        """Non-existent report returns 404."""
        resp = client.get("/api/v1/report/99999")
        assert resp.status_code == 404

    def test_get_report_with_sections(self, client: TestClient, seed_reports):
        """Report sections are correctly stored and returned."""
        rid = seed_reports[0]
        resp = client.get(f"/api/v1/report/{rid}")
        assert resp.status_code == 200
        sections = resp.json()["sections"]
        assert "product_analysis" in sections
        assert "trend_forecast" in sections

    def test_export_report_pdf(self, client: TestClient, seed_reports):
        """Export a report as downloadable PDF."""
        rid = seed_reports[0]
        resp = client.post("/api/v1/report/export", json={"report_id": rid, "format": "pdf"})
        assert resp.status_code == 200
        content = resp.content
        assert content[:4] == b"%PDF", f"Expected PDF header, got: {content[:20]}"
        assert len(content) > 1000, f"PDF too small: {len(content)} bytes"
        assert resp.headers["content-type"] == "application/pdf"

    def test_export_report_docx(self, client: TestClient, seed_reports):
        """Export a report as downloadable DOCX."""
        rid = seed_reports[0]
        resp = client.post("/api/v1/report/export", json={"report_id": rid, "format": "docx"})
        assert resp.status_code == 200
        content = resp.content
        assert content[:2] == b"PK", f"Expected DOCX header, got: {content[:20]}"
        assert len(content) > 1000, f"DOCX too small: {len(content)} bytes"
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_export_report_with_custom_sections(self, client: TestClient, seed_reports):
        """Export with custom sections overrides stored ones."""
        rid = seed_reports[1]
        custom = {"custom_analysis": {"key": "custom_value", "score": 95}}
        resp = client.post("/api/v1/report/export", json={"report_id": rid, "format": "pdf", "sections": custom})
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"

    def test_export_nonexistent_report(self, client: TestClient):
        """Exporting non-existent report returns 404."""
        resp = client.post("/api/v1/report/export", json={"report_id": 99999, "format": "pdf"})
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
