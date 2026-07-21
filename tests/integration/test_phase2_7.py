"""Tests for Marketing Copy \u2014 brief generator, template providers, validator, and agent.
All tests use real FakeStore data."""
from __future__ import annotations
from typing import Any
import pytest
import pytest_asyncio
from backend.agents.marketing_copy.brief_generator import (
    determine_tone, determine_price_strategy, extract_selling_points, build_marketing_brief)
from backend.agents.marketing_copy.template_providers import (
    generate_tagline, generate_bullets, generate_description, generate_social_copy, generate_all_copies)
from backend.agents.marketing_copy.validator import validate_length, anti_hallucination_check, validate_copy_set
from backend.agents.marketing_copy.agent import MarketingCopyAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, MarketingCopyOutput
from backend.services.fake_store import FakeStoreService

_REAL_PRODUCTS: list[dict] | None = None

@pytest_asyncio.fixture(scope="session")
async def real_products() -> list[dict]:
    global _REAL_PRODUCTS
    if _REAL_PRODUCTS is not None:
        return _REAL_PRODUCTS
    svc = FakeStoreService()
    try:
        _REAL_PRODUCTS = await svc.get_all_products()
    finally:
        await svc.close()
    assert len(_REAL_PRODUCTS) == 20
    return _REAL_PRODUCTS

@pytest.fixture(autouse=True)
def _reg_cleanup():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()

# ── Brief Generator Tests ──

class TestDetermineTone:
    def test_electronics_tone(self):
        tone = determine_tone("electronics", 4.2)
        assert "\u79d1\u6280" in tone or "\u4e13\u4e1a" in tone

    def test_high_rating_adds_confidence(self):
        tone = determine_tone("electronics", 4.5)
        assert "\u81ea\u4fe1" in tone

    def test_low_rating(self):
        tone = determine_tone("jewelery", 2.5)
        assert "诚恳" in tone

    @pytest.mark.asyncio
    async def test_from_real_product(self, real_products):
        p = real_products[0]
        tone = determine_tone(p["category"], p["rating"]["rate"])
        assert isinstance(tone, str) and len(tone) > 0

class TestDeterminePriceStrategy:
    def test_premium_pricing(self):
        strat = determine_price_strategy(200.0, 100.0, "\u9ad8\u4ef7")
        assert "\u9ad8\u4ef7" in strat
        assert "\u9ad8\u7aef" in strat or "\u7a00\u7f3a" in strat

    def test_penetration_pricing(self):
        strat = determine_price_strategy(10.0, 50.0, "\u4f4e\u4ef7")
        assert "\u4f4e\u4ef7" in strat or "\u6e17\u900f" in strat

    def test_competitive_default(self):
        strat = determine_price_strategy(50.0, 50.0)
        assert "\u7ade\u4e89" in strat

    @pytest.mark.asyncio
    async def test_from_real_product(self, real_products):
        p = real_products[0]
        strat = determine_price_strategy(p["price"])
        assert isinstance(strat, str) and len(strat) > 0

class TestExtractSellingPoints:
    @pytest.mark.asyncio
    async def test_from_real_products(self, real_products):
        for p in real_products[:5]:
            points = extract_selling_points(p)
            assert len(points) >= 2
            print(f"  {p['title'][:25]}...: {len(points)} points")

    def test_minimum_points(self):
        points = extract_selling_points({"id": 1, "title": "Test", "category": "x",
            "price": 10, "rating": {"rate": 3.0, "count": 5}, "description": ""})
        assert len(points) >= 2

class TestBuildMarketingBrief:
    @pytest.mark.asyncio
    async def test_from_real_product(self, real_products):
        brief = build_marketing_brief(real_products[0])
        assert "tone" in brief
        assert "core_selling_point" in brief
        assert "price_strategy" in brief
        assert "selling_points" in brief
        assert len(brief["selling_points"]) >= 2

    @pytest.mark.asyncio
    async def test_with_positioning_data(self, real_products):
        pos = {"price_label": "\u4f4e\u4ef7", "category_avg_price": 100.0, "advantages": ["\u4ef7\u683c\u4f18\u52bf"]}
        brief = build_marketing_brief(real_products[0], pos)
        assert len(brief["selling_points"]) >= 2

# ── Template Provider Tests ──

