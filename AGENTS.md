# Repository Guidelines

## Project Structure & Module Organization

Source code lives under two top-level directories:

- `backend/` — FastAPI + LangGraph application with agents under `backend/agents/` (one subdirectory per agent), shared services in `backend/services/`, and API routes in `backend/routers/`.
- `frontend/` — React + Vite + TypeScript application with pages in `src/pages/`, reusable components in `src/components/`, and API client code in `src/api/`.
- `data/` — SQLite database files (`.gitkeep` included; actual `.db` files gitignored).
- `backend/models/` — SQLAlchemy table definitions (`base.py`, `conversation.py`, `report.py`) and Pydantic v2 schemas (`schemas.py`).

Each agent directory under `backend/agents/` is self-contained: `agent.py` (entry point), plus supporting modules (`scorer.py`, `models.py`, `llm_prompts.py`, etc.) as needed. The orchestrator agent at `backend/agents/orchestrator/` owns the LangGraph workflow definition and Plan-and-Execute logic.

## Build, Test, and Development Commands

| Command | Purpose |
|---------|---------|
| `python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000` | Start the FastAPI dev server with hot reload |
| `cd frontend && pnpm dev` | Start the Vite frontend dev server |
| `pip install -r requirements.txt` | Install Python dependencies |
| `cd frontend && pnpm install` | Install frontend dependencies |
| `python -c "from backend.core.database import init_db; init_db()"` | Create/initialize SQLite tables |

## Coding Style & Naming Conventions

- **Python**: Follow PEP 8. Indent with 4 spaces. Use `snake_case` for functions and variables, `PascalCase` for classes and Pydantic models.
- **TypeScript**: Use 2-space indentation. Prefer `camelCase` for variables and functions, `PascalCase` for components and types.
- **Agent files**: Name the main agent entry `agent.py` and supporting modules by concern (`scorer.py`, `models.py`, `llm_prompts.py`, `validator.py`).
- **Imports**: Use absolute imports within `backend/` (e.g. `from backend.models.schemas import AgentInput`). Keep standard library, third-party, and local imports grouped.
- **Docstrings**: Every agent class must have a class-level docstring describing its responsibility and input/output shapes.

The project does not use an automated formatter by default. Keep diffs clean by not mixing formatting changes with logic changes.

## Testing Guidelines

- **Framework**: `pytest` for all Python tests, located alongside the module under test (e.g. `tests/agents/test_product_analysis.py`).
- **Naming**: Test files prefixed with `test_`. Test functions named `test_<unit>_<scenario>` (e.g. `test_scorer_handles_single_product`).
- **Coverage**: All scoring functions and edge cases (empty input, uniform values, single-product categories) must have tests. Agent integration tests that verify `AgentInput` → `AgentResult` shape are strongly encouraged.
- **Running**: `pytest tests/ -v` from the project root.

## Commit & Pull Request Guidelines

**Commit messages** follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(product-analysis): add 4-dimension Min-Max scorer
fix(orchestrator): handle empty plan from LLM fallback
chore(deps): pin langgraph to ^0.2.0
```

Allowed scopes: `intent`, `orchestrator`, `product-analysis`, `trend-forecast`, `competitor-analysis`, `marketing-copy`, `inventory`, `pricing`, `promotion`, `export`, `frontend`, `deps`, `docs`.

**Pull requests** must include:

- A description of what the PR changes and why.
- A link to the related issue (if applicable).
- Screenshots for frontend changes.
- A note on whether the change affects any agent's input/output schema.

## Architecture Overview

The system uses a **Plan-and-Execute** orchestration pattern via LangGraph. User input flows through:

1. **Intent Recognition** (rules + LLM fallback) — classifies the query as e-commerce or not.
2. **Orchestrator** (LLM Plan + code executor) — generates a DAG of agent steps, executes them in topological order, and replans on failure.
3. **7 domain agents** — product analysis, trend forecast, competitor analysis, marketing copy, inventory, pricing, and promotion. Each reads inputs from the shared context and writes results back.
4. **Report assembly** — the orchestrator collects all agent outputs into a structured report.

Agents never communicate directly. All inter-agent data flows through the orchestrator's `context` dictionary. Agents that are "pure code" (product analysis, competitor analysis, inventory, pricing, trend forecast) produce deterministic, reproducible results with zero LLM calls.

## Agent-Specific Instructions

- **Intent Recognition**: Keyword matching must be tried before LLM fallback. Maintain the keyword lists in `rules.py` — do not inline them in `agent.py`.
- **Orchestrator**: Always validate `plan_steps` for dependency cycles before execution. The `execution_meta` block in every agent result must include `execution_time_ms` and `llm_used`.
- **Marketing Copy**: The 3 LLM calls (tagline, bullets, description/social) must run as concurrent coroutines. Always run `validator.py` checks before returning results; fall back to template strings on failure.
- **Pricing**: The `suggested_price` must be clamped to the `[floor, ceiling]` interval. Never return a price outside that range.
