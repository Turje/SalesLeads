"""CRUD routes for leads."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_db
from api.schemas import LeadListResponse, LeadResponse, NotesUpdate, StageUpdate
from core.models import EnrichedLead

router = APIRouter(prefix="/api/leads", tags=["leads"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lead_to_response(lead: EnrichedLead) -> LeadResponse:
    """Convert a core EnrichedLead dataclass to a Pydantic LeadResponse."""
    return LeadResponse(
        id=lead.id,
        company_name=lead.company_name,
        company_type=lead.company_type,
        contact_name=lead.contact_name,
        contact_title=lead.contact_title,
        email=lead.email,
        phone=lead.phone,
        linkedin_url=lead.linkedin_url,
        website=lead.website,
        address=lead.address,
        building_type=lead.building_type,
        sqft=lead.sqft,
        num_tenants=lead.num_tenants,
        borough=lead.borough,
        neighborhood=lead.neighborhood,
        year_built=lead.year_built,
        floors=lead.floors,
        num_employees=lead.num_employees,
        building_isp=lead.building_isp,
        available_isps=lead.available_isps,
        equipment=lead.equipment,
        building_summary=lead.building_summary,
        current_it_provider=lead.current_it_provider,
        tech_signals=lead.tech_signals,
        recent_news=lead.recent_news,
        social_links=lead.social_links,
        sources=lead.sources,
        discovery_date=lead.discovery_date.isoformat(),
        score=lead.score,
        qualification_notes=lead.qualification_notes,
        pipeline_stage=lead.pipeline_stage,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=LeadListResponse)
@router.get("/", response_model=LeadListResponse, include_in_schema=False)
def list_leads(
    stage: str | None = Query(None),
    borough: str | None = Query(None),
    neighborhood: str | None = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    company_type: str | None = Query(None),
    source: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> LeadListResponse:
    db = get_db()
    offset = (page - 1) * page_size
    leads = db.get_all_leads(
        stage=stage,
        min_score=min_score,
        source=source,
        company_type=company_type,
        borough=borough,
        neighborhood=neighborhood,
        limit=page_size,
        offset=offset,
    )
    total = db.get_lead_count(stage=stage)
    return LeadListResponse(
        items=[_lead_to_response(l) for l in leads],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int) -> LeadResponse:
    db = get_db()
    lead = db.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    return _lead_to_response(lead)


@router.patch("/{lead_id}/stage", response_model=LeadResponse)
def update_stage(lead_id: int, body: StageUpdate) -> LeadResponse:
    db = get_db()
    lead = db.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    db.update_pipeline_stage(lead_id, body.stage)  # type: ignore[arg-type]
    updated = db.get_lead(lead_id)
    return _lead_to_response(updated)  # type: ignore[arg-type]


@router.patch("/{lead_id}/notes", response_model=LeadResponse)
def update_notes(lead_id: int, body: NotesUpdate) -> LeadResponse:
    db = get_db()
    lead = db.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    db.update_notes(lead_id, body.notes)
    updated = db.get_lead(lead_id)
    return _lead_to_response(updated)  # type: ignore[arg-type]


@router.delete("/{lead_id}", status_code=204)
def delete_lead(lead_id: int) -> None:
    db = get_db()
    lead = db.get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    db.delete_lead(lead_id)
