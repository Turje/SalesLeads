"""Filterable lead list view."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from core.database import Database
from core.models import VALID_COMPANY_TYPES, VALID_PIPELINE_STAGES

PAGE_SIZE = 25


def render() -> None:
    """Render the lead list page with sidebar filters."""
    st.header("Leads")

    db: Database = st.session_state["db"]

    # ── Sidebar filters ─────────────────────────────────────────
    with st.sidebar:
        st.subheader("Filters")

        company_type = st.selectbox(
            "Company Type",
            options=["All"] + sorted(VALID_COMPANY_TYPES),
            index=0,
            key="filter_company_type",
        )

        score_range = st.slider(
            "Score Range",
            min_value=0,
            max_value=100,
            value=(0, 100),
            key="filter_score_range",
        )

        source = st.text_input(
            "Source (contains)",
            value="",
            key="filter_source",
            placeholder="e.g. linkedin",
        )

        stage = st.selectbox(
            "Pipeline Stage",
            options=["All"] + sorted(VALID_PIPELINE_STAGES),
            index=0,
            key="filter_stage",
        )

        date_range = st.date_input(
            "Discovery Date Range",
            value=(date.today() - timedelta(days=365), date.today()),
            key="filter_date_range",
        )

    # ── Pagination state ────────────────────────────────────────
    if "leads_page" not in st.session_state:
        st.session_state["leads_page"] = 0
    current_page: int = st.session_state["leads_page"]

    # ── Query the database ──────────────────────────────────────
    query_kwargs: dict = {
        "min_score": score_range[0],
        "limit": PAGE_SIZE,
        "offset": current_page * PAGE_SIZE,
    }
    if company_type != "All":
        query_kwargs["company_type"] = company_type
    if stage != "All":
        query_kwargs["stage"] = stage
    if source:
        query_kwargs["source"] = source

    leads = db.get_all_leads(**query_kwargs)

    # Post-filter: score upper bound + date range (DB only has min_score)
    if len(date_range) == 2:
        start_date, end_date = date_range
        leads = [
            l for l in leads
            if l.score <= score_range[1]
            and start_date <= l.discovery_date <= end_date
        ]
    else:
        leads = [l for l in leads if l.score <= score_range[1]]

    # ── Results table ───────────────────────────────────────────
    if not leads:
        st.info("No leads match the current filters.")
        return

    rows = []
    for lead in leads:
        rows.append({
            "ID": lead.id,
            "Company": lead.company_name,
            "Contact": lead.contact_name or "—",
            "Score": lead.score,
            "Type": lead.company_type.replace("_", " ").title(),
            "Stage": lead.pipeline_stage,
            "Discovery Date": lead.discovery_date.isoformat(),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    # ── Quick action buttons per lead ───────────────────────────
    st.subheader("Quick Actions")
    action_cols = st.columns([2, 1, 1])
    with action_cols[0]:
        selected_id = st.selectbox(
            "Select Lead",
            options=[l.id for l in leads],
            format_func=lambda lid: next(
                (l.company_name for l in leads if l.id == lid), str(lid)
            ),
            key="leads_action_select",
        )
    with action_cols[1]:
        if st.button("View Detail", key="leads_view_detail"):
            st.session_state["selected_lead_id"] = selected_id
            st.session_state["active_page"] = "Lead Detail"
            st.rerun()
    with action_cols[2]:
        if st.button("Draft Email", key="leads_draft_email"):
            st.session_state["email_lead_id"] = selected_id
            st.session_state["active_page"] = "Email Drafter"
            st.rerun()

    # ── Pagination controls ─────────────────────────────────────
    st.divider()
    pcols = st.columns(3)
    with pcols[0]:
        if current_page > 0 and st.button("← Previous"):
            st.session_state["leads_page"] = current_page - 1
            st.rerun()
    with pcols[1]:
        st.caption(f"Page {current_page + 1}")
    with pcols[2]:
        if len(leads) == PAGE_SIZE and st.button("Next →"):
            st.session_state["leads_page"] = current_page + 1
            st.rerun()
