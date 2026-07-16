"""Product Analysis Agent — score, rank, and select top products."""
from __future__ import annotations

from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.product_analysis.scorer import (
    compute_global_extrema,
    generate_selection_reason,
    price_segment,
    score_product,
)
from backend.models.schemas import ProductRaw


class ProductAnalysisAgent(BaseAgent):
    """Analyse products from FakeStore API via 4-dimension scoring.

    Flow::

        products → Step 1: preprocess (category stats, extrema)
                 → Step 2: score each product (Min-Max + weighted)
                 → Step 3: rank, select top N, format output

    Pure code — zero LLM calls.
    """

    agent_name = "product_analysis"

    def __init__(self, top_n: int = 6) -> None:
        self._top_n = top_n

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        # Accept products either from input_data or context
        raw_products: list[dict[str, Any]] = (
            input_data.get("products")
            or context.get("all_products") or (context.get("product_analysis", {}).get("output_data", {}).get("all_products"))
            or []
        )

        if not raw_products:
            # Try parsing from ProductRaw
            products_raw = input_data.get("products")
            if products_raw and isinstance(products_raw, list):
                raw_products = [p.model_dump() if hasattr(p, "model_dump") else p for p in products_raw]

        if not raw_products:
            return {
                "selected_products": [],
                "statistics": {
                    "total_analyzed": 0,
                    "selected_count": 0,
                    "cutoff_score": 0,
                    "category_distribution": {},
                    "price_segment_breakdown": {},
                },
                "summary": "No products to analyse.",
            }

        # ── Step 1: Preprocess ──────────────────────────
        extrema = compute_global_extrema(raw_products)

        # Category stats
        cat_groups: dict[str, list[dict]] = {}
        for p in raw_products:
            cat = p["category"]
            cat_groups.setdefault(cat, []).append(p)

        # ── Step 2: Score each product ───────────────────
        scored: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for p in raw_products:
            scores = score_product(p, extrema)
            scored.append((p, scores))

        # Sort by final_score descending
        scored.sort(key=lambda x: -x[1]["final_score"])

        # Select top N
        cutoff_score = scored[self._top_n - 1][1]["final_score"] if len(scored) >= self._top_n else scored[-1][1]["final_score"]
        selected = scored[:self._top_n]

        # ── Step 3: Format output ────────────────────────
        selected_products = []
        cat_dist: dict[str, int] = {}
        price_dist: dict[str, int] = {}

        for p, scores in selected:
            cat = p["category"]
            cat_dist[cat] = cat_dist.get(cat, 0) + 1
            seg = price_segment(p["price"])
            price_dist[seg] = price_dist.get(seg, 0) + 1

            reason = generate_selection_reason(scores["contributions"], scores["dimensions"])

            selected_products.append({
                "id": p["id"],
                "title": p["title"],
                "category": cat,
                "price": p["price"],
                "original_rating": {"rate": p["rating"]["rate"], "count": p["rating"]["count"]},
                "final_score": scores["final_score"],
                "score_breakdown": {
                    "dimensions": scores["dimensions"],
                    "contributions": scores["contributions"],
                },
                "selection_reason": reason,
            })

        summary = (
            f"从{len(raw_products)}件商品中筛选出{len(selected)}件重点关注商品，"
            f"涵盖{len(cat_dist)}个品类，综合评分区间{selected[-1][1]['final_score']}-{selected[0][1]['final_score']}分"
        )

        return {
            "selected_products": selected_products,
            "statistics": {
                "total_analyzed": len(raw_products),
                "selected_count": len(selected),
                "cutoff_score": cutoff_score,
                "category_distribution": cat_dist,
                "price_segment_breakdown": price_dist,
            },
            "summary": summary,
        }
