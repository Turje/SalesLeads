# Gmail-Powered Email Outreach Pipeline

## Purpose

Add automated email outreach to SalesLeads: batch-generate personalized drafts, human-review queue, and Gmail API sending. Targets under 20 emails/day to NYC commercial real estate contacts.

## Workflow

1. User selects leads (by filter or manual pick) and clicks "Generate Drafts"
2. App generates personalized email for each lead using existing LLM templates (with hardcoded fallback)
3. Drafts appear in a review queue — user can edit subject/body for each
4. User approves individually or in bulk
5. "Send Approved" kicks off a background job that sends via Gmail API, spaced 30-60s apart
6. Sent emails logged against each lead with timestamp
7. User polls progress via status endpoint until batch completes

## Architecture

### Backend

**New files:**

- `api/routes/outreach.py` — endpoints for the outreach workflow
- `api/routes/auth.py` — Gmail OAuth2 endpoints
- `api/services/gmail_service.py` — Gmail API OAuth2 + send
- `api/services/outreach_service.py` — batch generation + send orchestration
- DB tables added to `core/database.py` `_SCHEMA` string

**Reuse:** Batch draft generation calls the existing `draft_email()` from `api/services/email_service.py` in a loop. No reimplementation.

**The existing `/email` page and `POST /api/email/draft` endpoint remain unchanged** — they serve as a quick single-lead drafting tool. The new `/outreach` page is for batch operations with sending. The sidebar will show both: "Email Drafter" (quick single draft) and "Outreach" (batch + send).

### Endpoints

#### Outreach

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/api/outreach/generate` | `{ lead_ids: int[], template: string }` | `{ generated: int, skipped: SkippedLead[], messages: OutreachMessage[] }` |
| GET | `/api/outreach/queue?status=&page=&page_size=` | query params | `{ items: OutreachMessage[], total: int }` |
| PATCH | `/api/outreach/queue/{id}` | `{ subject?: string, body?: string, status?: "approved" \| "discarded" }` | `OutreachMessage` |
| POST | `/api/outreach/approve` | `{ ids: int[] }` | `{ approved: int }` |
| POST | `/api/outreach/send` | `{}` | `{ job_id: string, total: int }` |
| GET | `/api/outreach/send-status/{job_id}` | — | `{ status: "running" \| "done", sent: int, failed: int, total: int, errors: SendError[] }` |
| GET | `/api/outreach/history/{lead_id}` | — | `OutreachMessage[]` |

**`SkippedLead`**: `{ lead_id: int, reason: string }` — e.g., "no email address", "contacted 12 days ago"

**`OutreachMessage`**: mirrors the DB row (see schema below)

**`SendError`**: `{ message_id: int, lead_id: int, error: string }`

#### Auth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/gmail` | Returns `{ auth_url: string }` — frontend opens this in a popup/new tab |
| GET | `/api/auth/gmail/callback` | Google redirects here with `code`. Exchanges for tokens, stores encrypted, returns HTML that calls `window.opener.postMessage({ gmail: "connected" })` then closes itself. |
| GET | `/api/auth/gmail/status` | Returns `{ connected: bool, email: string \| null }` |
| DELETE | `/api/auth/gmail` | Disconnect — delete stored credentials |

### Database Schema

Added to `core/database.py` `_SCHEMA` string (uses `CREATE TABLE IF NOT EXISTS` like existing tables):

