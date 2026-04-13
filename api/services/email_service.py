"""Email drafting service — generates personalised emails via LLM."""

from __future__ import annotations

from core.llm_client import LLMClient, LLMResponse
from core.models import EnrichedLead

# ---------------------------------------------------------------------------
# Prompt templates (keyed by the API-facing template name)
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, str] = {
    "initial_outreach": (
        "Write a professional initial outreach email to {contact_name} at "
        "{company_name}. They are a {company_type} located at {address}. "
        "Their building is a {building_type}."
        "{news_section}"
        "{pain_section}"
        "\nThe email should introduce our managed IT services for commercial "
        "real estate, mention how we can help with their specific building "
        "type, and request a brief introductory call. Keep it concise and "
        "professional — 3-4 paragraphs max."
        "\nStart the email with a 'Subject:' line."
    ),
    "follow_up": (
        "Write a professional follow-up email to {contact_name} at "
        "{company_name}. We previously reached out about our managed IT "
        "services for their {building_type} at {address}."
        "{news_section}"
        "{pain_section}"
        "\nThe tone should be friendly, not pushy. Reference the previous "
        "outreach and offer additional value. 2-3 paragraphs."
        "\nStart the email with a 'Subject:' line."
    ),
    "meeting_request": (
        "Write a concise meeting request email to {contact_name} at "
        "{company_name}. They manage a {building_type} at {address} with "
        "{num_tenants} tenants."
        "{news_section}"
        "{pain_section}"
        "\nRequest a 30-minute meeting to discuss how our IT solutions can "
        "improve their tenant experience and reduce operational overhead. "
        "Propose 2-3 time slots this week. 2-3 paragraphs."
        "\nStart the email with a 'Subject:' line."
    ),
}

_SYSTEM_PROMPT = (
    "You are an expert sales development representative "
    "for a managed IT services company that specializes "
    "in commercial real estate. Write professional, "
    "personalized emails. Output ONLY the email text — "
    "no commentary."
)


def draft_email(
    lead: EnrichedLead,
    template: str,
    llm: LLMClient,
) -> dict:
    """Build a personalised prompt, call the LLM, and return the draft.

    Returns
    -------
    dict
        Keys: subject, body, model, duration_ms
    """
    # --- contextual sections ------------------------------------------------
    news_section = ""
    if lead.recent_news:
        news_items = "; ".join(lead.recent_news[:3])
        news_section = f"\nRecent news about them: {news_items}."

    pain_section = ""
    pain_points: list[str] = []
    if lead.current_it_provider:
        pain_points.append(
            f"Their current IT provider is {lead.current_it_provider}"
        )
    if lead.tech_signals:
        pain_points.append(
            f"Tech signals: {', '.join(lead.tech_signals[:3])}"
        )
    if pain_points:
        pain_section = "\nRelevant context: " + ". ".join(pain_points) + "."

    # --- fill template ------------------------------------------------------
    prompt = _TEMPLATES[template].format(
        contact_name=lead.contact_name or "the team",
        company_name=lead.company_name,
        company_type=lead.company_type.replace("_", " ").title(),
        address=lead.address or "their location",
        building_type=lead.building_type or "commercial building",
        num_tenants=lead.num_tenants or "multiple",
        news_section=news_section,
        pain_section=pain_section,
    )

    # --- call LLM -----------------------------------------------------------
    response: LLMResponse = llm.generate(prompt=prompt, system=_SYSTEM_PROMPT)

    # --- parse subject from response ----------------------------------------
    content = response.content.strip()
    subject = ""
    body = content

    lines = content.split("\n", 1)
    first_line = lines[0].strip()
    if first_line.lower().startswith("subject:"):
        subject = first_line[len("subject:"):].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

    if not subject:
        subject = f"Introduction — Managed IT for {lead.company_name}"

    return {
        "subject": subject,
        "body": body,
        "model": response.model,
        "duration_ms": response.total_duration_ms,
    }
