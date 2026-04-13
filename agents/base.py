"""Base class for all source agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)


class BaseSourceAgent(ABC):
    """Abstract base for every lead-source agent.

    Subclasses **must** define a class-level ``name: str`` attribute.
    ``__init_subclass__`` enforces this at class-creation time so mistakes
    surface immediately rather than at runtime.
    """

    name: str  # enforced by __init_subclass__

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Allow intermediate abstract classes (they won't have `name` yet)
        if ABC in cls.__bases__:
            return
        if not getattr(cls, "name", None) or not isinstance(
            cls.__dict__.get("name"), str
        ):
            raise TypeError(
                f"Source agent {cls.__name__} must define a class-level "
                f"'name' attribute (got {cls.__dict__.get('name', '<missing>')!r})"
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch(self, context: PipelineContext) -> list[RawLead]:
        """Return raw leads from this source.  Must not raise."""

    def _safe_fetch(self, context: PipelineContext) -> list[RawLead]:
        """Wrapper that catches any exception and returns ``[]``.

        Source agents should call ``_safe_fetch`` from the pipeline runner
        so that a single broken source never takes down the whole run.
        """
        try:
            leads = self.fetch(context)
            logger.info(
                "%s returned %d lead(s) [run=%s]",
                self.name,
                len(leads),
                context.run_id[:8],
            )
            return leads
        except Exception:
            logger.exception(
                "Agent %s raised during fetch [run=%s]",
                self.name,
                context.run_id[:8],
            )
            return []
