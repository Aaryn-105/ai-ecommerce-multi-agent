"""Template-based marketing copy generators \u2014 zero-LLM fallback."""
from __future__ import annotations
from typing import Any

TAGLINE_TEMPLATES: dict[str, list[str]] = {
    "electronics": [
        "{title} \u2014 \u79d1\u6280\u8d4b\u80fd\uff0c\u4f53\u9a8c\u5347\u7ea7",
        "{short_title} \u2014 \u667a\u4eab\u672a\u6765\uff0c\u4ece\u6b64\u523b\u5f00\u59cb",
        "\u4e0d\u6b62\u4e8e\u6027\u80fd\uff1a{short_title}\uff0c\u4e3a\u6548\u7387\u800c\u751f",
        "\u4e13\u4e1a\u4e4b\u9009\uff1a{short_title}\uff0c\u7cbe\u51c6\u53ef\u9760",
    ],
    "men\u2019s clothing": [
        "{title} \u2014 \u578b\u683c\u5728\u7ebf\uff0c\u4ece\u5bb9\u6709\u5ea6",
        "{short_title}\uff0c\u5b9a\u4e49\u4f60\u7684\u98ce\u683c",
        "{short_title} \u2014 \u8d28\u611f\u7537\u58eb\u7684\u9009\u62e9",
        "\u7ecf\u5178\u4e0d\u8bbe\u9650\uff1a{short_title}\uff0c\u65e5\u5e38\u767e\u642d",
    ],
    "women\u2019s clothing": [
        "{title} \u2014 \u7efd\u653e\u4f60\u7684\u72ec\u7279\u9b45\u529b",
        "{short_title}\uff0c\u4f18\u96c5\u6bcf\u4e00\u523b",
        "{short_title} \u2014 \u6e29\u67d4\u800c\u6709\u529b\u91cf",
        "\u65f6\u5c1a\u4e0d\u968f\u6ce2\u9010\u6d41\uff1a{short_title}",
    ],
    "jewelery": [
        "{title} \u2014 \u73cd\u8d35\u65f6\u523b\uff0c\u95ea\u8000\u89c1\u8bc1",
        "{short_title}\uff0c\u4e3a\u4f18\u96c5\u800c\u751f",
        "{short_title} \u2014 \u6bcf\u4e00\u4ef6\u90fd\u662f\u827a\u672f\u54c1",
        "\u7480\u74a8\u4e4b\u9009\uff1a{short_title}\uff0c\u70b9\u4eae\u65e5\u5e38",
    ],
}

DEFAULT_TAGLINES = [
    "{title} \u2014 \u7cbe\u9009\u597d\u7269\uff0c\u503c\u5f97\u62e5\u6709",
    "{short_title}\uff0c\u54c1\u8d28\u751f\u6d3b\u4e4b\u9009",
]

BULLET_CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "electronics": [
        "\u26a1 {spec_tech} \u2014 \u6ee1\u8db3\u4e13\u4e1a\u9700\u6c42",
        "\U0001f4e6 \u5b98\u65b9\u6b63\u54c1\uff0c\u8d28\u91cf\u4fdd\u969c",
        "\U0001f4b0 {price_advantage}",
        "\u2b50 {rating_comment}",
        "\U0001f527 \u552e\u540e\u65e0\u5fe7\uff0c\u653e\u5fc3\u8d2d\u4e70",
    ],
    "men\u2019s clothing": [
        "\U0001f454 {fit_desc} \u2014 \u526a\u88c1\u5408\u4f53\uff0c\u7a7f\u7740\u8212\u9002",
        "\U0001f9f5 {material_note}",
        "\U0001f4b0 {price_advantage}",
        "\u2b50 {rating_comment}",
        "\U0001f504 7\u5929\u65e0\u7406\u7531\u9000\u6362",
    ],
    "women\u2019s clothing": [
        "\U0001f457 {style_note} \u2014 \u767e\u642d\u5355\u54c1",
        "\U0001f9f5 {material_note}",
        "\U0001f4b0 {price_advantage}",
        "\u2b50 {rating_comment}",
        "\U0001f4cf \u591a\u5c3a\u7801\u53ef\u9009\uff0c\u5b8c\u7f8e\u8d34\u5408",
    ],
    "jewelery": [
        "\U0001f48e {craft_note} \u2014 \u7cbe\u6e5b\u5de5\u827a",
        "\U0001f381 \u7cbe\u7f8e\u793c\u76d2\u5305\u88c5\uff0c\u9001\u793c\u4f73\u9009",
        "\U0001f4b0 {price_advantage}",
        "\u2b50 {rating_comment}",
        "\u2728 \u65e5\u5e38\u4f69\u6234\u6216\u7279\u6b8a\u573a\u5408\u7686\u5b9c",
    ],
}

DEFAULT_BULLETS = [
    "\u2705 {quality_note}",
    "\U0001f4b0 {price_advantage}",
    "\u2b50 {rating_comment}",
    "\U0001f4e6 \u5feb\u901f\u53d1\u8d27\uff0c\u6b63\u54c1\u4fdd\u969c",
]

