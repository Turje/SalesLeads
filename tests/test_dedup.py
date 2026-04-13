"""Tests for core.dedup — deduplication engine with fuzzy matching."""

from datetime import datetime

import pytest

from core.dedup import _field_count, _first_non_none, _is_duplicate, _merge_cluster, deduplicate
from core.models import RawLead


def _make_lead(
    company_name: str = "Acme Corp",
    source: str = "linkedin",
    **kwargs,
) -> RawLead:
    """Helper to create a RawLead with sensible defaults."""
    return RawLead(company_name=company_name, source=source, **kwargs)


# ── deduplicate() top-level function ────────────────────────────────


class TestDeduplicate:
    """Tests for the public deduplicate() function."""

    def test_empty_list_returns_empty(self):
        """Empty input produces empty output."""
        assert deduplicate([]) == []

    def test_single_lead_returns_as_is(self):
        """A single lead passes through unchanged."""
        lead = _make_lead("WeWork")
        result = deduplicate([lead])
        assert len(result) == 1
        assert result[0].company_name == "WeWork"

    def test_exact_duplicate_names_merge(self):
        """Two leads with the same company name merge into one."""
        lead_a = _make_lead("Brookfield Properties", source="costar")
        lead_b = _make_lead("Brookfield Properties", source="linkedin")
        result = deduplicate([lead_a, lead_b])
        assert len(result) == 1
        assert result[0].company_name == "Brookfield Properties"

    def test_different_companies_stay_separate(self):
        """Two clearly different companies remain as two leads."""
        lead_a = _make_lead("Brookfield Properties")
        lead_b = _make_lead("WeWork Inc")
        result = deduplicate([lead_a, lead_b])
        assert len(result) == 2

    def test_fuzzy_name_match(self):
        """Slight name variations are recognized as duplicates."""
        lead_a = _make_lead("Brookfield Properties", source="costar")
        lead_b = _make_lead("Brookfield Property", source="linkedin")
        result = deduplicate([lead_a, lead_b])
        assert len(result) == 1

    def test_fuzzy_match_below_threshold_stays_separate(self):
        """Names below the similarity threshold are not merged."""
        lead_a = _make_lead("Brookfield Properties LLC")
        lead_b = _make_lead("Brooklyn Paper Co")
        result = deduplicate([lead_a, lead_b])
        assert len(result) == 2

    def test_address_comparison_confirms_duplicate(self):
        """When both have addresses, address similarity is also checked."""
        lead_a = _make_lead(
            "Brookfield Properties",
            source="costar",
            address="250 Vesey St, New York, NY 10281",
        )
        lead_b = _make_lead(
            "Brookfield Properties",
            source="linkedin",
            address="250 Vesey Street, New York, NY",
        )
        result = deduplicate([lead_a, lead_b])
        assert len(result) == 1

    def test_same_name_different_address_stays_separate(self):
        """Same company name but very different addresses = not duplicates."""
        lead_a = _make_lead(
            "Acme Corp",
            source="costar",
            address="100 Main St, Boston, MA",
        )
        lead_b = _make_lead(
            "Acme Corp",
            source="linkedin",
            address="5000 Sunset Blvd, Los Angeles, CA",
        )
        result = deduplicate([lead_a, lead_b])
        # The address score for completely different addresses should be < 60
        assert len(result) == 2

    def test_merged_sources_aggregated(self):
        """Merged leads have _merged_sources in raw_data."""
        lead_a = _make_lead("WeWork", source="costar", raw_data={"id": "c1"})
        lead_b = _make_lead("WeWork", source="linkedin", raw_data={"url": "li1"})
        result = deduplicate([lead_a, lead_b])
        assert len(result) == 1
        merged = result[0]
        assert "_merged_sources" in merged.raw_data
        assert set(merged.raw_data["_merged_sources"]) == {"costar", "linkedin"}

    def test_merged_lead_prefers_populated_fields(self):
        """The merged lead picks non-None fields from the best candidate."""
        lead_a = _make_lead(
            "WeWork",
            source="costar",
            contact_name=None,
            email="from_costar@test.com",
        )
        lead_b = _make_lead(
            "WeWork",
            source="linkedin",
            contact_name="Jane Doe",
            email=None,
        )
        result = deduplicate([lead_a, lead_b])
        merged = result[0]
        # Should have the contact_name from lead_b and email from lead_a
        assert merged.contact_name == "Jane Doe"
        assert merged.email == "from_costar@test.com"

    def test_merged_raw_data_combines_entries(self):
        """raw_data from all cluster members is merged."""
        lead_a = _make_lead("WeWork", source="costar", raw_data={"costar_id": "C1"})
        lead_b = _make_lead("WeWork", source="linkedin", raw_data={"li_profile": "L1"})
        result = deduplicate([lead_a, lead_b])
        merged = result[0]
        assert merged.raw_data["costar_id"] == "C1"
        assert merged.raw_data["li_profile"] == "L1"

    def test_custom_threshold(self):
        """A stricter threshold keeps more leads separate."""
        lead_a = _make_lead("Brookfield Properties")
        lead_b = _make_lead("Brookfield Property")
        # With a very high threshold, slight variation is not enough
        result_strict = deduplicate([lead_a, lead_b], threshold=99)
        assert len(result_strict) == 2
        # With the default threshold, they merge
        result_relaxed = deduplicate([lead_a, lead_b], threshold=85)
        assert len(result_relaxed) == 1

    def test_three_duplicates_merge_into_one(self):
        """Three leads with the same company name cluster together."""
        leads = [
            _make_lead("Brookfield Properties", source="costar"),
            _make_lead("Brookfield Properties", source="linkedin"),
            _make_lead("Brookfield Properties Inc", source="nyc_opendata"),
        ]
        result = deduplicate(leads)
        assert len(result) == 1


