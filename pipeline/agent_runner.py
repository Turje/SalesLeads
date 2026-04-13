"""Parallel agent executor using ThreadPoolExecutor."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from agents.base import BaseSourceAgent
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)


class AgentRunner:
    """Run source agents in parallel, collect and flatten results."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers

    def run(
        self, agents: list[BaseSourceAgent], context: PipelineContext
    ) -> list[RawLead]:
        """Run all agents in parallel via ``_safe_fetch``.

        Returns a flat list of :class:`RawLead` gathered from every agent.
        Per-agent timing and counts are recorded in ``context.stats``
        under the ``"agents"`` key.
        """
        if not agents:
            return []

        agent_stats: dict[str, dict[str, Any]] = {}
        all_leads: list[RawLead] = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            future_to_agent = {
                pool.submit(self._timed_fetch, agent, context): agent
                for agent in agents
            }

            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                leads, duration, error = future.result()
                all_leads.extend(leads)

                agent_stats[agent.name] = {
                    "leads_found": len(leads),
                    "duration_seconds": round(duration, 3),
                    "errors": error,
                }

        context.stats["agents"] = agent_stats
        context.stats["total_raw_leads"] = len(all_leads)

        logger.info(
            "AgentRunner finished [run=%s]: %d agent(s), %d total lead(s)",
            context.run_id[:8],
            len(agents),
            len(all_leads),
        )
        return all_leads

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _timed_fetch(
        agent: BaseSourceAgent, context: PipelineContext
    ) -> tuple[list[RawLead], float, str | None]:
        """Call ``_safe_fetch`` and measure wall-clock time.

        Returns ``(leads, duration_seconds, error_message_or_none)``.
        """
        start = time.monotonic()
        error: str | None = None
        try:
            leads = agent._safe_fetch(context)
        except Exception as exc:
            # _safe_fetch should never raise, but guard anyway
            logger.exception(
                "Unexpected error from _safe_fetch for %s", agent.name
            )
            leads = []
            error = str(exc)
        duration = time.monotonic() - start

        if not leads and error is None:
            # _safe_fetch returned [] — could be legit empty or a caught error.
            # We can't distinguish here; _safe_fetch already logged it.
            pass

        return leads, duration, error
