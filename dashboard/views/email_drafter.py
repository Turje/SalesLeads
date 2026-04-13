"""LLM-powered email drafting page."""

from __future__ import annotations

import streamlit as st

from core.database import Database
from core.llm_client import LLMClient, LLMError

# ── Email templates ─────────────────────────────────────────────
_TEMPLATES: dict[str, str] = {
    "Initial Outreach": (
        "Write a professional initial outreach email to {contact_name} at "
        "{company_name}. They are a {company_type} located at {address}. "
        "Their building is a {building_type}."
        "{news_section}"
        "{pain_section}"
        "\nThe email should introduce our managed IT services for commercial "
        "real estate, mention how we can help with their specific building "
        "type, and request a brief introductory call. Keep it concise and "
        "professional — 3-4 paragraphs max."
    ),
    "Follow-up": (
        "Write a professional follow-up email to {contact_name} at "
        "{company_name}. We previously reached out about our managed IT "
        "services for their {building_type} at {address}."
        "{news_section}"
        "{pain_section}"
        "\nThe tone should be friendly, not pushy. Reference the previous "
        "outreach and offer additional value. 2-3 paragraphs."
    ),
    "Meeting Request": (
        "Write a concise meeting request email to {contact_name} at "
        "{company_name}. They manage a {building_type} at {address} with "
        "{num_tenants} tenants."
        "{news_section}"
        "{pain_section}"
        "\nRequest a 30-minute meeting to discuss how our IT solutions can "
        "improve their tenant experience and reduce operational overhead. "
        "Propose 2-3 time slots this week. 2-3 paragraphs."
    ),
}


def render() -> None:
    """Render the email drafter page."""
    st.header("Email Drafter")

    db: Database = st.session_state["db"]

    # ── Lead selection ──────────────────────────────────────────
    all_leads = db.get_all_leads(limit=500)
    if not all_leads:
        st.info("No leads available. Add leads to the database first.")
        return

    # Pre-select if arriving from another page
    preselected_id = st.session_state.get("email_lead_id")
    lead_ids = [l.id for l in all_leads]
    default_index = 0
    if preselected_id and preselected_id in lead_ids:
        default_index = lead_ids.index(preselected_id)

    selected_id = st.selectbox(
        "Select Lead",
        options=lead_ids,
        format_func=lambda lid: next(
            (l.company_name for l in all_leads if l.id == lid), str(lid)
        ),
        index=default_index,
        key="email_lead_select",
    )

    lead = db.get_lead(selected_id)
    if lead is None:
        st.error(f"Lead {selected_id} not found.")
        return

    # Show lead summary
    with st.expander("Lead Summary", expanded=False):
        cols = st.columns(3)
        with cols[0]:
            st.markdown(f"**Company:** {lead.company_name}")
            st.markdown(f"**Contact:** {lead.contact_name or 'N/A'}")
        with cols[1]:
            st.markdown(f"**Type:** {lead.company_type.replace('_', ' ').title()}")
            st.markdown(f"**Score:** {lead.score}/100")
        with cols[2]:
            st.markdown(f"**Stage:** {lead.pipeline_stage}")
            st.markdown(f"**Email:** {lead.email or 'N/A'}")

    st.divider()

    # ── Template selection ──────────────────────────────────────
    template_name = st.selectbox(
        "Email Template",
        options=list(_TEMPLATES.keys()),
        key="email_template",
    )

    # ── Generate ────────────────────────────────────────────────
    if st.button("Generate Email", type="primary", use_container_width=True):
        # Build personalization context
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

        prompt = _TEMPLATES[template_name].format(
            contact_name=lead.contact_name or "the team",
            company_name=lead.company_name,
            company_type=lead.company_type.replace("_", " ").title(),
            address=lead.address or "their location",
            building_type=lead.building_type or "commercial building",
            num_tenants=lead.num_tenants or "multiple",
            news_section=news_section,
            pain_section=pain_section,
        )

        try:
            with st.spinner("Generating email with LLM..."):
                llm = _get_llm_client()
                response = llm.generate(
                    prompt=prompt,
                    system=(
                        "You are an expert sales development representative "
                        "for a managed IT services company that specializes "
                        "in commercial real estate. Write professional, "
                        "personalized emails. Output ONLY the email text — "
                        "no commentary."
                    ),
                )
            st.session_state["generated_email"] = response.content
            st.session_state["email_model"] = response.model
            st.session_state["email_duration"] = response.total_duration_ms
        except LLMError as exc:
            st.error(f"LLM generation failed: {exc}")
        except Exception as exc:
            st.error(
                f"Could not connect to Ollama. Make sure it is running. "
                f"Error: {exc}"
            )

    # ── Display generated email ─────────────────────────────────
    if "generated_email" in st.session_state:
        st.divider()
        st.subheader("Generated Email")

        if "email_model" in st.session_state:
            meta_cols = st.columns(2)
            with meta_cols[0]:
                st.caption(f"Model: {st.session_state['email_model']}")
            with meta_cols[1]:
                st.caption(
                    f"Duration: {st.session_state.get('email_duration', 0):.0f}ms"
                )

        edited_email = st.text_area(
            "Edit the email below:",
            value=st.session_state["generated_email"],
            height=350,
            key="email_editor",
        )

        # Copy to clipboard via st.code
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Copy to Clipboard", use_container_width=True):
                st.code(edited_email, language=None)
                st.info("Select the text above and copy it (Ctrl/Cmd+C).")
        with col2:
            if st.button("Clear", use_container_width=True):
                for key in ("generated_email", "email_model", "email_duration"):
                    st.session_state.pop(key, None)
                st.rerun()


def _get_llm_client() -> LLMClient:
    """Return a cached LLM client."""
    if "llm_client" not in st.session_state:
        from config.settings import Settings

        settings = Settings()
        st.session_state["llm_client"] = LLMClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    return st.session_state["llm_client"]
