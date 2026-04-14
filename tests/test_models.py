"""Tests for core.models — RawLead, EnrichedLead, PipelineContext dataclasses."""

import uuid
from datetime import date, datetime

import pytest

from core.models import (
    VALID_COMPANY_TYPES,
    VALID_PIPELINE_STAGES,
    EnrichedLead,
    PipelineContext,
    RawLead,
)


# ── RawLead ─────────────────────────────────────────────────────────


class TestRawLead:
    """Tests for the RawLead dataclass."""

    def test_required_fields_only(self):
        """Creating a RawLead with only required fields succeeds."""
        lead = RawLead(company_name="Acme Corp", source="linkedin")
        assert lead.company_name == "Acme Corp"
        assert lead.source == "linkedin"

    def test_optional_fields_default_to_none(self):
        """All optional string fields default to None."""
        lead = RawLead(company_name="Acme Corp", source="linkedin")
        assert lead.contact_name is None
        assert lead.contact_title is None
        assert lead.email is None
        assert lead.phone is None
        assert lead.website is None
        assert lead.address is None

    def test_raw_data_defaults_to_empty_dict(self):
        """raw_data defaults to a fresh empty dict (not shared)."""
        lead_a = RawLead(company_name="A", source="s")
        lead_b = RawLead(company_name="B", source="s")
        assert lead_a.raw_data == {}
        assert lead_b.raw_data == {}
        # Ensure they are distinct objects, not a shared mutable default
        lead_a.raw_data["key"] = "val"
        assert "key" not in lead_b.raw_data

    def test_discovered_at_is_datetime(self):
        """discovered_at is auto-set to a datetime."""
        before = datetime.utcnow()
        lead = RawLead(company_name="X", source="s")
        after = datetime.utcnow()
        assert isinstance(lead.discovered_at, datetime)
        assert before <= lead.discovered_at <= after

    def test_all_fields_populated(self):
        """Creating a RawLead with every field works."""
        now = datetime(2026, 1, 15, 12, 0, 0)
        lead = RawLead(
            company_name="Brookfield Properties",
            source="costar",
            contact_name="Jane Doe",
            contact_title="VP Operations",
            email="jane@brookfield.com",
            phone="212-555-1234",
            website="https://brookfield.com",
            address="250 Vesey St, New York, NY",
            raw_data={"listing_id": "CS-12345"},
            discovered_at=now,
        )
        assert lead.company_name == "Brookfield Properties"
        assert lead.contact_name == "Jane Doe"
        assert lead.raw_data["listing_id"] == "CS-12345"
        assert lead.discovered_at == now


# ── EnrichedLead ────────────────────────────────────────────────────


class TestEnrichedLead:
    """Tests for the EnrichedLead dataclass."""

    def test_minimal_creation(self):
        """Creating an EnrichedLead with only company_name succeeds."""
        lead = EnrichedLead(company_name="WeWork")
        assert lead.company_name == "WeWork"

    def test_default_company_type(self):
        """Default company_type is OTHER."""
        lead = EnrichedLead(company_name="X")
        assert lead.company_type == "OTHER"

    def test_default_pipeline_stage(self):
        """Default pipeline_stage is NEW."""
        lead = EnrichedLead(company_name="X")
        assert lead.pipeline_stage == "NEW"

    def test_default_score_is_zero(self):
        """Default score is 0."""
        lead = EnrichedLead(company_name="X")
        assert lead.score == 0

    def test_default_string_fields_are_empty(self):
        """Non-optional string fields default to empty string."""
        lead = EnrichedLead(company_name="X")
        assert lead.contact_name == ""
        assert lead.contact_title == ""
        assert lead.address == ""
        assert lead.building_type == ""
        assert lead.qualification_notes == ""

    def test_optional_fields_default_to_none(self):
        """Optional fields (email, phone, etc.) default to None."""
        lead = EnrichedLead(company_name="X")
        assert lead.email is None
        assert lead.phone is None
        assert lead.linkedin_url is None
        assert lead.website is None
        assert lead.sqft is None
        assert lead.num_tenants is None
        assert lead.current_it_provider is None
        assert lead.id is None

    def test_list_fields_default_to_empty(self):
        """List fields default to empty and are distinct objects."""
        a = EnrichedLead(company_name="A")
        b = EnrichedLead(company_name="B")
        assert a.tech_signals == []
        assert a.recent_news == []
        assert a.sources == []
        # Ensure no shared mutable default
        a.tech_signals.append("fiber")
        assert "fiber" not in b.tech_signals

    def test_dict_fields_default_to_empty(self):
        """Dict fields default to empty and are distinct objects."""
        a = EnrichedLead(company_name="A")
        b = EnrichedLead(company_name="B")
        assert a.social_links == {}
        a.social_links["twitter"] = "@a"
        assert "twitter" not in b.social_links

    def test_discovery_date_is_today(self):
        """discovery_date defaults to today's date."""
        lead = EnrichedLead(company_name="X")
        assert lead.discovery_date == date.today()

    def test_fully_populated_lead(self):
        """Creating an EnrichedLead with all fields works."""
        lead = EnrichedLead(
            company_name="Brookfield Properties",
            company_type="CRE_OPERATOR",
            contact_name="Jane Doe",
            contact_title="VP Operations",
            email="jane@brookfield.com",
            phone="212-555-1234",
            linkedin_url="https://linkedin.com/in/janedoe",
            website="https://brookfield.com",
            address="250 Vesey St, New York, NY",
            building_type="Class A Office",
            sqft=500000,
            num_tenants=45,
            current_it_provider="Spectrum Enterprise",
            tech_signals=["fiber", "smart_building"],
            recent_news=["Acquired new property"],
            social_links={"twitter": "@brookfield"},
            sources=["costar", "linkedin"],
            discovery_date=date(2026, 1, 15),
            score=85,
            qualification_notes="High-value target",
            pipeline_stage="CONTACTED",
            id=42,
        )
        assert lead.company_type == "CRE_OPERATOR"
        assert lead.sqft == 500000
        assert lead.score == 85
        assert lead.pipeline_stage == "CONTACTED"
        assert lead.id == 42


