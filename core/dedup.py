"""Deduplication engine using fuzzy string matching."""

from __future__ import annotations

import logging
from dataclasses import replace

from rapidfuzz import fuzz

from core.models import RawLead

logger = logging.getLogger(__name__)


def deduplicate(leads: list[RawLead], threshold: int = 85) -> list[RawLead]:
    """Deduplicate raw leads by company_name + address similarity.

    When duplicates are found, merge their raw_data and keep the one
    with more populated fields.
    """
    if not leads:
        return []

    clusters: list[list[RawLead]] = []

    for lead in leads:
        placed = False
        for cluster in clusters:
            representative = cluster[0]
            if _is_duplicate(lead, representative, threshold):
                cluster.append(lead)
                placed = True
                break
        if not placed:
            clusters.append([lead])

    merged = [_merge_cluster(c) for c in clusters]
    logger.info("Dedup: %d leads → %d unique", len(leads), len(merged))
    return merged


def _is_duplicate(a: RawLead, b: RawLead, threshold: int) -> bool:
    """Check if two leads are duplicates based on name + address similarity."""
    name_score = fuzz.token_sort_ratio(
        a.company_name.lower().strip(),
        b.company_name.lower().strip(),
    )

    if name_score >= threshold:
        # If addresses are both present, also compare
        if a.address and b.address:
            addr_score = fuzz.token_sort_ratio(
                a.address.lower().strip(),
                b.address.lower().strip(),
            )
            # High name match + some address match = duplicate
            return addr_score >= 60
        # No address to compare — name match alone is sufficient
        return True

    return False


def _merge_cluster(cluster: list[RawLead]) -> RawLead:
    """Merge a cluster of duplicate leads into one, preferring populated fields."""
    if len(cluster) == 1:
        return cluster[0]

    # Sort by field completeness (most populated first)
    cluster.sort(key=_field_count, reverse=True)
    best = cluster[0]

    # Merge sources into raw_data
    all_sources = list({lead.source for lead in cluster})
    merged_raw = {}
    for lead in cluster:
        merged_raw.update(lead.raw_data)
    merged_raw["_merged_sources"] = all_sources

    # Fill in missing fields from other leads
    merged = replace(
        best,
        contact_name=best.contact_name or _first_non_none(cluster, "contact_name"),
        contact_title=best.contact_title or _first_non_none(cluster, "contact_title"),
        email=best.email or _first_non_none(cluster, "email"),
        phone=best.phone or _first_non_none(cluster, "phone"),
        website=best.website or _first_non_none(cluster, "website"),
        address=best.address or _first_non_none(cluster, "address"),
        raw_data=merged_raw,
    )
    return merged


def _field_count(lead: RawLead) -> int:
    """Count non-None fields for sorting."""
    fields = [
        lead.contact_name, lead.contact_title, lead.email,
        lead.phone, lead.website, lead.address,
    ]
    return sum(1 for f in fields if f)


def _first_non_none(cluster: list[RawLead], attr: str) -> str | None:
    """Return first non-None value for a field across the cluster."""
    for lead in cluster:
        val = getattr(lead, attr, None)
        if val:
            return val
    return None
