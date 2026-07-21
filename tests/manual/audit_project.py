import os

checklist = {
    "Phase 0 - Project Init": [
        ("README.md", "README"),
        ("AGENTS.md", "Contributor guide"),
        (".gitignore", "Git ignore"),
        (".env.example", "Env template"),
        ("Makefile", "Makefile"),
    ],
    "Phase 1 - Backend Setup": [
        ("backend/main.py", "FastAPI"),
        ("backend/core/config.py", "Config"),
        ("backend/core/database.py", "Database"),
        ("backend/core/deps.py", "Deps"),
        ("backend/models/base.py", "Base"),
        ("backend/models/schemas.py", "Schemas"),
        ("backend/models/conversation.py", "Conv model"),
        ("backend/models/report.py", "Report model"),
    ],
    "Phase 2 - Agents": [
        ("backend/agents/intent_recognition/agent.py", "Intent"),
        ("backend/agents/intent_recognition/rules.py", "Rules"),
        ("backend/agents/orchestrator/agent.py", "Orchestrator"),
        ("backend/agents/orchestrator/planner.py", "Planner"),
        ("backend/agents/orchestrator/executor.py", "Executor"),
        ("backend/agents/orchestrator/replanner.py", "Replanner"),
        ("backend/agents/product_analysis/agent.py", "Product"),
        ("backend/agents/trend_forecast/agent.py", "Trend"),
        ("backend/agents/competitor_analysis/agent.py", "Competitor"),
        ("backend/agents/marketing_copy/agent.py", "Marketing"),
        ("backend/agents/inventory/agent.py", "Inventory"),
        ("backend/agents/pricing/agent.py", "Pricing"),
        ("backend/agents/promotion/agent.py", "Promotion"),
        ("backend/agents/base.py", "Base agent"),
        ("backend/agents/registry.py", "Registry"),
    ],
    "Phase 3 - Services": [
        ("backend/services/fake_store.py", "FakeStore"),
        ("backend/services/llm_service.py", "LLM"),
        ("backend/services/conversation.py", "Conversation"),
        ("backend/services/data_generator.py", "Data gen"),
        ("backend/services/report_export.py", "Export"),
    ],
    "Phase 4 - Routers": [
        ("backend/routers/chat.py", "Chat"),
        ("backend/routers/dashboard.py", "Dashboard"),
        ("backend/routers/report.py", "Report"),
    ],
    "Phase 5 - Frontend": [
        ("frontend/src/App.tsx", "App"),
        ("frontend/src/main.tsx", "Entry"),
        ("frontend/src/types.ts", "Types"),
        ("frontend/src/api/index.ts", "API"),
        ("frontend/src/components/Sidebar.tsx", "Sidebar"),
        ("frontend/src/components/ChatInterface.tsx", "Chat"),
        ("frontend/src/components/Dashboard.tsx", "Dashboard"),
        ("frontend/src/components/ProductBrowser.tsx", "Products"),
        ("frontend/src/components/ReportList.tsx", "Reports"),
        ("frontend/src/components/ReportDetail.tsx", "Report detail"),
        ("frontend/src/components/ReportCard.tsx", "Report card"),
        ("frontend/src/components/MessageList.tsx", "Messages"),
        ("frontend/src/components/InputBar.tsx", "Input"),
        ("frontend/src/components/AgentMessage.tsx", "Agent msg"),
        ("frontend/src/components/UserMessage.tsx", "User msg"),
    ],
    "Phase 5 - CSS & Config": [
        ("frontend/src/index.css", "Global CSS"),
        ("frontend/src/Dashboard.css", "Dash CSS"),
        ("frontend/src/components/ChatInterface.css", "Chat CSS"),
        ("frontend/src/ProductBrowser.css", "Prod CSS"),
        ("frontend/src/ReportList.css", "Report CSS"),
        ("frontend/vite.config.ts", "Vite"),
        ("frontend/package.json", "Package"),
    ],
    "Phase 6 - Docker": [
        ("docker-compose.yml", "Compose"),
        ("backend/Dockerfile", "Backend"),
        ("frontend/Dockerfile", "Frontend"),
        ("frontend/nginx.conf", "Nginx"),
        (".dockerignore", "Ignore"),
    ],
    "Tests": [
        ("tests/test_phase1.py", "P1"),
        ("tests/test_phase2_2.py", "P2.2"),
        ("tests/test_phase2_3.py", "P2.3"),
        ("tests/test_phase2_4.py", "P2.4"),
        ("tests/test_phase2_5.py", "P2.5"),
        ("tests/test_phase2_6.py", "P2.6"),
        ("tests/test_phase2_7.py", "P2.7"),
        ("tests/test_phase2_8.py", "P2.8"),
        ("tests/test_phase2_9.py", "P2.9"),
        ("tests/test_phase2_10.py", "P2.10"),
        ("tests/test_phase3.py", "P3"),
        ("tests/test_phase4.py", "P4"),
        ("tests/test_phase5_2.py", "P5.2"),
        ("tests/test_phase5_3.py", "P5.3"),
        ("tests/test_phase5_4.py", "P5.4"),
        ("tests/test_phase5_5.py", "P5.5"),
        ("tests/test_phase5_6.py", "P5.6"),
    ],
}

total, found, total_phases, ok_phases = 0, 0, 0, 0
for phase, items in checklist.items():
    total_phases += 1
    pf = sum(1 for p, _ in items if os.path.exists(p))
    total += len(items)
    found += pf
    status = "PASS" if pf == len(items) else "MISS"
    if pf == len(items): ok_phases += 1
    print(f"  [{status}] {phase}: {pf}/{len(items)}")

print(f"\n  Files: {found}/{total} ({100*found//total}%)")
print(f"  Phases: {ok_phases}/{total_phases} complete")
if found == total:
    print("\n  RESULT: ALL PHASES COMPLETE - Project is fully built!")
else:
    print(f"\n  RESULT: {total-found} file(s) missing from {total_phases-ok_phases} phase(s)")