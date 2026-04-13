"""MarketplaceAgent — CRE data + intent signals (runs every 4 hours)."""

from __future__ import annotations

import logging

import requests

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# Reonomy-style CRE data endpoints (public info aggregation)
# These are representative endpoints — actual Reonomy requires paid access
REONOMY_SEARCH_URL = "https://api.reonomy.com/v2/property/search"

# Intent signal sources (Bombora-style topic data)
BOMBORA_SURGE_URL = "https://api.bombora.com/v1/surge"

# Free CRE listing APIs as fallback
CRE_LISTINGS_URL = (
    "https://data.cityofnewyork.us/resource/w7w3-xahh.json"  # DOF rolling sales
)

# Intent topics that signal buying readiness
INTENT_TOPICS = [
    "managed IT services",
    "smart building technology",
    "building automation",
    "commercial WiFi",
    "property management software",
    "co-working technology",
    "access control systems",
    "building security",
]

PAGE_SIZE = 200


class MarketplaceAgent(BaseSourceAgent):
    """CRE marketplace data + intent signals.  Runs more frequently (every 4h)."""

    name = "marketplace"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        leads: list[RawLead] = []
        leads.extend(self._fetch_rolling_sales())
        leads.extend(self._fetch_reonomy())
        leads.extend(self._fetch_intent_signals())
        return leads

    # ------------------------------------------------------------------
    # NYC DOF Rolling Sales (free, public)
    # ------------------------------------------------------------------

    def _fetch_rolling_sales(self) -> list[RawLead]:
        """Recent commercial property sales from NYC Dept of Finance."""
        try:
            token = self._settings.nyc_opendata_app_token
            params: dict[str, str] = {
                "$where": (
                    "building_class_at_time_of_sale LIKE 'O%' "
                    "OR building_class_at_time_of_sale LIKE 'D%' "
                    "OR building_class_at_time_of_sale LIKE 'K%'"
                ),
                "$limit": str(PAGE_SIZE),
                "$order": "sale_date DESC",
            }
            if token:
                params["$$app_token"] = token

            resp = requests.get(CRE_LISTINGS_URL, params=params, timeout=30)
            resp.raise_for_status()
            records = resp.json()

            leads: list[RawLead] = []
            for rec in records:
                sale_price = rec.get("sale_price", "0")
                # Skip $0 transfers (non-arms-length)
                if sale_price in ("0", ""):
                    continue

                address_parts = [
                    rec.get("address", ""),
                    rec.get("zip_code", ""),
                ]
                address = ", ".join(p for p in address_parts if p)

                leads.append(
                    RawLead(
                        company_name=rec.get("buyer_name", "Unknown Buyer"),
                        source=self.name,
                        address=address,
                        raw_data={
                            "signal_type": "recent_sale",
                            "sale_price": sale_price,
                            "sale_date": rec.get("sale_date"),
                            "building_class": rec.get(
                                "building_class_at_time_of_sale"
                            ),
                            "gross_sqft": rec.get("gross_square_feet"),
                            "borough": rec.get("borough"),
                            "block": rec.get("block"),
                            "lot": rec.get("lot"),
                            "year_built": rec.get("year_built"),
                        },
                    )
                )
            logger.info("Rolling sales returned %d records", len(leads))
            return leads
        except Exception:
            logger.exception("NYC rolling sales query failed")
            return []

    # ------------------------------------------------------------------
    # Reonomy (paid — graceful fallback)
    # ------------------------------------------------------------------

    def _fetch_reonomy(self) -> list[RawLead]:
        """Query Reonomy for CRE property data.  Requires paid API access."""
        # Reonomy requires paid access; log info and return empty
        logger.info(
            "Reonomy integration not configured — "
            "set REONOMY_API_KEY to enable CRE data enrichment"
        )
        return []

    # ------------------------------------------------------------------
    # Intent signals (Bombora-style)
    # ------------------------------------------------------------------

    def _fetch_intent_signals(self) -> list[RawLead]:
        """Query intent-data provider for companies researching relevant topics.

        Bombora requires paid access; this is a graceful stub that logs
        the intent and returns empty until credentials are configured.
        """
        # Intent data APIs (Bombora, G2, TrustRadius) require paid subscriptions
        logger.info(
            "Intent signal provider not configured — "
            "integrate Bombora or similar for intent data. "
            "Tracking topics: %s",
            ", ".join(INTENT_TOPICS[:3]),
        )
        return []
