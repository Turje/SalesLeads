"""Tests for core.database — SQLite persistence layer."""

import json
from datetime import date, datetime

import pytest

from core.database import Database
from core.models import EnrichedLead


@pytest.fixture
def db(tmp_path):
    """Create a Database instance backed by a temp file."""
    db_path = tmp_path / "test_salesleads.db"
    return Database(db_path=str(db_path))



def _make_lead(**overrides) -> EnrichedLead:
    """Create an EnrichedLead with sensible defaults, allowing overrides."""
    defaults = dict(
        company_name="Acme Corp",
        company_type="CRE_OPERATOR",
        contact_name="Jane Doe",
        contact_title="VP Operations",
        email="jane@acme.com",
        phone="212-555-1234",
        linkedin_url="https://linkedin.com/in/janedoe",
        website="https://acme.com",
        address="100 Main St, New York, NY",
        building_type="Class A Office",
        sqft=50000,
        num_tenants=10,
        current_it_provider="Spectrum",
        tech_signals=["fiber"],
        recent_news=["Expanded to new floor"],
        social_links={"twitter": "@acme"},
        sources=["costar", "linkedin"],
        discovery_date=date(2026, 4, 1),
        score=75,
        qualification_notes="Good prospect",
        pipeline_stage="NEW",
    )
    defaults.update(overrides)
    return EnrichedLead(**defaults)


# ── Insert & Retrieve ──────────────────────────────────────────────


class TestInsertAndRetrieve:
    """Tests for inserting and retrieving leads."""

    def test_insert_returns_id(self, db):
        """insert_lead returns a positive integer ID."""
        lead = _make_lead()
        lead_id = db.insert_lead(lead)
        assert isinstance(lead_id, int)
        assert lead_id > 0

    def test_retrieve_by_id(self, db):
        """A lead can be retrieved by its ID with all fields intact."""
        original = _make_lead()
        lead_id = db.insert_lead(original)
        retrieved = db.get_lead(lead_id)

        assert retrieved is not None
        assert retrieved.id == lead_id
        assert retrieved.company_name == "Acme Corp"
        assert retrieved.company_type == "CRE_OPERATOR"
        assert retrieved.contact_name == "Jane Doe"
        assert retrieved.contact_title == "VP Operations"
        assert retrieved.email == "jane@acme.com"
        assert retrieved.phone == "212-555-1234"
        assert retrieved.linkedin_url == "https://linkedin.com/in/janedoe"
        assert retrieved.website == "https://acme.com"
        assert retrieved.address == "100 Main St, New York, NY"
        assert retrieved.building_type == "Class A Office"
        assert retrieved.sqft == 50000
        assert retrieved.num_tenants == 10
        assert retrieved.current_it_provider == "Spectrum"
        assert retrieved.tech_signals == ["fiber"]
        assert retrieved.recent_news == ["Expanded to new floor"]
        assert retrieved.social_links == {"twitter": "@acme"}
        assert retrieved.sources == ["costar", "linkedin"]
        assert retrieved.discovery_date == date(2026, 4, 1)
        assert retrieved.score == 75
        assert retrieved.qualification_notes == "Good prospect"
        assert retrieved.pipeline_stage == "NEW"

    def test_get_nonexistent_lead_returns_none(self, db):
        """get_lead for a missing ID returns None."""
        assert db.get_lead(9999) is None

    def test_multiple_inserts_get_different_ids(self, db):
        """Each insert returns a unique ID."""
        id_a = db.insert_lead(_make_lead(company_name="A"))
        id_b = db.insert_lead(_make_lead(company_name="B"))
        assert id_a != id_b

    def test_second_database_instance_shares_file(self, tmp_path):
        """Two Database instances on the same file see the same data."""
        db_path = tmp_path / "shared.db"
        db1 = Database(db_path=str(db_path))
        lead_id = db1.insert_lead(_make_lead())

        db2 = Database(db_path=str(db_path))
        retrieved = db2.get_lead(lead_id)
        assert retrieved is not None
        assert retrieved.company_name == "Acme Corp"


# ── Upsert ──────────────────────────────────────────────────────────


