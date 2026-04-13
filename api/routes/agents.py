"""Agent status and trigger routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import get_db
from api.schemas import AgentStatus

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/status", response_model=AgentStatus)
def agent_status() -> AgentStatus:
    db = get_db()
    total_leads = db.get_lead_count()
    last_run = db.get_last_run()
    stage_counts = db.get_stage_counts()
    return AgentStatus(
        total_leads=total_leads,
        last_run=last_run,
        stage_counts=stage_counts,
    )


@router.post("/trigger")
def trigger_pipeline() -> dict:
    """Attempt to import and run the pipeline orchestrator.

    Returns 503 if the orchestrator module is not available.
    """
    try:
        from pipeline.orchestrator import Orchestrator  # type: ignore[import-untyped]

        orchestrator = Orchestrator()
        orchestrator.run()
        return {"status": "started"}
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Pipeline orchestrator is not available. Make sure the pipeline module is installed.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Pipeline trigger failed: {exc}",
        )
