"""LinkedInAgent — search for CRE decision-makers on LinkedIn."""

from __future__ import annotations

import logging
import time

import requests

from agents.base import BaseSourceAgent
from config.settings import Settings
from core.models import PipelineContext, RawLead

logger = logging.getLogger(__name__)

# Rate limiting
MAX_PROFILES_PER_RUN = 50
DELAY_BETWEEN_REQUESTS = 2.0  # seconds

# Target titles for CRE companies
TARGET_TITLES: list[str] = [
    "Property Manager",
    "IT Director",
    "Chief Technology Officer",
    "Director of Operations",
    "VP of Technology",
    "Building Manager",
    "Facilities Manager",
    "Director of IT",
    "Chief Operating Officer",
    "Head of Real Estate Technology",
]

# LinkedIn Voyager API (unofficial, reverse-engineered)
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/voyager/api/search/dash/clusters"


class LinkedInAgent(BaseSourceAgent):
    """Search LinkedIn for property managers and IT directors at CRE companies."""

    name = "linkedin"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._session: requests.Session | None = None

    def fetch(self, context: PipelineContext) -> list[RawLead]:
        email = self._settings.linkedin_email
        password = self._settings.linkedin_password

        if not email or not password:
            logger.warning(
                "LinkedIn credentials not configured — skipping. "
                "Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD to enable."
            )
            return []

        if not self._authenticate(email, password):
            logger.warning("LinkedIn authentication failed — skipping")
            return []

        leads: list[RawLead] = []
        companies = self._get_target_companies(context)

        for company in companies[:MAX_PROFILES_PER_RUN]:
            try:
                profiles = self._search_people(company)
                for profile in profiles:
                    leads.append(
                        RawLead(
                            company_name=company,
                            source=self.name,
                            contact_name=profile.get("name", ""),
                            contact_title=profile.get("title", ""),
                            website=profile.get("profile_url", ""),
                            raw_data={
                                "linkedin_profile": profile.get(
                                    "profile_url", ""
                                ),
                                "location": profile.get("location", ""),
                                "headline": profile.get("headline", ""),
                            },
                        )
                    )
                time.sleep(DELAY_BETWEEN_REQUESTS)
            except Exception:
                logger.exception(
                    "LinkedIn search failed for company %s", company
                )

            if len(leads) >= MAX_PROFILES_PER_RUN:
                break

        logger.info("LinkedIn returned %d profiles", len(leads))
        return leads

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self, email: str, password: str) -> bool:
        """Authenticate with LinkedIn and obtain session cookies."""
        try:
            self._session = requests.Session()
            self._session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36"
                    ),
                }
            )
            # Attempt login via LinkedIn's auth endpoint
            login_url = "https://www.linkedin.com/uas/authenticate"
            payload = {
                "session_key": email,
                "session_password": password,
                "loginCsrfParam": "",
            }
            resp = self._session.post(
                login_url, data=payload, timeout=15, allow_redirects=False
            )
            # Check if we got a session cookie
            if "li_at" in self._session.cookies.get_dict():
                logger.info("LinkedIn authentication successful")
                return True
            logger.warning(
                "LinkedIn auth: no session cookie (status=%d)", resp.status_code
            )
            return False
        except Exception:
            logger.exception("LinkedIn authentication error")
            return False

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search_people(self, company: str) -> list[dict[str, str]]:
        """Search LinkedIn for people matching target titles at a company."""
        if not self._session:
            return []

        profiles: list[dict[str, str]] = []
        titles_query = " OR ".join(f'"{t}"' for t in TARGET_TITLES[:5])
        keywords = f"{company} {titles_query}"

        try:
            params = {
                "decorationId": (
                    "com.linkedin.voyager.dash.deco.search"
                    ".SearchClusterCollection-174"
                ),
                "origin": "FACETED_SEARCH",
                "q": "all",
                "keywords": keywords,
                "start": "0",
                "count": "10",
            }
            headers = {
                "csrf-token": self._session.cookies.get("JSESSIONID", ""),
            }
            resp = self._session.get(
                LINKEDIN_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug(
                    "LinkedIn search returned %d for %s",
                    resp.status_code,
                    company,
                )
                return []

            data = resp.json()
            elements = (
                data.get("data", {})
                .get("searchDashClustersByAll", {})
                .get("elements", [])
            )

            for cluster in elements:
                for item in cluster.get("items", []):
                    entity = item.get("item", {}).get(
                        "entityResult", {}
                    )
                    if not entity:
                        continue
                    title_text = (
                        entity.get("primarySubtitle", {})
                        .get("text", "")
                    )
                    name_text = (
                        entity.get("title", {}).get("text", "")
                    )
                    profile_url = entity.get("navigationUrl", "")
                    location = (
                        entity.get("secondarySubtitle", {})
                        .get("text", "")
                    )
                    profiles.append(
                        {
                            "name": name_text,
                            "title": title_text,
                            "profile_url": profile_url,
                            "headline": title_text,
                            "location": location,
                        }
                    )
        except Exception:
            logger.exception("LinkedIn people search failed for %s", company)

        return profiles

    @staticmethod
    def _get_target_companies(context: PipelineContext) -> list[str]:
        """Extract unique company names from existing raw leads."""
        companies: list[str] = []
        seen: set[str] = set()
        for lead in context.raw_leads:
            key = lead.company_name.lower().strip()
            if key and key not in seen and key != "unknown owner":
                seen.add(key)
                companies.append(lead.company_name)
        return companies