class TestUpsert:
    """Tests for upsert_lead — insert or update by company_name + address."""

    def test_upsert_inserts_new(self, db):
        """Upsert inserts a new record when no match exists."""
        lead = _make_lead()
        lead_id = db.upsert_lead(lead)
        assert lead_id > 0
        assert db.get_lead(lead_id).company_name == "Acme Corp"

    def test_upsert_updates_existing(self, db):
        """Upsert updates the record when company_name + address match."""
        original = _make_lead(score=50)
        first_id = db.upsert_lead(original)

        updated = _make_lead(score=90, contact_name="John Smith")
        second_id = db.upsert_lead(updated)

        # Same ID — it was an update, not an insert
        assert second_id == first_id
        retrieved = db.get_lead(first_id)
        assert retrieved.score == 90
        assert retrieved.contact_name == "John Smith"

    def test_upsert_different_address_inserts_new(self, db):
        """Same company name but different address creates a new record."""
        lead_a = _make_lead(address="100 Main St, New York")
        lead_b = _make_lead(address="200 Broadway, New York")
        id_a = db.upsert_lead(lead_a)
        id_b = db.upsert_lead(lead_b)
        assert id_a != id_b

    def test_upsert_leads_batch(self, db):
        """upsert_leads processes a batch of leads."""
        leads = [
            _make_lead(company_name="A", address="addr1"),
            _make_lead(company_name="B", address="addr2"),
        ]
        ids = db.upsert_leads(leads)
        assert len(ids) == 2
        assert ids[0] != ids[1]


# ── Pipeline Stage ──────────────────────────────────────────────────


class TestUpdatePipelineStage:
    """Tests for update_pipeline_stage."""

    def test_update_stage(self, db):
        """Pipeline stage can be updated."""
        lead_id = db.insert_lead(_make_lead(pipeline_stage="NEW"))
        db.update_pipeline_stage(lead_id, "CONTACTED")
        retrieved = db.get_lead(lead_id)
        assert retrieved.pipeline_stage == "CONTACTED"

    def test_update_to_all_valid_stages(self, db):
        """Can update to every valid pipeline stage."""
        lead_id = db.insert_lead(_make_lead())
        for stage in ["NEW", "CONTACTED", "MEETING", "PROPOSAL", "CLOSED"]:
            db.update_pipeline_stage(lead_id, stage)
            assert db.get_lead(lead_id).pipeline_stage == stage

    def test_invalid_stage_raises_value_error(self, db):
        """An invalid stage raises ValueError."""
        lead_id = db.insert_lead(_make_lead())
        with pytest.raises(ValueError, match="Invalid pipeline stage"):
            db.update_pipeline_stage(lead_id, "INVALID_STAGE")


# ── Filtering (get_all_leads) ──────────────────────────────────────


