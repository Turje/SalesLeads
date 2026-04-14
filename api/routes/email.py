"""Email drafting routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from api.deps import get_db, get_settings
from api.schemas import EmailDraftRequest, EmailDraftResponse
from api.services.email_service import draft_email
from core.llm_client import LLMClient, LLMError
from core.models import EnrichedLead

router = APIRouter(prefix="/api/email", tags=["email"])


def _template_fallback(lead: EnrichedLead, template: str) -> dict:
    """Generate a professional email using templates when LLM is unavailable."""
    company = lead.company_name
    contact = lead.contact_name or "there"
    first_name = contact.split()[0] if contact != "there" else "there"
    building = lead.building_type or "commercial building"
    neighborhood = lead.neighborhood or lead.borough or "your area"

    templates = {
        "initial_outreach": {
            "subject": f"Managed IT Services for {company}",
            "body": (
                f"Hi {first_name},\n\n"
                f"I came across {company} and your {building} in {neighborhood}. "
                "We specialize in managed IT services and WiFi solutions for commercial real estate — "
                "including tenant WiFi monetization, network infrastructure upgrades, and building-wide connectivity.\n\n"
                "I'd love to share how we've helped similar properties increase NOI through managed WiFi programs.\n\n"
                "Would you have 15 minutes this week for a quick call?\n\n"
                "Best regards"
            ),
        },
        "follow_up": {
            "subject": f"Following Up — IT Services for {company}",
            "body": (
                f"Hi {first_name},\n\n"
                "I wanted to follow up on my previous message about managed IT and WiFi services "
                f"for {company}. We've been working with several properties in {neighborhood} "
                "and have seen great results with our tenant connectivity solutions.\n\n"
                "Happy to share some case studies if that would be helpful.\n\n"
                "Best regards"
            ),
        },
        "meeting_request": {
            "subject": f"Meeting Request — {company} IT Infrastructure",
            "body": (
                f"Hi {first_name},\n\n"
                f"I'd like to schedule a brief meeting to discuss how we can enhance the IT infrastructure "
                f"at {company}. We offer comprehensive solutions including:\n\n"
                "- Building-wide managed WiFi\n"
                "- Tenant WiFi monetization programs\n"
                "- Network security and monitoring\n"
                "- Smart building integrations\n\n"
                "Would any of these times work for a 20-minute call?\n\n"
                "Best regards"
            ),
        },
    }

    t = templates.get(template, templates["initial_outreach"])
    return {
        "subject": t["subject"],
        "body": t["body"],
        "model": "template",
        "duration_ms": 0,
    }


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
    except (LLMError, Exception):
        # LLM unavailable — fall back to template-based generation
        start = time.time()
        result = _template_fallback(lead, body.template)
        result["duration_ms"] = int((time.time() - start) * 1000)

    return EmailDraftResponse(
        subject=result["subject"],
        body=result["body"],
        model=result["model"],
        duration_ms=result["duration_ms"],
    )
