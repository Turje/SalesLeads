"""Pipeline orchestrator — schedules and coordinates pipeline runs."""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.database import Database
from core.dedup import deduplicate
from core.models import EnrichedLead, PipelineContext, RawLead
from pipeline.agent_runner import AgentRunner

logger = logging.getLogger(__name__)


def _raw_to_enriched(raw: RawLead) -> EnrichedLead:
    """Minimal conversion from RawLead to EnrichedLead.

    A real enrichment step (LLM scoring, API look-ups) would live in its
    own module.  This placeholder copies the fields we already have so
    the pipeline can persist results immediately.
    """
    return EnrichedLead(
        company_name=raw.company_name,
        contact_name=raw.contact_name or "",
        contact_title=raw.contact_title or "",
        email=raw.email,
        phone=raw.phone,
        website=raw.website,
        address=raw.address or "",
        sources=[raw.source],
    )


class Orchestrator:
    """Schedules and coordinates pipeline runs.

    Lifecycle::

        orch = Orchestrator()
        orch.start()   # kicks off APScheduler
        ...
        orch.stop()    # clean shutdown
    """

    def __init__(
        self,
        settings: Settings | None = None,
        agents: list[BaseSourceAgent] | None = None,
        database: Database | None = None,
        runner: AgentRunner | None = None,
        enrich_fn: Any | None = None,
    ):
        self.settings = settings or Settings()
        self._agents: list[BaseSourceAgent] = agents or []
        self._db = database or Database(self.settings.database_path)
        self._runner = runner or AgentRunner(
            max_workers=self.settings.max_agent_workers
        )
        self._enrich = enrich_fn or _raw_to_enriched
        self._scheduler: BackgroundScheduler | None = None

    # ------------------------------------------------------------------
    # Agent registry helpers
    # ------------------------------------------------------------------

    def register_agent(self, agent: BaseSourceAgent) -> None:
        """Add an agent to the roster."""
        self._agents.append(agent)

    def _find_agent(self, name: str) -> BaseSourceAgent | None:
        """Look up an agent by its ``name`` attribute (case-insensitive)."""
        target = name.lower()
        for agent in self._agents:
            if agent.name.lower() == target:
                return agent
        return None

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def schedule(self) -> None:
        """Create APScheduler jobs (daily + marketplace interval)."""
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self.run_daily,
            "cron",
            hour=self.settings.daily_run_hour,
            id="daily_pipeline",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self.run_marketplace,
            "interval",
            hours=self.settings.marketplace_interval_hours,
            id="marketplace_pipeline",
            replace_existing=True,
        )

    def start(self) -> None:
        """Set up schedule and start the background scheduler."""
        if self._scheduler is None:
            self.schedule()
        assert self._scheduler is not None
        self._scheduler.start()
        logger.info("Orchestrator scheduler started.")

    def stop(self) -> None:
        """Shut down the scheduler gracefully."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            logger.info("Orchestrator scheduler stopped.")

    # ------------------------------------------------------------------
    # Pipeline entry points
    # ------------------------------------------------------------------

    def run_daily(self) -> PipelineContext:
        """Full pipeline: fetch all agents -> dedup -> enrich -> store."""
        logger.info("Starting daily pipeline run.")
        return self._execute(self._agents)

    def run_marketplace(self) -> PipelineContext:
        """Quick run: marketplace agent only -> dedup -> enrich -> store."""
        agent = self._find_agent("marketplace")
        agents = [agent] if agent else []
        if not agents:
            logger.warning("No 'marketplace' agent registered — skipping run.")
        return self._execute(agents)

    def run_single_agent(self, agent_name: str) -> PipelineContext:
        """Manual trigger for one agent by name."""
        agent = self._find_agent(agent_name)
        if agent is None:
            logger.error("Agent '%s' not found.", agent_name)
            ctx = PipelineContext.new()
            ctx.stats["error"] = f"Agent '{agent_name}' not found"
            return ctx
        return self._execute([agent])

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def _execute(self, agents: list[BaseSourceAgent]) -> PipelineContext:
        """Shared execution logic: fetch -> dedup -> enrich -> store -> record."""
        ctx = PipelineContext.new()

        # 1. Fetch raw leads
        raw_leads = self._runner.run(agents, ctx)
        ctx.raw_leads = raw_leads

        # 2. Dedup
        deduped = deduplicate(
            raw_leads, threshold=self.settings.dedup_similarity_threshold
        )
        ctx.stats["leads_after_dedup"] = len(deduped)

        # 3. Enrich
        enriched = [self._enrich(lead) for lead in deduped]
        ctx.enriched_leads = enriched
        ctx.stats["leads_enriched"] = len(enriched)

        # 4. Persist
        if enriched:
            ids = self._db.upsert_leads(enriched)
            ctx.stats["leads_stored"] = len(ids)
        else:
            ctx.stats["leads_stored"] = 0

        # 5. Record pipeline run
        self._db.record_run(ctx.run_id, ctx.run_timestamp, ctx.stats)

        logger.info(
            "Pipeline run %s complete — %d raw, %d deduped, %d enriched, %d stored.",
            ctx.run_id[:8],
            len(raw_leads),
            len(deduped),
            len(enriched),
            ctx.stats["leads_stored"],
        )
        return ctx