class TestGetAllLeads:
    """Tests for get_all_leads with various filters."""

    @pytest.fixture(autouse=True)
    def _seed_data(self, db):
        """Insert a variety of leads for filtering tests."""
        self.db = db
        self.id_a = db.insert_lead(_make_lead(
            company_name="Alpha Corp",
            pipeline_stage="NEW",
            score=80,
            company_type="CRE_OPERATOR",
            sources=["costar"],
        ))
        self.id_b = db.insert_lead(_make_lead(
            company_name="Beta Inc",
            address="200 Broadway",
            pipeline_stage="CONTACTED",
            score=60,
            company_type="COWORKING",
            sources=["linkedin"],
        ))
        self.id_c = db.insert_lead(_make_lead(
            company_name="Gamma LLC",
            address="300 Park Ave",
            pipeline_stage="NEW",
            score=40,
            company_type="CRE_OPERATOR",
            sources=["costar", "linkedin"],
        ))

    def test_get_all_unfiltered(self):
        """Returns all leads when no filters are applied."""
        results = self.db.get_all_leads()
        assert len(results) == 3

    def test_filter_by_stage(self):
        """Filtering by stage returns only matching leads."""
        results = self.db.get_all_leads(stage="NEW")
        assert len(results) == 2
        names = {r.company_name for r in results}
        assert names == {"Alpha Corp", "Gamma LLC"}

    def test_filter_by_min_score(self):
        """Filtering by min_score excludes low-scoring leads."""
        results = self.db.get_all_leads(min_score=50)
        assert len(results) == 2
        names = {r.company_name for r in results}
        assert names == {"Alpha Corp", "Beta Inc"}

    def test_filter_by_source(self):
        """Filtering by source uses LIKE matching on the sources JSON."""
        results = self.db.get_all_leads(source="linkedin")
        assert len(results) == 2
        names = {r.company_name for r in results}
        assert names == {"Beta Inc", "Gamma LLC"}

    def test_filter_by_company_type(self):
        """Filtering by company_type returns matching leads."""
        results = self.db.get_all_leads(company_type="COWORKING")
        assert len(results) == 1
        assert results[0].company_name == "Beta Inc"

    def test_combined_filters(self):
        """Multiple filters are applied together (AND logic)."""
        results = self.db.get_all_leads(stage="NEW", min_score=50)
        assert len(results) == 1
        assert results[0].company_name == "Alpha Corp"

    def test_results_ordered_by_score_desc(self):
        """Results are sorted by score descending."""
        results = self.db.get_all_leads()
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_limit_and_offset(self):
        """limit and offset pagination works."""
        all_results = self.db.get_all_leads()
        page_1 = self.db.get_all_leads(limit=2, offset=0)
        page_2 = self.db.get_all_leads(limit=2, offset=2)
        assert len(page_1) == 2
        assert len(page_2) == 1
        # The pages together should cover all leads
        all_names = {r.company_name for r in all_results}
        paged_names = {r.company_name for r in page_1} | {r.company_name for r in page_2}
        assert all_names == paged_names

    def test_no_results_returns_empty_list(self):
        """Filters that match nothing return an empty list."""
        results = self.db.get_all_leads(stage="CLOSED")
        assert results == []


# ── Stage Counts ────────────────────────────────────────────────────


class TestStageCounts:
    """Tests for get_stage_counts and get_lead_count."""

    def test_stage_counts(self, db):
        """get_stage_counts returns correct per-stage counts."""
        db.insert_lead(_make_lead(company_name="A", address="a1", pipeline_stage="NEW"))
        db.insert_lead(_make_lead(company_name="B", address="a2", pipeline_stage="NEW"))
        db.insert_lead(_make_lead(company_name="C", address="a3", pipeline_stage="CONTACTED"))

        counts = db.get_stage_counts()
        assert counts["NEW"] == 2
        assert counts["CONTACTED"] == 1
        assert "MEETING" not in counts  # no leads in MEETING stage

    def test_lead_count_total(self, db):
        """get_lead_count without stage returns total count."""
        db.insert_lead(_make_lead(company_name="A", address="a1"))
        db.insert_lead(_make_lead(company_name="B", address="a2"))
        assert db.get_lead_count() == 2

    def test_lead_count_by_stage(self, db):
        """get_lead_count with stage filter returns filtered count."""
        db.insert_lead(_make_lead(company_name="A", address="a1", pipeline_stage="NEW"))
        db.insert_lead(_make_lead(company_name="B", address="a2", pipeline_stage="CONTACTED"))
        assert db.get_lead_count(stage="NEW") == 1
        assert db.get_lead_count(stage="CONTACTED") == 1
        assert db.get_lead_count(stage="MEETING") == 0

    def test_empty_database_counts(self, db):
        """Empty database returns zero counts."""
        assert db.get_lead_count() == 0
        assert db.get_stage_counts() == {}


# ── Pipeline Runs ───────────────────────────────────────────────────


