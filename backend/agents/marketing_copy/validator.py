"""Content validation and length capping for generated marketing copy."""
from __future__ import annotations
from typing import Any

MAX_TAGLINE_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 2000
MAX_SOCIAL_LENGTH = 500
MIN_DESCRIPTION_LENGTH = 60
MIN_SOCIAL_LENGTH = 30

TEMPLATE_FALLBACK: dict[str, str] = {
    "tagline": "{title} — 品质优选",
    "bullets": "- 品质保障\n- 价格实惠\n- 好评如潮\n- 快速发货",
    "description": "优质商品，值得购买。\n\n立即选购，享受品质生活。",
    "social": "**好物推荐** {title}\n\n品质优选，值得信赖。",
}


def validate_length(text: str, max_len: int) -> str:
    """Ensure text does not exceed *max_len* characters."""
    return text[:max_len] if len(text) > max_len else text


def _has_minimum_substance(text: str) -> bool:
    """Check that the copy is not empty, not pure symbols, and has some real content."""
    if not text or not text.strip():
        return False
    s = text.strip()
    # Must have at least one Chinese char OR a reasonable number of latin words
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in s)
    if has_cjk:
        # At least 4 chinese characters
        return len([ch for ch in s if "\u4e00" <= ch <= "\u9fff"]) >= 4
    # For non-CJK, must have at least 3 words
    return len([w for w in s.split() if len(w) >= 2]) >= 3


def _looks_template_like(text: str) -> bool:
    """Detect the historical template phrases so we can replace them."""
    if not text:
        return False
    bad_phrases = [
        "品质优选", "品质保障", "价格实惠", "好评如潮", "快速发货",
        "好物推荐", "优质商品，值得购买", "立即选购，享受品质生活",
        "品质优选，值得信赖",
    ]
    return any(p in text for p in bad_phrases)


def anti_hallucination_check(text: str, product: dict[str, Any]) -> tuple[bool, str]:
    """Lenient validation: just verify copy has substance; do NOT require title.
    
    Rationale: good creative marketing copy often omits the product name.
    We only check that the copy is non-empty and not the historical template filler.
    """
    if not _has_minimum_substance(text):
        return False, "Empty or insufficient content"
    return True, ""


def _enrich_with_title_if_missing(text: str, title: str) -> str:
    """For tagline/social only, gently prefix the brand name if it is absent."""
    if not title or title in text or title[:12] in text:
        return text
    # Only prepend for short tagline/social lines
    if len(text) <= 50:
        return f"{title} — {text}"
    return text


def validate_copy_set(copies: dict[str, str], product: dict[str, Any]) -> dict[str, str]:
    """Apply validation, length capping, and template fallback.

    Strict priority:
      1. If LLM copy is substantive AND not the template filler → trust it.
      2. Otherwise, fall back to template engine.
    """
    title = product.get("title", "Product")
    result: dict[str, str] = {}

    for key, max_len in [
        ("tagline", MAX_TAGLINE_LENGTH),
        ("bullets", 400),
        ("description", MAX_DESCRIPTION_LENGTH),
        ("social", MAX_SOCIAL_LENGTH),
    ]:
        text = copies.get(key, "") or ""
        # Strip whitespace
        text = text.strip()

        valid, _ = anti_hallucination_check(text, product)
        looks_template = _looks_template_like(text)

        if not valid or looks_template:
            # Fall back to template
            fallback = TEMPLATE_FALLBACK.get(key, "")
            text = fallback.replace("{title}", title)
        else:
            text = validate_length(text, max_len)
            # Only for tagline/social, optionally prefix the brand name
            if key in ("tagline", "social"):
                text = _enrich_with_title_if_missing(text, title)

        result[key] = text

    return result
