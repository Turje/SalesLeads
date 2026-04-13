"""Core data models for SalesLeads platform."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


@dataclass
class RawLead:
    """Output of each source agent — unprocessed lead data."""

    company_name: str
    source: str  # "linkedin", "costar", "nyc_opendata", etc.
    contact_name: str | None = None
    contact_title: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    raw_data: dict = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.utcnow)


CompanyType = Literal["CRE_OPERATOR", "COWORKING", "MULTI_TENANT", "OTHER"]
PipelineStage = Literal["NEW", "APPROVED", "CONTACTED", "MEETING", "PROPOSAL", "CLOSED", "DISAPPROVED"]

VALID_COMPANY_TYPES: set[CompanyType] = {"CRE_OPERATOR", "COWORKING", "MULTI_TENANT", "OTHER"}
VALID_PIPELINE_STAGES: set[PipelineStage] = {"NEW", "APPROVED", "CONTACTED", "MEETING", "PROPOSAL", "CLOSED", "DISAPPROVED"}


@dataclass
class EnrichedLead:
    """Output of enrichment agent — fully qualified lead profile."""

    # Identity
    company_name: str
    company_type: CompanyType = "OTHER"
    contact_name: str = ""
    contact_title: str = ""
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    website: str | None = None

    # Property details
    address: str = ""
    building_type: str = ""  # "Class A Office", "Flex Space", etc.
    sqft: int | None = None
    num_tenants: int | None = None
    borough: str = ""
    neighborhood: str = ""
    year_built: int | None = None
    floors: int | None = None
    num_employees: int | None = None

    # Building details
    building_isp: str | None = None
    available_isps: list[str] = field(default_factory=list)
    equipment: dict = field(default_factory=dict)  # {hvac, elevator, security, bms, network_infrastructure}
    building_summary: str = ""

    # Intelligence
    current_it_provider: str | None = None
    tech_signals: list[str] = field(default_factory=list)
    recent_news: list[str] = field(default_factory=list)
    social_links: dict = field(default_factory=dict)

    # Metadata
    sources: list[str] = field(default_factory=list)
    discovery_date: date = field(default_factory=date.today)
    score: int = 0  # 0-100 qualification score
    qualification_notes: str = ""
    pipeline_stage: PipelineStage = "NEW"

    # Database ID (set after persistence)
    id: int | None = None


@dataclass
class PipelineContext:
    """Immutable state container for a single pipeline run cycle."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_leads: list[RawLead] = field(default_factory=list)
    enriched_leads: list[EnrichedLead] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @classmethod
    def new(cls) -> PipelineContext:
        return cls()
