# Gmail Outreach Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Gmail-powered batch email outreach with human approval queue to SalesLeads.

**Architecture:** New outreach system layered on top of existing email drafting. Backend adds outreach DB tables, Gmail OAuth2 service, and batch generation/send endpoints. Frontend adds an Outreach page with lead selection, draft queue, and send controls. Reuses existing `draft_email()` for personalization.

**Tech Stack:** FastAPI, SQLite, google-auth + google-api-python-client, cryptography (Fernet), React + TanStack Query, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-04-14-gmail-outreach-pipeline-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `api/routes/outreach.py` | Outreach endpoints (generate, queue, approve, send, history) |
| `api/routes/auth.py` | Gmail OAuth2 endpoints (initiate, callback, status, disconnect) |
| `api/services/gmail_service.py` | Gmail API wrapper (OAuth token management, send email) |
| `api/services/outreach_service.py` | Batch draft generation, dedup, send orchestration |
| `tests/test_outreach.py` | Tests for outreach service + routes |
| `tests/test_gmail_service.py` | Tests for Gmail service (mocked) |
| `frontend/src/pages/outreach.tsx` | Outreach page (lead selector, queue, send) |
| `frontend/src/hooks/use-outreach.ts` | React Query hooks for outreach API |

### Modified Files
| File | Change |
|------|--------|
| `config/settings.py` | Add Gmail + outreach config fields |
| `core/database.py` | Add `outreach_messages` + `gmail_credentials` tables and query methods |
| `api/main.py` | Register outreach + auth routers |
| `api/schemas.py` | Add outreach Pydantic models |
| `frontend/src/lib/types.ts` | Add outreach TypeScript interfaces |
| `frontend/src/lib/api.ts` | Add outreach + auth API client methods |
| `frontend/src/components/layout/app-sidebar.tsx` | Add Outreach nav item |
| `frontend/src/App.tsx` | Add /outreach route |

---

## Task 1: Database Schema — Outreach Tables

**Files:**
- Modify: `core/database.py` (add tables to `_SCHEMA`, add query methods)
- Test: `tests/test_outreach_db.py`

- [ ] **Step 1: Write failing tests for outreach DB operations**

Create `tests/test_outreach_db.py`:

```python
import pytest
from datetime import datetime
from core.database import Database
from tests.test_database import _make_lead


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def db_with_lead(db):
    """DB with one lead inserted, returns (db, lead_id)."""
    lead = _make_lead(email="john@acme.com")
    lead_id = db.insert_lead(lead)
    return db, lead_id


class TestOutreachInsert:
    def test_insert_outreach_message(self, db_with_lead):
        db, lead_id = db_with_lead
        msg_id = db.insert_outreach_message(
            lead_id=lead_id,
            template="initial_outreach",
            subject="Hello Acme",
            body="We offer IT services...",
            to_email="john@acme.com",
            to_name="John Doe",
            model="llama3",
            duration_ms=1200,
        )
        assert isinstance(msg_id, int)
        assert msg_id > 0

    def test_retrieve_outreach_message(self, db_with_lead):
        db, lead_id = db_with_lead
        msg_id = db.insert_outreach_message(
            lead_id=lead_id,
            template="initial_outreach",
            subject="Hello",
            body="Body text",
            to_email="john@acme.com",
            to_name="John",
            model="template",
            duration_ms=5,
        )
        msg = db.get_outreach_message(msg_id)
        assert msg is not None
        assert msg["lead_id"] == lead_id
        assert msg["status"] == "draft"
        assert msg["subject"] == "Hello"


class TestOutreachQueue:
    def test_list_by_status(self, db_with_lead):
        db, lead_id = db_with_lead
        db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="S1", body="B1", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.insert_outreach_message(
            lead_id=lead_id, template="follow_up",
            subject="S2", body="B2", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        drafts = db.list_outreach_messages(status="draft")
        assert len(drafts) == 2

    def test_list_all(self, db_with_lead):
        db, lead_id = db_with_lead
        db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="S", body="B", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        all_msgs = db.list_outreach_messages()
        assert len(all_msgs) == 1


class TestOutreachStatusUpdate:
    def test_approve_message(self, db_with_lead):
        db, lead_id = db_with_lead
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="S", body="B", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "approved")
        msg = db.get_outreach_message(msg_id)
        assert msg["status"] == "approved"
        assert msg["approved_at"] is not None

    def test_mark_sent(self, db_with_lead):
        db, lead_id = db_with_lead
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="S", body="B", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "approved")
        db.update_outreach_status(msg_id, "sent", gmail_message_id="abc123")
        msg = db.get_outreach_message(msg_id)
        assert msg["status"] == "sent"
        assert msg["sent_at"] is not None
        assert msg["gmail_message_id"] == "abc123"


class TestOutreachDedup:
    def test_recent_outreach_exists(self, db_with_lead):
        db, lead_id = db_with_lead
        db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="S", body="B", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        assert db.has_recent_outreach(lead_id, "initial_outreach", days=30) is True
        assert db.has_recent_outreach(lead_id, "follow_up", days=30) is False

    def test_no_recent_outreach(self, db_with_lead):
        db, lead_id = db_with_lead
        assert db.has_recent_outreach(lead_id, "initial_outreach", days=30) is False


class TestOutreachEdit:
    def test_edit_draft_subject_and_body(self, db_with_lead):
        db, lead_id = db_with_lead
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="Old", body="Old body", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_content(msg_id, subject="New Subject", body="New body")
        msg = db.get_outreach_message(msg_id)
        assert msg["subject"] == "New Subject"
        assert msg["body"] == "New body"


class TestOutreachHistory:
    def test_history_for_lead(self, db_with_lead):
        db, lead_id = db_with_lead
        db.insert_outreach_message(
            lead_id=lead_id, template="initial_outreach",
            subject="S1", body="B1", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.insert_outreach_message(
            lead_id=lead_id, template="follow_up",
            subject="S2", body="B2", to_email="a@b.com", to_name="A",
            model="m", duration_ms=0,
        )
        history = db.get_outreach_history(lead_id)
        assert len(history) == 2


class TestGmailCredentials:
    def test_store_and_retrieve_credentials(self, db):
        db.store_gmail_credentials(
            email_address="me@gmail.com",
            encrypted_refresh_token="enc_refresh",
            encrypted_access_token="enc_access",
            token_expiry="2026-04-15T00:00:00",
        )
        creds = db.get_gmail_credentials()
        assert creds is not None
        assert creds["email_address"] == "me@gmail.com"
        assert creds["encrypted_refresh_token"] == "enc_refresh"

    def test_upsert_overwrites(self, db):
        db.store_gmail_credentials(
            email_address="old@gmail.com",
            encrypted_refresh_token="old",
            encrypted_access_token="old",
            token_expiry="2026-04-15T00:00:00",
        )
        db.store_gmail_credentials(
            email_address="new@gmail.com",
            encrypted_refresh_token="new",
            encrypted_access_token="new",
            token_expiry="2026-04-16T00:00:00",
        )
        creds = db.get_gmail_credentials()
        assert creds["email_address"] == "new@gmail.com"

    def test_delete_credentials(self, db):
        db.store_gmail_credentials(
            email_address="me@gmail.com",
            encrypted_refresh_token="enc",
            encrypted_access_token="enc",
            token_expiry="2026-04-15T00:00:00",
        )
        db.delete_gmail_credentials()
        assert db.get_gmail_credentials() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_outreach_db.py -v`
