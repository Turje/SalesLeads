"""NewsAgent — Google News + industry RSS feeds for CRE intelligence."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import quote_plus

import requests

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# Google News RSS (no API key required)
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Industry RSS feeds
INDUSTRY_FEEDS: list[dict[str, str]] = [
    {
        "name": "Commercial Observer",
        "url": "https://commercialobserver.com/feed/",
    },
    {
        "name": "The Real Deal",
        "url": "https://therealdeal.com/feed/",
    },
    {
        "name": "Bisnow NYC",
        "url": "https://www.bisnow.com/feed/new-york",
    },
]

# Search queries for Google News
SEARCH_QUERIES: list[str] = [
    "commercial real estate NYC",
    "co-working NYC",
    "smart building technology NYC",
    "commercial property management NYC",
]

REQUEST_TIMEOUT = 20


class NewsAgent(BaseSourceAgent):
    """Gather CRE news from RSS feeds and Google News."""

    name = "news"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        leads: list[RawLead] = []
        leads.extend(self._fetch_google_news())
        leads.extend(self._fetch_industry_feeds())
        return leads

    # ------------------------------------------------------------------
    # Google News RSS
    # ------------------------------------------------------------------

    def _fetch_google_news(self) -> list[RawLead]:
        leads: list[RawLead] = []
        for query in SEARCH_QUERIES:
            try:
                url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
                items = self._parse_rss(url)
                for item in items:
                    leads.append(
                        RawLead(
                            company_name=self._extract_company(
                                item["title"]
                            ),
                            source=self.name,
                            website=item.get("link", ""),
                            raw_data={
                                "headline": item["title"],
                                "pub_date": item.get("pub_date", ""),
                                "feed_source": "google_news",
                                "query": query,
                            },
                        )
                    )
            except Exception:
                logger.exception("Google News RSS failed for query=%s", query)
        logger.info("Google News returned %d items total", len(leads))
        return leads

    # ------------------------------------------------------------------
    # Industry RSS feeds
    # ------------------------------------------------------------------

    def _fetch_industry_feeds(self) -> list[RawLead]:
        leads: list[RawLead] = []
        for feed in INDUSTRY_FEEDS:
            try:
                items = self._parse_rss(feed["url"])
                for item in items:
                    leads.append(
                        RawLead(
                            company_name=self._extract_company(
                                item["title"]
                            ),
                            source=self.name,
                            website=item.get("link", ""),
                            raw_data={
                                "headline": item["title"],
                                "pub_date": item.get("pub_date", ""),
                                "feed_source": feed["name"],
                            },
                        )
                    )
            except Exception:
                logger.exception(
                    "Industry feed %s failed", feed["name"]
                )
        logger.info("Industry feeds returned %d items total", len(leads))
        return leads

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _parse_rss(self, url: str) -> list[dict[str, str]]:
        """Fetch and parse an RSS 2.0 feed, return list of item dicts."""
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        items: list[dict[str, str]] = []
        for item_el in root.iter("item"):
            title_el = item_el.find("title")
            link_el = item_el.find("link")
            pub_el = item_el.find("pubDate")

            title = unescape(title_el.text or "") if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            pub_date = (pub_el.text or "").strip() if pub_el is not None else ""

            if title:
                items.append(
                    {"title": title, "link": link, "pub_date": pub_date}
                )
        return items

    @staticmethod
    def _extract_company(headline: str) -> str:
        """Best-effort company name extraction from a headline.

        Heuristic: take text before the first dash, colon, or pipe.
        """
        for sep in (" - ", " | ", ": "):
            if sep in headline:
                return headline.split(sep, 1)[0].strip()
        # Fall back to first 80 chars of the headline
        return headline[:80].strip()
