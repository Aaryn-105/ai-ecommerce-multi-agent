"""Agent registry – maps agent names to their classes."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.base import BaseAgent


class AgentRegistry:
    """Central registry for looking up agents by name.

    Usage::

        from backend.agents.product_analysis.agent import ProductAnalysisAgent
        AgentRegistry.register(ProductAnalysisAgent)
        cls = AgentRegistry.get("product_analysis")
    """

    _registry: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_cls: type[BaseAgent], *, name: str | None = None) -> None:
        """Register an agent class under *name* (defaults to ``agent_cls.agent_name``)."""
        key = name or agent_cls.agent_name
        if not key:
            msg = f"{agent_cls.__name__} must define a non-empty ``agent_name``"
            raise ValueError(msg)
        if key in cls._registry:
            msg = f"Agent {key!r} is already registered"
            raise KeyError(msg)
        cls._registry[key] = agent_cls

    @classmethod
    def get(cls, name: str) -> type[BaseAgent]:
        """Return the agent class for *name*, or raise :class:`KeyError`."""
        if name not in cls._registry:
            msg = f"Unknown agent {name!r}. Registered: {list(cls._registry)}"
            raise KeyError(msg)
        return cls._registry[name]

    @classmethod
    def list_agents(cls) -> list[str]:
        """Return sorted list of all registered agent names."""
        return sorted(cls._registry)

    @classmethod
    def clear(cls) -> None:
        """Reset the registry (useful in tests)."""
        cls._registry.clear()
