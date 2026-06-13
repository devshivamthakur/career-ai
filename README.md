# CareerAI — AI-Powered Job Helper

> An intelligent job application assistant that tailors resumes, generates cover letters, and prepares interview answers using AI.

CareerAI is a full-stack application with a **FastAPI + LangGraph** backend and a **React + TypeScript + Vite** frontend. It uses large language models (OpenAI or AWS Bedrock) to help job seekers optimize their applications for specific roles.

---

## Features

### Resume Tailoring
- **ATS‑optimized rewriting** — Upload a resume PDF + job description; get a tailored resume with matched/missing skills highlighted
- **Real‑time streaming** — SSE‑based incremental output as the LangGraph workflow progresses
- **Skill comparison** — See exactly which skills match and which are missing (ATS score 0–100)
- **PDF export** — Download the tailored resume as a PDF

### Cover Letter Generation
- Generates a 3‑paragraph cover letter from your resume profile and the job posting

### Interview Preparation
- Generates likely interview questions with **STAR‑format** answers
- Optionally personalized using projects from your uploaded resume

### Production Infrastructure
- **Semantic caching** (Redis + HuggingFace embeddings) — semantically similar requests reuse cached LLM responses
- **Circuit breaker** — fails fast when error rate exceeds 10% in a 60‑second window
- **Concurrency management** — max 10 concurrent requests, max 5 concurrent PDF parses
- **Rate limiting** — 20 requests per client per 60 seconds (Redis‑backed)
- **Security headers** — X‑Frame‑Options, CSP, HSTS, X‑Content‑Type‑Options, X‑XSS‑Protection
- **Request ID tracking** — every request/response carries a unique ID
- **Observability** — LangFuse tracing for LLM calls

---

## Tech Stack

### Backend

| Technology | Purpose |
|---|---|
| **Python 3.14+, FastAPI** | Async web framework |
| **LangGraph** | Resume tailoring workflow as a state graph |
| **LangChain + LangChain‑OpenAI / AWS Bedrock** | LLM invocation |
| **LangFuse** | LLM observability and tracing |
| **Redis** | Rate limiting, semantic caching |
| **PostgreSQL** | Primary database (SQLAlchemy + Alembic) |
| **PDFplumber / ReportLab** | PDF text extraction & export generation |

### Frontend

| Technology | Purpose |
|---|---|
| **React 18, TypeScript** | UI framework |
| **Vite 8** | Build tool and dev server |
| **Tailwind CSS 4** | Utility‑first styling |
| **`@microsoft/fetch-event-source`** | SSE streaming client |
| **react‑markdown + remark‑gfm** | Rendering LLM markdown output |

---

## Project Structure

```
├── backend/                          # FastAPI Python backend
│   ├── app/
│   │   ├── agents/
│   │   │   ├── resume_tailor.py      # LangGraph state machine (4 nodes)
│   │   │   └── career_assistant.py   # Cover letter & interview prep agent
│   │   ├── api/
│   │   │   ├── resume_routes.py      # POST /api/resume/tailor/stream, /export-pdf
│   │   │   ├── assistant_routes.py   # POST /api/career/cover-letter, /interview-prep
│   │   │   ├── services.py           # Service layer: validation, PDF, streaming, orchestration
│   │   │   ├── rate_limit.py         # Redis‑backed rate limiter
│   │   │   ├── config.py             # Circuit breaker, concurrency manager, service config
│   │   │   └── routes.py             # Shared API router
│   │   ├── core/
│   │   │   ├── config.py             # Pydantic settings (env vars)
│   │   │   ├── llm.py                # Chat model builder (OpenAI or AWS Bedrock)
│   │   │   └── caching.py            # Redis semantic cache with HuggingFace embeddings
│   │   ├── db/
│   │   │   ├── database.py           # SQLAlchemy engine + session
│   │   │   └── models.py             # MasterResume, JobApplication, Generation
│   │   ├── schemas/
│   │   │   └── resume_schemas.py     # Pydantic models (JDValidation, SkillsComparison, state)
│   │   ├── services/
│   │   │   ├── pdf_service.py        # PDF text extraction
│   │   │   ├── pdf_export.py         # Resume PDF generation
│   │   │   └── career_assistant_service.py  # Career service orchestrator
│   │   ├── prompts/
│   │   │   └── resume_tailoring_prompts.py  # All LLM prompts
│   │   └── utils.py                  # Constants (file size, JD length limits)
│   ├── alembic/                      # Database migrations
│   ├── .env.example                  # Environment variable template
│   ├── pyproject.toml
│   └── main.py                       # Dev server entry point
│
├── frontend/                         # React + TypeScript frontend
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts             # Base API client (uses VITE_API_URL)
│   │   ├── components/
│   │   │   ├── ResumeUpload.tsx       # Resume PDF upload
│   │   │   ├── JobDescriptionForm.tsx # Job description text input
│   │   │   ├── StreamingOutput.tsx    # Streaming SSE output view
│   │   │   └── TextOutput.tsx         # Copyable generated text display
│   │   ├── hooks/
│   │   │   ├── useResumeTailor.ts     # Resume tailoring API hook
│   │   │   ├── useCoverLetter.ts      # Cover letter API hook
│   │   │   └── useInterviewPrep.ts    # Interview prep API hook
│   │   ├── pages/
│   │   │   └── ResumeTailor.tsx       # Main tabbed UI
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── package.json
│
└── README.md                         # ← You are here
```

