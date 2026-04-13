"""LeadPlatformAgent — Apollo.io + Hunter.io for decision-maker discovery."""

from __future__ import annotations

import logging
import time

import requests

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# Apollo.io API
APOLLO_SEARCH_URL = "https://api.apollo.io/v1/mixed_people/search"
# Hunter.io API
HUNTER_DOMAIN_URL = "https://api.hunter.io/v2/domain-search"

# CRE-related industry keywords for Apollo search
CRE_INDUSTRIES = [
    "commercial real estate",
    "property management",
    "real estate investment",
    "co-working",
]

TARGET_TITLES = [
    "IT Director",
    "CTO",
    "VP Technology",
    "Director of Operations",
    "Facilities Manager",
    "Property Manager",
]

DELAY_BETWEEN_REQUESTS = 1.0  # seconds
MAX_RESULTS_PER_SOURCE = 100


class LeadPlatformAgent(BaseSourceAgent):
    """Use Apollo.io and Hunter.io to find decision-makers at CRE companies."""

    name = "lead_platform"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        leads: list[RawLead] = []
        leads.extend(self._fetch_apollo())
        leads.extend(self._fetch_hunter(context))
        return leads

    # ------------------------------------------------------------------
    # Apollo.io
    # ------------------------------------------------------------------

    def _fetch_apollo(self) -> list[RawLead]:
        api_key = self._settings.apollo_api_key
        if not api_key:
            logger.warning(
                "APOLLO_API_KEY not set — skipping Apollo.io search"
            )
            return []

        leads: list[RawLead] = []
        try:
            payload = {
                "api_key": api_key,
                "q_organization_keyword_tags": CRE_INDUSTRIES,
                "person_titles": TARGET_TITLES,
                "person_locations": ["New York, NY"],
                "page": 1,
                "per_page": min(MAX_RESULTS_PER_SOURCE, 100),
            }
            resp = requests.post(
                APOLLO_SEARCH_URL, json=payload, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            people = data.get("people", [])
            for person in people:
                org = person.get("organization", {})
                leads.append(
                    RawLead(
                        company_name=org.get("name", "Unknown"),
                        source=self.name,
                        contact_name=person.get("name", ""),
                        contact_title=person.get("title", ""),
                        email=person.get("email"),
                        phone=person.get("phone_number"),
                        website=org.get("website_url"),
                        raw_data={
                            "platform": "apollo",
                            "apollo_id": person.get("id"),
                            "linkedin_url": person.get("linkedin_url"),
                            "org_industry": org.get("industry"),
                            "org_size": org.get("estimated_num_employees"),
                            "org_city": org.get("city"),
                            "seniority": person.get("seniority"),
                        },
                    )
                )
            logger.info("Apollo.io returned %d people", len(leads))
        except Exception:
            logger.exception("Apollo.io search failed")

        return leads

    # ------------------------------------------------------------------
    # Hunter.io — email discovery for domains from context
    # ------------------------------------------------------------------

    def _fetch_hunter(self, context: PipelineContext) -> list[RawLead]:
        api_key = self._settings.hunter_api_key
        if not api_key:
            logger.warning(
                "HUNTER_API_KEY not set — skipping Hunter.io search"
            )
            return []

        # Collect unique domains from existing leads
        domains = self._extract_domains(context)
        if not domains:
            logger.info("No domains to look up on Hunter.io")
            return []

        leads: list[RawLead] = []
        for domain in domains[:MAX_RESULTS_PER_SOURCE]:
            try:
                params = {
                    "domain": domain,
                    "api_key": api_key,
                    "limit": "10",
                    "type": "personal",
                }
                resp = requests.get(
                    HUNTER_DOMAIN_URL, params=params, timeout=15
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})

                org_name = data.get("organization", domain)
                emails_list = data.get("emails", [])

                for entry in emails_list:
                    name_parts = [
                        entry.get("first_name", ""),
                        entry.get("last_name", ""),
                    ]
                    full_name = " ".join(p for p in name_parts if p)

                    leads.append(
                        RawLead(
                            company_name=org_name,
                            source=self.name,
                            contact_name=full_name or None,
                            contact_title=entry.get("position"),
                            email=entry.get("value"),
                            phone=entry.get("phone_number"),
                            website=f"https://{domain}",
                            raw_data={
                                "platform": "hunter",
                                "domain": domain,
                                "confidence": entry.get("confidence"),
                                "department": entry.get("department"),
                                "linkedin": entry.get("linkedin"),
                                "sources_count": entry.get("sources"),
                            },
                        )
                    )
                time.sleep(DELAY_BETWEEN_REQUESTS)
            except Exception:
                logger.exception("Hunter.io lookup failed for %s", domain)

        logger.info("Hunter.io returned %d contacts", len(leads))
        return leads

    @staticmethod
    def _extract_domains(context: PipelineContext) -> list[str]:
        """Extract unique domains from existing raw lead websites."""
        domains: list[str] = []
        seen: set[str] = set()
        for lead in context.raw_leads:
            if not lead.website:
                continue
            # Strip protocol and path
            domain = lead.website.split("//")[-1].split("/")[0].lower()
            # Skip common non-company domains
            skip = {
                "loopnet.com",
                "google.com",
                "linkedin.com",
                "facebook.com",
                "twitter.com",
            }
            if domain and domain not in seen and domain not in skip:
                seen.add(domain)
                domains.append(domain)
        return domains
