# CareerAI Backend

FastAPI backend for **CareerAI** — an AI-powered job application assistant providing resume tailoring (with streaming), cover letter generation, interview preparation, and an interactive AI chat agent.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.14+, FastAPI | Async web framework |
| LangGraph | Resume tailoring workflow as a state graph |
| LangChain (create_agent) | Unified AI agent with middleware, tools & structured output |
| LangChain-OpenAI / AWS Bedrock | LLM invocation (multi-provider) |
| LangFuse | LLM observability and tracing |
| Redis | Rate limiting, semantic caching |
| PostgreSQL | Primary database (via SQLAlchemy + Alembic) |
| PDFplumber | PDF text extraction |
| ReportLab | PDF export / resume generation |
| HuggingFace Embeddings | Semantic cache similarity (`BAAI/bge-base-en-v1.5`) |

## Architecture

```
├── app/
│   ├── agents/
│   │   ├── unified_agent.py        # Unified CareerAgent (LangChain create_agent) — chat, tools, streaming
│   │   ├── resume_tailor.py        # LangGraph state machine (4 nodes) — resume tailoring workflow
│   │   ├── career_assistant.py     # Cover letter & interview prep agent
│   │   └── tools.py                # Agent tools: PDF extraction, skill comparison, resume rewriting, etc.
│   ├── api/
│   │   ├── resume_routes.py        # POST /api/resume/tailor/stream, /export-pdf
│   │   ├── assistant_routes.py     # POST /api/career/cover-letter, /interview-prep
│   │   ├── chat_routes.py          # POST /api/chat/stream — SSE streaming chat with session management
│   │   ├── services.py             # Service layer: validation, PDF, streaming, orchestration
│   │   ├── rate_limit.py           # Redis-backed rate limiter (Token Bucket)
│   │   ├── config.py               # Circuit breaker, concurrency manager, ServiceConfig
│   │   └── routes.py               # Shared API router (/api/status)
│   ├── core/
│   │   ├── config.py               # Pydantic BaseSettings (all env vars, CORS, security)
│   │   ├── llm.py                  # Chat model builder (OpenAI or AWS Bedrock providers)
│   │   └── caching.py              # Redis SemanticCacheService with HuggingFace embeddings
│   ├── db/
│   │   ├── database.py             # SQLAlchemy async engine + session
│   │   └── models.py               # MasterResume, JobApplication, Generation
│   ├── schemas/
│   │   └── resume_schemas.py       # Pydantic models (JDValidation, SkillsComparison, state, export)
│   ├── services/
│   │   ├── chat_session.py         # JSON file-based chat session store (CRUD, summarization)
│   │   ├── pdf_service.py          # PDF text extraction via pdfplumber
│   │   ├── pdf_export.py           # Resume PDF generation via reportlab
│   │   └── career_assistant_service.py  # Career service orchestrator
│   ├── prompts/
│   │   └── resume_tailoring_prompts.py  # All LLM prompts (skill comparison, rewrite, polish)
│   └── utils.py                    # SSE helpers, constants (file size, JD length limits)
├── alembic/                        # Database migrations (SQLAlchemy + Alembic)
│   └── versions/                   # Migration revision scripts
├── chat_sessions/                  # JSON file store for chat sessions (auto-created)
├── alembic.ini                     # Alembic configuration
├── pyproject.toml                  # Project metadata & dependencies
├── main.py                         # Entry point (simple CLI placeholder)
└── test_graph.py                   # Quick test script for ResumeTailorAgent
```

## Features

### 🤖 Unified AI Chat Agent (`/api/chat`)
- **LangChain `create_agent`** with structured Pydantic output and tool-calling
- **Middleware pipeline**: PII scrubbing, model/tool retry, call limits, todo-list tracking
- **SSE streaming** — real-time token, tool_call, tool_start, and tool_end events
- **Chat session management** — JSON file-based sessions with history summarization (last 7 messages + summary)
- **Tool set**: resume extraction, skill comparison, resume rewriting, cover letter generation, interview prep

### 📄 Resume Tailoring (`/api/resume`)
- **4-node LangGraph state machine**: `parallel_analyze` → `compare_skills` → `rewrite_resume` → `polish_resume`
- **Parallel execution**: JD parsing and CV analysis run concurrently
- **True token streaming** via `astream_events()` — only critical nodes emit SSE events
- **ATS score** (0–100) with matched/missing skills breakdown
- **JD validation** via structured LLM output (Pydantic-parsed)
- **PDF export** — generates a polished, formatted PDF of the tailored resume
- **Semantic caching** — avoids redundant LLM calls for similar job descriptions