# ── PipelineContext ─────────────────────────────────────────────────


class TestPipelineContext:
    """Tests for the PipelineContext dataclass."""

    def test_new_creates_fresh_instance(self):
        """PipelineContext.new() returns a fresh instance with a UUID run_id."""
        ctx = PipelineContext.new()
        # run_id should be a valid UUID string
        parsed = uuid.UUID(ctx.run_id)
        assert str(parsed) == ctx.run_id

    def test_new_returns_unique_run_ids(self):
        """Each call to PipelineContext.new() gives a different run_id."""
        ctx_a = PipelineContext.new()
        ctx_b = PipelineContext.new()
        assert ctx_a.run_id != ctx_b.run_id

    def test_default_lists_are_empty(self):
        """raw_leads and enriched_leads default to empty lists."""
        ctx = PipelineContext.new()
        assert ctx.raw_leads == []
        assert ctx.enriched_leads == []

    def test_default_stats_is_empty_dict(self):
        """stats defaults to an empty dict."""
        ctx = PipelineContext.new()
        assert ctx.stats == {}

    def test_run_timestamp_is_datetime(self):
        """run_timestamp is auto-set to a datetime."""
        before = datetime.utcnow()
        ctx = PipelineContext.new()
        after = datetime.utcnow()
        assert isinstance(ctx.run_timestamp, datetime)
        assert before <= ctx.run_timestamp <= after

    def test_mutable_defaults_are_independent(self):
        """Lists/dicts are not shared between instances."""
        ctx_a = PipelineContext.new()
        ctx_b = PipelineContext.new()
        ctx_a.raw_leads.append(RawLead(company_name="A", source="s"))
        assert len(ctx_b.raw_leads) == 0


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    """Tests for module-level constants."""

    def test_valid_company_types(self):
        """VALID_COMPANY_TYPES contains exactly the expected types."""
        expected = {"CRE_OPERATOR", "COWORKING", "MULTI_TENANT", "OTHER"}
        assert VALID_COMPANY_TYPES == expected

    def test_valid_pipeline_stages(self):
        """VALID_PIPELINE_STAGES contains exactly the expected stages."""
        expected = {"NEW", "APPROVED", "CONTACTED", "MEETING", "PROPOSAL", "CONTRACT_SIGNED", "CLOSED", "DISAPPROVED"}
        assert VALID_PIPELINE_STAGES == expected

    def test_company_types_is_set(self):
        """VALID_COMPANY_TYPES is a set (not a list or tuple)."""
        assert isinstance(VALID_COMPANY_TYPES, set)

    def test_pipeline_stages_is_set(self):
        """VALID_PIPELINE_STAGES is a set (not a list or tuple)."""
        assert isinstance(VALID_PIPELINE_STAGES, set)
