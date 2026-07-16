"""Abstract base class for all agents in the system."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from backend.models.schemas import AgentInput, AgentResult, ExecutionMeta


class BaseAgent(ABC):
    """Every agent must subclass this and implement :meth:`run`.

    Subclasses set ``agent_name`` as a class-level constant.
    The :meth:`run` wrapper automatically captures execution time
    and populates ``execution_meta``.
    """

    agent_name: str = ""

    @abstractmethod
    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Core business logic – override this.

        Args:
            input_data: The agent-specific payload from ``AgentInput.input_data``.
            context:    The orchestrator's shared context (results from earlier agents).

        Returns:
            A plain dict that will become ``AgentResult.output_data``.
        """
        ...

    async def run(self, agent_input: AgentInput) -> AgentResult:
        """Entry point – wraps :meth:`execute` with timing and error handling.

        This method is not meant to be overridden by subclasses.
        """
        start = time.perf_counter()
        llm_used = False
        error: str | None = None

        try:
            output_data = await self.execute(agent_input.input_data, agent_input.context)
            status = "completed"
        except Exception as exc:
            output_data = {}
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"

        elapsed_ms = (time.perf_counter() - start) * 1000

        return AgentResult(
            task_id=agent_input.task_id,
            status=status,
            output_data=output_data,
            execution_meta=ExecutionMeta(
                execution_time_ms=round(elapsed_ms, 2),
                llm_used=llm_used,
                llm_calls=0,
            ),
            error=error,
        )
