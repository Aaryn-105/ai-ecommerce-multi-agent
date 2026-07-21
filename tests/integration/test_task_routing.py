"""Task-specific routing tests for the conversational analysis endpoint."""
from __future__ import annotations

import asyncio

from backend.agents.orchestrator.planner import Planner


def _plan(query: str):
    return asyncio.run(Planner().plan(query))


def test_selection_query_runs_selection_and_trend_only():
    plan = _plan("\u5e2e\u6211\u5206\u6790\u7535\u5b50\u4ea7\u54c1\u7c7b\u76ee\u7684\u9009\u54c1\u673a\u4f1a")
    assert [step.agent for step in plan] == ["product_analysis", "trend_forecast"]
    assert all(step.report for step in plan)
    assert all(step.params["category"] == "electronics" for step in plan)


def test_marketing_trend_query_hides_product_support_step():
    plan = _plan("\u5e2e\u6211\u5206\u6790\u80cc\u5305\u7684\u8425\u9500\u8d8b\u52bf")
    assert [step.agent for step in plan] == ["product_analysis", "trend_forecast"]
    assert plan[0].report is False
    assert plan[1].report is True
    # "backpack" alias maps to FakeStore's "men's clothing" category
    assert plan[1].params["category"] == "men's clothing"


def test_competitor_query_does_not_run_unrequested_modules():
    plan = _plan("\u5e2e\u6211\u5bf9\u6bd4\u4e00\u4e0b\u80cc\u5305\u7684\u7ade\u54c1\u5206\u6790")
    assert [step.agent for step in plan] == ["product_analysis", "competitor_analysis"]
    assert [step.report for step in plan] == [False, True]
    assert plan[1].depends_on == ["product_analysis"]



def test_is_empty_data_detects_zero_matched_count():
    from backend.services.report_polisher import _is_empty_data
    # All sections have matched_count=0 -> empty
    sections = {
        "trend_forecast": {"summary": "no data", "analysis_scope": {"matched_count": 0}},
        "competitor_analysis": {"analysis_scope": {"matched_count": 0}},
    }
    assert _is_empty_data(sections) is True


def test_is_empty_data_detects_non_empty_products():
    from backend.services.report_polisher import _is_empty_data
    sections = {
        "product_analysis": {
            "selected_products": [{"id": 1, "title": "SSD"}],
            "analysis_scope": {"matched_count": 1},
        },
        "trend_forecast": {"analysis_scope": {"matched_count": 1}},
    }
    assert _is_empty_data(sections) is False


def test_is_empty_data_handles_empty_or_none_input():
    from backend.services.report_polisher import _is_empty_data
    assert _is_empty_data(None) is True
    assert _is_empty_data({}) is True


def test_planner_returns_fakestore_category_for_aliases():
    """The planner should return FakeStore category names so product filtering works."""
    from backend.agents.orchestrator.planner import extract_category
    # Chinese aliases -> FakeStore categories
    assert extract_category("\u5e2e\u6211\u5206\u6790\u80cc\u5305\u7684\u8d8b\u52bf") == "men's clothing"
    assert extract_category("\u5e2e\u6211\u5206\u6790\u7535\u5b50\u4ea7\u54c1") == "electronics"
    assert extract_category("\u5e2e\u6211\u5206\u6790\u5973\u88c5\u9500\u552e") == "women's clothing"


def test_empty_data_prompt_is_defined():
    from backend.services.report_polisher import _EMPTY_DATA_PROMPT
    # Must be a non-empty string with the empty-data protocol
    assert _EMPTY_DATA_PROMPT
    assert "\u6570\u636e\u91c7\u96c6\u7f3a\u53e3" in _EMPTY_DATA_PROMPT
    assert "{task_extensions}" in _EMPTY_DATA_PROMPT