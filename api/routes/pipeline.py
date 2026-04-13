"""Pipeline overview routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.deps import get_db
from api.routes.leads import _lead_to_response
from api.schemas import LeadListResponse, PipelineOverview

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/overview", response_model=PipelineOverview)
def pipeline_overview() -> PipelineOverview:
    db = get_db()
    stage_counts = db.get_stage_counts()
    total = sum(stage_counts.values())
    last_run = db.get_last_run()
    return PipelineOverview(
        stages=stage_counts,
        total=total,
        last_run=last_run,
    )


@router.get("/stages/{stage}", response_model=LeadListResponse)
def leads_by_stage(
    stage: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> LeadListResponse:
    db = get_db()
    offset = (page - 1) * page_size
    leads = db.get_all_leads(stage=stage, limit=page_size, offset=offset)
    total = db.get_lead_count(stage=stage)
    return LeadListResponse(
        items=[_lead_to_response(l) for l in leads],
        total=total,
        page=page,
        page_size=page_size,
    )
