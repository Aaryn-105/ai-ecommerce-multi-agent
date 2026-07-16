"""Content validation and length capping for generated marketing copy."""
from __future__ import annotations
from typing import Any

MAX_TAGLINE_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 2000
MAX_SOCIAL_LENGTH = 500

TEMPLATE_FALLBACK: dict[str, str] = {
    "tagline": "{title} \u2014 品质优选",
    "bullets": "- 品质保障\n- 价格实惠\n- 好评如潮\n- 快速发货",
    "description": "优质商品，值得购买。\n\n立即选购，享受品质生活。",
    "social": "**好物推荐** {title}\n\n品质优选，值得信赖。",
}


def validate_length(text: str, max_len: int) -> str:
    """Ensure text does not exceed *max_len* characters."""
    return text[:max_len] if len(text) > max_len else text


def anti_hallucination_check(text: str, product: dict[str, Any]) -> tuple[bool, str]:
    """Basic anti-hallucination: verify key product facts."""
    title = product.get("title", "")
    is_valid = True
    warnings = ""

    if title and len(title) > 5 and title not in text and title[:20] not in text:
        is_valid = False
        warnings = "Product title reference missing"

    return is_valid, warnings


def validate_copy_set(copies: dict[str, str], product: dict[str, Any]) -> dict[str, str]:
    """Apply validation, length capping, and template fallback."""
    result: dict[str, str] = {}

    for key, max_len in [
        ("tagline", MAX_TAGLINE_LENGTH),
        ("bullets", 400),
        ("description", MAX_DESCRIPTION_LENGTH),
        ("social", MAX_SOCIAL_LENGTH),
    ]:
        text = copies.get(key, "")
        valid, _ = anti_hallucination_check(text, product)

        if not text or not valid:
            fallback = TEMPLATE_FALLBACK.get(key, "")
            text = fallback.replace("{title}", product.get("title", "Product"))
        else:
            text = validate_length(text, max_len)

        result[key] = text

    return result