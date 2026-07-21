"""Lightweight wrapper around OpenAI-compatible APIs with JSON mode + robust parsing."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from httpx import AsyncClient
from openai import AsyncOpenAI

from backend.core.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_RETRIES = 0


def _try_fix_gbk_mojibake(text: str) -> str:
    """Re-decode a string that was wrongly decoded as UTF-8 instead of GBK.

    A "GBK mojibake" string is one that contains characters from the
    Latin-1 supplement range (0x80-0xFF) where every Chinese character
    has been turned into 2-3 weird Latin-1 characters.

    Validation rule: the candidate decoded text must contain a *high*
    density of CJK characters. Otherwise we treat the original as correct
    UTF-8 and return it untouched.
    """
    if not text:
        return text
    # Heuristic: mojibake patterns look like accented Latin chars (e.g. ÖÐÎÄ)
    # whereas legitimate UTF-8 CJK spans 0x4E00-0x9FFF (CJK Unified Ideographs)
    cjk_chars = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
    if cjk_chars > 0:
        # Already has real CJK characters - no fix needed
        return text
    # Try re-decoding from latin-1 to GBK
    try:
        raw = text.encode('latin-1', errors='ignore')
        candidate = raw.decode('gbk', errors='ignore')
        new_cjk = sum(1 for c in candidate if 0x4E00 <= ord(c) <= 0x9FFF)
        if new_cjk > cjk_chars + 2:
            return candidate
    except Exception:
        pass
    return text


def _safe_json_loads(content: str) -> dict | list | None:
    if not content or not content.strip():
        return None
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    fixed = _fix_json_newlines(text)
    if fixed != text:
        try:
            return json.loads(fixed)
        except Exception:
            pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        end = -1
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                repaired = _repair_truncated_json(candidate)
                if repaired:
                    try:
                        return json.loads(repaired)
                    except Exception:
                        pass
    return None


def _fix_json_newlines(text: str) -> str:
    result = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            result.append(ch)
            continue
        if ch == "\\":
            escape = True
            result.append(ch)
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and (ch == "\n" or ch == "\r"):
            result.append("\\n")
            continue
        result.append(ch)
    return "".join(result)


def _repair_truncated_json(text: str) -> str | None:
    if not text:
        return None
    text = text.rstrip()
    if text.endswith("\\"):
        text += '"'
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        text += '"'
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")
    text += "}" * max(0, open_braces) + "]" * max(0, open_brackets)
    return text


class LLMService:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            http_client = AsyncClient(timeout=_DEFAULT_TIMEOUT)
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.LLM_API_BASE,
                http_client=http_client,
                max_retries=_DEFAULT_MAX_RETRIES,
            )
        return self._client

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = True,
        fallback: Any = None,
    ) -> str | dict[str, Any] | Any:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set - returning fallback")
            return fallback or {}
        try:
            kwargs: dict = {
                "model": model or settings.LLM_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = await self.client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            content = _try_fix_gbk_mojibake(content)
            if json_mode:
                parsed = _safe_json_loads(content)
                if parsed is None:
                    logger.warning("LLM JSON parse failed; returning raw content. Content[0:200]=%r", content[:200])
                    return {"__raw__": content}
                return parsed
            return content
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return fallback or {}
