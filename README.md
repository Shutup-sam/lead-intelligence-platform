# AI Lead Intelligence Platform (Multi-Tenant SaaS)

> Production-grade AI Lead Intelligence platform that discovers public business signals, crawls permitted websites using Scrapling, extracts structured intelligence, qualifies leads using LLMs, tracks AI compute costs, and isolates organization workspace data across a Next.js 15 dashboard.

---

## Current Status: Milestone 6 Complete (Multi-Tenant SaaS, Auth & Analytics)

Milestone 6 transforms the platform from a single-user developer engine into a **secure, multi-tenant SaaS application**:

```text
User
 ↓
Authentication (JWT + bcrypt)
 ↓
Organization Workspace (OWNER / MEMBER)
 ↓
Campaigns (Structured ICP Criteria)
 ↓
Crawl Targets (Domain Scope & SSRF Protected)
 ↓
Async Jobs (ARQ + Redis + Live SSE Progress)
 ↓
Leads (Structured Intelligence & Evidence Signals)
 ↓
AI Qualification & Embeddings (pgvector HNSW)
 ↓
Usage Analytics & Cost Metering (Daily Timeline & Quotas)
```

### Key Capabilities Added in Milestone 6

1. **Authentication & Authorization:**
   - Password hashing with `bcrypt` (12 rounds) and stateless JWT sessions (`PyJWT`, HS256).
   - Endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
   - Automatic workspace bootstrap: registering a user automatically sets up their primary organization with `OWNER` role.
   - Bearer token authentication + `X-Organization-Id` workspace switching header.

2. **Organization Workspaces & Strict Tenant Isolation:**
   - Database entities: `users`, `organizations`, `organization_members` (`OWNER`, `MEMBER`), and `organization_usage_daily`.
   - `organization_id` foreign keys and indexed composite filters on all core models (`crawl_targets`, `crawled_pages`, `leads`, `lead_signals`, `lead_embeddings`, `llm_audit_logs`, `jobs`, `campaigns`).
   - Tenant isolation enforced across all database queries, API endpoints, background jobs, and vector embeddings. Cross-tenant access attempts return HTTP 404/403.

3. **Campaign Management & ICP Specification:**
   - `campaigns` model with customizable Ideal Customer Profile (ICP) parameters: target industries, company sizes, target geographies, technologies, business models, and minimum qualification score threshold.
   - Dynamic translation from campaign ICP settings into structured prompt instructions for LLM qualification.
   - Direct crawl dispatch: launch crawls scoped to specific campaigns.

4. **Resource Quotas & AI Compute Cost Tracking:**
   - Daily usage tracking (`organization_usage_daily`): crawls initiated, pages crawled, leads created, qualifications run, embeddings generated, and jobs executed.
   - Quota enforcement: HTTP 429 Too Many Requests raised when active concurrent jobs (`MAX_ACTIVE_JOBS_PER_ORG=5`) or monthly crawls (`MAX_MONTHLY_CRAWLS_PER_ORG=100`) are exhausted.
   - Estimated AI compute costs computed from real `llm_audit_logs` token usage ($0.15/1M input, $0.60/1M output).

5. **Telemetry & Analytics APIs:**
   - `GET /api/v1/analytics/overview`: High-level KPIs (total leads, qualified leads, qualification rate %, total crawls, pages crawled, jobs completed/failed, estimated AI cost).
   - `GET /api/v1/analytics/usage`: 30-day daily usage breakdown table and activity timeline.
   - `GET /api/v1/analytics/leads`: Multi-dimensional distribution by campaign, industry, and lead status.

6. **Next.js SaaS Frontend:**
   - Global sticky `Navigation` with workspace switcher, navigation tabs (Leads, Campaigns, Analytics), and authenticated user menu.
   - `/login` and `/register` pages with form validation, error states, and responsive dark aesthetics.
   - `/campaigns` view with ICP specification cards, campaign lead stats, delete operations, and direct crawl modal triggers.
   - `/analytics` view with KPI cards, quota monitors, daily usage timeline, and distribution charts.
   - Leads view integrated with active campaign filtering.

7. **Verification & Testing:**
   - 75 automated pytest unit and integration tests passing in 1.3s.
   - Multi-tenant isolation verified with automated security tests and live cross-organization HTTP assertions.
   - 100% clean Next.js production build (`npm run build`).

---

## Monorepo Structure

