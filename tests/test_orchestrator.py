"""Tests for pipeline.orchestrator and pipeline.agent_runner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.base import BaseSourceAgent
from core.models import EnrichedLead, PipelineContext, RawLead
from pipeline.agent_runner import AgentRunner
from pipeline.orchestrator import Orchestrator, _raw_to_enriched


# ── Helpers ─────────────────────────────────────────────────────────


class _StubAgent(BaseSourceAgent):
    """Concrete stub agent for testing."""

    name = "stub"

    def __init__(self, leads: list[RawLead] | None = None, *, name: str = "stub"):
        # Override the class-level name per-instance for testing convenience.
        object.__setattr__(self, "name", name)
        self._leads = leads or []

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        return list(self._leads)


class _FailingAgent(BaseSourceAgent):
    """Agent whose fetch() always raises."""

    name = "failing"

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        raise RuntimeError("boom")


def _make_raw_lead(company: str = "Acme Corp", source: str = "test") -> RawLead:
    return RawLead(company_name=company, source=source)


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.upsert_leads.return_value = [1, 2]
    db.record_run.return_value = None
    return db


def _identity_enrich(raw: RawLead) -> EnrichedLead:
    """Minimal enrichment stub — just copies company_name."""
    return EnrichedLead(company_name=raw.company_name, sources=[raw.source])


# ── AgentRunner ────────────────────────────────────────────────────


class TestAgentRunner:
    """Tests for the AgentRunner parallel executor."""

    def test_run_returns_flat_list(self):
        """Results from multiple agents are flattened into one list."""
        agent_a = _StubAgent(
            [_make_raw_lead("A1"), _make_raw_lead("A2")], name="agent_a"
        )
        agent_b = _StubAgent([_make_raw_lead("B1")], name="agent_b")

        runner = AgentRunner(max_workers=2)
        ctx = PipelineContext.new()
        leads = runner.run([agent_a, agent_b], ctx)

        assert len(leads) == 3
        company_names = {lead.company_name for lead in leads}
        assert company_names == {"A1", "A2", "B1"}

    def test_run_records_stats_per_agent(self):
        """Per-agent stats (leads_found, duration_seconds, errors) are set."""
        agent = _StubAgent([_make_raw_lead()], name="myagent")
        runner = AgentRunner(max_workers=1)
        ctx = PipelineContext.new()
        runner.run([agent], ctx)

        assert "agents" in ctx.stats
        assert "myagent" in ctx.stats["agents"]
        stats = ctx.stats["agents"]["myagent"]
        assert stats["leads_found"] == 1
        assert stats["duration_seconds"] >= 0
        assert stats["errors"] is None

    def test_run_records_total_raw_leads(self):
        """Total count of raw leads is stored in context stats."""
        agent = _StubAgent([_make_raw_lead(), _make_raw_lead()], name="a")
        runner = AgentRunner(max_workers=1)
        ctx = PipelineContext.new()
        runner.run([agent], ctx)

        assert ctx.stats["total_raw_leads"] == 2

    def test_failing_agent_returns_empty_and_records_no_error(self):
        """A failing agent produces no leads; _safe_fetch handles the exception."""
        agent = _FailingAgent()
        runner = AgentRunner(max_workers=1)
        ctx = PipelineContext.new()
        leads = runner.run([agent], ctx)

        assert leads == []
        stats = ctx.stats["agents"]["failing"]
        assert stats["leads_found"] == 0
        # _safe_fetch catches the error internally; AgentRunner sees []
        assert stats["errors"] is None

    def test_empty_agents_list(self):
        """Running with no agents returns empty list."""
        runner = AgentRunner()
        ctx = PipelineContext.new()
        assert runner.run([], ctx) == []


# ── Orchestrator ───────────────────────────────────────────────────


class TestOrchestrator:
    """Tests for the Orchestrator pipeline coordinator."""

    def _make_orch(
        self,
        agents: list[BaseSourceAgent] | None = None,
        db: MagicMock | None = None,
    ) -> Orchestrator:
        return Orchestrator(
            agents=agents or [],
            database=db or _make_mock_db(),
            enrich_fn=_identity_enrich,
        )

    # ── run_daily ──────────────────────────────────────────────────

    def test_run_daily_collects_from_all_agents(self):
        """run_daily feeds every registered agent into the pipeline."""
        agent_a = _StubAgent([_make_raw_lead("A")], name="alpha")
        agent_b = _StubAgent([_make_raw_lead("B")], name="beta")
        db = _make_mock_db()

        orch = self._make_orch(agents=[agent_a, agent_b], db=db)
        ctx = orch.run_daily()

        # Both agents were executed
        assert "agents" in ctx.stats
        assert "alpha" in ctx.stats["agents"]
        assert "beta" in ctx.stats["agents"]
        # Enriched leads were stored
        assert db.upsert_leads.called
        assert db.record_run.called

    def test_run_daily_enriches_and_stores(self):
        """run_daily enriches deduped leads and upserts them to the DB."""
        agent = _StubAgent([_make_raw_lead("X")], name="src")
        db = _make_mock_db()
        db.upsert_leads.return_value = [10]

        orch = self._make_orch(agents=[agent], db=db)
        ctx = orch.run_daily()

        # One lead enriched
        assert len(ctx.enriched_leads) == 1
        assert ctx.enriched_leads[0].company_name == "X"
        # DB received it
        db.upsert_leads.assert_called_once()
        assert ctx.stats["leads_stored"] == 1

    def test_run_daily_empty_agents(self):
        """run_daily with no agents stores nothing and still records the run."""
        db = _make_mock_db()
        orch = self._make_orch(agents=[], db=db)
        ctx = orch.run_daily()

        assert ctx.stats["leads_stored"] == 0
        db.record_run.assert_called_once()

    # ── run_single_agent ──────────────────────────────────────────

    def test_run_single_agent_finds_correct_agent(self):
        """run_single_agent looks up by name (case-insensitive)."""
        target = _StubAgent([_make_raw_lead("Found")], name="linkedin")
        other = _StubAgent([_make_raw_lead("Other")], name="costar")
        db = _make_mock_db()

        orch = self._make_orch(agents=[target, other], db=db)
        ctx = orch.run_single_agent("LinkedIn")

        assert len(ctx.enriched_leads) == 1
        assert ctx.enriched_leads[0].company_name == "Found"

    def test_run_single_agent_not_found(self):
        """run_single_agent returns context with error when name is unknown."""
        orch = self._make_orch(agents=[])
        ctx = orch.run_single_agent("nonexistent")

        assert "error" in ctx.stats
        assert "not found" in ctx.stats["error"].lower()

    # ── run_marketplace ───────────────────────────────────────────

    def test_run_marketplace_runs_marketplace_agent(self):
        """run_marketplace picks the agent named 'marketplace'."""
        mkt = _StubAgent([_make_raw_lead("M")], name="marketplace")
        other = _StubAgent([_make_raw_lead("O")], name="other")
        db = _make_mock_db()

        orch = self._make_orch(agents=[mkt, other], db=db)
        ctx = orch.run_marketplace()

        assert len(ctx.enriched_leads) == 1
        assert ctx.enriched_leads[0].company_name == "M"

    def test_run_marketplace_no_agent(self):
        """run_marketplace with no matching agent produces no leads."""
        db = _make_mock_db()
        orch = self._make_orch(agents=[], db=db)
        ctx = orch.run_marketplace()

        assert ctx.stats["leads_stored"] == 0

    # ── Stats tracking ────────────────────────────────────────────

    def test_stats_recorded_in_context(self):
        """Pipeline run populates context.stats with all expected keys."""
        agent = _StubAgent([_make_raw_lead()], name="src")
        db = _make_mock_db()
        db.upsert_leads.return_value = [1]

        orch = self._make_orch(agents=[agent], db=db)
        ctx = orch.run_daily()

        assert "agents" in ctx.stats
        assert "total_raw_leads" in ctx.stats
        assert "leads_after_dedup" in ctx.stats
        assert "leads_enriched" in ctx.stats
        assert "leads_stored" in ctx.stats

    def test_pipeline_run_is_recorded_in_db(self):
        """record_run is called with run_id, timestamp, and stats."""
        agent = _StubAgent([_make_raw_lead()], name="src")
        db = _make_mock_db()

        orch = self._make_orch(agents=[agent], db=db)
        ctx = orch.run_daily()

        db.record_run.assert_called_once_with(
            ctx.run_id, ctx.run_timestamp, ctx.stats
        )

    # ── Enrichment ────────────────────────────────────────────────

    def test_custom_enrich_fn_is_used(self):
        """Orchestrator uses the injected enrich_fn."""
        called_with: list[RawLead] = []

        def spy_enrich(raw: RawLead) -> EnrichedLead:
            called_with.append(raw)
            return EnrichedLead(company_name=raw.company_name, score=99)

        agent = _StubAgent([_make_raw_lead("Z")], name="s")
        db = _make_mock_db()
        orch = Orchestrator(
            agents=[agent], database=db, enrich_fn=spy_enrich
        )
        ctx = orch.run_daily()

        assert len(called_with) == 1
        assert called_with[0].company_name == "Z"
        assert ctx.enriched_leads[0].score == 99

    # ── register_agent ────────────────────────────────────────────

    def test_register_agent_adds_to_roster(self):
        """register_agent appends the agent so it runs on next daily."""
        db = _make_mock_db()
        orch = self._make_orch(agents=[], db=db)
        new_agent = _StubAgent([_make_raw_lead("New")], name="fresh")
        orch.register_agent(new_agent)

        ctx = orch.run_daily()
        assert len(ctx.enriched_leads) == 1
        assert ctx.enriched_leads[0].company_name == "New"


# ── _raw_to_enriched (placeholder) ────────────────────────────────


class TestRawToEnriched:
    """Smoke tests for the placeholder enrichment function."""

    def test_copies_company_name(self):
        raw = _make_raw_lead("Hello")
        enriched = _raw_to_enriched(raw)
        assert enriched.company_name == "Hello"

    def test_copies_source(self):
        raw = _make_raw_lead(source="linkedin")
        enriched = _raw_to_enriched(raw)
        assert enriched.sources == ["linkedin"]

    def test_none_fields_become_empty_strings(self):
        raw = RawLead(company_name="X", source="s")
        enriched = _raw_to_enriched(raw)
        assert enriched.contact_name == ""
        assert enriched.address == ""
