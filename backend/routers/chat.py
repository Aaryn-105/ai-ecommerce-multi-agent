"""Chat router — POST /api/v1/chat — orchestrates the full multi-agent pipeline."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.agents.intent_recognition.agent import IntentRecognitionAgent
from backend.agents.orchestrator.agent import OrchestratorAgent
from backend.agents.registry import AgentRegistry
from backend.core.deps import get_db_session
from backend.models.schemas import ChatRequest, ChatResponse, AgentInput
from backend.services.conversation import ConversationService
from backend.services.fake_store import FakeStoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Session = Depends(get_db_session),
) -> Any:
    """Process a user message through the multi-agent pipeline.

    1. Save user message to conversation history.
    2. Run Intent Recognition — if not e-commerce, return early.
    3. Run Orchestrator — Plan → Execute → (Replan if needed).
    4. Save assistant reply to conversation history.
    5. Return structured response with plan steps and agent sections.
    """
    conv_svc = ConversationService(db)
    conv = conv_svc.get_or_create(body.conversation_id)
    conv_svc.add_message(conv, "user", body.message)

    # ── Step 1: Intent Recognition ───────────────────────
    intent_agent = IntentRecognitionAgent()
    intent_input = AgentInput(
        task_id="intent_001",
        request_id=conv.session_id,
        input_data={"message": body.message},
    )
    intent_result = await intent_agent.run(intent_input)

    if not intent_result.output_data.get("is_ecommerce_query", False):
        reply = (
            "您好！我是电商选品分析助手。我可以帮您分析商品数据、"
            "预测销售趋势、对比竞品、生成营销文案、提供定价和促销建议。"
            "请告诉我您想分析哪些商品或品类？"
        )
        conv_svc.add_message(conv, "assistant", reply)
        return ChatResponse(
            reply=reply,
            conversation_id=conv.session_id,
        )

    # ── Step 2: Orchestrate ──────────────────────────────
    _ensure_agents_registered()

    # Fetch real products from FakeStore
    fake_store = FakeStoreService()
    try:
        all_products = await fake_store.get_all_products()
    finally:
        await fake_store.close()

    # The first agent (product_analysis) needs products either in
    # input_data.products or context.all_products. We inject them
    # into the orchestrator context so all agents can reference them.
    orch_context: dict[str, Any] = {"all_products": all_products}

    orchestrator = OrchestratorAgent()
    orch_input = AgentInput(
        task_id="orchestrator_001",
        request_id=conv.session_id,
        input_data={
            "message": body.message,
            "request_id": conv.session_id,
            # Inject products as the first agent's input so the
            # default plan's product_analysis step picks them up.
            "products": all_products,
        },
        context=orch_context,
    )
    orch_result = await orchestrator.run(orch_input)
    orch_output = orch_result.output_data

    # ── Step 3: Assemble reply ───────────────────────────
    final_report = orch_output.get("final_report", {})
    sections = final_report.get("sections", {})
    plan_steps = orch_output.get("plan_steps", [])

    summary_parts = []
    for agent_name, data in sections.items():
        agent_summary = data.get("summary") or data.get("market_summary") or ""
        if agent_summary:
            summary_parts.append(f"**{agent_name}**: {agent_summary}")

    report_summary = final_report.get("summary", "分析完成。")
    reply = (
        f"✅ 分析完成！\n\n"
        f"{report_summary}\n\n"
        + ("\n\n".join(summary_parts) if summary_parts else "")
    )

    conv_svc.add_message(conv, "assistant", reply)

    return ChatResponse(
        reply=reply,
        conversation_id=conv.session_id,
        plan=plan_steps,
        sections=sections,
    )


def _ensure_agents_registered() -> None:
    """Register all agents if not already done."""
    if AgentRegistry.list_agents():
        return
    from backend.agents.product_analysis.agent import ProductAnalysisAgent
    from backend.agents.trend_forecast.agent import TrendForecastAgent
    from backend.agents.competitor_analysis.agent import CompetitorAnalysisAgent
    from backend.agents.marketing_copy.agent import MarketingCopyAgent
    from backend.agents.inventory.agent import InventoryAgent
    from backend.agents.pricing.agent import PricingAgent
    from backend.agents.promotion.agent import PromotionAgent
    AgentRegistry.register(ProductAnalysisAgent)
    AgentRegistry.register(TrendForecastAgent)
    AgentRegistry.register(CompetitorAnalysisAgent)
    AgentRegistry.register(MarketingCopyAgent)
    AgentRegistry.register(InventoryAgent)
    AgentRegistry.register(PricingAgent)
    AgentRegistry.register(PromotionAgent)