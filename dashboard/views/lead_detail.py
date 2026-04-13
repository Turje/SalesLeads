"""Single lead detail view."""

from __future__ import annotations

import streamlit as st

from core.database import Database
from core.models import EnrichedLead


def _display_section(title: str, items: dict[str, str | None]) -> None:
    """Render a section with key-value pairs, skipping None values."""
    st.subheader(title)
    for label, value in items.items():
        if value:
            st.markdown(f"**{label}:** {value}")


def render() -> None:
    """Render the lead detail page."""
    st.header("Lead Detail")

    db: Database = st.session_state["db"]

    # ── Lead selection ──────────────────────────────────────────
    all_leads = db.get_all_leads(limit=500)
    if not all_leads:
        st.info("No leads in the database yet.")
        return

    # Check if we arrived here via a link from another page
    preselected_id = st.session_state.get("selected_lead_id")

    lead_options = {lead.id: f"{lead.company_name} (ID {lead.id})" for lead in all_leads}
    lead_ids = list(lead_options.keys())

    default_index = 0
    if preselected_id and preselected_id in lead_ids:
        default_index = lead_ids.index(preselected_id)

    selected_id = st.selectbox(
        "Select Lead",
        options=lead_ids,
        format_func=lambda lid: lead_options[lid],
        index=default_index,
        key="detail_lead_select",
    )

    lead = db.get_lead(selected_id)
    if lead is None:
        st.error(f"Lead with ID {selected_id} not found.")
        return

    # ── Score header ────────────────────────────────────────────
    mcols = st.columns([3, 1, 1])
    with mcols[0]:
        st.title(lead.company_name)
    with mcols[1]:
        if lead.score >= 80:
            score_color = "🟢"
        elif lead.score >= 60:
            score_color = "🟡"
        elif lead.score >= 40:
            score_color = "🔵"
        else:
            score_color = "⚪"
        st.metric("Score", f"{score_color} {lead.score}/100")
    with mcols[2]:
        st.metric("Stage", lead.pipeline_stage)

    st.divider()

    # ── Contact Info ────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        _display_section("Contact Information", {
            "Name": lead.contact_name,
            "Title": lead.contact_title,
            "Email": lead.email,
            "Phone": lead.phone,
            "LinkedIn": lead.linkedin_url,
            "Website": lead.website,
        })

    # ── Property Details ────────────────────────────────────────
    with col2:
        sqft_str = f"{lead.sqft:,}" if lead.sqft else None
        tenants_str = str(lead.num_tenants) if lead.num_tenants else None
        _display_section("Property Details", {
            "Address": lead.address,
            "Building Type": lead.building_type,
            "Square Footage": sqft_str,
            "Number of Tenants": tenants_str,
            "Company Type": lead.company_type.replace("_", " ").title(),
        })

    st.divider()

    # ── Intelligence ────────────────────────────────────────────
    st.subheader("Intelligence")
    intel_cols = st.columns(2)
    with intel_cols[0]:
        if lead.current_it_provider:
            st.markdown(f"**Current IT Provider:** {lead.current_it_provider}")
        if lead.tech_signals:
            st.markdown("**Tech Signals:**")
            for signal in lead.tech_signals:
                st.markdown(f"- {signal}")
    with intel_cols[1]:
        if lead.recent_news:
            st.markdown("**Recent News:**")
            for news in lead.recent_news:
                st.markdown(f"- {news}")
        if lead.social_links:
            st.markdown("**Social Links:**")
            for platform, url in lead.social_links.items():
                st.markdown(f"- **{platform}:** {url}")

    # ── Sources & Discovery ─────────────────────────────────────
    st.divider()
    src_cols = st.columns(2)
    with src_cols[0]:
        st.markdown(f"**Sources:** {', '.join(lead.sources) if lead.sources else 'N/A'}")
    with src_cols[1]:
        st.markdown(f"**Discovery Date:** {lead.discovery_date.isoformat()}")

    # ── Editable notes ──────────────────────────────────────────
    st.divider()
    st.subheader("Qualification Notes")
    notes = st.text_area(
        "Notes",
        value=lead.qualification_notes,
        height=150,
        key=f"notes_{lead.id}",
        label_visibility="collapsed",
    )
    if st.button("Save Notes", key="save_notes"):
        lead.qualification_notes = notes
        db.update_lead(lead.id, lead)
        st.success("Notes saved.")

    # ── Draft Email link ────────────────────────────────────────
    st.divider()
    if st.button("Draft Email for this Lead", key="detail_draft_email", use_container_width=True):
        st.session_state["email_lead_id"] = lead.id
        st.session_state["active_page"] = "Email Drafter"
        st.rerun()
