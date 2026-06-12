# CareerAI Backend

Backend API for CareerAI: AI-powered resume tailoring, cover letter generation, and interview prep.

## Features

- FastAPI backend with streaming resume tailoring
- PDF resume upload and text extraction
- Redis-backed rate limiting
- Job description validation and length limits
- Circuit breaker and concurrency protection
- Tailored resume export to PDF
- Cover letter and interview prep endpoints

## Requirements

- Python 3.14+
- Redis instance
- Backend virtual environment
- Environment variables configured

## Environment

Create a `.env` file in `backend/` with values for:

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
REDIS_URL=redis://localhost:6379
LLM_PROVIDER=openai  # or aws

# OpenAI settings
OPENAI_API_KEY=your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1

# AWS Bedrock settings (when LLM_PROVIDER=aws)
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=your-aws-access-key-id
# AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
# AWS_SESSION_TOKEN=your-aws-session-token
# AWS_CREDENTIALS_PROFILE_NAME=your-aws-profile-name
# AWS_MODEL_PROVIDER=mistral
# AWS_FAST_MODEL_NAME=mistral.voxtral-mini-3b-2507

LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_BASE_URL=https://api.langfuse.com
HUGGINGFACE_API_TOKEN=your-huggingface-token
```

> `REDIS_URL` is required for rate limiting and semantic cache support.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Resume Tailor

- `POST /api/resume/tailor/stream`
  - Form fields: `cv_file` (PDF), `job_description`
  - Returns server-sent events for streaming resume output

- `POST /api/resume/export-pdf`
  - JSON: `{ "resume_text": "..." }`
  - Returns generated PDF file

### Career Assistant

- `POST /api/career/cover-letter`
  - Form fields: `cv_file` (PDF), `job_description`

- `POST /api/career/interview-prep`
  - Form fields: `job_description`, optional `cv_file`

### Health & status

- `GET /health`
- `GET /api/resume/status`
- `GET /api/career/status`

## Notes

- Resume upload file size is limited to 10 MB.
- Job descriptions are validated between 50 and 5000 characters.
- Rate limiting is enforced with Redis, defaulting to 20 requests per client per 60 seconds.
- Concurrency limits and circuit breaker behavior are defined in `backend/app/api/config.py`.