Expected: All fail with `AttributeError` (methods don't exist yet)

- [ ] **Step 3: Add tables to `_SCHEMA` in `core/database.py`**

After the existing `CREATE INDEX` statements for leads (after line ~63), add:

```sql
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
```

- [ ] **Step 4: Add outreach query methods to `Database` class**

Add these methods to the `Database` class in `core/database.py`:

```python
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
    with self._conn() as conn:
        cur = conn.execute(
            """INSERT INTO outreach_messages
               (lead_id, template, subject, body, to_email, to_name, model, duration_ms, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lead_id, template, subject, body, to_email, to_name, model, duration_ms, datetime.now().isoformat()),
        )
        return cur.lastrowid

def get_outreach_message(self, msg_id: int) -> dict | None:
    with self._conn() as conn:
        row = conn.execute("SELECT * FROM outreach_messages WHERE id = ?", (msg_id,)).fetchone()
        return dict(row) if row else None

def list_outreach_messages(self, status: str | None = None, lead_id: int | None = None) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if lead_id:
        clauses.append("lead_id = ?")
        params.append(lead_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with self._conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM outreach_messages {where} ORDER BY generated_at DESC", params
        ).fetchall()
        return [dict(r) for r in rows]

def update_outreach_status(self, msg_id: int, status: str, gmail_message_id: str | None = None) -> None:
    now = datetime.now().isoformat()
    with self._conn() as conn:
        if status == "approved":
            conn.execute(
                "UPDATE outreach_messages SET status = ?, approved_at = ?, updated_at = ? WHERE id = ?",
                (status, now, now, msg_id),
            )
        elif status == "sent":
            conn.execute(
                "UPDATE outreach_messages SET status = ?, sent_at = ?, gmail_message_id = ?, updated_at = ? WHERE id = ?",
                (status, now, gmail_message_id, now, msg_id),
            )
        elif status == "failed":
            conn.execute(
                "UPDATE outreach_messages SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
                (status, gmail_message_id, now, msg_id),  # reuse param for error_message
            )
        else:
            conn.execute(
                "UPDATE outreach_messages SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, msg_id),
            )

def update_outreach_content(self, msg_id: int, subject: str | None = None, body: str | None = None) -> None:
    updates, params = [], []
    if subject is not None:
        updates.append("subject = ?")
        params.append(subject)
    if body is not None:
        updates.append("body = ?")
        params.append(body)
    if not updates:
        return
    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(msg_id)
    with self._conn() as conn:
        conn.execute(f"UPDATE outreach_messages SET {', '.join(updates)} WHERE id = ?", params)

def has_recent_outreach(self, lead_id: int, template: str, days: int = 30) -> bool:
    with self._conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM outreach_messages
               WHERE lead_id = ? AND template = ? AND status NOT IN ('failed', 'discarded')
               AND generated_at >= datetime('now', ?)""",
            (lead_id, template, f"-{days} days"),
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
               (id, email_address, encrypted_refresh_token, encrypted_access_token, token_expiry, created_at, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, ?)""",
            (email_address, encrypted_refresh_token, encrypted_access_token, token_expiry, now, now),
        )

def get_gmail_credentials(self) -> dict | None:
    with self._conn() as conn:
        row = conn.execute("SELECT * FROM gmail_credentials WHERE id = 1").fetchone()
        return dict(row) if row else None

def delete_gmail_credentials(self) -> None:
    with self._conn() as conn:
        conn.execute("DELETE FROM gmail_credentials")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_outreach_db.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite to check nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: All 165+ tests PASS

- [ ] **Step 7: Commit**

```bash
git add core/database.py tests/test_outreach_db.py
git commit -m "feat: add outreach_messages and gmail_credentials DB tables with query methods"
```

---

## Task 2: Configuration — Gmail Settings

**Files:**
- Modify: `config/settings.py`

- [ ] **Step 1: Add Gmail + outreach fields to Settings dataclass**

In `config/settings.py`, after the LinkedIn section (after `linkedin_password` field), add:

```python
    # Gmail Outreach
    gmail_client_id: str = field(default_factory=lambda: _env("GMAIL_CLIENT_ID"))
    gmail_client_secret: str = field(default_factory=lambda: _env("GMAIL_CLIENT_SECRET"))
    gmail_redirect_uri: str = field(default_factory=lambda: _env("GMAIL_REDIRECT_URI", "http://localhost:8000/api/auth/gmail/callback"))
    encryption_key: str = field(default_factory=lambda: _env("ENCRYPTION_KEY"))
    outreach_send_delay_min: int = field(default_factory=lambda: _env_int("OUTREACH_SEND_DELAY_MIN", 30))
    outreach_send_delay_max: int = field(default_factory=lambda: _env_int("OUTREACH_SEND_DELAY_MAX", 60))
    outreach_dedup_days: int = field(default_factory=lambda: _env_int("OUTREACH_DEDUP_DAYS", 30))
```

- [ ] **Step 2: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat: add Gmail outreach configuration settings"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Modify: `api/schemas.py`

- [ ] **Step 1: Add outreach schemas to `api/schemas.py`**

After `EmailDraftResponse` class, add:

```python
# ── Outreach ──────────────────────────────────────────────

class OutreachGenerateRequest(BaseModel):
    """Batch-generate email drafts for multiple leads."""
    lead_ids: list[int]
    template: str

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if v not in VALID_EMAIL_TEMPLATES:
            raise ValueError(f"Invalid template '{v}'. Must be one of: {', '.join(sorted(VALID_EMAIL_TEMPLATES))}")
        return v


class SkippedLead(BaseModel):
    lead_id: int
    reason: str


class OutreachMessageOut(BaseModel):
    id: int
    lead_id: int
    template: str
    status: str
    subject: str
    body: str
    to_email: str | None
    to_name: str | None
    error_message: str | None
    model: str
    duration_ms: int
    generated_at: str
    approved_at: str | None
    sent_at: str | None
    gmail_message_id: str | None


class OutreachGenerateResponse(BaseModel):
    generated: int
    skipped: list[SkippedLead]
    messages: list[OutreachMessageOut]


class OutreachQueueResponse(BaseModel):
    items: list[OutreachMessageOut]
    total: int


class OutreachApproveRequest(BaseModel):
    ids: list[int]


class OutreachApproveResponse(BaseModel):
    approved: int


class OutreachSendResponse(BaseModel):
    job_id: str
    total: int


class SendStatusResponse(BaseModel):
    status: str  # running | done
    sent: int
    failed: int
    total: int
    errors: list[dict]


class OutreachEditRequest(BaseModel):
    subject: str | None = None
    body: str | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("approved", "discarded"):
            raise ValueError("Status must be 'approved' or 'discarded'")
        return v


class GmailStatusResponse(BaseModel):
    connected: bool
    email: str | None = None
```

- [ ] **Step 2: Run existing tests to check nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add api/schemas.py
git commit -m "feat: add outreach Pydantic schemas"
```

---

## Task 4: Gmail Service

**Files:**
- Create: `api/services/gmail_service.py`
- Test: `tests/test_gmail_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_gmail_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from api.services.gmail_service import GmailService


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        svc = GmailService(encryption_key=GmailService.generate_key())
        original = "my_secret_token"
        encrypted = svc.encrypt(original)
        assert encrypted != original
        assert svc.decrypt(encrypted) == original

    def test_generate_key_is_valid(self):
        key = GmailService.generate_key()
        assert isinstance(key, str)
        svc = GmailService(encryption_key=key)
        assert svc.encrypt("test") != "test"


class TestBuildMimeMessage:
    def test_builds_valid_mime(self):
        svc = GmailService(encryption_key=GmailService.generate_key())
        raw = svc.build_mime_message(
            from_email="sender@test.com",
            to_email="recipient@test.com",
            subject="Test Subject",
            body="Hello, this is a test.",
        )
        assert isinstance(raw, str)
        assert len(raw) > 0

    def test_mime_contains_headers(self):
        svc = GmailService(encryption_key=GmailService.generate_key())
        raw = svc.build_mime_message(
            from_email="sender@test.com",
            to_email="recipient@test.com",
            subject="Test",
            body="Body",
        )
        # raw is base64-encoded, decode it to check
        import base64
        decoded = base64.urlsafe_b64decode(raw + "==").decode("utf-8", errors="replace")
        assert "sender@test.com" in decoded
        assert "recipient@test.com" in decoded


class TestOAuthUrl:
    def test_get_auth_url(self):
        svc = GmailService(
            encryption_key=GmailService.generate_key(),
            client_id="test_client_id",
            client_secret="test_secret",
            redirect_uri="http://localhost:8000/api/auth/gmail/callback",
        )
        url = svc.get_auth_url()
        assert "accounts.google.com" in url
        assert "test_client_id" in url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_gmail_service.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Create `api/services/gmail_service.py`**

```python
"""Gmail API integration — OAuth2 authentication and email sending."""

import base64
import logging
from email.mime.text import MIMEText
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet

log = logging.getLogger(__name__)

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send", "openid", "email"]


class GmailService:
    """Handles Gmail OAuth2 and email sending."""

    def __init__(
        self,
        encryption_key: str,
        client_id: str = "",
        client_secret: str = "",
        redirect_uri: str = "",
    ):
        self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def get_auth_url(self) -> str:
        """Build the Google OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GMAIL_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens. Returns dict with access_token, refresh_token, etc."""
        resp = requests.post(
            GMAIL_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def refresh_access_token(self, encrypted_refresh_token: str) -> dict:
        """Refresh the access token using a stored refresh token."""
        import requests

        refresh_token = self.decrypt(encrypted_refresh_token)
        resp = requests.post(
            GMAIL_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def get_user_email(self, access_token: str) -> str:
        """Get the authenticated user's email from Google userinfo."""
        resp = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("email", "")

    def build_mime_message(self, from_email: str, to_email: str, subject: str, body: str) -> str:
        """Build a base64url-encoded MIME message for Gmail API."""
        msg = MIMEText(body)
        msg["to"] = to_email
        msg["from"] = from_email
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return raw

    def send_email(self, access_token: str, from_email: str, to_email: str, subject: str, body: str) -> str:
        """Send an email via Gmail API. Returns the Gmail message ID."""
        raw = self.build_mime_message(from_email, to_email, subject, body)
        resp = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": raw},
        )
        resp.raise_for_status()
        return resp.json().get("id", "")
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_gmail_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/gmail_service.py tests/test_gmail_service.py
git commit -m "feat: add Gmail service with OAuth2, encryption, and email sending"
```

---

## Task 5: Outreach Service — Batch Generation + Send Orchestration

**Files:**
- Create: `api/services/outreach_service.py`
- Test: `tests/test_outreach_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_outreach_service.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from core.database import Database
from tests.test_database import _make_lead
from api.services.outreach_service import generate_batch, SendJob


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def db_with_leads(db):
    leads = []
    for i, name in enumerate(["Acme Corp", "BuildCo", "NoEmail LLC"]):
        lead = _make_lead(
            company_name=name,
            contact_name=f"Person {i}",
            email=f"person{i}@{name.lower().replace(' ', '')}.com" if name != "NoEmail LLC" else None,
        )
        lead_id = db.insert_lead(lead)
        leads.append(lead_id)
    return db, leads


class TestGenerateBatch:
    def test_generates_drafts_for_leads_with_email(self, db_with_leads):
        db, lead_ids = db_with_leads
        result = generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        # 2 with email, 1 without
        assert result["generated"] == 2
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "no email address"

    def test_skips_recently_contacted(self, db_with_leads):
        db, lead_ids = db_with_leads
        # Generate once
        generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        # Generate again — should skip the 2 already contacted
        result = generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        assert result["generated"] == 0
        assert len(result["skipped"]) == 3  # 1 no email + 2 already contacted

    def test_different_template_not_deduped(self, db_with_leads):
        db, lead_ids = db_with_leads
        generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        result = generate_batch(db=db, lead_ids=lead_ids, template="follow_up", dedup_days=30)
        assert result["generated"] == 2  # follow_up is different template


class TestSendJob:
    def test_send_job_tracks_progress(self):
        job = SendJob(job_id="test-123", total=3)
        assert job.status == "running"
        assert job.sent == 0
        job.record_sent()
        assert job.sent == 1
        job.record_failure(msg_id=1, error="timeout")
        assert job.failed == 1
        assert len(job.errors) == 1
        job.record_sent()
        job.complete()
        assert job.status == "done"

    def test_send_job_to_dict(self):
        job = SendJob(job_id="test-456", total=2)
        d = job.to_dict()
        assert d["job_id"] == "test-456"
        assert d["status"] == "running"
        assert d["total"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_outreach_service.py -v`
Expected: FAIL (module doesn't exist)

- [ ] **Step 3: Create `api/services/outreach_service.py`**

```python
"""Outreach batch generation and send orchestration."""

import logging
import time
import uuid
from dataclasses import dataclass, field

from core.database import Database
from core.llm_client import LLMClient, LLMError
from api.services.email_service import draft_email
from api.deps import get_settings

log = logging.getLogger(__name__)


def generate_batch(
    db: Database,
    lead_ids: list[int],
    template: str,
    dedup_days: int = 30,
) -> dict:
    """Generate email drafts for a batch of leads. Returns summary with generated/skipped counts."""
    settings = get_settings()
    llm = LLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)

    generated = 0
    skipped = []
    messages = []

    for lead_id in lead_ids:
        lead = db.get_lead(lead_id)
        if lead is None:
            skipped.append({"lead_id": lead_id, "reason": "lead not found"})
            continue

        if not lead.email:
            skipped.append({"lead_id": lead_id, "reason": "no email address"})
            continue

        if db.has_recent_outreach(lead_id, template, days=dedup_days):
            skipped.append({"lead_id": lead_id, "reason": f"contacted within last {dedup_days} days"})
            continue

        # Generate the draft
        try:
            result = draft_email(lead=lead, template=template, llm=llm)
        except (LLMError, Exception):
            # Fallback to simple template
            result = _simple_fallback(lead, template)

        msg_id = db.insert_outreach_message(
            lead_id=lead_id,
            template=template,
            subject=result["subject"],
            body=result["body"],
            to_email=lead.email,
            to_name=lead.contact_name or "",
            model=result.get("model", "template"),
            duration_ms=int(result.get("duration_ms", 0)),
        )

        msg = db.get_outreach_message(msg_id)
        messages.append(msg)
        generated += 1

    return {"generated": generated, "skipped": skipped, "messages": messages}


def _simple_fallback(lead, template: str) -> dict:
    """Minimal template fallback when LLM is unavailable."""
    name = (lead.contact_name or "").split()[0] if lead.contact_name else "there"
    company = lead.company_name or "your company"

    if template == "follow_up":
        subject = f"Following up — IT services for {company}"
        body = f"Hi {name},\n\nI wanted to follow up on my previous message about managed IT services for {company}.\n\nWould you be open to a brief call this week?\n\nBest regards"
    elif template == "meeting_request":
        subject = f"Meeting request — {company} IT infrastructure"
        body = f"Hi {name},\n\nI'd love to schedule a 15-minute call to discuss how we can help {company} with IT infrastructure management.\n\nAre you available this week?\n\nBest regards"
    else:
        subject = f"Introduction — Managed IT for {company}"
        body = f"Hi {name},\n\nI'm reaching out because we specialize in managed IT services for commercial real estate properties like {company}.\n\nWould you be open to a brief conversation about your IT needs?\n\nBest regards"

    return {"subject": subject, "body": body, "model": "template", "duration_ms": 0}


# ── Send Job Tracking ──────────────────────────────────────

@dataclass
class SendJob:
    job_id: str
    total: int
    status: str = "running"
    sent: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)

    def record_sent(self):
        self.sent += 1

    def record_failure(self, msg_id: int, error: str):
        self.failed += 1
        self.errors.append({"message_id": msg_id, "error": error})

    def complete(self):
        self.status = "done"

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "sent": self.sent,
            "failed": self.failed,
            "total": self.total,
            "errors": self.errors,
        }


