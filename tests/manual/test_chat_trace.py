import asyncio, sys, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from backend.agents.registry import AgentRegistry
from backend.agents.product_analysis.agent import ProductAnalysisAgent
from backend.agents.trend_forecast.agent import TrendForecastAgent
from backend.agents.competitor_analysis.agent import CompetitorAnalysisAgent
from backend.agents.marketing_copy.agent import MarketingCopyAgent
from backend.agents.inventory.agent import InventoryAgent
from backend.agents.pricing.agent import PricingAgent
from backend.agents.promotion.agent import PromotionAgent
for c in [ProductAnalysisAgent, TrendForecastAgent, CompetitorAnalysisAgent,
          MarketingCopyAgent, InventoryAgent, PricingAgent, PromotionAgent]:
    AgentRegistry.register(c)
print(f'Registered: {len(AgentRegistry.list_agents())} agents')

async def test():
    from backend.services.fake_store import FakeStoreService
    from backend.agents.orchestrator.agent import OrchestratorAgent
    from backend.models.schemas import AgentInput
    from backend.agents.intent_recognition.agent import IntentRecognitionAgent

    fs = FakeStoreService()
    try:
        products = await fs.get_all_products()
    finally:
        await fs.close()

    intent = IntentRecognitionAgent()
    intent_inp = AgentInput(task_id='i', request_id='r',
                           input_data={'message': '帮我分析电子产品类目的选品机会'})
    intent_res = await intent.run(intent_inp)
    print(f'Intent ecommerce: {intent_res.output_data.get("is_ecommerce_query")}')

    orch = OrchestratorAgent()
    orch_inp = AgentInput(task_id='o', request_id='r',
                          input_data={'message': '帮我分析电子产品类目的选品机会',
                                      'request_id': 'r',
                                      'products': products},
                          context={'all_products': products})
    t0 = time.time()
    res = await orch.run(orch_inp)
    print(f'Orchestrator: {time.time()-t0:.1f}s, status={res.status}')
    out = res.output_data
    print(f'Plan steps: {len(out.get("plan_steps", []))}')
    final_report = out.get('final_report', {})
    sections = final_report.get('sections', {}) if final_report else {}
    print(f'Final report sections: {len(sections)}')
    print(f'Final report keys: {list(final_report.keys()) if final_report else "empty"}')
    for k in sections:
        print(f'  - {k}')

asyncio.run(test())