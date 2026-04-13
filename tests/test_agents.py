"""Tests for all SalesLeads agents."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.base import BaseSourceAgent
from agents.coworking_agent import CoworkingAgent
from agents.enrichment_agent import EnrichmentAgent
from agents.lead_platform_agent import LeadPlatformAgent
from agents.linkedin_agent import LinkedInAgent
from agents.marketplace_agent import MarketplaceAgent
from agents.news_agent import NewsAgent
from agents.property_db_agent import PropertyDBAgent
from agents.public_records_agent import PublicRecordsAgent
from agents.web_scraper_agent import WebScraperAgent
from core.models import EnrichedLead, PipelineContext, RawLead


# ======================================================================
# BaseSourceAgent tests
# ======================================================================


class TestBaseSourceAgent:
    """Tests for __init_subclass__ enforcement and _safe_fetch."""

    def test_subclass_without_name_raises(self):
        """Subclass that omits 'name' should raise TypeError."""
        with pytest.raises(TypeError, match="must define a class-level 'name'"):

            class BadAgent(BaseSourceAgent):
                def fetch(self, context):
                    return []

    def test_subclass_with_empty_name_raises(self):
        """Subclass with name='' should raise TypeError."""
        with pytest.raises(TypeError, match="must define a class-level 'name'"):

            class EmptyNameAgent(BaseSourceAgent):
                name = ""

                def fetch(self, context):
                    return []

    def test_subclass_with_non_string_name_raises(self):
        """Subclass with name=123 should raise TypeError."""
        with pytest.raises(TypeError, match="must define a class-level 'name'"):

            class IntNameAgent(BaseSourceAgent):
                name = 123  # type: ignore[assignment]

                def fetch(self, context):
                    return []

    def test_subclass_with_valid_name_succeeds(self):
        """Subclass with a proper string name should be created fine."""

        class GoodAgent(BaseSourceAgent):
            name = "test_good"

            def fetch(self, context):
                return []

        agent = GoodAgent()
        assert agent.name == "test_good"

    def test_safe_fetch_returns_leads_on_success(self):
        """_safe_fetch should return what fetch returns on success."""

        class OkAgent(BaseSourceAgent):
            name = "test_ok"

            def fetch(self, context):
                return [
                    RawLead(company_name="Acme Corp", source=self.name)
                ]

        agent = OkAgent()
        ctx = PipelineContext.new()
        result = agent._safe_fetch(ctx)
        assert len(result) == 1
        assert result[0].company_name == "Acme Corp"

    def test_safe_fetch_catches_exceptions(self):
        """_safe_fetch should catch any exception and return []."""

        class BrokenAgent(BaseSourceAgent):
            name = "test_broken"

            def fetch(self, context):
                raise RuntimeError("network down")

        agent = BrokenAgent()
        ctx = PipelineContext.new()
        result = agent._safe_fetch(ctx)
        assert result == []

    def test_safe_fetch_catches_keyboard_interrupt(self):
        """_safe_fetch should even catch BaseException subclasses like KeyboardInterrupt.

        Note: _safe_fetch catches Exception, so KeyboardInterrupt would propagate.
        This test documents that behavior — KeyboardInterrupt is NOT caught.
        """

        class InterruptAgent(BaseSourceAgent):
            name = "test_interrupt"

            def fetch(self, context):
                raise KeyboardInterrupt()

        agent = InterruptAgent()
        ctx = PipelineContext.new()
        with pytest.raises(KeyboardInterrupt):
            agent._safe_fetch(ctx)


# ======================================================================
# Helper: mock responses
# ======================================================================


def _mock_response(json_data=None, text="", status_code=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or []
    resp.text = text
    resp.content = text.encode("utf-8") if text else b""
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def _make_settings(**overrides):
    """Build a Settings with sensible test defaults."""
    defaults = {
        "nyc_opendata_app_token": "test_token",
        "apollo_api_key": "",
        "hunter_api_key": "",
        "linkedin_email": "",
        "linkedin_password": "",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3",
    }
    defaults.update(overrides)
    settings = MagicMock()
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


# ======================================================================
# PropertyDBAgent tests
# ======================================================================


class TestPropertyDBAgent:

    @patch("agents.property_db_agent.requests.get")
    def test_fetch_returns_raw_leads(self, mock_get):
        """PropertyDBAgent should return list[RawLead] from OpenData."""
        pluto_data = [
            {
                "ownername": "ACME REALTY LLC",
                "address": "100 BROADWAY",
                "zipcode": "10001",
                "borough": "1",
                "bbl": "1001230045",
                "lotarea": "25000",
                "bldgarea": "100000",
                "landuse": "05",
                "yearbuilt": "1985",
                "numfloors": "20",
                "zonedist1": "C6-4",
            },
        ]
        # First call = OpenData, second call = LoopNet (fail gracefully)
        mock_get.side_effect = [
            _mock_response(json_data=pluto_data),
            _mock_response(status_code=403),
        ]

        agent = PropertyDBAgent(settings=_make_settings())
        ctx = PipelineContext.new()
        leads = agent.fetch(ctx)

        assert len(leads) >= 1
        assert isinstance(leads[0], RawLead)
        assert leads[0].company_name == "ACME REALTY LLC"
        assert leads[0].source == "property_db"
        assert leads[0].raw_data["lot_area_sqft"] == "25000"

    @patch("agents.property_db_agent.requests.get")
    def test_fetch_handles_api_failure(self, mock_get):
        """Should return [] if both sources fail."""
        mock_get.side_effect = Exception("connection timeout")

        agent = PropertyDBAgent(settings=_make_settings())
        ctx = PipelineContext.new()
        leads = agent.fetch(ctx)
        assert leads == []


# ======================================================================
# PublicRecordsAgent tests
# ======================================================================


class TestPublicRecordsAgent:

    @patch("agents.public_records_agent.requests.get")
    def test_fetch_returns_raw_leads(self, mock_get):
        """PublicRecordsAgent returns permits and transfers as RawLeads."""
        acris_data = [
            {
                "document_id": "DOC001",
                "good_through_date": "2026-03-01",
                "property_type": "CR",
                "street_number": "200",
                "street_name": "PARK AVE",
                "borough": "1",
                "block": "1234",
                "lot": "56",
            },
        ]
        parties_data = [
            {"document_id": "DOC001", "party_type": "2", "name": "NYC PROP LLC"},
        ]
        dob_data = [
            {
                "owner_name": "METRO HOLDINGS",
                "applicant_name": "John Smith",
                "house_number": "50",
                "street_name": "WALL ST",
                "borough": "MANHATTAN",
                "zip_code": "10005",
                "job_number": "J001",
                "job_type": "A1",
                "permit_type": "EW",
                "job_description": "RENOVATION",
                "issuance_date": "2026-02-15",
            },
        ]

        mock_get.side_effect = [
            _mock_response(json_data=acris_data),
            _mock_response(json_data=parties_data),
            _mock_response(json_data=dob_data),
        ]

        agent = PublicRecordsAgent(settings=_make_settings())
        ctx = PipelineContext.new()
        leads = agent.fetch(ctx)

        assert len(leads) == 2
        assert all(isinstance(l, RawLead) for l in leads)
        assert leads[0].company_name == "NYC PROP LLC"
        assert leads[0].source == "public_records"
        assert leads[1].company_name == "METRO HOLDINGS"
        assert leads[1].contact_name == "John Smith"

    @patch("agents.public_records_agent.requests.get")
    def test_fetch_handles_failure(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        agent = PublicRecordsAgent(settings=_make_settings())
        leads = agent.fetch(PipelineContext.new())
        assert leads == []


# ======================================================================
# NewsAgent tests
# ======================================================================


RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Brookfield Acquires NYC Tower - Commercial Observer</title>
      <link>https://example.com/article1</link>
      <pubDate>Mon, 10 Mar 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>WeWork Opens New Location | The Real Deal</title>
      <link>https://example.com/article2</link>
      <pubDate>Tue, 11 Mar 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class TestNewsAgent:

    @patch("agents.news_agent.requests.get")
    def test_fetch_parses_rss(self, mock_get):
        """NewsAgent should parse RSS XML into RawLeads."""
        mock_get.return_value = _mock_response(text=RSS_XML)

        agent = NewsAgent(settings=_make_settings())
        ctx = PipelineContext.new()
        leads = agent.fetch(ctx)

        assert len(leads) > 0
        assert all(isinstance(l, RawLead) for l in leads)
        assert all(l.source == "news" for l in leads)
        # Check company extraction from headline
        headlines = [l.raw_data["headline"] for l in leads]
        assert any("Brookfield" in h for h in headlines)

    @patch("agents.news_agent.requests.get")
    def test_fetch_handles_bad_rss(self, mock_get):
        """Should handle invalid RSS gracefully."""
        mock_get.return_value = _mock_response(text="<html>not rss</html>")

        agent = NewsAgent(settings=_make_settings())
        leads = agent.fetch(PipelineContext.new())
        # Should not crash — returns whatever it can parse (possibly [])
        assert isinstance(leads, list)


# ======================================================================
# CoworkingAgent tests
# ======================================================================


COWORKING_HTML = """\
<html><body>
<article class="space-card">
  <h3 class="space-card__title">WeWork Midtown</h3>
  <span class="space-card__address">100 W 33rd St, New York</span>
  <span class="space-card__brand">WeWork</span>
  <a href="/spaces/wework-midtown">View</a>