# In-memory job store (single-process deployment)
_jobs: dict[str, SendJob] = {}


def create_send_job(total: int) -> SendJob:
    job_id = str(uuid.uuid4())[:8]
    job = SendJob(job_id=job_id, total=total)
    _jobs[job_id] = job
    return job


def get_send_job(job_id: str) -> SendJob | None:
    return _jobs.get(job_id)
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_outreach_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/outreach_service.py tests/test_outreach_service.py
git commit -m "feat: add outreach service with batch generation, dedup, and send job tracking"
```

---

## Task 6: Outreach API Routes

**Files:**
- Create: `api/routes/outreach.py`
- Create: `api/routes/auth.py`
- Modify: `api/main.py`

- [ ] **Step 1: Create `api/routes/outreach.py`**

```python
"""Outreach endpoints — batch draft generation, queue management, sending."""

import logging
import random
import time
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import (
    OutreachGenerateRequest,
    OutreachGenerateResponse,
    OutreachQueueResponse,
    OutreachMessageOut,
    OutreachApproveRequest,
    OutreachApproveResponse,
    OutreachEditRequest,
    OutreachSendResponse,
    SendStatusResponse,
)
from api.services.outreach_service import generate_batch, create_send_job, get_send_job, SendJob
from api.services.gmail_service import GmailService
from api.deps import get_db, get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.post("/generate", response_model=OutreachGenerateResponse)
def batch_generate(body: OutreachGenerateRequest):
    db = get_db()
    settings = get_settings()
    result = generate_batch(
        db=db,
        lead_ids=body.lead_ids,
        template=body.template,
        dedup_days=settings.outreach_dedup_days,
    )
    return OutreachGenerateResponse(
        generated=result["generated"],
        skipped=result["skipped"],
        messages=[OutreachMessageOut(**m) for m in result["messages"]],
    )


