"""Tests for Phase 4 — Data Export (PDF + DOCX generation).

Tests both the service layer and the API endpoint using real FakeStore data.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.database import Base
from backend.main import create_app
from backend.services.report_export import ReportExportService

# ── Test building real sections from FakeStore ───────────

_REAL_PRODUCTS: list[dict] | None = None


@pytest_asyncio.fixture(scope="session")
async def real_products() -> list[dict]:
    global _REAL_PRODUCTS
    if _REAL_PRODUCTS is not None:
        return _REAL_PRODUCTS
    from backend.services.fake_store import FakeStoreService
    svc = FakeStoreService()
    try:
        _REAL_PRODUCTS = await svc.get_all_products()
    finally:
        await svc.close()
    assert len(_REAL_PRODUCTS) == 20
    return _REAL_PRODUCTS


@pytest_asyncio.fixture(scope="session")
async def real_analysis_sections(real_products: list[dict]) -> dict[str, Any]:
    """Build a realistic multi-agent output dict from real products."""
    from backend.agents.product_analysis.agent import ProductAnalysisAgent
    from backend.agents.trend_forecast.agent import TrendForecastAgent
    from backend.agents.competitor_analysis.agent import CompetitorAnalysisAgent
    from backend.agents.marketing_copy.agent import MarketingCopyAgent
    from backend.agents.inventory.agent import InventoryAgent
    from backend.agents.pricing.agent import PricingAgent
    from backend.agents.promotion.agent import PromotionAgent
    from backend.agents.registry import AgentRegistry
    from backend.models.schemas import AgentInput

    AgentRegistry.clear()
    AgentRegistry.register(ProductAnalysisAgent)
    AgentRegistry.register(TrendForecastAgent)
    AgentRegistry.register(CompetitorAnalysisAgent)
    AgentRegistry.register(MarketingCopyAgent)
    AgentRegistry.register(InventoryAgent)
    AgentRegistry.register(PricingAgent)
    AgentRegistry.register(PromotionAgent)

    context = {"all_products": real_products}
    sections: dict[str, Any] = {}

    # 1. Product Analysis
    pa = ProductAnalysisAgent()
    pa_result = await pa.run(AgentInput(
        task_id="pa_001", request_id="phase4",
        input_data={"products": real_products}, context=context,
    ))
    sections["product_analysis"] = pa_result.output_data
    context["product_analysis"] = {"output_data": pa_result.output_data, "status": "completed"}

    sel = pa_result.output_data.get("selected_products", real_products[:5])

    # 2. Trend Forecast
    tf = TrendForecastAgent()
    tf_result = await tf.run(AgentInput(
        task_id="tf_001", request_id="phase4",
        input_data={"products": sel}, context=context,
    ))
    sections["trend_forecast"] = tf_result.output_data
    context["trend_forecast"] = {"output_data": tf_result.output_data, "status": "completed"}

    # 3. Competitor Analysis
    ca = CompetitorAnalysisAgent()
    ca_result = await ca.run(AgentInput(
        task_id="ca_001", request_id="phase4",
        input_data={"selected_products": sel, "all_products": real_products}, context=context,
    ))
    sections["competitor_analysis"] = ca_result.output_data
    context["competitor_analysis"] = {"output_data": ca_result.output_data, "status": "completed"}

    # 4. Marketing Copy
    mc = MarketingCopyAgent()
    mc_result = await mc.run(AgentInput(
        task_id="mc_001", request_id="phase4",
        input_data={"products": sel}, context=context,
    ))
    sections["marketing_copy"] = mc_result.output_data

    # 5. Inventory
    inv = InventoryAgent()
    inv_result = await inv.run(AgentInput(
        task_id="inv_001", request_id="phase4",
        input_data={"candidate_products": sel}, context=context,
    ))
    sections["inventory"] = inv_result.output_data

    # 6. Pricing
    pr = PricingAgent()
    pr_result = await pr.run(AgentInput(
        task_id="pr_001", request_id="phase4",
        input_data={"target_products": sel, "all_products": real_products}, context=context,
    ))
    sections["pricing"] = pr_result.output_data

    # 7. Promotion
    promo = PromotionAgent()
    promo_result = await promo.run(AgentInput(
        task_id="promo_001", request_id="phase4",
        input_data={"products": sel}, context=dict(context, **{
            "pricing": {"output_data": pr_result.output_data, "status": "completed"},
            "marketing_copy": {"output_data": mc_result.output_data, "status": "completed"},
            "inventory": {"output_data": inv_result.output_data, "status": "completed"},
        }),
    ))
    sections["promotion"] = promo_result.output_data

    return sections


# ── Test database ────────────────────────────────────────

_engine: Any = None
_TestSessionLocal: Any = None
_db_path: str = ""


def _build_test_db() -> str:
    tmp = tempfile.gettempdir()
    return os.path.join(tmp, f"test_phase4_{os.urandom(4).hex()}.db")


@pytest.fixture(scope="session", autouse=True)
def _test_db() -> Generator[str, None, None]:
    global _engine, _TestSessionLocal, _db_path
    _db_path = _build_test_db()
    _engine = create_engine(
        f"sqlite:///{_db_path}",
        connect_args={"check_same_thread": False},
    )
    _TestSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=_engine)
    yield _db_path
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()
    if os.path.exists(_db_path):
        try:
            os.remove(_db_path)
        except PermissionError:
            pass


@pytest.fixture(autouse=True)
def _override_db(_test_db: str) -> Generator[None, None, None]:
    from backend.core import database as db_mod
    import backend.core.deps as deps_mod

    db_mod.engine = _engine
    db_mod.SessionLocal = _TestSessionLocal

    def _test_get_db() -> Generator[Session, None, None]:
        db = _TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    db_mod.get_db = _test_get_db
    deps_mod.get_db = _test_get_db
    yield


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════
#  1. Service Layer — PDF Generation
# ═══════════════════════════════════════════════════════════

class TestPDFGeneration:
    """Test ReportExportService.to_pdf() with real data."""

    def test_pdf_minimal_sections(self) -> None:
        """Minimal sections should produce valid PDF."""
        svc = ReportExportService()
        pdf = svc.to_pdf("Test Report", "A minimal test", {})
        assert isinstance(pdf, bytes)
        assert len(pdf) > 500  # PDF header + content
        assert pdf[:5] == b"%PDF-"

    def test_pdf_with_summary_only(self) -> None:
        """Report with only summary text."""
        svc = ReportExportService()
        pdf = svc.to_pdf(
            "Summary Only",
            "This is a test summary with some text content.",
            {},
        )
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    def test_pdf_renders_full_markdown_report(self) -> None:
        """Stored polished Markdown should be fully searchable in the PDF."""
        fitz = pytest.importorskip("fitz")
        content_md = """## 一、摘要与核心建议
