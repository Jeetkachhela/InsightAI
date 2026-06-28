# InsightForge AI

**Schema-Aware SQL Intelligence Platform**

InsightForge AI is a production-grade platform that connects to your databases, discovers schemas, and uses AI (Groq LLM + RAG) to generate, execute, and explain SQL queries through natural language.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                     │
│  Login / Register ─── Workspace ─── Query Interface      │
│              http://localhost:3000                        │
└──────────────────────────┬──────────────────────────────┘
                           │ REST API (JSON)
┌──────────────────────────┴──────────────────────────────┐
│                  Backend (FastAPI + Uvicorn)              │
│                  http://localhost:8000                    │
│                                                          │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌────────┐  │
│  │  Auth   │  │   Data   │  │   SQL/AI   │  │ System │  │
│  │ Service │  │  Sources │  │  Pipeline  │  │ Health │  │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘  └───┬────┘  │
│       │            │              │              │       │
│  ┌────┴────────────┴──────────────┴──────────────┴───┐  │
│  │              Service Layer                         │  │
│  │  AuthService │ DataSourceService │ LangGraph Agent │  │
│  └────┬────────────┴──────────────────┬──────────────┘  │
│       │                               │                  │
│  ┌────┴───────────────────────────────┴──────────────┐  │
│  │         Repository Layer (SQLAlchemy ORM)          │  │
│  └────┬───────────────────────────────┬──────────────┘  │
│       │                               │                  │
│  ┌────┴────┐                   ┌──────┴──────┐          │
│  │  Neon   │                   │  pgvector   │          │
│  │Postgres │                   │ Embeddings  │          │
│  └─────────┘                   └─────────────┘          │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer      | Technology                              |
|------------|----------------------------------------|
| Frontend   | Next.js 16, React, TailwindCSS          |
| Backend    | FastAPI, Uvicorn, Python 3.14           |
| Database   | Neon PostgreSQL, pgvector               |
| AI/LLM     | Groq (Llama 3.3 70B), LangGraph        |
| RAG        | Sentence Transformers, pgvector         |
| Auth       | JWT (HttpOnly cookies), bcrypt, AES-256 |
| Migrations | Alembic                                 |

## Quick Start

### Prerequisites
- Python 3.14+
- Node.js 20+
- PostgreSQL (or Neon serverless)

### Setup

1. **Clone and install backend dependencies:**
   ```bash
   cd backend
   python -m venv ../venv
   ../venv/Scripts/activate   # Windows
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database URL, API keys, and secrets
   ```

3. **Run database migrations:**
   ```bash
   cd backend
   alembic upgrade head
   ```

4. **Seed demo data (optional):**
   ```bash
   python seed_db.py
   ```

5. **Start backend:**
   ```bash
   PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
   ```

6. **Install and start frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

7. **Access the app:** http://localhost:3000

## API Endpoints

| Method | Endpoint                        | Description                      |
|--------|--------------------------------|----------------------------------|
| POST   | `/api/v1/auth/register`        | Register new user + auto-login   |
| POST   | `/api/v1/auth/login`           | Login with email/password        |
| POST   | `/api/v1/auth/refresh`         | Refresh access token             |
| GET    | `/api/v1/auth/sessions`        | List active sessions             |
| POST   | `/api/v1/data-sources/`        | Add a database connection        |
| GET    | `/api/v1/data-sources/`        | List user data sources           |
| POST   | `/api/v1/sql/generate`         | Generate SQL from natural lang   |
| POST   | `/api/v1/sql/execute`          | Execute SQL query                |
| GET    | `/api/v1/system/health`        | System health check              |
| GET    | `/api/v1/system/readiness`     | Readiness probe                  |
| GET    | `/api/v1/system/metrics`       | Runtime metrics                  |
| GET    | `/docs`                        | OpenAPI documentation            |

## Security Features

- JWT authentication with HttpOnly secure cookies
- Refresh token rotation with replay protection
- AES-256 encryption with key rotation for stored credentials
- SQL injection firewall blocking writes, system catalogs, and dangerous functions
- Rate limiting (per-user and per-IP)
- Login brute-force protection with exponential backoff
- Structured logging with automatic secret redaction
- CORS origin validation (wildcards blocked in production)
- Workspace concurrency locking (409 Conflict on simultaneous ops)
- Optimistic locking with ETags on resources

## License

Proprietary. All rights reserved.
