"""PublicRecordsAgent — NYC ACRIS ownership transfers + DOB permits."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# NYC ACRIS Real Property Legals (ownership transfers)
ACRIS_LEGALS_URL = (
    "https://data.cityofnewyork.us/resource/8h5j-fqxa.json"
)
# NYC ACRIS Real Property Parties (buyer/seller details)
ACRIS_PARTIES_URL = (
    "https://data.cityofnewyork.us/resource/636b-3b5g.json"
)
# NYC DOB NOW permit issuances
DOB_PERMITS_URL = (
    "https://data.cityofnewyork.us/resource/ipu4-2vj7.json"
)

PAGE_SIZE = 200
LOOKBACK_DAYS = 90


class PublicRecordsAgent(BaseSourceAgent):
    """Ownership transfers (ACRIS) and building permits (DOB) in NYC."""

    name = "public_records"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        leads: list[RawLead] = []
        leads.extend(self._fetch_acris_transfers())
        leads.extend(self._fetch_dob_permits())
        return leads

    # ------------------------------------------------------------------
    # ACRIS — property ownership transfers
    # ------------------------------------------------------------------

    def _fetch_acris_transfers(self) -> list[RawLead]:
        try:
            cutoff = (
                datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
            ).strftime("%Y-%m-%dT00:00:00.000")
            token = self._settings.nyc_opendata_app_token

            # Step 1: recent commercial deed transfers
            params: dict[str, str] = {
                "$where": (
                    f"good_through_date > '{cutoff}' "
                    "AND property_type IN('CR','CP','CO')"
                ),
                "$limit": str(PAGE_SIZE),
                "$order": "good_through_date DESC",
            }
            if token:
                params["$$app_token"] = token

            resp = requests.get(ACRIS_LEGALS_URL, params=params, timeout=30)
            resp.raise_for_status()
            legals = resp.json()

            leads: list[RawLead] = []
            for rec in legals:
                doc_id = rec.get("document_id", "")
                parties = self._fetch_parties(doc_id, token)
                buyer = parties.get("buyer", "Unknown Buyer")
                address_parts = [
                    rec.get("street_number", ""),
                    rec.get("street_name", ""),
                    rec.get("borough", ""),
                ]
                address = " ".join(p for p in address_parts if p).strip()

                leads.append(
                    RawLead(
                        company_name=buyer,
                        source=self.name,
                        address=address,
                        raw_data={
                            "record_type": "ownership_transfer",
                            "document_id": doc_id,
                            "property_type": rec.get("property_type"),
                            "borough": rec.get("borough"),
                            "block": rec.get("block"),
                            "lot": rec.get("lot"),
                            "seller": parties.get("seller"),
                        },
                    )
                )
            logger.info("ACRIS returned %d transfers", len(leads))
            return leads
        except Exception:
            logger.exception("ACRIS query failed")
            return []

    def _fetch_parties(self, document_id: str, token: str) -> dict:
        """Look up buyer/seller names for a document_id."""
        try:
            params: dict[str, str] = {
                "$where": f"document_id='{document_id}'",
                "$limit": "10",
            }
            if token:
                params["$$app_token"] = token

            resp = requests.get(
                ACRIS_PARTIES_URL, params=params, timeout=15
            )
            resp.raise_for_status()
            rows = resp.json()

            result: dict[str, str] = {}
            for row in rows:
                party_type = row.get("party_type", "")
                name = row.get("name", "")
                if party_type == "1":  # seller / grantor
                    result.setdefault("seller", name)
                elif party_type == "2":  # buyer / grantee
                    result.setdefault("buyer", name)
            return result
        except Exception:
            logger.debug(
                "Could not fetch parties for document %s", document_id
            )
            return {}

    # ------------------------------------------------------------------
    # DOB NOW — building permits
    # ------------------------------------------------------------------

    def _fetch_dob_permits(self) -> list[RawLead]:
        try:
            cutoff = (
                datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
            ).strftime("%Y-%m-%dT00:00:00.000")
            token = self._settings.nyc_opendata_app_token

            params: dict[str, str] = {
                "$where": (
                    f"issuance_date > '{cutoff}' "
                    "AND job_type IN('A1','A2','NB')"
                ),
                "$limit": str(PAGE_SIZE),
                "$order": "issuance_date DESC",
            }
            if token:
                params["$$app_token"] = token

            resp = requests.get(DOB_PERMITS_URL, params=params, timeout=30)
            resp.raise_for_status()
            permits = resp.json()

            leads: list[RawLead] = []
            for rec in permits:
                owner = rec.get("owner_name", "").strip()
                address_parts = [
                    rec.get("house_number", ""),
                    rec.get("street_name", ""),
                    rec.get("borough", ""),
                    rec.get("zip_code", ""),
                ]
                address = " ".join(p for p in address_parts if p).strip()

                leads.append(
                    RawLead(
                        company_name=owner or "Unknown Owner",
                        source=self.name,
                        contact_name=rec.get("applicant_name"),
                        address=address,
                        raw_data={
                            "record_type": "building_permit",
                            "job_number": rec.get("job_number"),
                            "job_type": rec.get("job_type"),
                            "permit_type": rec.get("permit_type"),
                            "work_description": rec.get(
                                "job_description", ""
                            )[:500],
                            "issuance_date": rec.get("issuance_date"),
                            "owner_phone": rec.get("owner_phone"),
                        },
                    )
                )
            logger.info("DOB returned %d permits", len(leads))
            return leads
        except Exception:
            logger.exception("DOB permits query failed")
            return []