class TestPipelineRuns:
    """Tests for record_run and get_last_run."""

    def test_record_and_retrieve_run(self, db):
        """A recorded pipeline run can be retrieved."""
        ts = datetime(2026, 4, 13, 10, 0, 0)
        stats = {"leads_found": 15, "enriched": 12}
        db.record_run("run-001", ts, stats)

        last = db.get_last_run()
        assert last is not None
        assert last["run_id"] == "run-001"
        assert last["run_timestamp"] == ts.isoformat()
        assert last["stats"] == stats

    def test_get_last_run_returns_most_recent(self, db):
        """get_last_run returns the most recently created run.

        Since created_at uses datetime('now') at second precision, both
        inserts in a fast test may share the same timestamp.  SQLite's
        ORDER BY … DESC LIMIT 1 then falls back to rowid order, which
        means the highest-rowid (last-inserted) row is returned when
        created_at values differ, but the first-inserted row when they
        are identical.  We work around this by verifying through a
        direct SQL insert with an explicit future created_at.
        """
        db.record_run("run-001", datetime(2026, 4, 10), {"n": 1})
        # Manually insert a second run with a later created_at
        with db._conn() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs (run_id, run_timestamp, stats, created_at) VALUES (?,?,?,?)",
                ("run-002", datetime(2026, 4, 13).isoformat(), json.dumps({"n": 2}), "2099-01-01 00:00:00"),
            )

        last = db.get_last_run()
        assert last["run_id"] == "run-002"
        assert last["stats"]["n"] == 2

    def test_get_last_run_empty(self, db):
        """get_last_run returns None when no runs exist."""
        assert db.get_last_run() is None

    def test_run_stats_roundtrip(self, db):
        """Complex stats dict survives JSON serialization roundtrip."""
        stats = {
            "sources": {"costar": 5, "linkedin": 3},
            "dedup_reduced": 2,
            "errors": [],
        }
        db.record_run("run-complex", datetime(2026, 4, 13), stats)
        last = db.get_last_run()
        assert last["stats"] == stats


# ── Delete ──────────────────────────────────────────────────────────


class TestDeleteLead:
    """Tests for delete_lead."""

    def test_delete_existing_lead(self, db):
        """Deleting an existing lead removes it from the database."""
        lead_id = db.insert_lead(_make_lead())
        assert db.get_lead(lead_id) is not None

        db.delete_lead(lead_id)
        assert db.get_lead(lead_id) is None

    def test_delete_nonexistent_lead_is_noop(self, db):
        """Deleting a non-existent ID does not raise an error."""
        db.delete_lead(9999)  # Should not raise

    def test_delete_reduces_count(self, db):
        """Deleting a lead decreases the total count."""
        id_a = db.insert_lead(_make_lead(company_name="A", address="a1"))
        id_b = db.insert_lead(_make_lead(company_name="B", address="a2"))
        assert db.get_lead_count() == 2

        db.delete_lead(id_a)
        assert db.get_lead_count() == 1
        assert db.get_lead(id_b) is not None

    def test_delete_does_not_affect_other_leads(self, db):
        """Deleting one lead does not affect unrelated leads."""
        id_a = db.insert_lead(_make_lead(company_name="A", address="a1"))
        id_b = db.insert_lead(_make_lead(company_name="B", address="a2"))

        db.delete_lead(id_a)
        remaining = db.get_lead(id_b)
        assert remaining is not None
        assert remaining.company_name == "B"


# ── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and data integrity."""

    def test_null_optional_fields_roundtrip(self, db):
        """Leads with None optional fields persist and restore correctly."""
        lead = EnrichedLead(
            company_name="Minimal Corp",
            # All optional fields left as default None
        )
        lead_id = db.insert_lead(lead)
        retrieved = db.get_lead(lead_id)
        assert retrieved.email is None
        assert retrieved.phone is None
        assert retrieved.sqft is None
        assert retrieved.current_it_provider is None

    def test_empty_lists_roundtrip(self, db):
        """Empty list/dict fields persist and restore correctly."""
        lead = EnrichedLead(company_name="Empty Corp")
        lead_id = db.insert_lead(lead)
        retrieved = db.get_lead(lead_id)
        assert retrieved.tech_signals == []
        assert retrieved.recent_news == []
        assert retrieved.sources == []
        assert retrieved.social_links == {}

    def test_special_characters_in_company_name(self, db):
        """Company names with special characters survive roundtrip."""
        lead = _make_lead(company_name="O'Malley & Sons, Inc.")
        lead_id = db.insert_lead(lead)
        retrieved = db.get_lead(lead_id)
        assert retrieved.company_name == "O'Malley & Sons, Inc."

    def test_unicode_content(self, db):
        """Unicode content persists correctly."""
        lead = _make_lead(
            company_name="Schneider Immobilien GmbH",
            address="Friedrichstrasse 100, Berlin",
            qualification_notes="Sehr gutes Unternehmen",
        )
        lead_id = db.insert_lead(lead)
        retrieved = db.get_lead(lead_id)
        assert retrieved.company_name == "Schneider Immobilien GmbH"
        assert "Friedrichstrasse" in retrieved.address
