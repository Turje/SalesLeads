"""EnrichmentAgent — merge, score, and qualify leads using LLM + rules."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

from config.settings import Settings
from core.llm_client import LLMClient, LLMError
from core.models import EnrichedLead, PipelineContext, RawLead

logger = logging.getLogger(__name__)

# Scoring weights for rule-based fallback
SCORE_WEIGHTS = {
    "has_email": 10,
    "has_phone": 8,
    "has_address": 5,
    "has_website": 5,
    "has_contact_name": 7,
    "has_contact_title": 5,
    "multi_source": 15,  # per extra source beyond the first
    "has_tech_signals": 10,
    "has_news": 8,
    "has_permit_activity": 12,
    "has_recent_sale": 10,
    "is_coworking": 5,
    "large_sqft": 10,
}

LLM_SYSTEM_PROMPT = """\
You are a B2B sales intelligence analyst for a managed IT services company \
targeting commercial real estate operators in NYC.

Given raw lead data, produce a JSON object with these fields:
- company_type: one of "CRE_OPERATOR", "COWORKING", "MULTI_TENANT", "OTHER"
- building_type: e.g. "Class A Office", "Flex Space", "Mixed-Use"
- score: 0-100 qualification score (higher = better fit for managed IT services)
- qualification_notes: 2-3 sentences explaining the score

Respond ONLY with valid JSON. No markdown, no explanation outside JSON.\
"""

LLM_USER_TEMPLATE = """\
Evaluate this lead for managed IT services sales potential:

Company: {company_name}
Contact: {contact_name} ({contact_title})
Address: {address}
Email: {email}
Sources: {sources}
Signals: {signals}
Raw data: {raw_data}
"""


class EnrichmentAgent:
    """Merge multi-source RawLeads into scored EnrichedLeads.

    This is NOT a BaseSourceAgent subclass — it runs after all source
    agents have completed to build unified lead profiles.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._llm: LLMClient | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich(
        self,
        raw_leads: list[RawLead],
        context: PipelineContext,
    ) -> list[EnrichedLead]:
        """Merge, deduplicate, score, and qualify raw leads.

        Returns a list of EnrichedLead objects sorted by score descending.
        """
        # Step 1: group raw leads by normalized company name
        grouped = self._group_leads(raw_leads)

        # Step 2: attempt LLM-based enrichment, fall back to rules
        llm_available = self._init_llm()

        enriched: list[EnrichedLead] = []
        for company_key, leads in grouped.items():
            try:
                merged = self._merge_leads(leads)
                if llm_available:
                    try:
                        merged = self._llm_enrich(merged, leads)
                    except (LLMError, Exception):
                        logger.warning(
                            "LLM enrichment failed for %s — using rules",
                            merged.company_name,
                        )
                        merged = self._rule_based_score(merged, leads)
                else:
                    merged = self._rule_based_score(merged, leads)
                enriched.append(merged)
            except Exception:
                logger.exception(
                    "Enrichment failed for group %s", company_key
                )

        # Sort by score descending
        enriched.sort(key=lambda e: e.score, reverse=True)
        logger.info(
            "Enrichment produced %d leads (LLM=%s) [run=%s]",
            len(enriched),
            "yes" if llm_available else "no",
            context.run_id[:8],
        )
        return enriched

    # ------------------------------------------------------------------
    # LLM initialization
    # ------------------------------------------------------------------

    def _init_llm(self) -> bool:
        """Try to connect to Ollama.  Returns True if available."""
        if self._llm is not None:
            return self._llm.is_available()
        try:
            self._llm = LLMClient(
                base_url=self._settings.ollama_base_url,
                model=self._settings.ollama_model,
            )
            if self._llm.is_available():
                logger.info("LLM client connected for enrichment")
                return True
            logger.info("LLM not available — will use rule-based scoring")
            return False
        except Exception:
            logger.info("LLM init failed — will use rule-based scoring")
            return False

    # ------------------------------------------------------------------
    # Grouping & merging
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_key(name: str) -> str:
        """Normalize company name for grouping."""
        key = name.lower().strip()
        # Remove common suffixes
        for suffix in (" llc", " inc", " corp", " ltd", " co", " lp"):
            if key.endswith(suffix):
                key = key[: -len(suffix)]
        # Collapse whitespace
        key = re.sub(r"\s+", " ", key).strip()
        return key

    def _group_leads(
        self, raw_leads: list[RawLead]
    ) -> dict[str, list[RawLead]]:
        """Group raw leads by normalized company name."""
        groups: dict[str, list[RawLead]] = defaultdict(list)
        for lead in raw_leads:
            key = self._normalize_key(lead.company_name)
            if key and key not in ("unknown", "unknown owner"):
                groups[key].append(lead)
        return dict(groups)

    @staticmethod
    def _merge_leads(leads: list[RawLead]) -> EnrichedLead:
        """Merge multiple RawLeads into a single EnrichedLead."""
        # Use the first non-empty value for each field
        company_name = ""
        contact_name = ""
        contact_title = ""
        email = None
        phone = None
        website = None
        address = ""
        sources: list[str] = []
        tech_signals: list[str] = []
        recent_news: list[str] = []
        sqft = None

        for lead in leads:
            if not company_name and lead.company_name:
                company_name = lead.company_name
            if not contact_name and lead.contact_name:
                contact_name = lead.contact_name
            if not contact_title and lead.contact_title:
                contact_title = lead.contact_title
            if not email and lead.email:
                email = lead.email
            if not phone and lead.phone:
                phone = lead.phone
            if not website and lead.website:
                website = lead.website
            if not address and lead.address:
                address = lead.address

            if lead.source not in sources:
                sources.append(lead.source)

            # Extract tech signals and news from raw_data
            raw = lead.raw_data
            if "tech_signals" in raw:
                tech_signals.extend(raw["tech_signals"])
            if "headline" in raw:
                recent_news.append(raw["headline"])

            # Extract square footage
            for key in ("lot_area_sqft", "bldg_area_sqft", "gross_sqft"):
                if key in raw and raw[key]:
                    try:
                        val = int(float(str(raw[key])))
                        if sqft is None or val > sqft:
                            sqft = val
                    except (ValueError, TypeError):
                        pass

        return EnrichedLead(
            company_name=company_name,
            contact_name=contact_name or "",
            contact_title=contact_title or "",
            email=email,
            phone=phone,
            website=website,
            address=address,
            sources=sources,
            tech_signals=sorted(set(tech_signals)),
            recent_news=recent_news[:5],
            sqft=sqft,
        )

    # ------------------------------------------------------------------
    # LLM enrichment
    # ------------------------------------------------------------------

    def _llm_enrich(
        self, lead: EnrichedLead, raw_leads: list[RawLead]
    ) -> EnrichedLead:
        """Use LLM to classify, score, and qualify the lead."""
        if self._llm is None:
            raise LLMError("LLM not initialized")

        # Build combined raw_data summary
        raw_summary: dict = {}
        for rl in raw_leads:
            for k, v in rl.raw_data.items():
                if v and k not in raw_summary:
                    raw_summary[k] = v

        prompt = LLM_USER_TEMPLATE.format(
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            contact_title=lead.contact_title,
            address=lead.address,
            email=lead.email or "N/A",
            sources=", ".join(lead.sources),
            signals=", ".join(lead.tech_signals) or "none detected",
            raw_data=json.dumps(raw_summary, default=str)[:1500],
        )

        response = self._llm.generate(prompt=prompt, system=LLM_SYSTEM_PROMPT)

        # Parse JSON from response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]

        parsed = json.loads(content)

        lead.company_type = parsed.get("company_type", lead.company_type)
        lead.building_type = parsed.get("building_type", lead.building_type)
        lead.score = max(0, min(100, int(parsed.get("score", 0))))
        lead.qualification_notes = parsed.get(
            "qualification_notes", ""
        )

        return lead

    # ------------------------------------------------------------------
    # Rule-based scoring fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_based_score(
        lead: EnrichedLead, raw_leads: list[RawLead]
    ) -> EnrichedLead:
        """Score lead using deterministic rules when LLM is unavailable."""
        score = 0

        if lead.email:
            score += SCORE_WEIGHTS["has_email"]
        if lead.phone:
            score += SCORE_WEIGHTS["has_phone"]
        if lead.address:
            score += SCORE_WEIGHTS["has_address"]
        if lead.website:
            score += SCORE_WEIGHTS["has_website"]
        if lead.contact_name:
            score += SCORE_WEIGHTS["has_contact_name"]
        if lead.contact_title:
            score += SCORE_WEIGHTS["has_contact_title"]
        if lead.tech_signals:
            score += SCORE_WEIGHTS["has_tech_signals"]
        if lead.recent_news:
            score += SCORE_WEIGHTS["has_news"]

        # Multi-source bonus
        extra_sources = max(0, len(lead.sources) - 1)
        score += extra_sources * SCORE_WEIGHTS["multi_source"]

        # Check for permit activity or recent sale in raw_data
        for rl in raw_leads:
            if rl.raw_data.get("record_type") == "building_permit":
                score += SCORE_WEIGHTS["has_permit_activity"]
                break
        for rl in raw_leads:
            if rl.raw_data.get("signal_type") == "recent_sale":
                score += SCORE_WEIGHTS["has_recent_sale"]
                break

        # Coworking bonus
        for rl in raw_leads:
            if rl.source == "coworking":
                score += SCORE_WEIGHTS["is_coworking"]
                lead.company_type = "COWORKING"
                break

        # Large property bonus
        if lead.sqft and lead.sqft > 50_000:
            score += SCORE_WEIGHTS["large_sqft"]

        lead.score = min(100, score)

        # Generate qualification notes
        notes_parts: list[str] = []
        if len(lead.sources) > 1:
            notes_parts.append(
                f"Found across {len(lead.sources)} sources ({', '.join(lead.sources)})"
            )
        if lead.tech_signals:
            notes_parts.append(
                f"Tech signals: {', '.join(lead.tech_signals[:3])}"
            )
        if lead.sqft:
            notes_parts.append(f"Property size: {lead.sqft:,} sqft")
        lead.qualification_notes = ". ".join(notes_parts) or "Basic lead profile"

        return lead
