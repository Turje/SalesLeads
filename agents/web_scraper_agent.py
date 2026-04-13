"""WebScraperAgent — scrape company websites for contact info and tech signals."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Subpages to look for
CONTACT_PATHS = ["/contact", "/contact-us", "/about/contact", "/get-in-touch"]
ABOUT_PATHS = ["/about", "/about-us", "/company", "/who-we-are"]

# Patterns for extraction
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")

# Tech-signal keywords found in meta tags, scripts, or page text
TECH_SIGNALS: list[str] = [
    "hubspot",
    "salesforce",
    "zendesk",
    "intercom",
    "marketo",
    "pardot",
    "mailchimp",
    "google-analytics",
    "segment",
    "drift",
    "slack",
    "microsoft-365",
    "aws",
    "azure",
    "google-cloud",
    "cloudflare",
    "wordpress",
    "shopify",
]


class WebScraperAgent(BaseSourceAgent):
    """Scrape company websites for contact details and technology signals."""

    name = "web_scraper"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        """Process company URLs from context.raw_leads that have websites."""
        leads: list[RawLead] = []
        urls_seen: set[str] = set()

        for existing_lead in context.raw_leads:
            url = existing_lead.website
            if not url or url in urls_seen:
                continue
            urls_seen.add(url)
            try:
                enriched = self._scrape_site(url, existing_lead.company_name)
                if enriched:
                    leads.append(enriched)
            except Exception:
                logger.exception("Failed to scrape %s", url)

        logger.info("WebScraper processed %d sites", len(leads))
        return leads

    # ------------------------------------------------------------------
    # Core scraping logic
    # ------------------------------------------------------------------

    def _scrape_site(self, base_url: str, company_name: str) -> RawLead | None:
        """Scrape a company's website for contact info and tech signals."""
        parsed = urlparse(base_url)
        if not parsed.scheme:
            base_url = f"https://{base_url}"

        # Fetch the homepage
        homepage_soup = self._get_page(base_url)
        if homepage_soup is None:
            return None

        # Collect data from homepage
        emails: set[str] = set()
        phones: set[str] = set()
        tech: set[str] = set()

        self._extract_contacts(homepage_soup, emails, phones)
        self._extract_tech_signals(homepage_soup, base_url, tech)

        # Try contact pages
        for path in CONTACT_PATHS:
            contact_url = urljoin(base_url, path)
            soup = self._get_page(contact_url)
            if soup:
                self._extract_contacts(soup, emails, phones)

        # Try about pages
        about_text = ""
        for path in ABOUT_PATHS:
            about_url = urljoin(base_url, path)
            soup = self._get_page(about_url)
            if soup:
                self._extract_contacts(soup, emails, phones)
                body = soup.find("main") or soup.find("body")
                if body:
                    about_text = body.get_text(separator=" ", strip=True)[:1000]
                break

        # Filter out common no-reply addresses
        emails = {
            e for e in emails
            if not e.startswith(("noreply", "no-reply", "mailer-daemon"))
        }

        return RawLead(
            company_name=company_name,
            source=self.name,
            email=next(iter(emails), None),
            phone=next(iter(phones), None),
            website=base_url,
            raw_data={
                "all_emails": sorted(emails),
                "all_phones": sorted(phones),
                "tech_signals": sorted(tech),
                "about_snippet": about_text[:500],
                "domain": urlparse(base_url).netloc,
            },
        )

    def _get_page(self, url: str) -> BeautifulSoup | None:
        """Fetch a URL and return parsed soup, or None on failure."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            return BeautifulSoup(resp.text, "lxml")
        except Exception:
            return None

    @staticmethod
    def _extract_contacts(
        soup: BeautifulSoup,
        emails: set[str],
        phones: set[str],
    ) -> None:
        """Pull emails and phone numbers from page text."""
        text = soup.get_text()
        emails.update(EMAIL_RE.findall(text))
        phones.update(PHONE_RE.findall(text))

        # Also check mailto: links
        for a_tag in soup.select("a[href^='mailto:']"):
            href = a_tag.get("href", "")
            addr = href.replace("mailto:", "").split("?")[0].strip()
            if addr:
                emails.add(addr)

        # Also check tel: links
        for a_tag in soup.select("a[href^='tel:']"):
            href = a_tag.get("href", "")
            phone = href.replace("tel:", "").strip()
            if phone:
                phones.add(phone)

    @staticmethod
    def _extract_tech_signals(
        soup: BeautifulSoup,
        base_url: str,
        tech: set[str],
    ) -> None:
        """Detect technology stack from meta tags, scripts, etc."""
        page_html = str(soup).lower()

        for signal in TECH_SIGNALS:
            if signal in page_html:
                tech.add(signal)

        # Check meta generator tag
        gen = soup.find("meta", attrs={"name": "generator"})
        if gen and gen.get("content"):
            tech.add(f"generator:{gen['content'].strip()}")
