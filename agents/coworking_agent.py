"""CoworkingAgent — scrape coworking directory listings for NYC."""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# Coworking directories to scrape
DIRECTORIES: list[dict[str, str]] = [
    {
        "name": "Coworker.com",
        "url": "https://www.coworker.com/united-states/new-york/new-york-city",
        "card_selector": ".space-card",
        "name_selector": ".space-card__title",
        "address_selector": ".space-card__address",
        "operator_selector": ".space-card__brand",
    },
    {
        "name": "LiquidSpace",
        "url": "https://liquidspace.com/Search/New-York--NY",
        "card_selector": ".venue-card",
        "name_selector": ".venue-card-title",
        "address_selector": ".venue-card-address",
        "operator_selector": ".venue-card-host",
    },
]

REQUEST_TIMEOUT = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Simple regex patterns to find contact info on pages
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
PHONE_RE = re.compile(
    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
)


class CoworkingAgent(BaseSourceAgent):
    """Scrape coworking directories for NYC spaces."""

    name = "coworking"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        leads: list[RawLead] = []
        for directory in DIRECTORIES:
            try:
                leads.extend(self._scrape_directory(directory))
            except Exception:
                logger.exception(
                    "Failed to scrape directory %s", directory["name"]
                )
        return leads

    def _scrape_directory(self, directory: dict[str, str]) -> list[RawLead]:
        """Scrape a single coworking directory page."""
        resp = requests.get(
            directory["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        leads: list[RawLead] = []
        cards = soup.select(directory["card_selector"])

        for card in cards:
            name_el = card.select_one(directory["name_selector"])
            addr_el = card.select_one(directory["address_selector"])
            operator_el = card.select_one(directory["operator_selector"])

            space_name = name_el.get_text(strip=True) if name_el else "Unknown"
            operator = (
                operator_el.get_text(strip=True) if operator_el else ""
            )
            address = addr_el.get_text(strip=True) if addr_el else ""

            # Prefer operator as company_name, fall back to space name
            company = operator or space_name

            # Extract link if present
            link_el = card.select_one("a[href]")
            website = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    href = directory["url"].split("/", 3)[:3]
                    href = "/".join(href) + link_el["href"]
                website = href

            # Try to pull contact info from the card text
            card_text = card.get_text()
            emails = EMAIL_RE.findall(card_text)
            phones = PHONE_RE.findall(card_text)

            leads.append(
                RawLead(
                    company_name=company,
                    source=self.name,
                    address=address,
                    website=website if isinstance(website, str) else "",
                    email=emails[0] if emails else None,
                    phone=phones[0] if phones else None,
                    raw_data={
                        "space_name": space_name,
                        "operator": operator,
                        "directory": directory["name"],
                    },
                )
            )

        logger.info(
            "%s returned %d spaces", directory["name"], len(leads)
        )
        return leads
