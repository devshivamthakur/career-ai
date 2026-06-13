# CareerAI Backend

FastAPI backend for CareerAI — an AI-powered job application assistant providing resume tailoring (with streaming), cover letter generation, and interview preparation.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.14+, FastAPI | Async web framework |
| LangGraph | Resume tailoring workflow as a state graph |
| LangChain + LangChain-OpenAI / AWS Bedrock | LLM invocation |
| LangFuse | LLM observability and tracing |
| Redis | Rate limiting, semantic caching |
| PostgreSQL | Primary database (via SQLAlchemy + Alembic) |
| PDFplumber | PDF text extraction |
| ReportLab | PDF export generation |

## Architecture

```
├── app/
│   ├── agents/
│   │   ├── resume_tailor.py       # LangGraph state machine (4 nodes)
│   │   └── career_assistant.py    # Cover letter & interview prep agent
│   ├── api/
│   │   ├── resume_routes.py       # POST /api/resume/tailor/stream, /export-pdf
│   │   ├── assistant_routes.py    # POST /api/career/cover-letter, /interview-prep
│   │   ├── services.py            # Service layer: validation, PDF, streaming, orchestration
│   │   ├── rate_limit.py          # Redis-backed rate limiter
│   │   ├── config.py              # Circuit breaker, concurrency manager, service config
│   │   └── routes.py              # Shared API router
│   ├── core/
│   │   ├── config.py              # Pydantic settings (env vars)
│   │   ├── llm.py                 # Chat model builder (OpenAI or AWS Bedrock)
│   │   └── caching.py             # Redis semantic cache with HuggingFace embeddings
│   ├── db/
│   │   ├── database.py            # SQLAlchemy engine + session
│   │   └── models.py              # MasterResume, JobApplication, Generation
│   ├── schemas/
│   │   └── resume_schemas.py      # Pydantic models (JDValidation, SkillsComparison, state)
│   ├── services/
│   │   ├── pdf_service.py         # PDF text extraction
│   │   ├── pdf_export.py          # Resume PDF generation
│   │   └── career_assistant_service.py  # Career service orchestrator
│   ├── prompts/
│   │   └── resume_tailoring_prompts.py  # All LLM prompts
│   └── utils.py                   # Constants (file size, JD length limits)
├── alembic/                       # Database migrations
├── pyproject.toml
└── main.py                        # Entry point for dev server
```

## Features

### Resume Tailoring (LangGraph Workflow)
- **4-node state graph**: `parallel_analyze` → `compare_skills` → `rewrite_resume` → `polish_resume`
- **Parallel execution**: JD parsing and CV analysis run concurrently
- **True token streaming** via `astream_events()` — only critical nodes emit SSE events
- **ATS score** (0–100) with matched/missing skills
- **JD validation** via structured LLM output (Pydantic-parsed)
- **PDF export** via reportlab

### Career Assistant
- **Cover letter generation** — parses job context + resume profile, generates 3-paragraph letter
- **Interview preparation** — generates questions with STAR-format answers, optionally personalized with resume projects

### Production Infrastructure
- **Semantic caching** — Redis + HuggingFace embeddings (`BAAI/bge-base-en-v1.5`) cache LLM responses semantically
- **Circuit breaker** — opens when error rate exceeds 10% in 60s window
- **Concurrency management** — max 10 concurrent requests, max 5 concurrent PDF parses
- **Rate limiting** — 20 requests/client/60s (Redis-backed)
- **Security headers** — X-Frame-Options, CSP, HSTS, X-Content-Type-Options, X-XSS-Protection
- **Request ID tracking** — every request/response gets a unique ID
- **CORS** — configurable allowed origins (separate dev/prod)

## Requirements