DESCRIPTION_TEMPLATES: dict[str, str] = {
    "electronics": (
        "### \u4ea7\u54c1\u6982\u8ff0\n\n"
        "{title}\u662f\u4e00\u6b3e\u9ad8\u54c1\u8d28{category}\u4ea7\u54c1\uff0c{rating_comment}\u3002"
        "\u51ed\u501f\u51fa\u8272\u7684\u6027\u80fd\u548c\u53ef\u9760\u7684\u8d28\u91cf\uff0c\u6df1\u53d7{review_count}\u4f4d\u7528\u6237\u7684\u8ba4\u53ef\u3002\n\n"
        "### \u6838\u5fc3\u7279\u6027\n\n"
        "{bullet_text}\n\n"
        "### \u9002\u7528\u573a\u666f\n\n"
        "\u9002\u5408\u65e5\u5e38\u4f7f\u7528\u3001\u4e13\u4e1a\u5de5\u4f5c\u548c\u5347\u7ea7\u66f4\u6362\u9700\u6c42\u3002"
        "{short_title}\u90fd\u662f\u4e00\u4e2a\u660e\u667a\u4e4b\u9009\u3002\n\n"
        "### \u4e3a\u4ec0\u4e48\u9009\u62e9\u6211\u4eec\n\n"
        "{price_strategy}{core_selling_point}"
    ),
    "men\u2019s clothing": (
        "### \u4ea7\u54c1\u4ecb\u7ecd\n\n"
        "{title} \u2014 {price_advantage}\u3002{rating_comment}\uff0c"
        "\u662f{review_count}\u4f4d\u987e\u5ba2\u7684\u5171\u540c\u9009\u62e9\u3002\n\n"
        "### \u7a7f\u642d\u5efa\u8bae\n\n"
        "{bullet_text}\n\n"
        "### \u54c1\u8d28\u4fdd\u969c\n\n"
        "{core_selling_point}"
    ),
    "women\u2019s clothing": (
        "### \u4ea7\u54c1\u4ecb\u7ecd\n\n"
        "{title} \u2014 \u4e3a\u65f6\u5c1a\u800c\u751f\u3002{rating_comment}\uff0c"
        "{price_advantage}\u3002\n\n"
        "### \u642d\u914d\u63a8\u8350\n\n"
        "{bullet_text}\n\n"
        "### \u54c1\u8d28\u627f\u8bfa\n\n"
        "{core_selling_point}"
    ),
    "jewelery": (
        "### \u4ea7\u54c1\u4ecb\u7ecd\n\n"
        "{title} \u2014 \u7cbe\u81f4\u4e4b\u4f5c\u3002{rating_comment}\uff0c"
        "{price_advantage}\u3002\n\n"
        "### \u8bbe\u8ba1\u4eae\u70b9\n\n"
        "{bullet_text}\n\n"
        "### \u9001\u793c\u9996\u9009\n\n"
        "{core_selling_point}"
    ),
}

SOCIAL_TEMPLATES: list[str] = [
    "\U0001f4e2 **\u65b0\u54c1\u63a8\u8350** {title}\n\n"
    "{tagline}\n\n"
    "\u2b50 \u7528\u6237\u8bc4\u5206 {rating}/5 \u00b7 {reviews}\u6761\u8bc4\u4ef7\n"
    "\U0001f4b0 \u4ec5\u552e ${price:.2f}\n\n"
    "#\u597d\u7269\u63a8\u8350 #{category_tag}",

    "\U0001f525 **\u70ed\u5356\u5355\u54c1** {short_title}\n\n"
    "{tagline}\n\n"
    "\u2705 {selling_point_1}\n"
    "\u2705 {selling_point_2}\n\n"
    "\U0001f4b5 ${price:.2f} \u5373\u523b\u62e5\u6709\n\n"
    "#\u54c1\u8d28\u751f\u6d3b #{category_tag}",

    "\U0001f48e **\u53d1\u73b0\u597d\u7269** {title}\n\n"
    "{short_desc}\n\n"
    "\u2b50 {rating}/5 | {reviews} \u8bc4\u4ef7\n"
    "\U0001f4b0 \u9650\u65f6\u597d\u4ef7 ${price:.2f}\n\n"
    "#\u6bcf\u65e5\u63a8\u8350 #{category_tag}",
]


# Public API

def _short_title(title: str, max_len: int = 30) -> str:
    return title if len(title) <= max_len else title[:max_len-1] + "\u2026"

def _category_tag(category: str) -> str:
    tags = {"electronics": "\u7535\u5b50\u4ea7\u54c1", "men\u2019s clothing": "\u7537\u88c5",
            "women\u2019s clothing": "\u5973\u88c5", "jewelery": "\u9996\u9970\u73e0\u5b9d"}
    return tags.get(category, category)

def _rating_comment(rating: float) -> str:
    if rating >= 4.5: return f"\u8bc4\u5206{rating}\u661f\uff0c\u53e3\u7891\u7206\u68da"
    if rating >= 4.0: return f"\u8bc4\u5206{rating}\u661f\uff0c\u597d\u8bc4\u5982\u6f6e"
    if rating >= 3.0: return f"\u8bc4\u5206{rating}\u661f\uff0c\u8868\u73b0\u4e2d\u4e0a"
    return f"\u8bc4\u5206{rating}\u661f\uff0c\u4ecd\u6709\u63d0\u5347\u7a7a\u95f4"

