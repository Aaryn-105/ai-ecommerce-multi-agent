import asyncio, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from backend.agents.orchestrator.agent import OrchestratorAgent
from backend.models.schemas import AgentInput
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

async def test():
    from backend.services.fake_store import FakeStoreService
    fs = FakeStoreService()
    try:
        products = await fs.get_all_products()
    finally:
        await fs.close()

    orch = OrchestratorAgent()
    inp = AgentInput(task_id='t1', request_id='r1',
                     input_data={'message': '\u5e2e\u6211\u5206\u6790\u7535\u5b50\u4ea7\u54c1\u7c7b\u76ee\u7684\u9009\u54c1\u673a\u4f1a', 'products': products},
                     context={'all_products': products})
    t0 = time.time()
    result = await orch.run(inp)
    print(f'Elapsed: {time.time()-t0:.1f}s, status: {result.status}, error: {result.error}')
    out = result.output_data
    plan_steps = out.get('plan_steps', [])
    final_report = out.get('final_report', {})
    sections = final_report.get('sections', {})
    print(f'Plan steps: {len(plan_steps)}')
    print(f'Final sections: {len(sections)}')
    print(f'Section keys: {list(sections.keys())}')
    if plan_steps:
        for s in plan_steps:
            print(f'  - {s.get("agent","?")}')

asyncio.run(test())