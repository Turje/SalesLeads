"""Tests for outreach service — batch generation, dedup, and send job tracking."""

import pytest
from unittest.mock import patch, MagicMock

from core.database import Database
from tests.test_database import _make_lead
from api.services.outreach_service import generate_batch, SendJob, create_send_job, get_send_job


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def db_with_leads(db):
    leads = []
    for i, name in enumerate(["Acme Corp", "BuildCo", "NoEmail LLC"]):
        lead = _make_lead(
            company_name=name, contact_name=f"Person {i}",
            email=f"person{i}@{name.lower().replace(' ', '')}.com" if name != "NoEmail LLC" else None,
        )
        lead_id = db.insert_lead(lead)
        leads.append(lead_id)
    return db, leads


class TestGenerateBatch:
    def test_generates_drafts_for_leads_with_email(self, db_with_leads):
        db, lead_ids = db_with_leads
        result = generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        assert result["generated"] == 2
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["reason"] == "no email address"

    def test_skips_recently_contacted(self, db_with_leads):
        db, lead_ids = db_with_leads
        generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        result = generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        assert result["generated"] == 0
        assert len(result["skipped"]) == 3

    def test_different_template_not_deduped(self, db_with_leads):
        db, lead_ids = db_with_leads
        generate_batch(db=db, lead_ids=lead_ids, template="initial_outreach", dedup_days=30)
        result = generate_batch(db=db, lead_ids=lead_ids, template="follow_up", dedup_days=30)
        assert result["generated"] == 2


class TestSendJob:
    def test_send_job_tracks_progress(self):
        job = SendJob(job_id="test-123", total=3)
        assert job.status == "running"
        assert job.sent == 0
        job.record_sent()
        assert job.sent == 1
        job.record_failure(msg_id=1, error="timeout")
        assert job.failed == 1
        job.record_sent()
        job.complete()
        assert job.status == "done"

    def test_send_job_to_dict(self):
        job = SendJob(job_id="test-456", total=2)
        d = job.to_dict()
        assert d["job_id"] == "test-456"
        assert d["status"] == "running"
        assert d["total"] == 2