def _price_advantage(price: float, cat_avg: float | None = None) -> str:
    if cat_avg and price < cat_avg * 0.8:
        return f"\u4ec5\u552e${price:.2f}\uff0c\u4f4e\u4e8e\u54c1\u7c7b\u5747\u4ef7${cat_avg-price:.2f}"
    if cat_avg and price > cat_avg * 1.2:
        return f"\u5b9a\u4f4d\u9ad8\u7aef${price:.2f}\uff0c\u54c1\u8d28\u5353\u8d8a"
    return f"\u8d85\u503c\u4ef7\u683c${price:.2f}"

def generate_tagline(product: dict[str, Any], brief: dict[str, Any]) -> str:
    title = product.get("title", "")
    short = _short_title(title)
    category = product.get("category", "unknown")
    templates = TAGLINE_TEMPLATES.get(category, DEFAULT_TAGLINES)
    idx = product.get("id", 0) % len(templates)
    return templates[idx].format(title=title, short_title=short)

def generate_bullets(product: dict[str, Any], brief: dict[str, Any]) -> list[str]:
    category = product.get("category", "unknown")
    price = product.get("price", 0)
    rating = product.get("rating", {})
    rate = rating.get("rate", 0)
    count = rating.get("count", 0)
    desc = product.get("description", "")
    fmt = {
        "spec_tech": (product.get("title","").split() or ["\u4ea7\u54c1"])[0],
        "price_advantage": _price_advantage(price),
        "rating_comment": _rating_comment(rate),
        "fit_desc": "\u7ecf\u5178\u7248\u578b" if price > 30 else "\u4f11\u95f2\u7248\u578b",
        "material_note": f"\u91c7\u7528\u4f18\u8d28\u6750\u6599\uff0c{desc[:30] if desc else '\u8212\u9002\u8010\u7528'}",
        "style_note": "\u7b80\u7ea6\u65f6\u5c1a",
        "craft_note": "\u7cbe\u7ec6\u6253\u78e8",
        "quality_note": f"{category}\u6b63\u54c1\uff0c\u8d28\u91cf\u4fdd\u969c",
        "review_count": str(count),
    }
    templates = BULLET_CATEGORY_TEMPLATES.get(category, DEFAULT_BULLETS)
    start = product.get("id", 0) % len(templates)
    return [templates[(start + i) % len(templates)].format(**fmt) for i in range(min(5, len(templates)))]

def generate_description(product: dict[str, Any], brief: dict[str, Any], tagline: str, bullets: list[str]) -> str:
    title = product.get("title", "")
    short = _short_title(title)
    category = product.get("category", "unknown")
    price = product.get("price", 0)
    rating = product.get("rating", {})
    rate = rating.get("rate", 0)
    count = rating.get("count", 0)
    bullet_text = "\n".join(f"- {b}" for b in bullets[:4])
    template = DESCRIPTION_TEMPLATES.get(category, DESCRIPTION_TEMPLATES.get("electronics", ""))
    desc = template.format(
        title=title, short_title=short, category=category, bullet_text=bullet_text,
        price_advantage=_price_advantage(price), rating_comment=_rating_comment(rate),
        review_count=count, price_strategy=brief.get("price_strategy",""),
        core_selling_point=brief.get("core_selling_point",""))
    orig = product.get("description", "")
    if orig:
        desc += f"\n\n### \u5546\u54c1\u8be6\u60c5\n\n{orig[:300]}"
    return desc

def generate_social_copy(product: dict[str, Any], brief: dict[str, Any], tagline: str) -> str:
    title = product.get("title", "")
    short = _short_title(title)
    category = product.get("category", "unknown")
    price = product.get("price", 0)
    rating = product.get("rating", {})
    rate = rating.get("rate", 0)
    count = rating.get("count", 0)
    desc = product.get("description", "")
    short_desc = desc[:60] + "\u2026" if len(desc) > 60 else desc
    sp = brief.get("selling_points", [])
    sp1 = sp[0] if sp else "\u54c1\u8d28\u4fdd\u8bc1"
    sp2 = sp[1] if len(sp) > 1 else "\u4ef7\u683c\u5b9e\u60e0"
    idx = product.get("id", 0) % len(SOCIAL_TEMPLATES)
    return SOCIAL_TEMPLATES[idx].format(
        title=title, short_title=short, short_desc=short_desc,
        tagline=tagline, selling_point_1=sp1, selling_point_2=sp2,
        rating=rate, reviews=count, price=price, category_tag=_category_tag(category))

def generate_all_copies(product: dict[str, Any], brief: dict[str, Any]) -> dict[str, str]:
    tagline = generate_tagline(product, brief)
    bullets = generate_bullets(product, brief)
    description = generate_description(product, brief, tagline, bullets)
    social = generate_social_copy(product, brief, tagline)
    return {"tagline": tagline, "bullets": "\n".join(bullets), "description": description, "social": social}