---

## Prerequisites

- **Python 3.14+**
- **Node.js 18+** and **npm** (or yarn / pnpm)
- **Redis** instance (required for rate limiting + semantic cache)
- **PostgreSQL** database
- **LLM API key** — OpenAI‑compatible endpoint or AWS Bedrock access
- **HuggingFace API token** (for semantic cache embeddings)

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd ai-powered-job-helper
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Configure environment
cp .env.example .env   # then edit .env with your credentials
```

See [backend/.env.example](./backend/.env.example) for all available options.

### 3. Frontend

```bash
cd frontend
npm install

# Optional: override the backend URL
echo "VITE_API_URL=http://localhost:8000/api" > .env
```

The frontend defaults to `http://localhost:8000/api` if `VITE_API_URL` is not set.

### 4. Database migrations (if using PostgreSQL)

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

---

## Running the App

### Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs are available at `http://localhost:8000/docs` (hidden in production when `HIDE_DOCS_IN_PRODUCTION=True`).

### Start the frontend (in a separate terminal)

```bash
cd frontend
npm run dev
```

Open the URL shown in the terminal (typically `http://localhost:5173`).

---

## API Overview

All endpoints are prefixed with `/api`.

| Endpoint | Method | Description |
|---|---|---|
| `/api/resume/tailor/stream` | `POST` | Upload resume PDF + job description → streaming tailored resume |
| `/api/resume/export-pdf` | `POST` | Generate a PDF from tailored resume content |
| `/api/career/cover-letter` | `POST` | Generate a cover letter from resume + job description |
| `/api/career/interview-prep` | `POST` | Generate interview Q&A from job description (optional resume context) |
| `/api/health` | `GET` | Health check |

All endpoints are documented interactively at `/docs` (Swagger UI) and `/redoc` (ReDoc) when running in development mode.

---

## Environment Variables

Key environment variables (see [backend/.env.example](./backend/.env.example) for the full list):

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | Yes | `development`, `staging`, or `production` |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `OPENAI_API_KEY` | Conditional | OpenAI API key (when `LLM_PROVIDER=openai`) |
| `LLM_PROVIDER` | Yes | `openai` or `aws` |
| `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Conditional | AWS credentials (when `LLM_PROVIDER=aws`) |
| `HUGGINGFACE_API_TOKEN` | Recommended | Token for semantic cache embeddings |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Optional | LangFuse observability |
| `ALLOWED_ORIGINS` | Yes | Comma‑separated CORS origins |
| `HIDE_DOCS_IN_PRODUCTION` | No | Set `True` to hide Swagger docs in production |
| `ENABLE_SECURITY_HEADERS` | No | Set `True` to enable security response headers |

---

## LangGraph Resume Tailoring Workflow

The resume tailoring is powered by a **4‑node LangGraph state machine**:

1. **`parallel_analyze`** — JD analysis and CV extraction run concurrently
2. **`compare_skills`** — Compares extracted skills, produces matched/missing lists and an ATS score
3. **`rewrite_resume`** — Rewrites the resume to emphasize matching skills
4. **`polish_resume`** — Final polish pass for tone, grammar, and formatting

Only critical nodes emit SSE events to the frontend, enabling **true token‑level streaming** via `astream_events()`.

---

## Build & Deployment

### Frontend production build

```bash
cd frontend
npm run build
npm run preview   # serve the built files locally
```

The production build is output to `frontend/dist/`.

### Backend production considerations

- Set `ENVIRONMENT=production` and `HIDE_DOCS_IN_PRODUCTION=True`
- Configure `ALLOWED_ORIGINS` with your production frontend URL(s)
- Ensure PostgreSQL and Redis are properly secured
- Use a production ASGI server (e.g. `uvicorn` with Gunicorn, or `daphne`)

---

## Notes

- The frontend is optimized for **browser SSE streaming** — the resume is displayed incrementally as the LangGraph workflow progresses
- Make sure the backend is healthy and reachable before using the UI
- Semantic caching reduces LLM costs by reusing responses for semantically similar job descriptions
- The circuit breaker prevents cascading failures when the LLM provider is degraded