</article>
<article class="space-card">
  <h3 class="space-card__title">Industrious FiDi</h3>
  <span class="space-card__address">1 Liberty Plaza, New York</span>
  <span class="space-card__brand">Industrious</span>
  <a href="/spaces/industrious-fidi">View</a>
</article>
</body></html>
"""


class TestCoworkingAgent:

    @patch("agents.coworking_agent.requests.get")
    def test_fetch_scrapes_listings(self, mock_get):
        """CoworkingAgent should parse HTML listings into RawLeads."""
        mock_get.return_value = _mock_response(text=COWORKING_HTML)

        agent = CoworkingAgent(settings=_make_settings())
        ctx = PipelineContext.new()
        leads = agent.fetch(ctx)

        assert len(leads) >= 2
        assert all(isinstance(l, RawLead) for l in leads)
        assert all(l.source == "coworking" for l in leads)
        names = [l.company_name for l in leads]
        assert "WeWork" in names
        assert "Industrious" in names

    @patch("agents.coworking_agent.requests.get")
    def test_fetch_handles_empty_page(self, mock_get):
        """Should return [] for pages with no matching cards."""
        mock_get.return_value = _mock_response(text="<html><body></body></html>")

        agent = CoworkingAgent(settings=_make_settings())
        leads = agent.fetch(PipelineContext.new())
        assert leads == []


# ======================================================================
# WebScraperAgent tests
# ======================================================================


CONTACT_HTML = """\
<html><body>
<main>
  <p>Contact us at info@acmerealty.com or call (212) 555-1234</p>
  <a href="mailto:sales@acmerealty.com">Email Sales</a>