class TestGenerateTagline:
    @pytest.mark.asyncio
    async def test_from_real_products(self, real_products):
        for p in real_products[:3]:
            brief = build_marketing_brief(p)
            tagline = generate_tagline(p, brief)
            assert isinstance(tagline, str) and len(tagline) > 5
            assert p["title"][:10] in tagline
            print(f"  Tagline: {tagline[:50]}...")

    def test_deterministic(self):
        p = {"id": 1, "title": "Test Product", "category": "electronics"}
        b = build_marketing_brief(p)
        t1 = generate_tagline(p, b)
        t2 = generate_tagline(p, b)
        assert t1 == t2

class TestGenerateBullets:
    @pytest.mark.asyncio
    async def test_from_real_products(self, real_products):
        for p in real_products[:3]:
            brief = build_marketing_brief(p)
            bullets = generate_bullets(p, brief)
            assert 3 <= len(bullets) <= 5
            for b in bullets:
                assert len(b) > 5
            print(f"  {p['title'][:20]}...: {len(bullets)} bullets")

    @pytest.mark.asyncio
    async def test_all_categories_covered(self, real_products):
        cats = set(p["category"] for p in real_products)
        for cat in cats:
            products_in_cat = [p for p in real_products if p["category"] == cat]
            p = products_in_cat[0]
            brief = build_marketing_brief(p)
            bullets = generate_bullets(p, brief)
            assert len(bullets) >= 3, f"Failed for category: {cat}"

class TestGenerateDescription:
    @pytest.mark.asyncio
    async def test_from_real_product(self, real_products):
        p = real_products[0]
        brief = build_marketing_brief(p)
        tagline = generate_tagline(p, brief)
        bullets = generate_bullets(p, brief)
        desc = generate_description(p, brief, tagline, bullets)
        assert len(desc) > 50
        assert "###" in desc
        print(f"  Description length: {len(desc)} chars")

class TestGenerateSocialCopy:
    @pytest.mark.asyncio
    async def test_from_real_products(self, real_products):
        for p in real_products[:3]:
            brief = build_marketing_brief(p)
            tagline = generate_tagline(p, brief)
            social = generate_social_copy(p, brief, tagline)
            assert len(social) > 30
            assert "$" in social
            print(f"  Social: {social[:40]}...")

class TestGenerateAllCopies:
    @pytest.mark.asyncio
    async def test_contains_all_keys(self, real_products):
        p = real_products[0]
        brief = build_marketing_brief(p)
        copies = generate_all_copies(p, brief)
        for key in ["tagline", "bullets", "description", "social"]:
            assert key in copies
            assert len(copies[key]) > 0

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products):
        p = real_products[0]
        brief = build_marketing_brief(p)
        c1 = generate_all_copies(p, brief)
        c2 = generate_all_copies(p, brief)
        assert c1 == c2

# ── Validator Tests ──

class TestValidateLength:
    def test_short_text_unchanged(self):
        assert validate_length("hello", 100) == "hello"

    def test_long_text_truncated(self):
        assert validate_length("hello world", 5) == "hello"

class TestAntiHallucinationCheck:
    @pytest.mark.asyncio
    async def test_valid_copy_passes(self, real_products):
        p = real_products[0]
        text = f"This is {p['title']} - a great product"
        valid, warn = anti_hallucination_check(text, p)
        assert valid is True

    @pytest.mark.asyncio
    async def test_copy_without_title_fails(self, real_products):
        p = real_products[0]
        text = "This is a generic product description"
        valid, warn = anti_hallucination_check(text, p)
        if p.get("title") and len(p["title"]) > 5:
            assert valid is False

class TestValidateCopySet:
    @pytest.mark.asyncio
    async def test_valid_copies_pass(self, real_products):
        p = real_products[0]
        brief = build_marketing_brief(p)
        copies = generate_all_copies(p, brief)
        validated = validate_copy_set(copies, p)
        for key in ["tagline", "bullets", "description", "social"]:
            assert key in validated
            assert len(validated[key]) > 0

    @pytest.mark.asyncio
    async def test_empty_copies_get_fallback(self, real_products):
        p = real_products[0]
        validated = validate_copy_set({}, p)
        assert len(validated["tagline"]) > 0

# ── MarketingCopyAgent Tests ──