```
lead-intelligence-platform/
├── backend/                      # FastAPI Application
│   ├── app/
│   │   ├── ai/                   # AI Intelligence & Qualification Layer
│   │   │   ├── models.py         # Pydantic models (CompanyQualification, ICPProfile, Signals)
│   │   │   ├── prompt.py         # Evidence-based system & user prompt engineering
│   │   │   ├── llm_provider.py   # LLM abstraction (OpenAILLMProvider, MockLLMProvider)
│   │   │   ├── embeddings.py     # Canonical doc builder, hashing, OpenAI/Mock embeddings
│   │   │   └── pipeline.py       # Orchestrates content selection, LLM, validation, vectors
│   │   ├── api/v1/               # API Routers (/auth, /campaigns, /analytics, /jobs, /leads, /crawl)
│   │   │   ├── auth.py           # User registration, login, logout, profile
│   │   │   ├── campaigns.py      # Campaign CRUD & ICP configuration
│   │   │   ├── analytics.py      # KPI overview, daily usage, lead distributions
│   │   │   ├── jobs.py           # Async job enqueueing & SSE stream
│   │   │   ├── leads.py          # Lead qualification and retrieval endpoints
│   │   │   ├── crawl.py          # Scrapling crawl endpoint
│   │   │   └── router.py         # API router v1 aggregator
│   │   ├── core/                 # Config, Security, Database engine, Auth dependencies
│   │   │   ├── auth.py           # Dependency injection for user & org security
│   │   │   ├── security.py       # Bcrypt password hashing & PyJWT token utilities
│   │   │   ├── config.py         # Environment settings & SaaS quota constants
│   │   │   └── database.py       # Async SQLAlchemy session factory
│   │   ├── crawler/              # Scrapling Crawling Engine
│   │   ├── models/               # SQLAlchemy 2 Declarative Models
│   │   │   ├── user.py           # User model
│   │   │   ├── organization.py   # Organization & OrganizationMember models
│   │   │   ├── campaign.py       # Campaign model & status enums
│   │   │   ├── usage.py          # OrganizationUsageDaily model
│   │   │   ├── crawl.py          # CrawlTarget & CrawledPage models
│   │   │   ├── lead.py           # Lead, LeadSignal, LeadEmbedding, LLMAuditLog models
│   │   │   └── job.py            # Job model & status enums
│   │   ├── services/             # Business Logic & Orchestration
│   │   │   ├── auth_service.py   # Account creation, password checks, org setup
│   │   │   ├── campaign_service.py # Campaign management & ICP prompts
│   │   │   ├── analytics_service.py # Telemetry aggregation & quota enforcement
│   │   │   ├── crawl_service.py  # Crawling orchestration & persistence
│   │   │   ├── lead_service.py   # Transactional qualification & pgvector search
│   │   │   └── job_service.py    # Background job enqueueing & state transitions
│   │   ├── workers/              # Redis + ARQ Worker System
│   │   └── main.py               # FastAPI entrypoint & middleware
│   ├── alembic/                  # Database migration scripts (Async)
│   │   └── versions/             # 0001 through 0006 migrations
│   ├── tests/                    # Pytest test suite (75 automated tests)
│   ├── requirements.txt          # Python dependencies
│   └── pytest.ini                # Pytest configuration
├── frontend/                     # Next.js Application (App Router, TS, Tailwind)
│   ├── src/
│   │   ├── app/                  # App Router views (/, /login, /register, /campaigns, /analytics, /leads/[id])
│   │   ├── components/           # UI components (Navigation, Leads, Campaigns)
│   │   └── lib/                  # AuthContext, API client, types
│   └── package.json
├── docker/                       # Docker Infrastructure
│   ├── docker-compose.yml        # PostgreSQL 16 + pgvector and Redis 7 definitions
│   └── init-pgvector.sql         # Database initialization script
├── .env.example                  # Environment variables template
├── docker-compose.yml            # Root compose shortcut
└── README.md
```

---

## Prerequisites

- **Docker & Docker Compose** (Docker Desktop or Colima)
- **Python 3.11+**
- **Node.js 18+ & npm**

---

## Local Development Quickstart

### 1. Configure Environment Variables

```bash
cp .env.example .env
```

To enable live OpenAI evaluations, set `LLM_API_KEY=sk-...` and `LLM_MOCK_MODE=false`. Otherwise, the system runs in deterministic `LLM_MOCK_MODE=true` for zero-cost testing.

### 2. Start PostgreSQL + pgvector and Redis

Start the infrastructure containers in detached mode:

```bash
docker compose up -d
```

Verify containers are running:
```bash
docker compose ps
```

### 3. Run Backend & Migrations

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Apply all database migrations
alembic upgrade head

# Run FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In a separate terminal, start the background ARQ worker:
```bash
cd backend
source .venv/bin/activate
python -m app.workers.worker
```

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to open the Lead Intelligence Platform dashboard.

---

## Multi-Tenant Security & Tenant Isolation

- **Authentication Header:** All protected endpoints require a Bearer token:
  ```http
  Authorization: Bearer <jwt_token>
  ```
- **Active Workspace Header:** When a user belongs to multiple organizations, specify the active workspace:
  ```http
  X-Organization-Id: <organization_uuid>
  ```
- **Strict Tenant Boundary:** Every database query filters by `organization_id`. Any query attempting to view or modify an entity belonging to another organization returns HTTP 404 (or 403 Forbidden).

---

## Running Automated Tests

Run the full backend test suite:

```bash
cd backend
source .venv/bin/activate
pytest -v
```

All 75 tests pass across:
- Authentication & JWT token security
- Multi-tenant campaign and lead isolation
- Organization quota limits (concurrency & monthly crawls)
- Scrapling crawling engine & SSRF defenses
- AI qualification schema & prompt engineering
- Vector embeddings and pgvector similarity search
- Asynchronous ARQ jobs & SSE live streams
- Analytics & daily usage metrics

---

## Roadmap

- [x] **Milestone 1:** Local development foundation, monorepo, Docker, health checks, async DB, Next.js.
- [x] **Milestone 2:** Scrapling crawling engine, fetcher routing, rate limiting, and HTML-to-Markdown sanitization.
- [x] **Milestone 3:** LLM qualification pipeline, Pydantic schema validation, and pgvector embeddings.
- [x] **Milestone 4:** Next.js interactive lead table, search/filter, and real-time SSE streaming.
- [x] **Milestone 5:** Asynchronous ARQ worker system, Redis queues, persistent jobs, SSE live progress, distributed rate limiting, and jittered retries.
- [x] **Milestone 6:** Multi-Tenant SaaS, Authentication, Workspaces, Campaigns (ICP), and Usage Analytics.
