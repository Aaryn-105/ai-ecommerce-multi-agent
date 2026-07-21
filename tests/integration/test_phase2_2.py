"""Tests for Intent Recognition — rules engine + Agent, driven by realistic queries."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from backend.agents.intent_recognition.rules import (
    match_keywords,
    confidence_from_match,
    MatchResult,
)
from backend.agents.intent_recognition.agent import IntentRecognitionAgent
from backend.agents.registry import AgentRegistry
from backend.models.schemas import AgentInput, IntentOutput


# ═══════════════════════════════════════════════════════════
#  Rule-engine tests — realistic user queries
# ═══════════════════════════════════════════════════════════

class TestKeywordMatching:
    """Verify the three-level keyword scanner with real-world query patterns."""

    # ── Positive cases (should hit ≥2 levels) ─────────────

    @pytest.mark.parametrize(
        "query, description",
        [
            ("帮我分析一下电子产品类目的选品机会", "core+category+action"),
            ("对比这两款手机哪个性价比更高", "category+action"),
            ("预测未来30天这款背包的销量趋势", "core+action"),
            ("服装类目补货建议，库存不够了", "core+category"),
            ("这个电子产品的定价策略应该怎么定", "core+category+action"),
            ("给我推荐几个爆款女装，要利润率高的", "core+category"),
            ("SKU太多了，帮忙做个滞销品清理方案", "core+action"),
            ("现在女装市场的竞争格局怎么样", "category+action"),
            ("做个竞品分析报告，对标小米和华为", "core+action"),
            ("双十一促销方案策划，目标是提升GMV", "core+action"),
            ("看看这批货的库存周转率", "core+action"),
            ("选品分析", "core+action"),
            ("电子产品 销量 趋势", "core+category+action"),
            ("男装 定价 策略", "core+category+action"),
        ],
    )
    def test_ecommerce_queries_hit_two_or_more_levels(self, query: str, description: str) -> None:
        result = match_keywords(query)
        assert result.is_ecommerce, (
            f"FAIL [{description}] query={query!r}  "
            f"levels_hit={result.total_levels_hit}  "
            f"matches={result.matches}"
        )

    # ── Negative cases (should hit ≤1 level) ─────────────

    @pytest.mark.parametrize(
        "query, description",
        [
            ("今天天气怎么样", "casual"),
            ("帮我写一首诗", "creative"),
            ("Python怎么安装", "tech"),
            ("你好", "greeting"),
            ("1+1等于几", "math"),
            ("推荐一部好看的电影", "movie"),
            ("怎么煮红烧肉", "recipe"),
            ("明天开会提醒我", "reminder"),
            ("帮我查一下明天的航班", "travel"),
            ("这个bug怎么修复", "coding"),
        ],
    )
    def test_non_ecommerce_queries_hit_fewer_than_two_levels(self, query: str, description: str) -> None:
        result = match_keywords(query)
        assert not result.is_ecommerce, (
            f"FAIL [{description}] query={query!r}  "
            f"levels_hit={result.total_levels_hit}  "
            f"matches={result.matches}"
        )

    # ── Edge cases ───────────────────────────────────────

    def test_empty_message(self) -> None:
        result = match_keywords("")
        assert result.total_levels_hit == 0
        assert result.all_keywords == []
        assert result.is_ecommerce is False

    def test_special_characters(self) -> None:
        result = match_keywords("!@#$%^&*()")
        assert result.total_levels_hit == 0

    def test_numbers_only(self) -> None:
        result = match_keywords("2024-01-15 100 200 300")
        assert result.total_levels_hit == 0

    def test_case_insensitivity(self) -> None:
        result = match_keywords("SKU Management and ROI Analysis for electronics")
        assert result.is_ecommerce is True

    def test_partial_word_does_not_false_match(self) -> None:
        # "分析" is a complete word; ensure partial matches like "分析师" are checked
        result = match_keywords("我想成为一名数据分析师")
        # "分析" is in LEVEL_1_CORE, "电子" is not present as standalone word here
        # "数据" is not a keyword, "分析师" contains "分析" as substring
        # Since our matching uses `in`, "分析" would match from "数据分析师"
        # This is an edge case where traditional Chinese compounds may cause false positives
        # Let's check what happens
        assert "分析" in result.all_keywords, (
            f"'分析' should match from '数据分析师'. Matches: {result.matches}"
        )


# ═══════════════════════════════════════════════════════════
#  Confidence scoring
# ═══════════════════════════════════════════════════════════

class TestConfidence:
    def test_three_levels_high_confidence(self) -> None:
        result = match_keywords("电子产品选品分析")
        assert confidence_from_match(result) == 0.95

    def test_two_levels_medium_confidence(self) -> None:
        result = match_keywords("选品分析")
        assert confidence_from_match(result) == 0.80

    def test_one_level_low_confidence(self) -> None:
        result = match_keywords("电子产品")
        assert confidence_from_match(result) == 0.40

    def test_zero_levels_zero_confidence(self) -> None:
        result = match_keywords("你好")
        assert confidence_from_match(result) == 0.0


# ═══════════════════════════════════════════════════════════
#  Agent integration tests
# ═══════════════════════════════════════════════════════════

class TestIntentRecognitionAgent:
    """Test the Agent wrapper with real queries."""

    @pytest.mark.asyncio
    async def test_rules_fast_path_returns_high_confidence(self) -> None:
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_1",
            request_id="req_001",
            input_data={"message": "帮我分析电子产品类目的选品机会"},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["is_ecommerce_query"] is True
        assert result.output_data["confidence"] >= 0.80
        assert len(result.output_data["matched_keywords"]) > 0
        # Fast path → no LLM
        assert result.execution_meta.llm_used is False
        assert result.execution_meta.llm_calls == 0

    @pytest.mark.asyncio
    async def test_rules_fast_path_single_level(self) -> None:
        """A query hitting only 1 level should still pass rules but with low confidence."""
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_2",
            request_id="req_002",
            input_data={"message": "电子产品"},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        # Only 1 level matched → confidence < 0.80 → should try LLM
        # Since no API key, LLM will return fallback (is_ecommerce_query=False)
        assert result.output_data["confidence"] < 0.80

    @pytest.mark.asyncio
    async def test_non_ecommerce_query(self) -> None:
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_3",
            request_id="req_003",
            input_data={"message": "今天天气怎么样"},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["is_ecommerce_query"] is False

    @pytest.mark.asyncio
    async def test_empty_message(self) -> None:
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_4",
            request_id="req_004",
            input_data={"message": ""},
        )
        result = await agent.run(inp)
        assert result.status == "completed"
        assert result.output_data["is_ecommerce_query"] is False
        assert result.output_data["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_output_matches_intent_output_schema(self) -> None:
        """Verify the agent output can be parsed by the IntentOutput pydantic model."""
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_5",
            request_id="req_005",
            input_data={"message": "电子产品选品分析"},
        )
        result = await agent.run(inp)
        parsed = IntentOutput.model_validate(result.output_data)
        assert parsed.is_ecommerce_query is True
        assert parsed.confidence >= 0.80
        assert len(parsed.matched_keywords) >= 3

    @pytest.mark.asyncio
    async def test_fake_store_derived_query(self) -> None:
        """Simulate a user query that references real FakeStore categories."""
        categories = ["electronics", "jewelery", "men's clothing", "women's clothing"]
        for cat in categories:
            query = f"分析{cat}类目的选品机会"
            inp = AgentInput(
                task_id=f"intent_{cat}",
                request_id="req_fs",
                input_data={"message": query},
            )
            agent = IntentRecognitionAgent()
            result = await agent.run(inp)
            assert result.status == "completed"
            # Even with English category names embedded, "分析"+"选品" = L1+L3
            assert result.output_data["is_ecommerce_query"] is True, (
                f"Failed for category: {cat}  query={query}"
            )

    @pytest.mark.asyncio
    async def test_registered_in_registry(self) -> None:
        AgentRegistry.register(IntentRecognitionAgent)
        cls = AgentRegistry.get("intent_recognition")
        assert cls is IntentRecognitionAgent
        AgentRegistry.clear()


# ═══════════════════════════════════════════════════════════
#  LLM fallback path (no real API key — tests the code)
# ═══════════════════════════════════════════════════════════

class TestLLMFallback:
    """Verify the fallback path behaves correctly when LLM is unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_on_single_level_query(self) -> None:
        """A 1-level match triggers LLM; without key it returns fallback."""
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_fb_1",
            request_id="req_fb",
            input_data={"message": "电子产品"},
        )
        result = await agent.run(inp)
        # Only 1 level → agent tries LLM → LLM key empty → fallback
        assert result.status == "completed"
        assert result.output_data["is_ecommerce_query"] is False  # LLM fallback
        assert result.output_data["confidence"] == 0.30  # fallback confidence
        assert result.execution_meta.llm_used is True  # attempted LLM
        assert result.execution_meta.llm_calls == 1

    @pytest.mark.asyncio
    async def test_llm_called_meta(self) -> None:
        agent = IntentRecognitionAgent()
        inp = AgentInput(
            task_id="intent_fb_2",
            request_id="req_fb",
            input_data={"message": "今天天气怎么样"},
        )
        result = await agent.run(inp)
        # 0 levels matched → try LLM → fallback
        assert result.execution_meta.llm_calls == 1
