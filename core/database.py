"""SQLite database layer for SalesLeads platform."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

from core.models import EnrichedLead, PipelineStage, VALID_PIPELINE_STAGES

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT NOT NULL,
    company_type    TEXT NOT NULL DEFAULT 'OTHER',
    contact_name    TEXT NOT NULL DEFAULT '',
    contact_title   TEXT NOT NULL DEFAULT '',
    email           TEXT,
    phone           TEXT,
    linkedin_url    TEXT,
    website         TEXT,
    address         TEXT NOT NULL DEFAULT '',
    building_type   TEXT NOT NULL DEFAULT '',
    sqft            INTEGER,
    num_tenants     INTEGER,
    borough         TEXT NOT NULL DEFAULT '',
    neighborhood    TEXT NOT NULL DEFAULT '',
    year_built      INTEGER,
    floors          INTEGER,
    num_employees   INTEGER,
    building_isp    TEXT,
    available_isps  TEXT NOT NULL DEFAULT '[]',
    equipment       TEXT NOT NULL DEFAULT '{}',
    building_summary TEXT NOT NULL DEFAULT '',
    current_it_provider TEXT,
    tech_signals    TEXT NOT NULL DEFAULT '[]',
    recent_news     TEXT NOT NULL DEFAULT '[]',
    social_links    TEXT NOT NULL DEFAULT '{}',
    sources         TEXT NOT NULL DEFAULT '[]',
    discovery_date  TEXT NOT NULL,
    score           INTEGER NOT NULL DEFAULT 0,
    qualification_notes TEXT NOT NULL DEFAULT '',
    pipeline_stage  TEXT NOT NULL DEFAULT 'NEW',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL UNIQUE,
    run_timestamp   TEXT NOT NULL,
    stats           TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company_name);
CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);
CREATE INDEX IF NOT EXISTS idx_leads_borough ON leads(borough);
CREATE INDEX IF NOT EXISTS idx_leads_neighborhood ON leads(neighborhood);

CREATE TABLE IF NOT EXISTS outreach_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL,
    template        TEXT NOT NULL,
    subject         TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'draft',
    to_email        TEXT,
    to_name         TEXT,
    error_message   TEXT,
    model           TEXT NOT NULL DEFAULT '',
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at     TEXT,
    sent_at         TEXT,
    gmail_message_id TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_messages(status);
CREATE INDEX IF NOT EXISTS idx_outreach_lead_id ON outreach_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_messages(sent_at);

CREATE TABLE IF NOT EXISTS gmail_credentials (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    email_address TEXT NOT NULL,
    encrypted_refresh_token TEXT NOT NULL,
    encrypted_access_token TEXT,
    token_expiry TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Columns added after initial release — used by _migrate()
_NEW_COLUMNS = [
    ("borough", "TEXT NOT NULL DEFAULT ''"),
    ("neighborhood", "TEXT NOT NULL DEFAULT ''"),
    ("year_built", "INTEGER"),
    ("floors", "INTEGER"),
    ("num_employees", "INTEGER"),
    ("building_isp", "TEXT"),
    ("available_isps", "TEXT NOT NULL DEFAULT '[]'"),
    ("equipment", "TEXT NOT NULL DEFAULT '{}'"),
    ("building_summary", "TEXT NOT NULL DEFAULT ''"),
]


class Database:
    """SQLite database for persisting leads and pipeline runs."""

    def __init__(self, db_path: str | Path = "salesleads.db"):
        self._db_path = str(db_path)
        self._init_schema()
        self._migrate()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)

    def _migrate(self) -> None:
        """Add new columns to existing databases that lack them."""
        with self._conn() as conn:
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(leads)").fetchall()
            }
            for col_name, col_def in _NEW_COLUMNS:
                if col_name not in existing:
                    conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_def}")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── Lead CRUD ──────────────────────────────────────────────

    def insert_lead(self, lead: EnrichedLead) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO leads
                   (company_name, company_type, contact_name, contact_title,
                    email, phone, linkedin_url, website, address, building_type,
                    sqft, num_tenants, borough, neighborhood, year_built, floors,
                    num_employees, building_isp, available_isps, equipment,
                    building_summary, current_it_provider, tech_signals,
                    recent_news, social_links, sources, discovery_date,
                    score, qualification_notes, pipeline_stage)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    lead.company_name, lead.company_type,
                    lead.contact_name, lead.contact_title,
                    lead.email, lead.phone, lead.linkedin_url, lead.website,
                    lead.address, lead.building_type,
                    lead.sqft, lead.num_tenants,
                    lead.borough, lead.neighborhood,
                    lead.year_built, lead.floors, lead.num_employees,
                    lead.building_isp,
                    json.dumps(lead.available_isps),
                    json.dumps(lead.equipment),
                    lead.building_summary,
                    lead.current_it_provider,
                    json.dumps(lead.tech_signals),
                    json.dumps(lead.recent_news),
                    json.dumps(lead.social_links),
                    json.dumps(lead.sources),
                    lead.discovery_date.isoformat(),
                    lead.score, lead.qualification_notes, lead.pipeline_stage,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def upsert_lead(self, lead: EnrichedLead) -> int:
        """Insert or update based on company_name + address match."""
        existing = self._find_by_company_and_address(lead.company_name, lead.address)
        if existing:
            self.update_lead(existing["id"], lead)
            return existing["id"]
        return self.insert_lead(lead)

    def upsert_leads(self, leads: list[EnrichedLead]) -> list[int]:
        return [self.upsert_lead(lead) for lead in leads]

    def update_lead(self, lead_id: int, lead: EnrichedLead) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE leads SET
                   company_name=?, company_type=?, contact_name=?, contact_title=?,
                   email=?, phone=?, linkedin_url=?, website=?, address=?,
                   building_type=?, sqft=?, num_tenants=?, borough=?, neighborhood=?,
                   year_built=?, floors=?, num_employees=?, building_isp=?,
                   available_isps=?, equipment=?, building_summary=?,
                   current_it_provider=?, tech_signals=?, recent_news=?,
                   social_links=?, sources=?, discovery_date=?, score=?,
                   qualification_notes=?, pipeline_stage=?,
                   updated_at=datetime('now')
                   WHERE id=?""",
                (
                    lead.company_name, lead.company_type,
                    lead.contact_name, lead.contact_title,
                    lead.email, lead.phone, lead.linkedin_url, lead.website,
                    lead.address, lead.building_type,
                    lead.sqft, lead.num_tenants,
                    lead.borough, lead.neighborhood,
                    lead.year_built, lead.floors, lead.num_employees,
                    lead.building_isp,
                    json.dumps(lead.available_isps),
                    json.dumps(lead.equipment),
                    lead.building_summary,
                    lead.current_it_provider,
                    json.dumps(lead.tech_signals),
                    json.dumps(lead.recent_news),
                    json.dumps(lead.social_links),
                    json.dumps(lead.sources),
                    lead.discovery_date.isoformat(),
                    lead.score, lead.qualification_notes, lead.pipeline_stage,
                    lead_id,
                ),
            )

    def update_pipeline_stage(self, lead_id: int, stage: PipelineStage) -> None:
        if stage not in VALID_PIPELINE_STAGES:
            raise ValueError(f"Invalid pipeline stage: {stage}")
        with self._conn() as conn:
            conn.execute(
                "UPDATE leads SET pipeline_stage=?, updated_at=datetime('now') WHERE id=?",
                (stage, lead_id),
            )

    def update_notes(self, lead_id: int, notes: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE leads SET qualification_notes=?, updated_at=datetime('now') WHERE id=?",
                (notes, lead_id),
            )

    def get_lead(self, lead_id: int) -> EnrichedLead | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        return self._row_to_lead(row) if row else None

    def get_all_leads(
        self,
        stage: PipelineStage | None = None,
        min_score: int = 0,
        source: str | None = None,
        company_type: str | None = None,
        borough: str | None = None,
        neighborhood: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[EnrichedLead]:
        query = "SELECT * FROM leads WHERE score >= ?"
        params: list = [min_score]

        if stage:
            query += " AND pipeline_stage = ?"
            params.append(stage)
        if company_type:
            query += " AND company_type = ?"
            params.append(company_type)
        if source:
            query += " AND sources LIKE ?"
            params.append(f"%{source}%")
        if borough:
            query += " AND borough = ?"
            params.append(borough)
        if neighborhood:
            query += " AND neighborhood = ?"
            params.append(neighborhood)

        query += " ORDER BY score DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_lead(r) for r in rows]

    def get_lead_count(self, stage: PipelineStage | None = None) -> int:
        with self._conn() as conn:
            if stage:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM leads WHERE pipeline_stage=?", (stage,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM leads").fetchone()
        return row["cnt"]

    def get_stage_counts(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT pipeline_stage, COUNT(*) as cnt FROM leads GROUP BY pipeline_stage"
            ).fetchall()
        return {row["pipeline_stage"]: row["cnt"] for row in rows}

    def delete_lead(self, lead_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))

    # ── Pipeline Runs ──────────────────────────────────────────

    def record_run(self, run_id: str, run_timestamp: datetime, stats: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs (run_id, run_timestamp, stats) VALUES (?,?,?)",
                (run_id, run_timestamp.isoformat(), json.dumps(stats)),
            )

    def get_last_run(self) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return {
            "run_id": row["run_id"],
            "run_timestamp": row["run_timestamp"],
            "stats": json.loads(row["stats"]),
        }

    # ── Outreach Messages ──────────────────────────────────────

    def insert_outreach_message(
        self,
        lead_id: int,
        template: str,
        subject: str,
        body: str,
        to_email: str | None,
        to_name: str | None,
        model: str,
        duration_ms: int,
    ) -> int:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO outreach_messages
                   (lead_id, template, subject, body, to_email, to_name,
                    model, duration_ms, generated_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (lead_id, template, subject, body, to_email, to_name,
                 model, duration_ms, now, now, now),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_outreach_message(self, msg_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM outreach_messages WHERE id=?", (msg_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_outreach_messages(
        self,
        status: str | None = None,
        lead_id: int | None = None,
    ) -> list[dict]:
        query = "SELECT * FROM outreach_messages WHERE 1=1"
        params: list = []
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if lead_id is not None:
            query += " AND lead_id = ?"
            params.append(lead_id)
        query += " ORDER BY generated_at DESC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def update_outreach_status(
        self,
        msg_id: int,
        status: str,
        gmail_message_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            if status == "approved":
                conn.execute(
                    """UPDATE outreach_messages
                       SET status=?, approved_at=?, updated_at=?
                       WHERE id=?""",
                    (status, now, now, msg_id),
                )
            elif status == "sent":
                conn.execute(
                    """UPDATE outreach_messages
                       SET status=?, sent_at=?, gmail_message_id=?, updated_at=?
                       WHERE id=?""",
                    (status, now, gmail_message_id, now, msg_id),
                )
            elif status == "failed":
                conn.execute(
                    """UPDATE outreach_messages
                       SET status=?, error_message=?, updated_at=?
                       WHERE id=?""",
                    (status, error_message, now, msg_id),
                )
            else:
                conn.execute(
                    """UPDATE outreach_messages
                       SET status=?, updated_at=?
                       WHERE id=?""",
                    (status, now, msg_id),
                )

    def update_outreach_content(
        self,
        msg_id: int,
        subject: str | None = None,
        body: str | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            if subject is not None and body is not None:
                conn.execute(
                    """UPDATE outreach_messages
                       SET subject=?, body=?, updated_at=? WHERE id=?""",
                    (subject, body, now, msg_id),
                )
            elif subject is not None:
                conn.execute(
                    """UPDATE outreach_messages
                       SET subject=?, updated_at=? WHERE id=?""",
                    (subject, now, msg_id),
                )
            elif body is not None:
                conn.execute(
                    """UPDATE outreach_messages
                       SET body=?, updated_at=? WHERE id=?""",
                    (body, now, msg_id),
                )

    def has_recent_outreach(
        self, lead_id: int, template: str, days: int = 30
    ) -> bool:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM outreach_messages
                   WHERE lead_id=? AND template=?
                     AND status NOT IN ('failed', 'discarded')
                     AND generated_at >= ?""",
                (lead_id, template, cutoff),
            ).fetchone()
        return row["cnt"] > 0

    def get_outreach_history(self, lead_id: int) -> list[dict]:
        return self.list_outreach_messages(lead_id=lead_id)

    # ── Gmail Credentials ──────────────────────────────────────

    def store_gmail_credentials(
        self,
        email_address: str,
        encrypted_refresh_token: str,
        encrypted_access_token: str | None,
        token_expiry: str | None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute("DELETE FROM gmail_credentials")
            conn.execute(
                """INSERT INTO gmail_credentials
                   (id, email_address, encrypted_refresh_token,
                    encrypted_access_token, token_expiry, created_at, updated_at)
                   VALUES (1,?,?,?,?,?,?)""",
                (email_address, encrypted_refresh_token,
                 encrypted_access_token, token_expiry, now, now),
            )

    def get_gmail_credentials(self) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM gmail_credentials WHERE id=1"
            ).fetchone()
        return dict(row) if row else None

    def delete_gmail_credentials(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM gmail_credentials")

    # ── Internal ───────────────────────────────────────────────

    def _find_by_company_and_address(self, company_name: str, address: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM leads WHERE company_name=? AND address=?",
                (company_name, address),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _row_to_lead(row: sqlite3.Row) -> EnrichedLead:
        return EnrichedLead(
            id=row["id"],
            company_name=row["company_name"],
            company_type=row["company_type"],
            contact_name=row["contact_name"],
            contact_title=row["contact_title"],
            email=row["email"],
            phone=row["phone"],
            linkedin_url=row["linkedin_url"],
            website=row["website"],
            address=row["address"],
            building_type=row["building_type"],
            sqft=row["sqft"],
            num_tenants=row["num_tenants"],
            borough=row["borough"],
            neighborhood=row["neighborhood"],
            year_built=row["year_built"],
            floors=row["floors"],
            num_employees=row["num_employees"],
            building_isp=row["building_isp"],
            available_isps=json.loads(row["available_isps"]),
            equipment=json.loads(row["equipment"]),
            building_summary=row["building_summary"],
            current_it_provider=row["current_it_provider"],
            tech_signals=json.loads(row["tech_signals"]),
            recent_news=json.loads(row["recent_news"]),
            social_links=json.loads(row["social_links"]),
            sources=json.loads(row["sources"]),
            discovery_date=date.fromisoformat(row["discovery_date"]),
            score=row["score"],
            qualification_notes=row["qualification_notes"],
            pipeline_stage=row["pipeline_stage"],
        )
