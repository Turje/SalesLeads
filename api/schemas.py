"""Pydantic v2 request / response schemas for the SalesLeads API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from core.models import VALID_PIPELINE_STAGES

# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

class LeadResponse(BaseModel):
    """Mirrors EnrichedLead with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_name: str
    company_type: str = "OTHER"
    contact_name: str = ""
    contact_title: str = ""
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    website: str | None = None

    address: str = ""
    building_type: str = ""
    sqft: int | None = None
    num_tenants: int | None = None
    borough: str = ""
    neighborhood: str = ""
    year_built: int | None = None
    floors: int | None = None
    num_employees: int | None = None

    building_isp: str | None = None
    available_isps: list[str] = []
    equipment: dict = {}
    building_summary: str = ""

    current_it_provider: str | None = None
    tech_signals: list[str] = []
    recent_news: list[str] = []
    social_links: dict = {}

    sources: list[str] = []
    discovery_date: str = ""
    score: int = 0
    qualification_notes: str = ""
    pipeline_stage: str = "NEW"

    created_at: str | None = None
    updated_at: str | None = None


class LeadListResponse(BaseModel):
    """Paginated list of leads."""

    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class StageUpdate(BaseModel):
    """Body for updating a lead's pipeline stage."""

    stage: str

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v not in VALID_PIPELINE_STAGES:
            raise ValueError(
                f"Invalid stage '{v}'. Must be one of: {', '.join(sorted(VALID_PIPELINE_STAGES))}"
            )
        return v


class NotesUpdate(BaseModel):
    """Body for updating a lead's qualification notes."""

    notes: str


class PipelineOverview(BaseModel):
    """Summary of pipeline stage counts."""

    stages: dict[str, int]
    total: int
    last_run: dict | None = None


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

VALID_EMAIL_TEMPLATES = {"initial_outreach", "follow_up", "meeting_request"}


class EmailDraftRequest(BaseModel):
    """Request body for generating an email draft."""

    lead_id: int
    template: str

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if v not in VALID_EMAIL_TEMPLATES:
            raise ValueError(
                f"Invalid template '{v}'. Must be one of: {', '.join(sorted(VALID_EMAIL_TEMPLATES))}"
            )
        return v


class EmailDraftResponse(BaseModel):
    """Response body with the generated email draft."""

    subject: str
    body: str
    model: str
    duration_ms: float


# ── Outreach ──────────────────────────────────────────────

class OutreachGenerateRequest(BaseModel):
    """Batch-generate email drafts for multiple leads."""
    lead_ids: list[int]
    template: str

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if v not in VALID_EMAIL_TEMPLATES:
            raise ValueError(f"Invalid template '{v}'. Must be one of: {', '.join(sorted(VALID_EMAIL_TEMPLATES))}")
        return v


class SkippedLead(BaseModel):
    lead_id: int
    reason: str


class OutreachMessageOut(BaseModel):
    id: int
    lead_id: int
    template: str
    status: str
    subject: str
    body: str
    to_email: str | None
    to_name: str | None
    error_message: str | None
    model: str
    duration_ms: int
    generated_at: str
    approved_at: str | None
    sent_at: str | None
    gmail_message_id: str | None


class OutreachGenerateResponse(BaseModel):
    generated: int
    skipped: list[SkippedLead]
    messages: list[OutreachMessageOut]


class OutreachQueueResponse(BaseModel):
    items: list[OutreachMessageOut]
    total: int


class OutreachApproveRequest(BaseModel):
    ids: list[int]


class OutreachApproveResponse(BaseModel):
    approved: int


class OutreachSendResponse(BaseModel):
    job_id: str
    total: int


class SendStatusResponse(BaseModel):
    status: str
    sent: int
    failed: int
    total: int
    errors: list[dict]


class OutreachEditRequest(BaseModel):
    subject: str | None = None
    body: str | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("approved", "discarded"):
            raise ValueError("Status must be 'approved' or 'discarded'")
        return v


class GmailStatusResponse(BaseModel):
    connected: bool
    email: str | None = None


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class AgentStatus(BaseModel):
    """Current agent / pipeline status."""

    total_leads: int
    last_run: dict | None = None
    stage_counts: dict[str, int]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    """Request body for Excel export."""

    stages: list[str] | None = None
    min_score: int = 0