class TestMarketingCopyAgent:
    @pytest.mark.asyncio
    async def test_agent_with_real_products(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_001", request_id="req_001",
            input_data={"products": real_products[:3]})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["total_generated"] == 3

    @pytest.mark.asyncio
    async def test_each_copy_has_all_fields(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_fields", request_id="req_fields",
            input_data={"products": real_products[:2]})
        result = await agent.run(inp)
        for c in result.output_data["copies"]:
            assert c["product_id"] > 0
            gc = c["generated_copies"]
            for key in ["tagline", "bullets", "description", "social"]:
                assert key in gc
                assert len(gc[key]) > 0, f"Empty {key} for product {c['product_id']}"
            cs = c["copy_strategy"]
            for key in ["tone", "core_selling_point", "price_strategy"]:
                assert key in cs
                assert len(cs[key]) > 0

    @pytest.mark.asyncio
    async def test_all_categories_generated(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_cats", request_id="req_cats",
            input_data={"products": real_products})
        result = await agent.run(inp)
        cats = set(c["category"] for c in result.output_data["copies"])
        assert len(cats) == 4
        print(f"  Categories: {cats}")

    @pytest.mark.asyncio
    async def test_deterministic(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_det", request_id="req_det",
            input_data={"products": real_products[:3]})
        r1 = await agent.run(inp)
        r2 = await agent.run(inp)
        for c1, c2 in zip(r1.output_data["copies"], r2.output_data["copies"]):
            assert c1["generated_copies"] == c2["generated_copies"]

    @pytest.mark.asyncio
    async def test_empty_products(self):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_empty", request_id="req_empty",
            input_data={"products": []})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["copies"] == []

    @pytest.mark.asyncio
    async def test_output_matches_schema(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_schema", request_id="req_schema",
            input_data={"products": [real_products[0]]})
        result = await agent.run(inp)
        parsed = MarketingCopyOutput.model_validate(result.output_data)
        assert len(parsed.copies) == 1
        assert parsed.copies[0].product_id == real_products[0]["id"]

    @pytest.mark.asyncio
    async def test_execution_meta_no_llm(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_meta", request_id="req_meta",
            input_data={"products": real_products[:3]})
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0
        print(f"  Execution time: {result.execution_meta.execution_time_ms}ms")

    @pytest.mark.asyncio
    async def test_registered_in_registry(self):
        AgentRegistry.register(MarketingCopyAgent)
        cls = AgentRegistry.get("marketing_copy")
        assert cls is MarketingCopyAgent

    @pytest.mark.asyncio
    async def test_integration_with_executor(self, real_products):
        from backend.agents.orchestrator.executor import Executor
        from backend.models.schemas import PlanStep
        AgentRegistry.register(MarketingCopyAgent)
        plan = [PlanStep(agent="marketing_copy", params={"products": real_products[:2]}, depends_on=[])]
        executor = Executor(request_id="exec_mc")
        context = await executor.run(plan)
        assert "marketing_copy" in context
        assert context["marketing_copy"]["status"] == "completed"
        assert len(context["marketing_copy"]["output_data"]["copies"]) == 2

    @pytest.mark.asyncio
    async def test_with_positioning_data(self, real_products):
        pos_data = [{"product_id": p["id"], "price_label": "\u4e2d\u7b49",
                     "category_avg_price": 50.0, "advantages": ["\u4ef7\u683c\u5408\u7406"]}
                    for p in real_products[:2]]
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_pos", request_id="req_pos",
            input_data={"products": real_products[:2], "positioning_data": pos_data})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["copies"]) == 2

    @pytest.mark.asyncio
    async def test_context_pipeline_from_competitor(self, real_products):
        AgentRegistry.register(MarketingCopyAgent)
        pos_data = [{"product_id": p["id"], "title": p["title"], "category": p["category"],
                     "price": p["price"], "rating": p["rating"],
                     "price_label": "\u4e2d\u7b49", "category_avg_price": 50.0}
                    for p in real_products[:3]]
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_ctx", request_id="req_ctx",
            input_data={},
            context={"competitor_analysis": {"output_data": {"product_positioning": pos_data}}})
        result = await agent.run(inp)
        assert result.status == "completed"
        assert len(result.output_data["copies"]) == 3

    @pytest.mark.asyncio
    async def test_summary_reflects_count(self, real_products):
        agent = MarketingCopyAgent()
        inp = AgentInput(task_id="mc_sum", request_id="req_sum",
            input_data={"products": real_products[:5]})
        result = await agent.run(inp)
        assert result.output_data["summary"] != ""
        assert "5" in result.output_data["summary"] or "\u4e94" in result.output_data["summary"]
        print(f"  Summary: {result.output_data['summary']}")


