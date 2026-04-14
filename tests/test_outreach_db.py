"""Tests for outreach_messages and gmail_credentials tables in core.database."""

from datetime import datetime, timedelta

import pytest

from core.database import Database
from tests.test_database import _make_lead


@pytest.fixture
def db(tmp_path):
    """Create a Database instance backed by a temp file."""
    db_path = tmp_path / "test_outreach.db"
    return Database(db_path=str(db_path))


@pytest.fixture
def lead_id(db):
    """Insert a sample lead and return its ID."""
    return db.insert_lead(_make_lead())


# ── Insert & Retrieve ──────────────────────────────────────────────


class TestOutreachInsertRetrieve:
    """Insert and retrieve outreach messages."""

    def test_insert_returns_positive_id(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id,
            template="intro_cold",
            subject="Hello from Acme",
            body="We would like to help.",
            to_email="jane@acme.com",
            to_name="Jane Doe",
            model="llama3",
            duration_ms=1200,
        )
        assert isinstance(msg_id, int)
        assert msg_id > 0

    def test_retrieve_by_id(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id,
            template="intro_cold",
            subject="Hello",
            body="Body text here.",
            to_email="j@a.com",
            to_name="Jane",
            model="llama3",
            duration_ms=800,
        )
        msg = db.get_outreach_message(msg_id)
        assert msg is not None
        assert msg["id"] == msg_id
        assert msg["lead_id"] == lead_id
        assert msg["template"] == "intro_cold"
        assert msg["subject"] == "Hello"
        assert msg["body"] == "Body text here."
        assert msg["status"] == "draft"
        assert msg["to_email"] == "j@a.com"
        assert msg["to_name"] == "Jane"
        assert msg["model"] == "llama3"
        assert msg["duration_ms"] == 800
        assert msg["generated_at"] is not None
        assert msg["created_at"] is not None
        assert msg["approved_at"] is None
        assert msg["sent_at"] is None

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_outreach_message(9999) is None


# ── List Messages ──────────────────────────────────────────────────


class TestOutreachList:
    """List messages by status and by lead_id."""

    @pytest.fixture(autouse=True)
    def _seed(self, db, lead_id):
        self.db = db
        self.lead_id = lead_id
        # Insert a second lead
        self.lead_id_2 = db.insert_lead(_make_lead(company_name="Beta Inc"))

        self.msg1 = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S1", body="B1", to_email="a@a.com", to_name="A",
            model="m1", duration_ms=100,
        )
        self.msg2 = db.insert_outreach_message(
            lead_id=lead_id, template="follow_up",
            subject="S2", body="B2", to_email="a@a.com", to_name="A",
            model="m1", duration_ms=100,
        )
        self.msg3 = db.insert_outreach_message(
            lead_id=self.lead_id_2, template="intro_cold",
            subject="S3", body="B3", to_email="b@b.com", to_name="B",
            model="m1", duration_ms=100,
        )
        # Approve msg2
        db.update_outreach_status(self.msg2, "approved")

    def test_list_all(self):
        msgs = self.db.list_outreach_messages()
        assert len(msgs) == 3

    def test_list_by_status_draft(self):
        msgs = self.db.list_outreach_messages(status="draft")
        assert len(msgs) == 2
        assert all(m["status"] == "draft" for m in msgs)

    def test_list_by_status_approved(self):
        msgs = self.db.list_outreach_messages(status="approved")
        assert len(msgs) == 1
        assert msgs[0]["id"] == self.msg2

    def test_list_by_lead_id(self):
        msgs = self.db.list_outreach_messages(lead_id=self.lead_id)
        assert len(msgs) == 2
        assert all(m["lead_id"] == self.lead_id for m in msgs)

    def test_list_by_lead_id_and_status(self):
        msgs = self.db.list_outreach_messages(
            lead_id=self.lead_id, status="draft"
        )
        assert len(msgs) == 1
        assert msgs[0]["id"] == self.msg1

    def test_list_ordered_by_generated_at_desc(self):
        msgs = self.db.list_outreach_messages()
        # Most recently inserted should come first
        assert msgs[0]["id"] == self.msg3
        assert msgs[-1]["id"] == self.msg1