```sql
CREATE TABLE IF NOT EXISTS outreach_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    template TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    to_email TEXT,
    to_name TEXT,
    error_message TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at TEXT,
    sent_at TEXT,
    gmail_message_id TEXT
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

**Notes:**
- `gmail_credentials` uses `CHECK (id = 1)` to enforce single-row (one Gmail account).
- `lead_id` is not a SQL-level foreign key since the existing schema doesn't enforce them. Validated at application level before insert.
- `outreach_messages.status` values: `draft`, `approved`, `discarded`, `sending`, `sent`, `failed`.

### Gmail Integration

**Authentication:** OAuth2 with scopes `gmail.send` + `openid email` (the `email` scope lets us capture the user's email address during the OAuth flow from the ID token). User clicks "Connect Gmail", frontend opens the auth URL in a popup. Google redirects to the callback endpoint which stores tokens and posts a message back to the opener window.

**Token storage:** Refresh token encrypted with Fernet (key from `ENCRYPTION_KEY` env var). Access token also stored encrypted with expiry. Auto-refreshed on each send batch.

**Sending flow:**
1. `POST /api/outreach/send` starts a `BackgroundTasks` job (FastAPI built-in) and returns a `job_id` immediately
2. Background job iterates approved messages sequentially
3. For each: build plaintext MIME message (from, to, subject, body), call Gmail API `users.messages.send`
4. Store returned `gmail_message_id`, update status to `sent`
5. On failure: update status to `failed` with `error_message`, continue with remaining
6. Wait random 30-60s between sends
7. Job status tracked in-memory dict keyed by `job_id` (sufficient for single-process deployment)

**Startup recovery:** On app startup, reset any messages stuck in `sending` status back to `approved` so they can be retried.

**MIME format:** Plaintext body (matching existing template output). Subject set via MIME header. No HTML conversion needed.

**Rate limiting:** Max 20 sends per batch invocation. Sequential with random 30-60s delays.

### Deduplication

Before generating a draft for a lead:
- Skip if lead has no `email` field (report as skipped with reason "no email address")
- Skip if an outreach message with status in (`draft`, `approved`, `sending`, `sent`) exists for that `(lead_id, template)` pair within the last `outreach_dedup_days` (default 30)
- This allows sending a `follow_up` to a lead that already received an `initial_outreach`

### Frontend

**New page: `/outreach`** — added to sidebar as "Outreach" (below existing "Email Drafter")

**Layout — three sections:**

1. **Lead Selector** (top)
   - Filter by borough, stage, or select individual leads via checkboxes
   - Template dropdown (initial_outreach, follow_up, meeting_request)
   - "Generate Drafts" button with count badge
   - Shows skipped leads summary after generation (e.g., "3 skipped: no email")

2. **Draft Queue** (middle, main area)
   - Card list of generated drafts showing: lead name, company, subject preview, status badge
   - Click card to expand: editable subject + body fields
   - Per-card actions: Approve, Discard
   - Bulk actions toolbar: "Approve All", "Discard All"
   - Filter tabs: All / Drafts / Approved / Sent / Failed

3. **Gmail Connection + Send** (top-right area)
   - "Connect Gmail" button (if not connected) — opens OAuth popup
   - Connected status: green dot + email address
   - "Send Approved (N)" button (disabled if nothing approved or Gmail not connected)
   - Progress bar during send (polls `/send-status/{job_id}`)

**Lead detail page addition:**
- New "Outreach" tab showing email history for that lead (date, template, status, subject)

### Dependencies

**Python packages (add to both `requirements.txt` and `requirements.prod.txt`):**
- `cryptography` — Fernet encryption for stored tokens

Note: `requests` (already installed) is used for Gmail API calls directly instead of heavier Google client libraries.

**Environment variables:**
- `GMAIL_CLIENT_ID` — from Google Cloud Console (OAuth2 credentials)
- `GMAIL_CLIENT_SECRET` — from Google Cloud Console
- `GMAIL_REDIRECT_URI` — e.g., `http://localhost:8000/api/auth/gmail/callback` (or production URL)
- `ENCRYPTION_KEY` — Fernet key, generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### Configuration

Add to `config/settings.py` following the existing `field(default_factory=lambda: _env(...))` pattern:

```python
gmail_client_id: str = field(default_factory=lambda: _env("GMAIL_CLIENT_ID"))
gmail_client_secret: str = field(default_factory=lambda: _env("GMAIL_CLIENT_SECRET"))
gmail_redirect_uri: str = field(default_factory=lambda: _env("GMAIL_REDIRECT_URI", "http://localhost:8000/api/auth/gmail/callback"))
encryption_key: str = field(default_factory=lambda: _env("ENCRYPTION_KEY"))
outreach_send_delay_min: int = field(default_factory=lambda: int(_env("OUTREACH_SEND_DELAY_MIN", "30")))
outreach_send_delay_max: int = field(default_factory=lambda: int(_env("OUTREACH_SEND_DELAY_MAX", "60")))
outreach_dedup_days: int = field(default_factory=lambda: int(_env("OUTREACH_DEDUP_DAYS", "30")))
```

## Assumptions

- Single-user tool (no multi-user auth or user attribution needed)
- Single Gmail account for sending
- Single-process deployment (in-memory job tracking is sufficient)

## Out of Scope

- Open/click tracking
- Scheduled/cron-based sending
- Multiple Gmail accounts
- Email threading / reply detection
- A/B testing of templates
- Custom user-defined templates (uses existing 3 templates)
- Lead generation / scraping (separate workstream)

## Testing

- Unit tests for batch generation logic (including dedup and null-email skipping)
- Unit tests for Fernet encrypt/decrypt of credentials
- Integration test for Gmail OAuth flow (mocked Google endpoints)
- Integration test for send flow (mocked Gmail API)
- Integration test for background job status tracking
- Frontend: manual testing of queue UI, approval flow, and send progress