class MockLLMService:
    """Simple mock LLM service for testing — returns preset data."""
    def __init__(self, return_value=None):
        self._return_value = return_value or {}
        self.chat_calls = []
        self.client = None

    async def chat(self, system_prompt="", user_message="", temperature=0.7,
                   max_tokens=1024, json_mode=True, fallback=None):
        self.chat_calls.append({
            "system_prompt": system_prompt,
            "user_message": user_message,
        })
        return self._return_value


class TestMarketingCopyLLMIntegration:
    """Tests for LLM integration path of Marketing Copy Agent."""

    @pytest.mark.asyncio
    async def test_sources_used_is_template_when_no_key(self, real_products):
        """Without API key, sources_used should show template engine."""
        agent = MarketingCopyAgent()
        inp = AgentInput(
            task_id="mc_src",
            request_id="req_src",
            input_data={"products": [real_products[0]]},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        copy_data = result.output_data["copies"][0]
        assert "模板引擎" in copy_data["sources_used"]

    @pytest.mark.asyncio
    async def test_llm_used_false_when_no_key(self, real_products):
        """Without API key, llm_used should be False."""
        agent = MarketingCopyAgent()
        inp = AgentInput(
            task_id="mc_llm_false",
            request_id="req_llm_false",
            input_data={"products": [real_products[0]]},
        )
        result = await agent.run(inp)
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0

    @pytest.mark.asyncio
    async def test_llm_path_with_mock_service(self, real_products):
        """When a mock LLM returns valid output, agent should use it.

        All mock values include the product title prefix to pass
        the anti_hallucination_check in validate_copy_set.
        """
        p = real_products[0]
        title_prefix = p["title"][:20]

        mock_llm = MockLLMService(return_value={
            "tagline": f"{title_prefix} — AI生成广告语",
            "bullets": f"{title_prefix}\n卖点1\n卖点2\n卖点3\n卖点4",
            "description": f"{title_prefix}是一款AI生成的产品描述，内容丰富值得购买。",
            "social": f"AI生成社交媒体文案，{title_prefix}快来购买！",
        })

        import backend.core.config as cfg
        original_key = cfg.settings.OPENAI_API_KEY
        cfg.settings.OPENAI_API_KEY = "sk-test-fake-key"

        try:
            agent = MarketingCopyAgent(llm_service=mock_llm)
            inp = AgentInput(
                task_id="mc_llm",
                request_id="req_llm",
                input_data={"products": [p]},
            )
            result = await agent.run(inp)
            assert result.status == "completed"
            copy_data = result.output_data["copies"][0]
            assert "LLM" in copy_data["sources_used"]
            assert result.execution_meta.llm_used is True
            assert result.execution_meta.llm_calls > 0
            generated = copy_data["generated_copies"]
            assert "AI生成" in generated["tagline"]
            assert "卖点1" in generated["bullets"]
            assert "AI生成" in generated["description"]
            assert "AI生成" in generated["social"]
        finally:
            cfg.settings.OPENAI_API_KEY = original_key

    @pytest.mark.asyncio
    async def test_llm_fallback_to_template(self, real_products):
        """When LLM returns empty/invalid data, agent falls back to templates."""
        mock_llm = MockLLMService(return_value={})

        import backend.core.config as cfg
        original_key = cfg.settings.OPENAI_API_KEY
        cfg.settings.OPENAI_API_KEY = "sk-test-fake-key"

        try:
            agent = MarketingCopyAgent(llm_service=mock_llm)
            inp = AgentInput(
                task_id="mc_fallback",
                request_id="req_fallback",
                input_data={"products": [real_products[0]]},
            )
            result = await agent.run(inp)
            assert result.status == "completed"
            copy_data = result.output_data["copies"][0]
            generated = copy_data["generated_copies"]
            assert generated["tagline"]  # Should be non-empty from template
        finally:
            cfg.settings.OPENAI_API_KEY = original_key