# ── Status Transitions ─────────────────────────────────────────────


class TestOutreachStatusTransitions:
    """Update message status (draft -> approved -> sent) with timestamps."""

    def test_approve_sets_approved_at(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "approved")
        msg = db.get_outreach_message(msg_id)
        assert msg["status"] == "approved"
        assert msg["approved_at"] is not None
        assert msg["sent_at"] is None

    def test_sent_sets_sent_at_and_gmail_id(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "approved")
        db.update_outreach_status(msg_id, "sent", gmail_message_id="abc123")
        msg = db.get_outreach_message(msg_id)
        assert msg["status"] == "sent"
        assert msg["sent_at"] is not None
        assert msg["gmail_message_id"] == "abc123"

    def test_failed_sets_error_message(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "failed", error_message="SMTP timeout")
        msg = db.get_outreach_message(msg_id)
        assert msg["status"] == "failed"
        assert msg["error_message"] == "SMTP timeout"

    def test_discard_status(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "discarded")
        msg = db.get_outreach_message(msg_id)
        assert msg["status"] == "discarded"


# ── Edit Draft Content ─────────────────────────────────────────────


class TestOutreachEditDraft:
    """Edit draft subject/body."""

    def test_update_subject_only(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="Old Subject", body="Old Body",
            to_email="a@a.com", to_name="A", model="m", duration_ms=0,
        )
        db.update_outreach_content(msg_id, subject="New Subject")
        msg = db.get_outreach_message(msg_id)
        assert msg["subject"] == "New Subject"
        assert msg["body"] == "Old Body"

    def test_update_body_only(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="Subject", body="Old Body",
            to_email="a@a.com", to_name="A", model="m", duration_ms=0,
        )
        db.update_outreach_content(msg_id, body="New Body")
        msg = db.get_outreach_message(msg_id)
        assert msg["subject"] == "Subject"
        assert msg["body"] == "New Body"

    def test_update_both(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="Old S", body="Old B",
            to_email="a@a.com", to_name="A", model="m", duration_ms=0,
        )
        db.update_outreach_content(msg_id, subject="New S", body="New B")
        msg = db.get_outreach_message(msg_id)
        assert msg["subject"] == "New S"
        assert msg["body"] == "New B"

    def test_update_sets_updated_at(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B",
            to_email="a@a.com", to_name="A", model="m", duration_ms=0,
        )
        before = db.get_outreach_message(msg_id)["updated_at"]
        db.update_outreach_content(msg_id, subject="Updated")
        after = db.get_outreach_message(msg_id)["updated_at"]
        assert after >= before


# ── Dedup Check ────────────────────────────────────────────────────


class TestOutreachDedup:
    """has_recent_outreach checks for non-failed/non-discarded outreach."""

    def test_no_outreach_returns_false(self, db, lead_id):
        assert db.has_recent_outreach(lead_id, "intro_cold") is False

    def test_draft_outreach_returns_true(self, db, lead_id):
        db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        assert db.has_recent_outreach(lead_id, "intro_cold") is True

    def test_failed_outreach_returns_false(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "failed", error_message="err")
        assert db.has_recent_outreach(lead_id, "intro_cold") is False

    def test_discarded_outreach_returns_false(self, db, lead_id):
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.update_outreach_status(msg_id, "discarded")
        assert db.has_recent_outreach(lead_id, "intro_cold") is False

    def test_different_template_returns_false(self, db, lead_id):
        db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        assert db.has_recent_outreach(lead_id, "follow_up") is False

    def test_old_outreach_beyond_window_returns_false(self, db, lead_id):
        """Outreach older than the specified days window returns False."""
        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        # Manually backdate the generated_at to 45 days ago
        old_date = (datetime.now() - timedelta(days=45)).isoformat()
        with db._conn() as conn:
            conn.execute(
                "UPDATE outreach_messages SET generated_at=? WHERE id=?",
                (old_date, msg_id),
            )
        assert db.has_recent_outreach(lead_id, "intro_cold", days=30) is False

    def test_recent_outreach_within_window_returns_true(self, db, lead_id):
        db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S", body="B", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        assert db.has_recent_outreach(lead_id, "intro_cold", days=30) is True