@router.get("/queue", response_model=OutreachQueueResponse)
def get_queue(status: str | None = None, page: int = 1, page_size: int = 50):
    db = get_db()
    messages = db.list_outreach_messages(status=status)
    total = len(messages)
    start = (page - 1) * page_size
    page_items = messages[start : start + page_size]
    return OutreachQueueResponse(
        items=[OutreachMessageOut(**m) for m in page_items],
        total=total,
    )


@router.patch("/queue/{msg_id}", response_model=OutreachMessageOut)
def edit_message(msg_id: int, body: OutreachEditRequest):
    db = get_db()
    msg = db.get_outreach_message(msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if body.subject is not None or body.body is not None:
        db.update_outreach_content(msg_id, subject=body.subject, body=body.body)
    if body.status is not None:
        db.update_outreach_status(msg_id, body.status)

    return OutreachMessageOut(**db.get_outreach_message(msg_id))


@router.post("/approve", response_model=OutreachApproveResponse)
def approve_messages(body: OutreachApproveRequest):
    db = get_db()
    count = 0
    for msg_id in body.ids:
        msg = db.get_outreach_message(msg_id)
        if msg and msg["status"] == "draft":
            db.update_outreach_status(msg_id, "approved")
            count += 1
    return OutreachApproveResponse(approved=count)


@router.post("/send", response_model=OutreachSendResponse)
def send_approved(background_tasks: BackgroundTasks):
    db = get_db()
    settings = get_settings()
    creds = db.get_gmail_credentials()
    if not creds:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    approved = db.list_outreach_messages(status="approved")
    if not approved:
        raise HTTPException(status_code=400, detail="No approved messages to send")

    if len(approved) > 20:
        approved = approved[:20]

    job = create_send_job(total=len(approved))
    background_tasks.add_task(_send_batch, job, approved, settings, db)

    return OutreachSendResponse(job_id=job.job_id, total=job.total)


def _send_batch(job: SendJob, messages: list[dict], settings, db: Database):
    """Background task: send emails sequentially with delays."""
    gmail = GmailService(
        encryption_key=settings.encryption_key,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        redirect_uri=settings.gmail_redirect_uri,
    )

    creds = db.get_gmail_credentials()
    if not creds:
        job.complete()
        return

    # Refresh access token
    try:
        token_data = gmail.refresh_access_token(creds["encrypted_refresh_token"])
        access_token = token_data["access_token"]
        # Update stored access token
        db.store_gmail_credentials(
            email_address=creds["email_address"],
            encrypted_refresh_token=creds["encrypted_refresh_token"],
            encrypted_access_token=gmail.encrypt(access_token),
            token_expiry=datetime.now().isoformat(),
        )
    except Exception as e:
        log.error(f"Failed to refresh Gmail token: {e}")
        for msg in messages:
            db.update_outreach_status(msg["id"], "failed", gmail_message_id=str(e))
            job.record_failure(msg["id"], str(e))
        job.complete()
        return

    from_email = creds["email_address"]

    for i, msg in enumerate(messages):
        db.update_outreach_status(msg["id"], "sending")
        try:
            gmail_msg_id = gmail.send_email(
                access_token=access_token,
                from_email=from_email,
                to_email=msg["to_email"],
                subject=msg["subject"],
                body=msg["body"],
            )
            db.update_outreach_status(msg["id"], "sent", gmail_message_id=gmail_msg_id)
            job.record_sent()
            log.info(f"Sent email {i+1}/{len(messages)} to {msg['to_email']}")
        except Exception as e:
            log.error(f"Failed to send to {msg['to_email']}: {e}")
            db.update_outreach_status(msg["id"], "failed", gmail_message_id=str(e))
            job.record_failure(msg["id"], str(e))

        # Delay between sends (skip delay after last email)
        if i < len(messages) - 1:
            delay = random.randint(settings.outreach_send_delay_min, settings.outreach_send_delay_max)
            time.sleep(delay)

    job.complete()


@router.get("/send-status/{job_id}", response_model=SendStatusResponse)
def send_status(job_id: str):
    job = get_send_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return SendStatusResponse(**job.to_dict())


@router.get("/history/{lead_id}")
def lead_history(lead_id: int):
    db = get_db()
    history = db.get_outreach_history(lead_id)
    return [OutreachMessageOut(**m) for m in history]
```

- [ ] **Step 2: Create `api/routes/auth.py`**

```python
"""Gmail OAuth2 authentication endpoints."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from api.schemas import GmailStatusResponse
from api.services.gmail_service import GmailService
from api.deps import get_db, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_gmail_service() -> GmailService:
    settings = get_settings()
    return GmailService(
        encryption_key=settings.encryption_key,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        redirect_uri=settings.gmail_redirect_uri,
    )


@router.get("/gmail")
def gmail_auth():
    """Return the Google OAuth2 authorization URL."""
    svc = _get_gmail_service()
    if not svc.client_id:
        raise HTTPException(status_code=500, detail="Gmail client ID not configured")
    return {"auth_url": svc.get_auth_url()}


@router.get("/gmail/callback", response_class=HTMLResponse)
def gmail_callback(code: str):
    """Handle OAuth2 callback from Google. Stores tokens and closes popup."""
    svc = _get_gmail_service()
    db = get_db()

    try:
        token_data = svc.exchange_code(code)
    except Exception as e:
        return HTMLResponse(f"<html><body><h2>Authentication failed</h2><p>{e}</p></body></html>", status_code=400)

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")

    # Get user email
    try:
        email = svc.get_user_email(access_token)
    except Exception:
        email = "unknown"

    # Store encrypted credentials
    db.store_gmail_credentials(
        email_address=email,
        encrypted_refresh_token=svc.encrypt(refresh_token),
        encrypted_access_token=svc.encrypt(access_token),
        token_expiry=token_data.get("expires_in", ""),
    )

    # Return HTML that notifies the opener and closes the popup
    return HTMLResponse("""
    <html><body>
    <h2>Gmail connected successfully!</h2>
    <p>You can close this window.</p>
    <script>
        if (window.opener) {
            window.opener.postMessage({ gmail: "connected" }, "*");
        }
        setTimeout(() => window.close(), 1500);
    </script>
    </body></html>
    """)


@router.get("/gmail/status", response_model=GmailStatusResponse)
def gmail_status():
    db = get_db()
    creds = db.get_gmail_credentials()
    if not creds:
        return GmailStatusResponse(connected=False)
    return GmailStatusResponse(connected=True, email=creds["email_address"])


@router.delete("/gmail")
def gmail_disconnect():
    db = get_db()
    db.delete_gmail_credentials()
    return {"disconnected": True}
```

- [ ] **Step 3: Register routers in `api/main.py`**

Add to imports:
```python
from api.routes import leads, pipeline, email, export, agents, outreach, auth
```

Add after `app.include_router(agents.router)`:
```python
    app.include_router(outreach.router)
    app.include_router(auth.router)
```

- [ ] **Step 4: Add startup recovery for stuck "sending" messages**

In `api/main.py`, inside `create_app()`, after router registration:

```python
    @app.on_event("startup")
    def reset_stuck_messages():
        """Reset any messages stuck in 'sending' status back to 'approved'."""
        try:
            db = get_db()
            stuck = db.list_outreach_messages(status="sending")
            for msg in stuck:
                db.update_outreach_status(msg["id"], "approved")
            if stuck:
                log.info(f"Reset {len(stuck)} stuck 'sending' messages to 'approved'")
        except Exception:
            pass
```

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add api/routes/outreach.py api/routes/auth.py api/main.py
git commit -m "feat: add outreach and auth API routes with background send job"
```

---

## Task 7: Python Dependencies

**Files:**
- Modify: `requirements.txt` (if exists) and `requirements.prod.txt`

- [ ] **Step 1: Add new dependencies**

Add to `requirements.prod.txt` (and `requirements.txt` if it exists):
```
cryptography
```

Note: `requests` is already in the requirements. The Gmail integration uses direct REST calls via `requests` rather than the heavier `google-auth`/`google-api-python-client` libraries.

- [ ] **Step 2: Install locally**

Run: `pip install cryptography`

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add requirements*.txt
git commit -m "feat: add Gmail and cryptography dependencies"
```

---

## Task 8: Frontend Types + API Client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add outreach types to `frontend/src/lib/types.ts`**

After `EmailDraftResponse` interface, add:

```typescript
// ── Outreach ──────────────────────────────────────────────

export interface OutreachGenerateRequest {
  lead_ids: number[];
  template: "initial_outreach" | "follow_up" | "meeting_request";
}

export interface SkippedLead {
  lead_id: number;
  reason: string;
}

export interface OutreachMessage {
  id: number;
  lead_id: number;
  template: string;
  status: "draft" | "approved" | "sending" | "sent" | "failed" | "discarded";
  subject: string;
  body: string;
  to_email: string | null;
  to_name: string | null;
  error_message: string | null;
  model: string;
  duration_ms: number;
  generated_at: string;
  approved_at: string | null;
  sent_at: string | null;
  gmail_message_id: string | null;
}

export interface OutreachGenerateResponse {
  generated: number;
  skipped: SkippedLead[];
  messages: OutreachMessage[];
}

export interface OutreachQueueResponse {
  items: OutreachMessage[];
  total: number;
}

export interface OutreachSendResponse {
  job_id: string;
  total: number;
}

export interface SendStatusResponse {
  status: "running" | "done";
  sent: number;
  failed: number;
  total: number;
  errors: Array<{ message_id: number; error: string }>;
}

export interface GmailStatusResponse {
  connected: boolean;
  email: string | null;
}
```

- [ ] **Step 2: Add outreach API methods to `frontend/src/lib/api.ts`**

Add inside the `api` object:

```typescript
  outreach: {
    generate: (req: OutreachGenerateRequest) =>
      fetchJSON<OutreachGenerateResponse>(`${BASE}/outreach/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      }),
    queue: (params?: Record<string, string>) => {
      const qs = params ? `?${new URLSearchParams(params)}` : "";
      return fetchJSON<OutreachQueueResponse>(`${BASE}/outreach/queue${qs}`);
    },
    editMessage: (id: number, data: { subject?: string; body?: string; status?: string }) =>
      fetchJSON<OutreachMessage>(`${BASE}/outreach/queue/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    approve: (ids: number[]) =>
      fetchJSON<{ approved: number }>(`${BASE}/outreach/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      }),
    send: () =>
      fetchJSON<OutreachSendResponse>(`${BASE}/outreach/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    sendStatus: (jobId: string) =>
      fetchJSON<SendStatusResponse>(`${BASE}/outreach/send-status/${jobId}`),
    history: (leadId: number) =>
      fetchJSON<OutreachMessage[]>(`${BASE}/outreach/history/${leadId}`),
  },
  auth: {
    gmailStatus: () => fetchJSON<GmailStatusResponse>(`${BASE}/auth/gmail/status`),
    gmailAuthUrl: () => fetchJSON<{ auth_url: string }>(`${BASE}/auth/gmail`),
    gmailDisconnect: () => fetch(`${BASE}/auth/gmail`, { method: "DELETE" }),
  },
```

Add the necessary type imports at the top of the file.

- [ ] **Step 3: Build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat: add outreach TypeScript types and API client methods"
```

---

## Task 9: Frontend Hooks

**Files:**
- Create: `frontend/src/hooks/use-outreach.ts`

- [ ] **Step 1: Create `frontend/src/hooks/use-outreach.ts`**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OutreachGenerateRequest } from "@/lib/types";
import { toast } from "sonner";

export function useOutreachQueue(status?: string) {
  const params = status ? { status } : undefined;
  return useQuery({
    queryKey: ["outreach", "queue", status],
    queryFn: () => api.outreach.queue(params),
  });
}

export function useGmailStatus() {
  return useQuery({
    queryKey: ["gmail", "status"],
    queryFn: () => api.auth.gmailStatus(),
  });
}

export function useGenerateOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: OutreachGenerateRequest) => api.outreach.generate(req),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
      toast.success(`Generated ${data.generated} drafts`);
      if (data.skipped.length > 0) {
        toast.info(`${data.skipped.length} leads skipped`);
      }
    },
    onError: (err) => {
      toast.error(`Generation failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    },
  });
}

export function useApproveOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: number[]) => api.outreach.approve(ids),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
      toast.success(`${data.approved} messages approved`);
    },
  });
}

export function useEditOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; subject?: string; body?: string; status?: string }) =>
      api.outreach.editMessage(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
    },
  });
}

export function useSendOutreach() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.outreach.send(),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["outreach"] });
      toast.success(`Sending ${data.total} emails...`);
    },
    onError: (err) => {
      toast.error(`Send failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    },
  });
}

export function useSendStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["outreach", "send-status", jobId],
    queryFn: () => api.outreach.sendStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === "done" ? false : 2000;
    },
  });
}

export function useOutreachHistory(leadId: number) {
  return useQuery({
    queryKey: ["outreach", "history", leadId],
    queryFn: () => api.outreach.history(leadId),
    enabled: !!leadId,
  });
}
```

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-outreach.ts
git commit -m "feat: add outreach React Query hooks"
```

---

## Task 10: Outreach Page

**Files:**
- Create: `frontend/src/pages/outreach.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Modify: `frontend/src/components/layout/app-sidebar.tsx` (add nav item)

- [ ] **Step 1: Create `frontend/src/pages/outreach.tsx`**

Build the page with three sections:
1. **Lead selector** — multi-select leads with template dropdown + "Generate Drafts" button
2. **Draft queue** — card list with status tabs, inline edit, approve/discard per card, bulk approve
3. **Gmail connection + send** — connect button, status indicator, "Send Approved" button with progress

Key components to use: `Card`, `CardContent`, `CardHeader`, `Badge`, `Button`, `Select`, `Textarea`, `Input`, `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`, `Skeleton`, `Checkbox` (from `@/components/ui/`).

Use hooks from `use-outreach.ts` and `use-leads.ts`.

The page should be ~300-400 lines. Use the existing `email.tsx` page as a pattern reference for state management and mutation patterns.

**Gmail connect flow:**
```typescript
const connectGmail = async () => {
  const { auth_url } = await api.auth.gmailAuthUrl();
  const popup = window.open(auth_url, "gmail-auth", "width=500,height=600");
  // Listen for postMessage from callback
  const handler = (event: MessageEvent) => {
    if (event.data?.gmail === "connected") {
      window.removeEventListener("message", handler);
      // Refetch gmail status
      queryClient.invalidateQueries({ queryKey: ["gmail"] });
    }
  };
  window.addEventListener("message", handler);
};
```

**Send progress polling:**
```typescript
const [jobId, setJobId] = useState<string | null>(null);
const { data: sendStatus } = useSendStatus(jobId);
// Show progress bar when sendStatus exists and status === "running"
```

- [ ] **Step 2: Add route to `App.tsx`**

Add import:
```typescript
import OutreachPage from "@/pages/outreach";
```

Add route inside `<Routes>`:
```tsx
<Route path="/outreach" element={<OutreachPage />} />
```

- [ ] **Step 3: Add nav item to `app-sidebar.tsx`**

Add import:
```typescript
import { Send } from "lucide-react";
```

Add to `navItems` array after Email Drafter:
```typescript
{ title: "Outreach", icon: Send, to: "/outreach" },
```

- [ ] **Step 4: Build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/outreach.tsx frontend/src/App.tsx frontend/src/components/layout/app-sidebar.tsx
git commit -m "feat: add Outreach page with lead selector, draft queue, and Gmail send"
```

---

## Task 11: Lead Detail — Outreach History Tab

**Files:**
- Modify: `frontend/src/pages/lead-detail.tsx`

- [ ] **Step 1: Add outreach history tab to lead detail page**

Import `useOutreachHistory` from `@/hooks/use-outreach`.

Add a new tab "Outreach" to the existing tabbed layout. The tab shows a timeline/list of all outreach messages for this lead with: date, template name, status badge, subject line.

Use `Badge` component with color variants per status:
- `draft` → default/gray
- `approved` → blue
- `sent` → green
- `failed` → destructive/red
- `discarded` → muted

- [ ] **Step 2: Build to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/lead-detail.tsx
git commit -m "feat: add outreach history tab to lead detail page"
```

---

## Task 12: Final Integration Test + Cleanup

- [ ] **Step 1: Run full Python test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Manual smoke test**

Start backend: `uvicorn api.main:app --reload --port 8000`
Start frontend: `cd frontend && npm run dev`

Verify:
1. Navigate to `/outreach` — page loads
2. Sidebar shows "Outreach" link
3. Gmail status shows "Not connected" (expected without env vars)
4. Select leads and click Generate Drafts — drafts appear in queue
5. Approve a draft — status changes
6. Lead detail page shows Outreach tab

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete Gmail outreach pipeline — batch drafts, approval queue, send"
```
