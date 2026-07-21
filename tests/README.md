# Tests

Three layers of tests, separated by who/what runs them.

## `agents/` — Unit
Per-agent unit tests. Mirror `backend/agents/<agent_name>/` and verify the
deterministic scorer / validator / heuristic logic. Run with `pytest`.

## `services/` — Unit
Unit tests for shared backend services (export, polisher, LLM wrappers).
Run with `pytest`.

## `integration/` — End-to-end
Phase-level integration scripts. Each `test_phase*.py` simulates one phase of
the development plan (intent → orchestrator → agent → export). Run manually:

```bash
python tests/integration/test_phase3.py
```

## `manual/` — Probes & one-offs
Ad-hoc probes, audit scripts, and debugging dumps. **Not** for CI. Examples:
- `test_chat_trace.py` — traces a chat exchange through the orchestrator
- `audit_project.py` — quick project health check
- `write_e2e_test.py` — drafts an end-to-end test from a recorded session

Anything in here is safe to delete after its question has been answered.