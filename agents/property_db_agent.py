"""PropertyDBAgent — NYC OpenData SODA API + LoopNet scraping."""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# NYC OpenData: PLUTO (Primary Land Use Tax Lot Output) dataset
# Resource ID for latest PLUTO — commercial lots
PLUTO_RESOURCE_ID = "64uk-42ks"
PLUTO_BASE_URL = (
    f"https://data.cityofnewyork.us/resource/{PLUTO_RESOURCE_ID}.json"
)

# LoopNet NYC commercial listings
LOOPNET_SEARCH_URL = "https://www.loopnet.com/search/commercial-real-estate/new-york-ny/for-lease/"

# Commercial land-use codes in PLUTO (office, retail, commercial)
COMMERCIAL_LAND_USE = {"05", "06", "07", "08", "09"}

# Minimum lot square footage filter
MIN_SQFT = 10_000

# Page size for SODA queries
PAGE_SIZE = 200


class PropertyDBAgent(BaseSourceAgent):
    """Fetch commercial property records from NYC OpenData + LoopNet."""

    name = "property_db"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    # ------------------------------------------------------------------
    # fetch
    # ------------------------------------------------------------------

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        leads: list[RawLead] = []
        leads.extend(self._fetch_nyc_opendata())
        leads.extend(self._fetch_loopnet())
        return leads

    # ------------------------------------------------------------------
    # NYC OpenData (SODA API)
    # ------------------------------------------------------------------

    def _fetch_nyc_opendata(self) -> list[RawLead]:
        """Query PLUTO for large commercial properties via SODA API."""
        try:
            land_use_filter = " OR ".join(
                f"landuse='{code}'" for code in COMMERCIAL_LAND_USE
            )
            params: dict[str, str] = {
                "$where": f"({land_use_filter}) AND lotarea > {MIN_SQFT}",
                "$limit": str(PAGE_SIZE),
                "$order": "lotarea DESC",
            }
            token = self._settings.nyc_opendata_app_token
            if token:
                params["$$app_token"] = token
            else:
                logger.warning(
                    "NYC_OPENDATA_APP_TOKEN not set — requests may be throttled"
                )

            resp = requests.get(PLUTO_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            records = resp.json()

            leads: list[RawLead] = []
            for rec in records:
                address = self._build_address(rec)
                owner = rec.get("ownername", "").strip()
                leads.append(
                    RawLead(
                        company_name=owner or "Unknown Owner",
                        source=self.name,
                        address=address,
                        raw_data={
                            "bbl": rec.get("bbl"),
                            "lot_area_sqft": rec.get("lotarea"),
                            "bldg_area_sqft": rec.get("bldgarea"),
                            "land_use": rec.get("landuse"),
                            "year_built": rec.get("yearbuilt"),
                            "num_floors": rec.get("numfloors"),
                            "zoning": rec.get("zonedist1"),
                            "borough": rec.get("borough"),
                        },
                    )
                )
            logger.info("NYC OpenData returned %d properties", len(leads))
            return leads
        except Exception:
            logger.exception("NYC OpenData query failed")
            return []

    @staticmethod
    def _build_address(rec: dict) -> str:
        parts = [
            rec.get("address", ""),
            rec.get("zipcode", ""),
        ]
        borough = rec.get("borough", "")
        if borough:
            parts.insert(1, f"Borough {borough}")
        return ", ".join(p for p in parts if p).strip(", ")

    # ------------------------------------------------------------------
    # LoopNet scraping
    # ------------------------------------------------------------------

    def _fetch_loopnet(self) -> list[RawLead]:
        """Best-effort scrape of LoopNet commercial listings."""
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
            resp = requests.get(
                LOOPNET_SEARCH_URL, headers=headers, timeout=30
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            leads: list[RawLead] = []
            for card in soup.select("article.placard"):
                title_el = card.select_one(".placard-header-title")
                addr_el = card.select_one(".placard-header-subtitle")
                size_el = card.select_one("[data-testid='annotatedValue']")

                company = (
                    title_el.get_text(strip=True) if title_el else "Unknown"
                )
                address = (
                    addr_el.get_text(strip=True) if addr_el else ""
                )
                raw: dict = {}
                if size_el:
                    raw["listed_size"] = size_el.get_text(strip=True)

                link_el = card.select_one("a[href]")
                website = ""
                if link_el and link_el.get("href"):
                    website = "https://www.loopnet.com" + link_el["href"]

                leads.append(
                    RawLead(
                        company_name=company,
                        source=self.name,
                        address=address,
                        website=website,
                        raw_data=raw,
                    )
                )
            logger.info("LoopNet returned %d listings", len(leads))
            return leads
        except Exception:
            logger.exception("LoopNet scrape failed — may be blocked")
            return []