</main>
</body></html>
"""

HOMEPAGE_HTML = """\
<html><head>
<meta name="generator" content="WordPress 6.4">
<script src="https://js.hubspot.com/analytics.js"></script>
</head><body>
<p>Welcome to ACME Realty</p>
</body></html>
"""


class TestWebScraperAgent:

    @patch("agents.web_scraper_agent.requests.get")
    def test_fetch_extracts_contacts(self, mock_get):
        """WebScraperAgent should extract emails and phones from websites."""
        # Homepage -> contact pages -> about pages
        mock_get.return_value = _mock_response(text=CONTACT_HTML)

        ctx = PipelineContext.new()
        ctx.raw_leads = [
            RawLead(
                company_name="ACME Realty",
                source="property_db",
                website="https://www.acmerealty.com",
            ),
        ]

        agent = WebScraperAgent(settings=_make_settings())
        leads = agent.fetch(ctx)

        assert len(leads) == 1
        assert isinstance(leads[0], RawLead)
        assert leads[0].source == "web_scraper"
        assert leads[0].email is not None
        assert "acmerealty.com" in leads[0].email

    @patch("agents.web_scraper_agent.requests.get")
    def test_fetch_detects_tech_signals(self, mock_get):
        """WebScraperAgent should detect technology signals."""
        mock_get.return_value = _mock_response(text=HOMEPAGE_HTML)

        ctx = PipelineContext.new()
        ctx.raw_leads = [
            RawLead(
                company_name="ACME Realty",
                source="property_db",
                website="https://www.acmerealty.com",
            ),
        ]

        agent = WebScraperAgent(settings=_make_settings())
        leads = agent.fetch(ctx)

        assert len(leads) == 1
        signals = leads[0].raw_data.get("tech_signals", [])
        assert "hubspot" in signals or "wordpress" in signals

    @patch("agents.web_scraper_agent.requests.get")
    def test_fetch_skips_without_websites(self, mock_get):
        """Should return [] when no leads have websites."""
        ctx = PipelineContext.new()
        ctx.raw_leads = [
            RawLead(company_name="No Site Co", source="news"),
        ]

        agent = WebScraperAgent(settings=_make_settings())
        leads = agent.fetch(ctx)
        assert leads == []
        mock_get.assert_not_called()


# ======================================================================
# LinkedInAgent tests
# ======================================================================


class TestLinkedInAgent:

    def test_fetch_skips_without_credentials(self):
        """Should log warning and return [] with no credentials."""
        agent = LinkedInAgent(
            settings=_make_settings(linkedin_email="", linkedin_password="")
        )
        leads = agent.fetch(PipelineContext.new())
        assert leads == []

    @patch("agents.linkedin_agent.requests.Session")
    def test_fetch_with_failed_auth(self, mock_session_cls):
        """Should return [] when authentication fails."""
        mock_session = MagicMock()
        mock_session.cookies.get_dict.return_value = {}  # no li_at cookie
        mock_session.post.return_value = MagicMock(status_code=302)
        mock_session_cls.return_value = mock_session

        agent = LinkedInAgent(
            settings=_make_settings(
                linkedin_email="test@test.com",
                linkedin_password="pass123",
            )
        )
        leads = agent.fetch(PipelineContext.new())
        assert leads == []


# ======================================================================
# LeadPlatformAgent tests
# ======================================================================


class TestLeadPlatformAgent:

    def test_fetch_skips_without_api_keys(self):
        """Should return [] when both API keys are missing."""
        agent = LeadPlatformAgent(
            settings=_make_settings(apollo_api_key="", hunter_api_key="")
        )
        leads = agent.fetch(PipelineContext.new())
        assert leads == []

    @patch("agents.lead_platform_agent.requests.post")
    def test_apollo_returns_leads(self, mock_post):
        """Apollo.io integration should return RawLeads."""
        apollo_response = {
            "people": [
                {
                    "id": "abc123",
                    "name": "Jane Doe",
                    "title": "IT Director",
                    "email": "jane@brookfield.com",
                    "phone_number": "212-555-0001",
                    "linkedin_url": "https://linkedin.com/in/janedoe",
                    "seniority": "director",
                    "organization": {
                        "name": "Brookfield Properties",
                        "website_url": "https://brookfield.com",
                        "industry": "Commercial Real Estate",
                        "estimated_num_employees": 5000,
                        "city": "New York",
                    },
                },
            ]
        }
        mock_post.return_value = _mock_response(json_data=apollo_response)

        agent = LeadPlatformAgent(
            settings=_make_settings(apollo_api_key="test_key")
        )
        leads = agent.fetch(PipelineContext.new())

        assert len(leads) == 1
        assert leads[0].company_name == "Brookfield Properties"
        assert leads[0].contact_name == "Jane Doe"
        assert leads[0].source == "lead_platform"
        assert leads[0].raw_data["platform"] == "apollo"

    @patch("agents.lead_platform_agent.requests.get")
    def test_hunter_returns_leads(self, mock_get):
        """Hunter.io integration should return RawLeads."""
        hunter_response = {
            "data": {
                "organization": "Brookfield Properties",
                "emails": [
                    {
                        "value": "john@brookfield.com",
                        "first_name": "John",
                        "last_name": "Smith",
                        "position": "VP Technology",
                        "confidence": 95,
                        "department": "IT",
                    },
                ],
            }
        }
        mock_get.return_value = _mock_response(json_data=hunter_response)

        ctx = PipelineContext.new()
        ctx.raw_leads = [
            RawLead(
                company_name="Brookfield",
                source="news",
                website="https://brookfield.com",
            ),
        ]

        agent = LeadPlatformAgent(
            settings=_make_settings(hunter_api_key="test_key")
        )
        leads = agent.fetch(ctx)

        assert len(leads) == 1
        assert leads[0].email == "john@brookfield.com"
        assert leads[0].source == "lead_platform"
        assert leads[0].raw_data["platform"] == "hunter"


# ======================================================================
# MarketplaceAgent tests
# ======================================================================


class TestMarketplaceAgent:

    @patch("agents.marketplace_agent.requests.get")
    def test_fetch_rolling_sales(self, mock_get):
        """MarketplaceAgent should parse NYC rolling sales data."""
        sales_data = [
            {
                "buyer_name": "MANHATTAN TOWER LLC",
                "address": "1 WORLD TRADE CTR",
                "zip_code": "10007",
                "sale_price": "50000000",
                "sale_date": "2026-01-15",
                "building_class_at_time_of_sale": "O4",
                "gross_square_feet": "200000",
                "borough": "1",
                "block": "100",
                "lot": "1",
                "year_built": "2014",
            },
        ]
        mock_get.return_value = _mock_response(json_data=sales_data)

        agent = MarketplaceAgent(settings=_make_settings())
        leads = agent.fetch(PipelineContext.new())

        # Should have leads from rolling sales (reonomy/intent return [])
        assert len(leads) >= 1
        assert leads[0].company_name == "MANHATTAN TOWER LLC"
        assert leads[0].source == "marketplace"
        assert leads[0].raw_data["signal_type"] == "recent_sale"

    @patch("agents.marketplace_agent.requests.get")
    def test_fetch_skips_zero_sales(self, mock_get):
        """Should skip $0 non-arms-length transfers."""
        sales_data = [
            {
                "buyer_name": "SELF TRANSFER LLC",
                "address": "100 BROADWAY",
                "sale_price": "0",
                "building_class_at_time_of_sale": "O4",
            },
        ]
        mock_get.return_value = _mock_response(json_data=sales_data)

        agent = MarketplaceAgent(settings=_make_settings())
        leads = agent.fetch(PipelineContext.new())
        assert leads == []


# ======================================================================
# EnrichmentAgent tests
# ======================================================================


class TestEnrichmentAgent:

    def test_enrich_produces_enriched_leads(self):
        """EnrichmentAgent should convert RawLeads to EnrichedLeads."""
        raw_leads = [
            RawLead(
                company_name="ACME Realty LLC",
                source="property_db",
                address="100 Broadway, NYC",
                raw_data={"lot_area_sqft": "50000"},
            ),
            RawLead(
                company_name="Acme Realty",
                source="news",
                website="https://acmerealty.com",
                raw_data={"headline": "Acme Realty expands in NYC"},
            ),
            RawLead(
                company_name="ACME REALTY",
                source="web_scraper",
                email="info@acmerealty.com",
                phone="(212) 555-1234",
                raw_data={"tech_signals": ["hubspot", "salesforce"]},
            ),
        ]

        agent = EnrichmentAgent(settings=_make_settings())
        ctx = PipelineContext.new()
        enriched = agent.enrich(raw_leads, ctx)

        assert len(enriched) == 1  # all 3 should merge into one
        lead = enriched[0]
        assert isinstance(lead, EnrichedLead)
        assert lead.company_name == "ACME Realty LLC"
        assert lead.email == "info@acmerealty.com"
        assert lead.phone == "(212) 555-1234"
        assert "property_db" in lead.sources
        assert "news" in lead.sources
        assert "web_scraper" in lead.sources
        assert lead.score > 0
        assert lead.qualification_notes != ""

    def test_enrich_scores_multi_source_higher(self):
        """Leads from multiple sources should score higher."""
        single_source = [
            RawLead(company_name="Solo Corp", source="news"),
        ]
        multi_source = [
            RawLead(
                company_name="Multi Corp",
                source="property_db",
                email="info@multi.com",
            ),
            RawLead(
                company_name="Multi Corp",
                source="news",
                website="https://multi.com",
            ),
            RawLead(
                company_name="Multi Corp",
                source="web_scraper",
                phone="212-555-0000",
                raw_data={"tech_signals": ["hubspot"]},
            ),
        ]

        agent = EnrichmentAgent(settings=_make_settings())
        ctx = PipelineContext.new()

        enriched_single = agent.enrich(single_source, ctx)
        enriched_multi = agent.enrich(multi_source, ctx)

        assert enriched_multi[0].score > enriched_single[0].score

    def test_enrich_handles_empty_input(self):
        """Should return [] for empty input."""
        agent = EnrichmentAgent(settings=_make_settings())
        result = agent.enrich([], PipelineContext.new())
        assert result == []

    def test_enrich_skips_unknown_companies(self):
        """Should filter out 'Unknown Owner' entries."""
        raw = [
            RawLead(company_name="Unknown Owner", source="property_db"),
            RawLead(company_name="Unknown", source="news"),
            RawLead(company_name="Real Company", source="property_db"),
        ]
        agent = EnrichmentAgent(settings=_make_settings())
        result = agent.enrich(raw, PipelineContext.new())
        assert len(result) == 1
        assert result[0].company_name == "Real Company"

    def test_enrich_with_coworking_source(self):
        """Leads from coworking source should be typed COWORKING."""
        raw = [
            RawLead(
                company_name="WeWork",
                source="coworking",
                address="100 W 33rd St",
            ),
        ]
        agent = EnrichmentAgent(settings=_make_settings())
        result = agent.enrich(raw, PipelineContext.new())
        assert len(result) == 1
        assert result[0].company_type == "COWORKING"

    @patch("agents.enrichment_agent.LLMClient")
    def test_enrich_uses_llm_when_available(self, mock_llm_cls):
        """Should use LLM for enrichment when Ollama is available."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate.return_value = MagicMock(
            content=json.dumps(
                {
                    "company_type": "CRE_OPERATOR",
                    "building_type": "Class A Office",
                    "score": 85,
                    "qualification_notes": "Strong CRE operator with IT needs.",
                }
            )
        )
        mock_llm_cls.return_value = mock_llm

        raw = [
            RawLead(
                company_name="Brookfield Properties",
                source="property_db",
                email="info@brookfield.com",
            ),
        ]
        agent = EnrichmentAgent(settings=_make_settings())
        result = agent.enrich(raw, PipelineContext.new())

        assert len(result) == 1
        assert result[0].score == 85
        assert result[0].company_type == "CRE_OPERATOR"

    @patch("agents.enrichment_agent.LLMClient")
    def test_enrich_falls_back_on_llm_error(self, mock_llm_cls):
        """Should use rule-based scoring when LLM fails."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate.side_effect = Exception("Ollama down")
        mock_llm_cls.return_value = mock_llm

        raw = [
            RawLead(
                company_name="Fallback Corp",
                source="property_db",
                email="info@fallback.com",
                address="100 Broadway",
            ),
        ]
        agent = EnrichmentAgent(settings=_make_settings())
        result = agent.enrich(raw, PipelineContext.new())

        assert len(result) == 1
        assert result[0].score > 0  # rule-based scored it
        assert result[0].company_name == "Fallback Corp"


# ======================================================================
# Verify all agents have correct name attribute
# ======================================================================


class TestAllAgentNames:
    """Verify every concrete agent has the expected name."""

    @pytest.mark.parametrize(
        "agent_cls,expected_name",
        [
            (PropertyDBAgent, "property_db"),
            (PublicRecordsAgent, "public_records"),
            (NewsAgent, "news"),
            (CoworkingAgent, "coworking"),
            (WebScraperAgent, "web_scraper"),
            (LinkedInAgent, "linkedin"),
            (LeadPlatformAgent, "lead_platform"),
            (MarketplaceAgent, "marketplace"),
        ],
    )
    def test_agent_name(self, agent_cls, expected_name):
        assert agent_cls.name == expected_name
