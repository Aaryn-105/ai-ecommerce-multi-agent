"""LangGraph StateGraph definition for Plan-and-Execute orchestration."""
from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict

from backend.agents.orchestrator.executor import Executor
from backend.agents.orchestrator.planner import Planner
from backend.agents.orchestrator.replanner import Replanner


# ── Graph state ──────────────────────────────────────────

class WorkflowState(TypedDict):
    query: str
    request_id: str
    plan_steps: list[dict[str, Any]]
    context: dict[str, Any]
    attempt: int
    max_attempts: int


_MAX_ATTEMPTS = 2


# ── Node functions ───────────────────────────────────────

async def node_plan(state: WorkflowState) -> dict[str, Any]:
    # Only plan if no steps injected yet
    if state.get("plan_steps"):
        return {"attempt": state.get("attempt", 0) + 1}
    planner = Planner()
    steps = await planner.plan(state["query"])
    return {
        "plan_steps": [s.model_dump() for s in steps],
        "attempt": state.get("attempt", 0) + 1,
    }


async def node_execute(state: WorkflowState) -> dict[str, Any]:
    from backend.models.schemas import PlanStep

    steps = [PlanStep.model_validate(s) for s in state["plan_steps"]]
    executor = Executor(request_id=state["request_id"])
    context = await executor.run(steps, shared_context=state.get("context"))
    return {"context": context}


async def node_replan(state: WorkflowState) -> dict[str, Any]:
    from backend.models.schemas import PlanStep

    replanner = Replanner()
    steps = [PlanStep.model_validate(s) for s in state["plan_steps"]]
    new_steps = await replanner.replan(state["query"], steps, state["context"])
    return {
        "plan_steps": [s.model_dump() for s in new_steps],
        "attempt": state["attempt"] + 1,
    }


# ── Router ───────────────────────────────────────────────

def router_after_execute(state: WorkflowState) -> Literal["replan", "assemble", "__end__"]:
    """Decide next step after execution."""
    context = state.get("context", {})
    any_failed = any(
        isinstance(v, dict) and v.get("status") == "failed"
        for v in context.values()
    )
    if any_failed and state.get("attempt", 0) < _MAX_ATTEMPTS:
        return "replan"
    return "assemble"


def router_after_replan(state: WorkflowState) -> Literal["execute", "__end__"]:
    """After replan, execute again if we have steps left."""
    if state.get("plan_steps"):
        return "execute"
    return "__end__"


async def node_assemble(state: WorkflowState) -> dict[str, Any]:
    """Assemble the final report from context."""
    context = state.get("context", {})
    sections = {}
    visible_agents: set[str] = set()
    for step in state.get("plan_steps", []):
        if isinstance(step, dict):
            if step.get("report", True) and step.get("agent"):
                visible_agents.add(step["agent"])
        elif step.report:
            visible_agents.add(step.agent)
    for key, value in context.items():
        if key in visible_agents and isinstance(value, dict) and "output_data" in value:
            sections[key] = value["output_data"]

    summary_parts = []
    for agent_name, section in sections.items():
        if isinstance(section, dict) and section:
            summary_parts.append(f"{agent_name}: {len(section)} fields")
    summary = "; ".join(summary_parts) if summary_parts else "No data collected."

    return {
        "context": {
            **context,
            "final_report": {
                "summary": summary,
                "sections": sections,
                "total_agents_run": len(sections),
            },
        }
    }


# ── Build graph ──────────────────────────────────────────

def build_workflow() -> CompiledStateGraph:
    """Build and return the compiled LangGraph StateGraph."""
    builder = StateGraph(WorkflowState)

    builder.add_node("plan", node_plan)
    builder.add_node("execute", node_execute)
    builder.add_node("replan", node_replan)
    builder.add_node("assemble", node_assemble)

    builder.set_entry_point("plan")
    builder.add_edge("plan", "execute")
    builder.add_conditional_edges("execute", router_after_execute)
    builder.add_conditional_edges("replan", router_after_replan)
    builder.add_edge("assemble", END)

    return builder.compile()
