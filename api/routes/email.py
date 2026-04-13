"""Email drafting routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import get_db, get_settings
from api.schemas import EmailDraftRequest, EmailDraftResponse
from api.services.email_service import draft_email
from core.llm_client import LLMClient, LLMError

router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/draft", response_model=EmailDraftResponse)
def generate_draft(body: EmailDraftRequest) -> EmailDraftResponse:
    db = get_db()
    lead = db.get_lead(body.lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {body.lead_id} not found")

    settings = get_settings()
    llm = LLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)

    try:
        result = draft_email(lead=lead, template=body.template, llm=llm)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"LLM service unavailable: {exc}")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to LLM service: {exc}",
        )

    return EmailDraftResponse(
        subject=result["subject"],
        body=result["body"],
        model=result["model"],
        duration_ms=result["duration_ms"],
    )
