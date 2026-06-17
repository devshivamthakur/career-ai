# CareerAI — AI-Powered Job Application Assistant

> An intelligent job application assistant powered by AI — tailors résumés, generates cover letters, prepares you for interviews, and answers career-related questions through a conversational chat agent.

🔗 **Live Demo:** [career-ai-tan.vercel.app/chat](https://career-ai-tan.vercel.app/chat)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AI Chat Agent** | Conversational career assistant with tool-calling, session memory, and real-time SSE streaming |
| 📄 **Resume Tailoring** | Upload a PDF resume + paste a job description → get an ATS-optimized, tailored resume with matched/missing skills breakdown |
| ✍️ **Cover Letter Generation** | Generate tailored, 3-paragraph cover letters based on your resume and job context |
| 🎤 **Interview Preparation** | Generate role-specific questions with STAR-format answers, optionally personalized with your project experience |
| 📊 **ATS Score** | Real-time compatibility scoring with visual ring indicator (0–100) |
| 📎 **PDF Export** | Download your tailored resume as a polished PDF |

## 🏗️ Architecture

```
ai-powered-job-helper/
├── backend/          # FastAPI + Python backend
│   ├── app/
│   │   ├── agents/       # LangGraph workflows & LangChain agents
│   │   ├── api/          # REST routes (resume, chat, career assistant)
│   │   ├── core/         # Config, LLM builder, caching, rate limiting
│   │   ├── db/           # SQLAlchemy models + Alembic migrations
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # Business logic (chat sessions, PDF, validation)
│   │   └── prompts/      # LLM system prompts
│   └── alembic/          # Database migration scripts
├── frontend/         # React + TypeScript + Vite SPA
│   └── src/
│       ├── components/   # UI components (chat, resume, career, layout, shared)
│       ├── pages/        # Route pages (/chat, /resume, /cover-letter, /interview)
│       ├── stores/       # Zustand state management
│       ├── hooks/        # Custom React hooks (SSE streaming, chat sessions, etc.)
│       └── api/          # API client utilities
└── README.md         # ← You are here
```

## 🧰 Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3.14+ / FastAPI** | Async web framework |
| **LangGraph** | Resume tailoring workflow (4-node state machine) |
| **LangChain (create_agent)** | Unified AI agent with middleware, tools & structured output |
| **LangChain-OpenAI / AWS Bedrock** | Multi-provider LLM invocation |
| **LangFuse** | LLM observability & tracing |
| **Redis** | Rate limiting & semantic caching |
| **PostgreSQL** | Primary database (SQLAlchemy + Alembic) |
| **PDFplumber / ReportLab** | PDF extraction & generation |
| **HuggingFace Embeddings** | Semantic cache similarity (`BAAI/bge-base-en-v1.5`) |

### Frontend
| Technology | Purpose |
|---|---|
| **React 19** | UI framework |
| **Vite 8** | Build tool & dev server |
| **Tailwind CSS v4** | Utility-first styling |
| **React Router v7** | Client-side routing |
| **Zustand** | Lightweight state management |
| **TanStack Query v5** | Server state & mutations |
| **Lucide React** | Icon library |
| **fetch-event-source** | SSE streaming client |

## 🚀 Getting Started

### Prerequisites
- Python 3.14+
- Node.js 22+
- Redis (for caching & rate limiting)
- PostgreSQL (optional, for persistence)

### Backend Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys (OpenAI / AWS Bedrock)

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:5173` and proxies `/api` requests to the backend.

### Environment Variables (Backend)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `AWS_ACCESS_KEY_ID` | AWS credentials (Bedrock) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials (Bedrock) |
| `REDIS_URL` | Redis connection string |
| `DATABASE_URL` | PostgreSQL connection string |
| `LANGFUSE_PUBLIC_KEY` | LangFuse observability |
| `LANGFUSE_SECRET_KEY` | LangFuse observability |

## 🧪 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Health check |
| `POST` | `/api/chat/stream` | SSE streaming chat with AI agent |
| `POST` | `/api/resume/tailor/stream` | Streaming resume tailoring (4 stages) |
| `POST` | `/api/resume/export-pdf` | Download tailored resume as PDF |
| `POST` | `/api/career/cover-letter` | Generate a cover letter |
| `POST` | `/api/career/interview-prep` | Generate interview Q&A |

## 📁 Frontend Pages

| Route | Page | Description |
|---|---|---|
| `/chat` | ChatPage | Conversational AI career assistant with tool-calling |
| `/resume` | ResumePage | Upload resume + JD → tailored ATS-optimized resume |
| `/cover-letter` | CoverLetterPage | Generate tailored cover letters |
| `/interview` | InterviewPage | Generate interview questions with STAR answers |

## 🛡️ Infrastructure

- **Semantic Caching** — Redis + HuggingFace embeddings cache LLM responses for similar JDs
- **Rate Limiting** — 20 requests/client/60s (Redis-backed Token Bucket)
- **Circuit Breaker** — Opens when error rate exceeds 10% in a 60s window
- **Concurrency Management** — asyncio semaphores (max 10 concurrent requests, max 5 concurrent PDF parses)
- **Security Headers** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **Request ID Tracking** — Every request gets a unique `X-Request-ID`

---

Built with ❤️ using FastAPI, LangChain, React, and Tailwind CSS.
