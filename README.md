# AI Lead Intelligence Platform

> Production-oriented AI system that discovers publicly available business information, crawls permitted public websites using Scrapling, extracts structured intelligence, qualifies leads using LLMs, and presents real-time data in a Next.js dashboard.

---

## Current Status: Milestone 1 (Local Development Foundation)

Milestone 1 establishes the operational core of the platform:
- **FastAPI Backend:** Asynchronous API with SQLAlchemy 2, Pydantic v2, and asyncpg.
- **PostgreSQL 16 + pgvector:** Native vector extension enabled for upcoming lead embeddings.
- **Redis 7:** High-speed broker and cache container for task orchestration and rate limiting.
- **Alembic:** Asynchronous database migration system with initial schema and vector extension registration.
- **Next.js 14+ Frontend:** App Router, TypeScript, and Tailwind CSS.
- **Health Checks & Observability:** Detailed `/health` API verifying database latency, pgvector readiness, and Redis connectivity.

---

## Monorepo Structure

```
lead-intelligence-platform/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/v1/           # API Routers & Endpoints (/health, etc.)
│   │   ├── core/             # Configuration, Database engine, Redis client
│   │   ├── models/           # SQLAlchemy 2 Async Declarative Models
│   │   └── main.py           # Application entrypoint & middleware
│   ├── alembic/              # Database migration scripts (Async)
│   ├── tests/                # Pytest test suite
│   ├── requirements.txt      # Python dependencies
│   └── pytest.ini            # Pytest configuration
├── frontend/                 # Next.js Application (App Router, TS, Tailwind)
│   ├── src/
│   │   └── app/              # Next.js App Router pages
│   └── package.json
├── docker/                   # Docker Infrastructure
│   ├── docker-compose.yml    # PostgreSQL + pgvector and Redis 7 definitions
│   └── init-pgvector.sql     # Database initialization script
├── .env.example              # Environment variables template
├── .gitignore
├── docker-compose.yml        # Root compose shortcut
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

### 2. Start PostgreSQL + pgvector and Redis

Start the infrastructure containers in detached mode:

```bash
docker compose up -d
```

Verify containers are running:
```bash
docker compose ps
```

### 3. Set Up and Run the Backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run initial database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

The backend will be available at:
- **API Base:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/api/v1/docs`
- **Health Check:** `http://localhost:8000/health`

### 4. Run Backend Tests

From the `backend/` directory:

```bash
pytest -v
```

### 5. Set Up and Run the Frontend

In a separate terminal:

```bash
cd frontend

# Install dependencies (if not already installed)
npm install

# Start Next.js development server
npm run dev
```

The frontend will be available at:
- **Dashboard:** `http://localhost:3000`

---

## Health Check Verification

You can verify all platform services using `curl`:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "environment": "development",
  "timestamp": "2026-10-02T11:25:00.000000+00:00",
  "services": {
    "database": {
      "status": "connected",
      "latency_ms": 1.25,
      "pgvector_ready": true,
      "error": null
    },
    "redis": {
      "status": "connected",
      "latency_ms": 0.45,
      "ping": true,
      "error": null
    }
  }
}
```

---

## Roadmap

- [x] **Milestone 1:** Local development foundation, monorepo, Docker, health checks, async DB, Next.js.
- [ ] **Milestone 2:** Scrapling crawler engine, fetcher routing, rate limiting, and HTML-to-Markdown sanitization.
- [ ] **Milestone 3:** LLM qualification pipeline, Pydantic/Instructor schema validation, and pgvector embeddings.
- [ ] **Milestone 4:** Next.js interactive lead table, search/filter, and real-time SSE streaming.
- [ ] **Milestone 5:** Evaluation benchmark suite, integration testing, and production hardening.