### ✍️ Career Assistant (`/api/career`)
- **Cover letter generation** — parses job context + resume profile, generates 3-paragraph tailored letter
- **Interview preparation** — generates questions with STAR-format answers, optionally personalized with resume projects

### 🛡️ Production Infrastructure
| Component | Implementation |
|---|---|
| **Semantic caching** | Redis + HuggingFace embeddings (`BAAI/bge-base-en-v1.5`) cache LLM responses semantically |
| **Circuit breaker** | Opens when error rate exceeds 10% in 60s window; half-open recovery after timeout |
| **Concurrency management** | Max 10 concurrent requests, max 5 concurrent PDF parses (asyncio semaphores) |
| **Rate limiting** | 20 requests/client/60s (Redis-backed Token Bucket via `app.api.rate_limit`) |
| **Security headers** | `X-Frame-Options: DENY`, `CSP`, `HSTS` (prod), `X-Content-Type-Options`, `X-XSS-Protection` |
| **Request ID tracking** | Every request/response gets a unique `X-Request-ID` header |
| **CORS** | Configurable allowed origins (separate dev/prod) |
| **Error handling** | Centralized exception handlers for validation, HTTP, and unexpected errors; structured JSON error responses with `request_id` |

### 🗄️ Database (PostgreSQL)
- **`master_resumes`** — stores parsed resume data and original text
- **`job_applications`** — tracks applications with company, role, JD, and match score (linked to resume)
- **`generations`** — stores generated content (resume, cover letter, interview prep) per application
- **Alembic** for schema migrations

## Requirements

- **Python 3.14+**
- **Redis** — required for rate limiting and semantic cache
- **PostgreSQL** — primary database
- **LLM API key** — OpenAI-compatible or AWS Bedrock (Mistral / Llama via `poolside/*` models)
- **HuggingFace API token** — for semantic cache embeddings

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Configure environment
cp .env.example .env   # then edit .env with your keys
```

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `REDIS_URL` | | `redis://localhost:6379` | Redis connection string |
| `OPENAI_API_KEY` | * | — | OpenAI API key (if using OpenAI provider) |
| `LLM_PROVIDER` | | `openai` | `openai` or `aws` |
| `AWS_REGION` | * | — | AWS region (if using Bedrock) |
| `AWS_ACCESS_KEY_ID` | * | — | AWS credentials (if using Bedrock) |
| `AWS_SECRET_ACCESS_KEY` | * | — | AWS credentials (if using Bedrock) |
| `HUGGINGFACE_API_TOKEN` | ✅ | — | For semantic cache embeddings |
| `LANGFUSE_PUBLIC_KEY` | | — | LangFuse observability (optional) |
| `LANGFUSE_SECRET_KEY` | | — | LangFuse observability (optional) |
| `FAST_MODEL_NAME` | | `poolside/laguna-xs.2` | Fast/cheap model for simple tasks |
| `QUALITY_MODEL_NAME` | | `poolside/laguna-m.1` | Quality model for complex tasks |
| `ALLOWED_ORIGINS` | | `http://localhost:5173,http://localhost:3000` | CORS allowed origins |
| `ENVIRONMENT` | | `development` | `development` or `production` |
| `ENABLE_SECURITY_HEADERS` | | `True` | Enable/disable security response headers |

## Run

```bash
source .venv/bin/activate

# Development server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Database Migrations

```bash
# Generate a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check (returns `{"status": "healthy"}`) |
| `GET` | `/api/status` | API status check |
| `POST` | `/api/resume/tailor/stream` | Tailor resume (SSE stream) — upload PDF + JD |
| `POST` | `/api/resume/export-pdf` | Export tailored resume as PDF |
| `POST` | `/api/career/cover-letter` | Generate a tailored cover letter |
| `POST` | `/api/career/interview-prep` | Generate interview questions with STAR answers |
| `POST` | `/api/chat/stream` | Unified chat agent (SSE stream) — message + optional file |
| `POST` | `/api/chat/session` | Create a new chat session |
| `GET` | `/api/chat/session/{id}` | Get chat session history |
| `DELETE` | `/api/chat/session/{id}` | Delete a chat session |
| `GET` | `/docs` | Swagger UI (dev only) |
| `GET` | `/redoc` | ReDoc UI (dev only) |

## Testing

```bash
# Run the resume tailoring agent test
python test_graph.py
```

## LLM Providers

Supports two providers selected via `LLM_PROVIDER`:

- **OpenAI** — Uses `ChatOpenAI` with configurable `base_url` (supports custom endpoints like Poolside.ai)
- **AWS Bedrock** — Uses `ChatBedrockConverse` with Mistral models

## Input Validation

- Max file size: **10 MB**
- Min job description length: **50 characters**
- Max job description length: **5000 characters**
- Only PDF files accepted for resume upload