# ── _is_duplicate() ────────────────────────────────────────────────


class TestIsDuplicate:
    """Tests for the internal _is_duplicate function."""

    def test_exact_match(self):
        a = _make_lead("Acme Corp")
        b = _make_lead("Acme Corp")
        assert _is_duplicate(a, b, threshold=85) is True

    def test_case_insensitive(self):
        a = _make_lead("ACME CORP")
        b = _make_lead("acme corp")
        assert _is_duplicate(a, b, threshold=85) is True

    def test_totally_different(self):
        a = _make_lead("Acme Corp")
        b = _make_lead("Zillow Group")
        assert _is_duplicate(a, b, threshold=85) is False

    def test_address_match_required_when_both_present(self):
        """When both leads have addresses, address must also match."""
        a = _make_lead("Acme Corp", address="123 Main St, New York")
        b = _make_lead("Acme Corp", address="999 Other Ave, San Francisco")
        assert _is_duplicate(a, b, threshold=85) is False

    def test_no_address_means_name_alone_decides(self):
        """When neither lead has an address, name match alone is sufficient."""
        a = _make_lead("Acme Corp")
        b = _make_lead("Acme Corp")
        assert _is_duplicate(a, b, threshold=85) is True

    def test_one_address_missing_name_alone_decides(self):
        """When only one lead has an address, name match alone decides."""
        a = _make_lead("Acme Corp", address="123 Main St")
        b = _make_lead("Acme Corp")
        assert _is_duplicate(a, b, threshold=85) is True


# ── _merge_cluster() ───────────────────────────────────────────────


class TestMergeCluster:
    """Tests for the internal _merge_cluster function."""

    def test_single_element_cluster(self):
        """A cluster of one returns the lead as-is."""
        lead = _make_lead("X")
        result = _merge_cluster([lead])
        assert result is lead

    def test_prefers_most_populated_lead(self):
        """The lead with the most filled-in fields becomes the base."""
        sparse = _make_lead("X", source="s1")
        rich = _make_lead(
            "X",
            source="s2",
            contact_name="Jane",
            email="j@x.com",
            phone="555-0001",
        )
        # Regardless of order in the cluster, the rich one should win
        result = _merge_cluster([sparse, rich])
        assert result.contact_name == "Jane"
        assert result.email == "j@x.com"
        assert result.phone == "555-0001"

    def test_fills_gaps_from_other_leads(self):
        """Missing fields on the best lead are filled from others."""
        lead_a = _make_lead("X", source="s1", contact_name="Jane", email=None)
        lead_b = _make_lead("X", source="s2", contact_name=None, email="x@x.com")
        result = _merge_cluster([lead_a, lead_b])
        assert result.contact_name == "Jane"
        assert result.email == "x@x.com"


# ── _field_count() ─────────────────────────────────────────────────


class TestFieldCount:
    """Tests for the internal _field_count function."""

    def test_no_fields(self):
        lead = _make_lead("X")
        assert _field_count(lead) == 0

    def test_all_fields(self):
        lead = _make_lead(
            "X",
            contact_name="A",
            contact_title="B",
            email="C",
            phone="D",
            website="E",
            address="F",
        )
        assert _field_count(lead) == 6

    def test_some_fields(self):
        lead = _make_lead("X", contact_name="A", email="B")
        assert _field_count(lead) == 2


# ── _first_non_none() ──────────────────────────────────────────────


class TestFirstNonNone:
    """Tests for the internal _first_non_none function."""

    def test_returns_first_non_none(self):
        leads = [
            _make_lead("X", email=None),
            _make_lead("X", email="found@test.com"),
            _make_lead("X", email="also@test.com"),
        ]
        assert _first_non_none(leads, "email") == "found@test.com"

    def test_all_none_returns_none(self):
        leads = [_make_lead("X"), _make_lead("X")]
        assert _first_non_none(leads, "email") is None

    def test_empty_cluster(self):
        assert _first_non_none([], "email") is None
