"""SalesLeads Streamlit Dashboard — main entry point.

Run with:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Ensure project root is on sys.path so `core.*` imports work ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from core.database import Database
from config.settings import Settings

# ── Page modules ────────────────────────────────────────────────
from dashboard.views import (
    pipeline,
    leads,
    lead_detail,
    email_drafter,
    export,
    agent_status,
)

# ── Page config (must be first Streamlit call) ──────────────────
st.set_page_config(
    page_title="SalesLeads",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Page registry ───────────────────────────────────────────────
_PAGES: dict[str, object] = {
    "Pipeline": pipeline,
    "Leads": leads,
    "Lead Detail": lead_detail,
    "Email Drafter": email_drafter,
    "Export": export,
    "Agent Status": agent_status,
}

_PAGE_ICONS: dict[str, str] = {
    "Pipeline": "📋",
    "Leads": "👥",
    "Lead Detail": "🔍",
    "Email Drafter": "✉️",
    "Export": "📤",
    "Agent Status": "🤖",
}


# ── Initialise database connection once ─────────────────────────
def _init_db() -> None:
    """Initialise a Database in session state if absent."""
    if "db" not in st.session_state:
        settings = Settings()
        st.session_state["db"] = Database(db_path=settings.db_path)


def main() -> None:
    """Main application entry point."""
    _init_db()

    # ── Sidebar navigation ──────────────────────────────────────
    with st.sidebar:
        st.title("SalesLeads")
        st.caption("CRE Lead Intelligence Platform")
        st.divider()

        # Determine active page (may be set by other pages for navigation)
        if "active_page" not in st.session_state:
            st.session_state["active_page"] = "Pipeline"

        page_names = list(_PAGES.keys())
        current_index = 0
        if st.session_state["active_page"] in page_names:
            current_index = page_names.index(st.session_state["active_page"])

        selected = st.radio(
            "Navigation",
            options=page_names,
            index=current_index,
            format_func=lambda p: f"{_PAGE_ICONS.get(p, '')} {p}",
            key="nav_radio",
            label_visibility="collapsed",
        )

        # Sync back to session state
        st.session_state["active_page"] = selected

        # ── Sidebar footer ──────────────────────────────────────
        st.divider()
        db: Database = st.session_state["db"]
        total = db.get_lead_count()
        st.caption(f"Total leads: {total}")

        last_run = db.get_last_run()
        if last_run:
            st.caption(f"Last run: {last_run['run_timestamp'][:16]}")

    # ── Render active page ──────────────────────────────────────
    page_module = _PAGES[st.session_state["active_page"]]
    try:
        page_module.render()  # type: ignore[union-attr]
    except Exception as exc:
        st.error(f"Error rendering page: {exc}")
        st.exception(exc)


if __name__ == "__main__":
    main()
