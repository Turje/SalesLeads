"""Agent monitoring and status page."""

from __future__ import annotations

import json
import logging

import streamlit as st

from core.database import Database

logger = logging.getLogger(__name__)


def render() -> None:
    """Render the agent status monitoring page."""
    st.header("Agent Status")

    db: Database = st.session_state["db"]

    # ── System health overview ──────────────────────────────────
    st.subheader("System Health")

    health_cols = st.columns(3)

    total_leads = db.get_lead_count()
    last_run = db.get_last_run()
    stage_counts = db.get_stage_counts()

    with health_cols[0]:
        st.metric("Total Leads in DB", total_leads)

    with health_cols[1]:
        if last_run:
            st.metric("Last Successful Run", last_run["run_timestamp"][:19])
        else:
            st.metric("Last Successful Run", "Never")

    with health_cols[2]:
        active_stages = sum(
            v for k, v in stage_counts.items() if k != "CLOSED"
        )
        st.metric("Active Pipeline Leads", active_stages)

    st.divider()

    # ── Stage distribution ──────────────────────────────────────
    if stage_counts:
        st.subheader("Pipeline Distribution")
        chart_cols = st.columns(len(stage_counts))
        for col, (stage, count) in zip(chart_cols, sorted(stage_counts.items())):
            with col:
                st.metric(stage, count)

    st.divider()

    # ── Pipeline run history ────────────────────────────────────
    st.subheader("Pipeline Run History")

    runs = _get_recent_runs(db, limit=20)

    if not runs:
        st.info("No pipeline runs recorded yet.")
    else:
        run_rows = []
        for run in runs:
            stats = run.get("stats", {})
            run_rows.append({
                "Run ID": run["run_id"][:8] + "...",
                "Timestamp": run["run_timestamp"][:19],
                "Leads Found": stats.get("total_leads_found", "—"),
                "Leads Enriched": stats.get("total_enriched", "—"),
                "Errors": stats.get("errors", 0),
                "Duration (s)": stats.get("duration_seconds", "—"),
            })

        st.dataframe(run_rows, use_container_width=True, hide_index=True)

    st.divider()

    # ── Agent table ─────────────────────────────────────────────
    st.subheader("Agent Details")

    # Extract per-agent stats from the most recent run
    agent_rows = _extract_agent_stats(last_run)

    if agent_rows:
        st.dataframe(agent_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No per-agent statistics available from the latest run.")

    # ── Manual run trigger ──────────────────────────────────────
    st.divider()
    st.subheader("Manual Run")
    st.caption(
        "Trigger an individual agent or the full pipeline. "
        "Requires the pipeline orchestrator to be available."
    )

    agent_names = ["Full Pipeline", "LinkedInAgent", "CoStarAgent", "NYCOpenDataAgent"]
    selected_agent = st.selectbox("Agent to run", options=agent_names, key="run_agent_select")

    if st.button("Run Now", type="primary", key="run_agent_btn"):
        _trigger_run(selected_agent, db)


def _get_recent_runs(db: Database, limit: int = 20) -> list[dict]:
    """Fetch the most recent pipeline runs from the database."""
    try:
        import sqlite3

        with db._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "run_timestamp": row["run_timestamp"],
                "stats": json.loads(row["stats"]),
            }
            for row in rows
        ]
    except Exception as exc:
        logger.warning("Failed to fetch pipeline runs: %s", exc)
        return []


def _extract_agent_stats(last_run: dict | None) -> list[dict]:
    """Parse per-agent statistics from a run's stats dict."""
    if not last_run:
        return []

    stats = last_run.get("stats", {})
    agents_data = stats.get("agents", {})

    if not agents_data:
        return []

    rows = []
    for agent_name, agent_stats in agents_data.items():
        rows.append({
            "Agent": agent_name,
            "Last Run": last_run["run_timestamp"][:19],
            "Leads Found": agent_stats.get("leads_found", 0),
            "Errors": agent_stats.get("errors", 0),
            "Duration (s)": agent_stats.get("duration_seconds", "—"),
            "Status": "OK" if agent_stats.get("errors", 0) == 0 else "ERROR",
        })

    return rows


def _trigger_run(agent_name: str, db: Database) -> None:
    """Attempt to trigger an agent run."""
    try:
        if agent_name == "Full Pipeline":
            # Try to import and run the orchestrator
            try:
                from pipeline import orchestrator  # type: ignore[attr-defined]

                with st.spinner("Running full pipeline..."):
                    orchestrator.run()
                st.success("Pipeline run completed.")
                st.rerun()
            except ImportError:
                st.warning(
                    "Pipeline orchestrator not yet implemented. "
                    "Run will be available once the orchestrator module is built."
                )
        else:
            try:
                from pipeline import orchestrator  # type: ignore[attr-defined]

                with st.spinner(f"Running {agent_name}..."):
                    orchestrator.run_single_agent(agent_name)
                st.success(f"{agent_name} completed.")
                st.rerun()
            except ImportError:
                st.warning(
                    f"Cannot run {agent_name} — pipeline orchestrator "
                    f"not yet implemented."
                )
    except Exception as exc:
        st.error(f"Run failed: {exc}")
