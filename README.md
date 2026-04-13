# SalesLeads — Multi-Agent Lead Generation Platform

Automated sales lead discovery, enrichment, and qualification for managed IT + building infrastructure services targeting NYC commercial real estate operators, co-working spaces, and multi-tenant buildings.

## Architecture

Multi-agent pipeline that discovers leads from 8 diverse sources, deduplicates, enriches with LLM scoring, and presents results via a React + FastAPI dashboard.

```
Source Agents (parallel) → Dedup → LLM Enrichment → SQLite → FastAPI → React UI
```

### Source Agents

| Agent | Source | Data |
|-------|--------|------|
| PropertyDB | NYC OpenData, LoopNet | Commercial properties, sqft, owners |
| PublicRecords | NYC ACRIS, DOB NOW | Ownership transfers, building permits |
| News | Google News RSS, industry feeds | CRE news, expansions, openings |
| Coworking | Coworker.com, LiquidSpace | Co-working operators, addresses |
| WebScraper | Company websites | Contact info, tech signals |
| LinkedIn | LinkedIn profiles | Decision-makers, titles |
| LeadPlatform | Apollo.io, Hunter.io | Verified emails, company data |
| Marketplace | NYC DOF, Reonomy, intent data | Property sales, intent signals |

## Setup

```bash
# Clone and enter directory
cd SalesLeads

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys (all optional — agents degrade gracefully)

# Seed the database
python3 seed_data.py
```

### Ollama (for LLM features)

```bash
# Install Ollama: https://ollama.ai
ollama pull llama3
```

LLM features (lead scoring, email drafting) work without Ollama — they fall back to rule-based scoring.

## Usage

### Development (two terminals)

```bash
# Terminal 1: FastAPI backend
uvicorn api.main:app --reload --port 8000

# Terminal 2: React frontend (proxies /api → localhost:8000)
cd frontend && npm run dev
```

Open http://localhost:5173 — React app with dark mode, sidebar nav.

### Production

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Serve both API + static frontend
uvicorn api.main:app --port 8000
```

Open http://localhost:8000 — FastAPI serves both the API and the built React app.

### Legacy Streamlit Dashboard

```bash
streamlit run dashboard/app.py
```

### Run Tests

```bash
python3 -m pytest tests/ -v
```

### Pages

- **Pipeline** — Kanban board with drag-and-drop (NEW → CONTACTED → MEETING → PROPOSAL → CLOSED)
- **Leads** — Filterable table with sorting, pagination, borough/neighborhood filters
- **Lead Detail** — Tabbed profile: Overview, Building (ISP, equipment, summary), Intelligence, Notes
- **Email Drafter** — LLM-powered personalized outreach emails
- **Export** — Excel download with stage and score filters
- **Agent Status** — System health, run history, manual pipeline triggers

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/leads` | Filtered/paginated lead list |
| GET | `/api/leads/{id}` | Single lead |
| PATCH | `/api/leads/{id}/stage` | Move pipeline stage |
| PATCH | `/api/leads/{id}/notes` | Update notes |
| DELETE | `/api/leads/{id}` | Delete lead |
| GET | `/api/pipeline/overview` | Stage counts + last run |
| GET | `/api/pipeline/stages/{stage}` | Leads in a stage |
| POST | `/api/email/draft` | Generate email via LLM |
| POST | `/api/export/xlsx` | Download Excel |
| GET | `/api/agents/status` | Agent run stats |
| POST | `/api/agents/trigger` | Manual pipeline run |

### Run Pipeline Programmatically

```python
from pipeline.orchestrator import Orchestrator

orch = Orchestrator()
ctx = orch.run_daily()       # Run all agents
ctx = orch.run_marketplace() # Marketplace agent only
ctx = orch.run_single_agent("property_db")  # Single agent
```

## Project Structure

```
SalesLeads/
├── api/                 # FastAPI REST backend
│   ├── main.py          # App factory, CORS, static mount
│   ├── deps.py          # Shared dependencies (DB, settings)
│   ├── schemas.py       # Pydantic request/response models
│   ├── routes/          # leads, pipeline, email, export, agents
│   └── services/        # Email template logic
├── frontend/            # React + Tailwind + shadcn/ui
│   ├── src/
│   │   ├── components/  # layout, leads, pipeline, detail, email, agents
│   │   ├── pages/       # 6 page components
│   │   ├── hooks/       # React Query hooks
│   │   └── lib/         # API client, types, utils
│   └── dist/            # Production build (gitignored)
├── agents/              # 8 source agents + enrichment
│   ├── base.py          # BaseSourceAgent ABC
│   └── *_agent.py       # Individual agent implementations
├── core/
│   ├── models.py        # RawLead, EnrichedLead, PipelineContext
│   ├── database.py      # SQLite CRUD with migration
│   ├── llm_client.py    # Ollama wrapper with retry
│   └── dedup.py         # Fuzzy deduplication
├── pipeline/
│   ├── agent_runner.py  # ThreadPoolExecutor parallel runner
│   └── orchestrator.py  # Scheduling + coordination
├── dashboard/           # Legacy Streamlit dashboard
├── config/settings.py   # Environment-based config
├── seed_data.py         # Database seeder with NYC sample data
└── tests/               # 165 tests
```

## Configuration

All config via environment variables (see `.env.example`). Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3` | LLM model for enrichment/emails |
| `DATABASE_PATH` | `salesleads.db` | SQLite database file |
| `FASTAPI_PORT` | `8000` | FastAPI server port |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |
| `MAX_AGENT_WORKERS` | `4` | Parallel agent threads |
| `DAILY_RUN_HOUR` | `6` | Daily pipeline run hour (24h) |
| `DEDUP_SIMILARITY_THRESHOLD` | `85` | Fuzzy match threshold (0-100) |

API keys (all optional):
- `APOLLO_API_KEY` — Apollo.io for contact enrichment
- `HUNTER_API_KEY` — Hunter.io for email discovery
- `NYC_OPENDATA_APP_TOKEN` — NYC OpenData for property records
