"""Pydantic v2 schemas for API and inter-agent communication."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
#  API Request / Response
# ═══════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    executive_summary: str = ''
    plan: list[dict[str, Any]] = []
    sections: dict[str, Any] = {}


class ExportRequest(BaseModel):
    report_id: int
    format: Literal["pdf", "docx"] = "pdf"
    sections: dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════
#  Agent Input / Output (通用包装)
# ═══════════════════════════════════════════════════════════

class AgentInput(BaseModel):
    task_id: str
    request_id: str
    input_data: dict[str, Any] = {}
    context: dict[str, Any] = {}
    dependencies: list[str] = []
    status: str = "pending"


class ExecutionMeta(BaseModel):
    execution_time_ms: float = 0.0
    llm_used: bool = False
    llm_calls: int = 0


class AgentResult(BaseModel):
    task_id: str
    status: Literal["completed", "failed"] = "completed"
    output_data: dict[str, Any] = {}
    execution_meta: ExecutionMeta = Field(default_factory=ExecutionMeta)
    error: str | None = None


# ═══════════════════════════════════════════════════════════
#  Intent Recognition
# ═══════════════════════════════════════════════════════════

class IntentInput(BaseModel):
    message: str


class IntentOutput(BaseModel):
    is_ecommerce_query: bool = False
    confidence: float = 0.0
    matched_keywords: list[str] = []
    explanation: str = ""


# ═══════════════════════════════════════════════════════════
#  Orchestrator — Plan step
# ═══════════════════════════════════════════════════════════

class PlanStep(BaseModel):
    agent: str
    params: dict[str, Any] = {}
    depends_on: list[str] = []
    description: str = ""
    report: bool = True


# ═══════════════════════════════════════════════════════════
#  Product Analysis
# ═══════════════════════════════════════════════════════════

class Rating(BaseModel):
    rate: float
    count: int


class ProductRaw(BaseModel):
    id: int
    title: str
    price: float
    description: str
    category: str
    image: str = ""
    rating: Rating


class ProductAnalysisInput(BaseModel):
    products: list[ProductRaw]
    context: dict[str, Any] = {}


class DimensionScores(BaseModel):
    rating: float = 0.0
    popularity: float = 0.0
    value: float = 0.0
    description: float = 0.0


class ScoreBreakdown(BaseModel):
    dimensions: DimensionScores
    contributions: DimensionScores


class SelectedProduct(BaseModel):
    id: int
    title: str
    category: str
    price: float
    original_rating: Rating
    final_score: float
    score_breakdown: ScoreBreakdown
    selection_reason: str = ""


class AnalysisStatistics(BaseModel):
    total_analyzed: int
    selected_count: int
    cutoff_score: float
    category_distribution: dict[str, int] = {}
    price_segment_breakdown: dict[str, int] = {}


class ProductAnalysisOutput(BaseModel):
    selected_products: list[SelectedProduct]
    statistics: AnalysisStatistics
    summary: str = ""


# ═══════════════════════════════════════════════════════════
#  Trend Forecast
# ═══════════════════════════════════════════════════════════

class TrendForecastInput(BaseModel):
    product_id: int
    days: int = 30
    window: int = 7


class DailySales(BaseModel):
    date: str
    units: int


class TrendForecastOutput(BaseModel):
    product_id: int
    historical: list[DailySales] = []
    ma_trend: list[float] = []
    forecast_7d: list[int] = []
    forecast_30d: list[int] = []
    summary: str = ""


# ═══════════════════════════════════════════════════════════
#  Competitor Analysis
# ═══════════════════════════════════════════════════════════

class CompetitorAnalysisInput(BaseModel):
    all_products: list[ProductRaw]
    selected_products: list[SelectedProduct]
    context: dict[str, Any] = {}


class CategoryBenchmark(BaseModel):
    product_count: int = 0
    avg_price: float = 0.0
    price_range: dict[str, float] = {}
    price_median: float = 0.0
    avg_rating: float = 0.0
    rating_range: dict[str, float] = {}
    total_reviews: int = 0
    avg_reviews: float = 0.0


class ProductPositioning(BaseModel):
    product_id: int
    title: str = ""
    category: str = ""
    price: float = 0.0
    category_avg_price: float = 0.0
    price_label: str = ""
    price_vs_avg_pct: float = 0.0
    rating: float = 0.0
    category_avg_rating: float = 0.0
    competitive_score: float = 0.0
    dimension_norms: dict[str, float] = {}
    contributions: dict[str, float] = {}
    price_percentile: float = 0.0
    rating_percentile: float = 0.0
    advantages: list[str] = []
    disadvantages: list[str] = []
    differentiators: list[str] = []


class CompetitorAnalysisOutput(BaseModel):
    category_benchmarks: dict[str, CategoryBenchmark] = {}
    product_positioning: list[ProductPositioning] = []
    market_summary: str = ""


# ═══════════════════════════════════════════════════════════
#  Marketing Copy
# ═══════════════════════════════════════════════════════════

class MarketingCopyInput(BaseModel):
    products: list[ProductRaw]
    positioning_data: list[ProductPositioning] = []
    context: dict[str, Any] = {}


class CopyStrategy(BaseModel):
    tone: str = ""
    core_selling_point: str = ""
    price_strategy: str = ""


class ProductCopy(BaseModel):
    product_id: int
    generated_copies: dict[str, str] = {}
    copy_strategy: CopyStrategy = Field(default_factory=CopyStrategy)
    sources_used: list[str] = []


class MarketingCopyOutput(BaseModel):
    copies: list[ProductCopy] = []


# ═══════════════════════════════════════════════════════════
#  Inventory
# ═══════════════════════════════════════════════════════════

class InventoryInput(BaseModel):
    candidate_products: list[dict[str, Any]] = []


class ReplenishmentPlan(BaseModel):
    product_id: int
    title: str = ""
    sales_velocity_score: float = 0.0
    stock_health_score: float = 0.0
    replenishment_urgency_score: float = 0.0
    turnover_rate_score: float = 0.0
    composite_score: float = 0.0
    suggested_reorder_qty: int = 0
    suggested_action: str = ""
    priority: int = 99


class InventorySummary(BaseModel):
    urgent_count: int = 0
    normal_count: int = 0
    no_action_count: int = 0
    total_order_value: float = 0.0


class InventoryOutput(BaseModel):
    replenishment_plans: list[ReplenishmentPlan] = []
    overall_summary: InventorySummary = Field(default_factory=InventorySummary)


# ═══════════════════════════════════════════════════════════
#  Pricing
# ═══════════════════════════════════════════════════════════

class PricingInput(BaseModel):
    target_product: dict[str, Any] = {}
    market_benchmark: dict[str, Any] = {}
    competitive_position: dict[str, Any] = {}


class PricingOutput(BaseModel):
    suggested_price: float = 0.0
    price_change: float = 0.0
    strategy: str = ""
    confidence: str = ""
    reason: str = ""


# ═══════════════════════════════════════════════════════════
#  Promotion
# ═══════════════════════════════════════════════════════════

class PromotionInput(BaseModel):
    product: dict[str, Any] = {}
    pricing_strategy: dict[str, Any] = {}
    marketing_copy: dict[str, Any] = {}
    inventory_status: dict[str, Any] = {}


class PromotionPlan(BaseModel):
    promotion_type: str = ""
    campaign_name: str = ""
    original_price: float = 0.0
    promotion_price: float = 0.0
    discount_rate: float = 0.0
    discount_label: str = ""
    estimated_roi: float = 0.0
    promotion_copy: str = ""
    duration_days: int = 0
    conditions: str = ""


class PromotionOutput(BaseModel):
    product_id: int = 0
    promotion_plan: PromotionPlan = Field(default_factory=PromotionPlan)
    alternative_plans: list[PromotionPlan] = []
    recommended_plan_index: int = 0


# ═══════════════════════════════════════════════════════════
#  Shared orchestration state
# ═══════════════════════════════════════════════════════════

class SharedState(BaseModel):
    query: str = ""
    plan_steps: list[PlanStep] = []
    context: dict[str, Any] = {}
    current_step_index: int = 0
    errors: list[str] = []
    final_report: dict[str, Any] | None = None
    conversation_id: str | None = None