### 一句话结论
电子产品类目存在明确选品机会。

## 二、候选商品综合评估
| 商品名称 | 综合得分 | 推荐等级 |
|---|---:|---|
| Silicon Power 256GB SSD | 80.85 | 强势推荐 |

## 三、趋势预测与GMV估算
- 30日销量预测为139件。

## 四、风险矩阵与敏感性分析
核心风险为库存不足与价格竞争。
"""
        svc = ReportExportService()
        pdf = svc.to_pdf(
            "电子产品选品分析",
            "真实报告正文渲染测试",
            {},
            content_md=content_md,
        )

        document = fitz.open(stream=pdf, filetype="pdf")
        extracted_text = "\n".join(page.get_text() for page in document)
        assert "一、摘要与核心建议" in extracted_text
        assert "Silicon Power 256GB SSD" in extracted_text
        assert "三、趋势预测与GMV估算" in extracted_text
        assert "四、风险矩阵与敏感性分析" in extracted_text

    @pytest.mark.asyncio
    async def test_pdf_with_real_agent_output(self, real_analysis_sections: dict[str, Any]) -> None:
        """Full sections from real agent outputs should produce a valid PDF."""
        svc = ReportExportService()
        pdf = svc.to_pdf(
            "电商多智能体分析报告",
            "基于FakeStore真实数据的完整多智能体分析报告。涵盖选品分析、趋势预测、竞品对比、营销文案、库存补货、定价建议和促销方案。",
            real_analysis_sections,
        )
        assert pdf[:5] == b"%PDF-"
        # A full report should be substantial (>10 KB)
        assert len(pdf) > 5000, f"PDF only {len(pdf)} bytes — expected >5 KB"

    def test_pdf_writes_to_file(self, tmp_path: Path) -> None:
        """Generated PDF should be savable to disk."""
        svc = ReportExportService()
        pdf = svc.to_pdf("File Test", "Testing file output", {})
        out = tmp_path / "test.pdf"
        out.write_bytes(pdf)
        assert out.exists()
        assert out.stat().st_size > 500
        # Verify it's a valid PDF by reading the header
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"


# ═══════════════════════════════════════════════════════════
#  2. Service Layer — DOCX Generation
# ═══════════════════════════════════════════════════════════

class TestDOCXGeneration:
    """Test ReportExportService.to_docx() with real data."""

    def test_docx_minimal_sections(self) -> None:
        """Minimal sections should produce valid DOCX."""
        svc = ReportExportService()
        docx = svc.to_docx("Test Report", "A minimal test", {})
        assert isinstance(docx, bytes)
        assert len(docx) > 500
        # DOCX files are ZIP archives starting with PK
        assert docx[:2] == b"PK"

    def test_docx_with_summary_only(self) -> None:
        """Report with only summary text."""
        svc = ReportExportService()
        docx = svc.to_docx(
            "Summary Only",
            "This is a test summary.",
            {},
        )
        assert docx[:2] == b"PK"
        assert len(docx) > 500

    @pytest.mark.asyncio
    async def test_docx_with_real_agent_output(self, real_analysis_sections: dict[str, Any]) -> None:
        """Full sections from real agent outputs should produce a valid DOCX."""
        svc = ReportExportService()
        docx = svc.to_docx(
            "电商多智能体分析报告",
            "基于FakeStore真实数据的完整多智能体分析报告。",
            real_analysis_sections,
        )
        assert docx[:2] == b"PK"
        assert len(docx) > 5000, f"DOCX only {len(docx)} bytes — expected >5 KB"

    def test_docx_writes_to_file(self, tmp_path: Path) -> None:
        """Generated DOCX should be savable to disk."""
        svc = ReportExportService()
        docx = svc.to_docx("File Test", "Testing file output", {})
        out = tmp_path / "test.docx"
        out.write_bytes(docx)
        assert out.exists()
        assert out.stat().st_size > 500
        # Verify it's a valid DOCX (ZIP archive)
        import zipfile
        with zipfile.ZipFile(out) as zf:
            assert "word/document.xml" in zf.namelist()


# ═══════════════════════════════════════════════════════════
#  3. API Endpoint — Export
# ═══════════════════════════════════════════════════════════

class TestExportEndpoint:
    """Test POST /api/v1/report/export via HTTP."""

    def _create_test_report(self, client: TestClient) -> int:
        """Helper: create a report record directly in the DB and return its ID."""
        from backend.models.report import Report
        db = _TestSessionLocal()
        try:
            r = Report(
                title="测试报告",
                summary="通过API导出的测试报告",
                sections={
                    "product_analysis": {
                        "selected_products": [
                            {
                                "id": 1,
                                "title": "Test Product",
                                "category": "electronics",
                                "price": 29.99,
                                "original_rating": {"rate": 4.5, "count": 100},
                                "final_score": 0.85,
                            }
                        ],
                        "statistics": {"total_analyzed": 1, "selected_count": 1, "category_distribution": {"electronics": 1}},
                        "summary": "测试分析摘要",
                    }
                },
            )
            db.add(r)
            db.commit()
            db.refresh(r)
            return r.id
        finally:
            db.close()

    def test_export_pdf_download(self, client: TestClient) -> None:
        """Exporting a PDF should return a downloadable file."""
        report_id = self._create_test_report(client)
        resp = client.post(
            "/api/v1/report/export",
            json={"report_id": report_id, "format": "pdf"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "content-disposition" in resp.headers
        assert f"report_{report_id}.pdf" in resp.headers["content-disposition"]
        content = resp.content
        assert len(content) > 500
        assert content[:5] == b"%PDF-"

    def test_export_docx_download(self, client: TestClient) -> None:
        """Exporting a DOCX should return a downloadable file."""
        report_id = self._create_test_report(client)
        resp = client.post(
            "/api/v1/report/export",
            json={"report_id": report_id, "format": "docx"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert "content-disposition" in resp.headers
        assert f"report_{report_id}.docx" in resp.headers["content-disposition"]
        content = resp.content
        assert len(content) > 500
        assert content[:2] == b"PK"

    def test_export_report_not_found(self, client: TestClient) -> None:
        """Exporting a non-existent report returns 404."""
        resp = client.post(
            "/api/v1/report/export",
            json={"report_id": 9999, "format": "pdf"},
        )
        assert resp.status_code == 404

    def test_export_with_custom_sections(self, client: TestClient) -> None:
        """Sections from the request body should override stored sections."""
        report_id = self._create_test_report(client)
        resp = client.post(
            "/api/v1/report/export",
            json={
                "report_id": report_id,
                "format": "pdf",
                "sections": {
                    "product_analysis": {
                        "selected_products": [],
                        "statistics": {"total_analyzed": 0, "selected_count": 0, "category_distribution": {}},
                        "summary": "自定义覆盖内容",
                    }
                },
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    def test_export_content_length_header(self, client: TestClient) -> None:
        """Response should include Content-Length header."""
        report_id = self._create_test_report(client)
        resp = client.post(
            "/api/v1/report/export",
            json={"report_id": report_id, "format": "pdf"},
        )
        assert resp.status_code == 200
        assert "content-length" in resp.headers
        assert int(resp.headers["content-length"]) == len(resp.content)