# ── Outreach History ───────────────────────────────────────────────


class TestOutreachHistory:
    """get_outreach_history returns messages for a specific lead."""

    def test_history_returns_lead_messages(self, db, lead_id):
        lead_id_2 = db.insert_lead(_make_lead(company_name="Other Corp"))
        db.insert_outreach_message(
            lead_id=lead_id, template="intro_cold",
            subject="S1", body="B1", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )
        db.insert_outreach_message(
            lead_id=lead_id_2, template="intro_cold",
            subject="S2", body="B2", to_email="b@b.com", to_name="B",
            model="m", duration_ms=0,
        )
        db.insert_outreach_message(
            lead_id=lead_id, template="follow_up",
            subject="S3", body="B3", to_email="a@a.com", to_name="A",
            model="m", duration_ms=0,
        )

        history = db.get_outreach_history(lead_id)
        assert len(history) == 2
        assert all(m["lead_id"] == lead_id for m in history)

    def test_history_empty_for_no_messages(self, db, lead_id):
        history = db.get_outreach_history(lead_id)
        assert history == []


# ── Gmail Credentials ──────────────────────────────────────────────


class TestGmailCredentials:
    """Store, retrieve, upsert, delete gmail credentials."""

    def test_store_and_retrieve(self, db):
        db.store_gmail_credentials(
            email_address="user@gmail.com",
            encrypted_refresh_token="enc_refresh_abc",
            encrypted_access_token="enc_access_xyz",
            token_expiry="2026-04-15T12:00:00",
        )
        cred = db.get_gmail_credentials()
        assert cred is not None
        assert cred["email_address"] == "user@gmail.com"
        assert cred["encrypted_refresh_token"] == "enc_refresh_abc"
        assert cred["encrypted_access_token"] == "enc_access_xyz"
        assert cred["token_expiry"] == "2026-04-15T12:00:00"
        assert cred["created_at"] is not None

    def test_get_returns_none_when_empty(self, db):
        assert db.get_gmail_credentials() is None

    def test_upsert_overwrites(self, db):
        db.store_gmail_credentials(
            email_address="old@gmail.com",
            encrypted_refresh_token="old_token",
            encrypted_access_token=None,
            token_expiry=None,
        )
        db.store_gmail_credentials(
            email_address="new@gmail.com",
            encrypted_refresh_token="new_token",
            encrypted_access_token="new_access",
            token_expiry="2026-05-01T00:00:00",
        )
        cred = db.get_gmail_credentials()
        assert cred["email_address"] == "new@gmail.com"
        assert cred["encrypted_refresh_token"] == "new_token"

    def test_delete(self, db):
        db.store_gmail_credentials(
            email_address="user@gmail.com",
            encrypted_refresh_token="token",
            encrypted_access_token=None,
            token_expiry=None,
        )
        db.delete_gmail_credentials()
        assert db.get_gmail_credentials() is None

    def test_delete_when_empty_is_noop(self, db):
        db.delete_gmail_credentials()  # Should not raise
        assert db.get_gmail_credentials() is None

    def test_store_with_none_optional_fields(self, db):
        db.store_gmail_credentials(
            email_address="user@gmail.com",
            encrypted_refresh_token="token",
            encrypted_access_token=None,
            token_expiry=None,
        )
        cred = db.get_gmail_credentials()
        assert cred["encrypted_access_token"] is None
        assert cred["token_expiry"] is None
