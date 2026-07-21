# Repository Guidelines

## Project Structure & Module Organization

Source code lives under two top-level directories:

- `backend/` — FastAPI + LangGraph application with agents under `backend/agents/` (one subdirectory per agent), shared services in `backend/services/`, and API routes in `backend/routers/`.
- `frontend/` — React + Vite + TypeScript application with pages in `src/pages/`, reusable components in `src/components/`, and API client code in `src/api/`.
- `data/` — SQLite database files (`.gitkeep` included; actual `.db` files gitignored).
- `backend/models/` — SQLAlchemy table definitions (`base.py`, `conversation.py`, `report.py`) and Pydantic v2 schemas (`schemas.py`).

Each agent directory under `backend/agents/` is self-contained: `agent.py` (entry point), plus supporting modules (`scorer.py`, `models.py`, `llm_prompts.py`, etc.) as needed. The orchestrator agent at `backend/agents/orchestrator/` owns the LangGraph workflow definition and Plan-and-Execute logic.

### Top-level layout

| Directory | Purpose |
|-----------|---------|
| `backend/` | FastAPI app, agents, routers, services, models, core |
| `frontend/` | React/Vite app (UI, API client, components) |
| `data/` | SQLite database files (gitignored) |
| `tests/` | Pytest suite (see below) |
| `tests/agents/` | Unit tests for each agent (one subdir per agent) |
| `tests/services/` | Unit tests for shared services (export, polisher, etc.) |
| `tests/integration/` | End-to-end phase tests (`test_phase1.py` … `test_phase5_*.py`) |
| `tests/manual/` | One-off probes and audit scripts (run manually, not via pytest) |
| `docs/` | Architecture notes, figma references, sample reports |
| `docs/figma-reference/` | Figma design screenshots used during UI work |
| `docs/reference-reports/` | Sample PDFs cited as quality benchmarks |
| `scripts/maintenance/` | One-off helper scripts (PDF/PNG conversion, fixes) |
| `tmp/preview/` | Rendered report pages (gitignored) |
| `tmp/responses/` | Captured LLM response JSON (gitignored) |
| `logs/` | Server and frontend logs |
| `AGENTS.md` | This contributor guide |
| `README.md` | User-facing project overview and run instructions |

The tests directory follows three layers: **unit** tests live under `tests/agents/` and `tests/services/`, **integration** scripts go to `tests/integration/`, and **manual probes** that should never be invoked by CI go to `tests/manual/`.


## Agent-Specific Instructions

- **Intent Recognition**: Keyword matching must be tried before LLM fallback. Maintain the keyword lists in `rules.py` — do not inline them in `agent.py`.
- **Orchestrator**: Always validate `plan_steps` for dependency cycles before execution. The `execution_meta` block in every agent result must include `execution_time_ms` and `llm_used`.
- **Marketing Copy**: The 3 LLM calls (tagline, bullets, description/social) must run as concurrent coroutines. Always run `validator.py` checks before returning results; fall back to template strings on failure.
- **Pricing**: The `suggested_price` must be clamped to the `[floor, ceiling]` interval. Never return a price outside that range.
