"""Kanban-style pipeline view."""

from __future__ import annotations

import streamlit as st

from core.database import Database
from core.models import VALID_PIPELINE_STAGES, PipelineStage
from dashboard.components.lead_card import render_lead_card

# Ordered stages for the kanban board
_STAGES: list[PipelineStage] = ["NEW", "CONTACTED", "MEETING", "PROPOSAL", "CLOSED"]

_STAGE_EMOJI: dict[str, str] = {
    "NEW": "🆕",
    "CONTACTED": "📞",
    "MEETING": "🤝",
    "PROPOSAL": "📋",
    "CLOSED": "✅",
}


def _next_stage(current: PipelineStage) -> PipelineStage | None:
    idx = _STAGES.index(current)
    return _STAGES[idx + 1] if idx < len(_STAGES) - 1 else None


def _prev_stage(current: PipelineStage) -> PipelineStage | None:
    idx = _STAGES.index(current)
    return _STAGES[idx - 1] if idx > 0 else None


def render() -> None:
    """Render the kanban pipeline board."""
    st.header("Pipeline")

    db: Database = st.session_state["db"]
    stage_counts = db.get_stage_counts()

    # ── Column headers ──────────────────────────────────────────
    columns = st.columns(len(_STAGES))

    for col, stage in zip(columns, _STAGES):
        count = stage_counts.get(stage, 0)
        emoji = _STAGE_EMOJI.get(stage, "")
        with col:
            st.subheader(f"{emoji} {stage} ({count})")
            st.divider()

            leads = db.get_all_leads(stage=stage, limit=50)
            if not leads:
                st.caption("No leads in this stage.")
                continue

            for lead in leads:
                with st.container(border=True):
                    st.markdown(f"**{lead.company_name}**")
                    if lead.contact_name:
                        st.caption(lead.contact_name)
                    st.caption(f"Score: {lead.score}")

                    btn_cols = st.columns(2)
                    prev = _prev_stage(stage)
                    nxt = _next_stage(stage)

                    with btn_cols[0]:
                        if prev and st.button(
                            f"← {prev}",
                            key=f"move_{lead.id}_back",
                            use_container_width=True,
                        ):
                            db.update_pipeline_stage(lead.id, prev)
                            st.rerun()

                    with btn_cols[1]:
                        if nxt and st.button(
                            f"{nxt} →",
                            key=f"move_{lead.id}_fwd",
                            use_container_width=True,
                        ):
                            db.update_pipeline_stage(lead.id, nxt)
                            st.rerun()
