### Plan: CareerAI - Step-by-Step Job Application Assistant

**Steps**

**Phase 1: Foundation & Project Setup**
1. **Setup Monorepo**: Initialize frontend (Vite + React + Tailwind) and backend (FastAPI + Python).
2. **Database Setup**: Configure PostgreSQL with SQLAlchemy & Alembic (tables: `master_resumes`, `job_applications`, `generations`). No complex auth tables needed.
3. **Basic API Structure**: Set up base FastAPI routers, CORS, and strict Pydantic schemas.

**Phase 2: Smart Resume Tailor (Week 1)**
4. **Document Processing**: Implement backend PDF parsing (`pdfplumber`/`pypdf`) to extract text from the master resume.
5. **AI Workflow**: Build the Resume Tailor LangGraph agent: Parse JD -> Extract Skills -> Compare with master -> Rewrite sections.
6. **Streaming API**: Create FastAPI endpoints using `StreamingResponse` to stream Claude's output in real-time.
7. **Frontend UI**: Build React components for resume upload, JD input, and real-time streaming text display.
8. **Export**: Implement PDF generation (`reportlab`) on the backend to export the finalized tailored resume.

**Phase 3: Cover Letters & Interview Prep (Week 2)**
9. **Cover Letter Agent**: Build langchain open ai for Cover Letters, reusing the JD extraction logic.
10. **Interview Prep Agent**: Build langchain workflow to extract role context, map user projects to STAR method, and predict 20 likely questions and answers.
11. **Frontend Integration**: Build React UI views for the Cover Letter and Interview Prep generation. if user click on interview question then only jd is required but if user click on cover letter then both jd and resume required.
12. **Observability**: Integrate langfuse to monitor LLM traces, token usage, and prompt effectiveness.

**Phase 4: Dashboard & Job Matching (Week 3)**
13. **Data Extraction**: Build an initial resume parser to auto-extract structured data (skills, projects, metrics) on upload.
14. **Match Agent**: Build the Job Matching agent to score skill overlap (0–100), identify gaps, and estimate fit.
15. **Dashboard UI**: Build a React dashboard showing application history, match scores, and a 1-click "Generate Materials" button.

**Phase 5: Polish, Monetization & Launch (Week 4)**
16. **Monetization**: Integrate Stripe Checkout links based on email alone (avoiding complex signup flows).
17. **Security/Stability**: Implement rate limiting, input validation, and proper error handling.
18. **Deployment**: Deploy PostgreSQL and FastAPI backend to Railway, and React frontend to Vercel.
19. **Launch**: Dogfood the product with real applications and launch on ProductHunt/Twitter.

**Production Folder Structure**
- `/frontend`
  - `/src/components` — Reusable UI (buttons, cards, streaming text blocks)
  - `/src/hooks` — Custom React hooks for API and SSE (Server-Sent Events)
  - `/src/pages` — Dashboard, Resume, Cover Letter, Interview Prep
  - `/src/api` — API client configuration
- `/backend`
  - `/app/api` — FastAPI endpoints (divided by feature, no auth middleware)
  - `/app/core` — Config, database connection, rate limiting
  - `/app/db` — SQLAlchemy models and Alembic migrations
  - `/app/agents` — LangGraph graphs, nodes, prompts, Claude API logic
  - `/app/services` — PDF extraction, ReportLab generation, Stripe integration

**Verification**
1. Test PDF parsing to ensure it accurately grabs text without mangling columns.
2. Verify LangGraph agent flows via LangFuse to ensure it doesn't hallucinate skills.
3. Test Server-Sent Events (SSE) streaming latency for smooth frontend UX.
4. Manually verify PDF export styling and formatting.

**Decisions**
- Removed Firebase/JWT auth to drastically speed up time-to-market. The app operates locally or via simple session tracking. 
- Using a Monorepo approach for easier coordination between frontend and backend.
- Using SSE for streaming to keep it lightweight compared to WebSockets.