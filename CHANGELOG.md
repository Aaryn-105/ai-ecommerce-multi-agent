# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-21

### Added

- FastAPI + LangGraph multi-agent backend with 7 domain agents:
  product_analysis, trend_forecast, competitor_analysis, marketing_copy,
  inventory, pricing, promotion. Plus intent_recognition and orchestrator.
- Plan-and-Execute orchestrator with topological step execution and replan-on-failure.
- React + Vite + TypeScript frontend with chat interface, dashboard, and
  history/report library.
- Semantic document model (`backend/services/report_document.py`) consumed by
  PDF and DOCX exporters so both formats share heading ordering, chart
  placement, and block coverage.
- Professional PDF export (ReportLab) with cover page, header/footer, callout
  blocks, tables, and Pillow-rendered PNG charts (bar / grouped-bar / pie).
- DOCX export (python-docx) with cover page, H1/H2 headings, tables with bold
  headers, and chart insertion matching PDF semantics.
- DeepSeek LLM integration for marketing_copy, report polisher, and report
  export prompts (configurable via `backend/core/config.py`).
- Project layout cleanup: `docs/`, `scripts/maintenance/`, `tests/integration/`,
  `tests/manual/`, `tmp/preview/`, `tmp/responses/`, `logs/`.
- Developer documentation: `AGENTS.md`, `README.md`, `docs/README.md`,
  `scripts/README.md`, `tests/README.md`, `tmp/README.md`.

### Changed

- DOCX generation rewritten to consume the same semantic document model as PDF
  (single source of truth for headings, blocks, and chart placement).
- Project directory structure reorganized; loose scripts relocated to
  `scripts/maintenance/`; phase tests moved to `tests/integration/`.

## [0.1.0] - 2026-07

### Added

- Initial scaffold: FastAPI app, agent skeletons, SQLite persistence,
  preliminary frontend skeleton.