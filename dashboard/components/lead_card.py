"""Reusable Streamlit lead card component."""

from __future__ import annotations

import streamlit as st

from core.models import EnrichedLead

# ── Score colour thresholds ─────────────────────────────────────
_SCORE_COLORS: list[tuple[int, str, str]] = [
    # (min_score, bg_colour, label)
    (80, "#2e7d32", "Hot"),
    (60, "#f57f17", "Warm"),
    (40, "#1565c0", "Cool"),
    (0, "#757575", "Cold"),
]

# ── Company-type badge colours ──────────────────────────────────
_TYPE_BADGE: dict[str, str] = {
    "CRE_OPERATOR": "#7b1fa2",
    "COWORKING": "#00838f",
    "MULTI_TENANT": "#c62828",
    "OTHER": "#546e7a",
}

# ── Source icons (emoji fallbacks) ──────────────────────────────
_SOURCE_ICONS: dict[str, str] = {
    "linkedin": "🔗",
    "costar": "🏢",
    "nyc_opendata": "🗽",
    "apollo": "🚀",
    "hunter": "🎯",
    "clearbit": "🔎",
    "web": "🌐",
}


def _score_chip(score: int) -> str:
    """Return an HTML badge for the lead score."""
    for threshold, colour, label in _SCORE_COLORS:
        if score >= threshold:
            return (
                f'<span style="background:{colour};color:#fff;padding:2px 8px;'
                f'border-radius:10px;font-size:0.85em;font-weight:600;">'
                f"{score} &middot; {label}</span>"
            )
    return f"<span>{score}</span>"


def _type_badge(company_type: str) -> str:
    colour = _TYPE_BADGE.get(company_type, "#546e7a")
    label = company_type.replace("_", " ").title()
    return (
        f'<span style="background:{colour};color:#fff;padding:2px 8px;'
        f'border-radius:10px;font-size:0.8em;">{label}</span>'
    )


def _source_icons(sources: list[str]) -> str:
    icons = " ".join(_SOURCE_ICONS.get(s.lower(), "📄") for s in sources)
    return icons


def render_lead_card(lead: EnrichedLead, key_prefix: str = "") -> bool:
    """Render a compact lead card inside an st.expander.

    Returns True if the user clicks the *View Detail* button so the
    caller can navigate to the detail page.
    """
    card_key = f"{key_prefix}card_{lead.id}"

    header_parts = [
        f"**{lead.company_name}**",
    ]
    if lead.contact_name:
        header_parts.append(f" — {lead.contact_name}")

    header_text = "".join(header_parts)

    with st.expander(header_text, expanded=False):
        # Row 1 — badges
        badge_html = " &nbsp; ".join(
            filter(None, [
                _score_chip(lead.score),
                _type_badge(lead.company_type),
            ])
        )
        source_text = _source_icons(lead.sources) if lead.sources else ""
        st.markdown(
            f"{badge_html} &nbsp; {source_text}",
            unsafe_allow_html=True,
        )

        # Row 2 — contact info
        cols = st.columns(3)
        with cols[0]:
            if lead.contact_title:
                st.caption(f"Title: {lead.contact_title}")
            if lead.email:
                st.caption(f"Email: {lead.email}")
        with cols[1]:
            if lead.phone:
                st.caption(f"Phone: {lead.phone}")
            if lead.address:
                st.caption(f"Address: {lead.address}")
        with cols[2]:
            if lead.building_type:
                st.caption(f"Building: {lead.building_type}")
            if lead.sqft:
                st.caption(f"SqFt: {lead.sqft:,}")

        # Row 3 — action button
        return st.button("View Detail", key=f"{card_key}_detail", use_container_width=True)