- Python 3.14+
- Redis instance (required for rate limiting + semantic cache)
- PostgreSQL database
- LLM API key (OpenAI-compatible or AWS Bedrock)
- HuggingFace API token (for semantic cache embeddings)

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Configure environment
cp .env.example .env   # then edit .env
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`.

## Database Migrations

```bash
alembic upgrade head
```

## Environment Variables

Key variables (see `.env.example` for full list):

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `LLM_PROVIDER` | `"openai"` or `"aws"` | Yes |
| `OPENAI_API_KEY` | OpenAI-compatible API key | If provider=openai |
| `OPENAI_BASE_URL` | Custom API base URL | Optional |
| `FAST_MODEL_NAME` | Fast model (default: `poolside/laguna-xs.2`) | Yes |
| `QUALITY_MODEL_NAME` | Quality model (default: `poolside/laguna-m.1`) | Yes |
| `EMBEDDING_MODEL_REPO_ID` | Embeddings model (default: `BAAI/bge-base-en-v1.5`) | Yes |
| `HUGGINGFACE_API_TOKEN` | HuggingFace token for embeddings | Yes |
| `LANGFUSE_PUBLIC_KEY` | LangFuse observability key | Optional |
| `LANGFUSE_SECRET_KEY` | LangFuse observability secret | Optional |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | Yes |
| `ENVIRONMENT` | `"development"` or `"production"` | Yes |
| `HIDE_DOCS_IN_PRODUCTION` | Hide `/docs` in production | Optional |
| `ENABLE_SECURITY_HEADERS` | Security response headers | Optional |

AWS Bedrock variables (when `LLM_PROVIDER=aws`): `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_CREDENTIALS_PROFILE_NAME`, `AWS_MODEL_PROVIDER`.

## API Endpoints

### Resume Tailor
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resume/tailor/stream` | Tailor resume (SSE streaming). Fields: `cv_file` (PDF), `job_description` |
| POST | `/api/resume/export-pdf` | Export resume as PDF. Body: `{ "resume_text": "..." }` |
| GET | `/api/resume/status` | Service status and configuration |
| GET | `/api/resume/health` | Liveness probe |

### Career Assistant
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/career/cover-letter` | Generate cover letter. Fields: `cv_file`, `job_description` |
| POST | `/api/career/interview-prep` | Generate interview prep. Fields: `job_description`, optional `cv_file` |
| GET | `/api/career/status` | Service status |

### General
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/status` | API status |

## Service Configuration

Tunable in `app/api/config.py` (`ServiceConfig`):

| Setting | Default | Description |
|---|---|---|
| `MAX_CONCURRENT_REQUESTS` | 10 | Max simultaneous requests |
| `MAX_CONCURRENT_PDF_PARSING` | 5 | Max concurrent PDF parses |
| `JD_VALIDATION_TIMEOUT` | 20s | Job description validation timeout |
| `PDF_PARSING_TIMEOUT` | 60s | PDF extraction timeout |
| `STREAMING_TIMEOUT` | 300s | Total streaming timeout |
| `KEEP_ALIVE_TIMEOUT` | 15s | SSE keep-alive interval |
| `MAX_REQUESTS_PER_CLIENT` | 20 | Rate limit per window |
| `RATE_LIMIT_WINDOW` | 60s | Rate limit window |
| `ERROR_THRESHOLD` | 10% | Circuit breaker error threshold |
| `VALIDATION_CACHE_TTL` | 1h | Validation cache TTL |

## Input Validation

- Max file size: **10 MB**
- Min job description length: **50 characters**
- Max job description length: **5000 characters**
- Only PDF files accepted for resume upload

## Database Schema

Three tables:
- `master_resumes` — Parsed resume data (JSON + plain text)
- `job_applications` — Links resume to job (company, role, JD, ATS score)
- `generations` — Generated content (resume/cover_letter/interview_prep)

## LLM Providers

Supports two providers selected via `LLM_PROVIDER`:

- **OpenAI** — Uses `ChatOpenAI` with configurable `base_url` (supports custom endpoints like Poolside.ai)
- **AWS Bedrock** — Uses `ChatBedrockConverse` with Mistral models

## Semantic Caching

LLM responses are semantically cached using:
- **Redis** as the cache backend
- **HuggingFaceEndpointEmbeddings** (`BAAI/bge-base-en-v1.5`) for embedding
- **Distance threshold**: 0.7
- **TTL**: 8 hours

Cached operations: JD validation, JD parsing, CV analysis, resume tailoring, cover letters, interview prep.
