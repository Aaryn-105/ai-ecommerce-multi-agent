"""Lightweight wrapper around OpenAI API for LLM calls."""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from backend.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Encapsulates OpenAI chat completion calls with JSON mode support."""

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.LLM_API_BASE)
        return self._client

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = True,
        fallback: Any = None,
    ) -> str | dict[str, Any] | Any:
        """Call the chat API.

        Returns a parsed dict when *json_mode=True*, a raw string otherwise.
        Falls back to *fallback* on failure (instead of raising).
        """
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set — returning fallback")
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

            if json_mode:
                return json.loads(content)
            return content

        except Exception as exc:
            logger.exception("LLM call failed: %s", exc)
            return fallback or {}
