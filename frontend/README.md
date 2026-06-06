# CareerAI Frontend

Frontend application for CareerAI, built with React, TypeScript, Vite, and Tailwind CSS.

## Features

- Upload resume PDF
- Enter a job description
- Generate tailored resume output via streaming SSE
- Generate targeted cover letters
- Generate interview prep questions and answers
- Copy generated text to clipboard

## Requirements

- Node.js 18+
- npm, yarn, or pnpm
- Backend API running and accessible via `VITE_API_URL`

## Setup

```bash
cd frontend
npm install
```

## Environment

Create a `.env` file in `frontend/` if you want to override the backend base URL:

```env
VITE_API_URL=http://localhost:8000/api
```

The app defaults to `http://localhost:8000/api` if `VITE_API_URL` is not provided.

## Run

```bash
npm run dev
```

Open the local URL shown in the terminal to use the UI.

## Build

```bash
npm run build
npm run preview
```

## Code structure

- `src/pages/ResumeTailor.tsx` - Main UI and tabbed workflows
- `src/components/ResumeUpload.tsx` - Resume upload component
- `src/components/JobDescriptionForm.tsx` - Job description form
- `src/components/StreamingOutput.tsx` - Streaming resume output view
- `src/components/TextOutput.tsx` - Copyable generated text display
- `src/hooks/useResumeTailor.ts` - API hook for resume tailoring
- `src/hooks/useCoverLetter.ts` - API hook for cover letter generation
- `src/hooks/useInterviewPrep.ts` - API hook for interview prep generation
- `src/api/client.ts` - Base API client with `VITE_API_URL`

## Notes

- The frontend is optimized for browser streaming and incremental resume generation.
- Make sure the backend is healthy and reachable before using the app.
