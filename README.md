# prepAIred Backend

FastAPI + Supabase backend for **prepAIred** — an AI-powered exam preparation platform for JEE and NEET.

## Features

- **Score Calculation** — Processes student test attempts: computes section/chapter scores, difficulty breakdowns, topic-level stats, and blunder detection.
- **Analytics Processing** — Tracks chapter-wise progress, calculates percentile rankings, and maintains per-user history on GitHub.
- **GitHub Integration** — Stores score results and analytics history as JSON files in a GitHub repository.
- **JWT Authentication** — Supabase JWT verification (toggleable via `ENABLE_AUTH`).
- **Async/Await** throughout all database and external API operations.
- **Docker** support.

## Project Structure

```
.
├── app
│   ├── api
│   │   ├── deps.py               # Auth dependency injection
│   │   ├── api.py                # Router aggregation
│   │   └── endpoints
│   │       ├── scores.py         # Score calculation endpoint
│   │       └── analytics.py      # Analytics processing endpoint
│   ├── core
│   │   ├── config.py             # Environment configuration
│   │   ├── security.py           # JWT verification
│   │   └── supabase.py           # Supabase client manager
│   ├── schemas
│   │   ├── score.py              # Score response schema
│   │   └── common.py             # Shared API response wrapper
│   ├── services
│   │   ├── score_service.py      # Scoring business logic
│   │   └── analytics_service.py  # Analytics business logic
│   ├── main.py                   # App entrypoint
│   └── __init__.py
├── chapters.json                 # Master chapter-to-topics mapping (loaded at runtime)
├── tests
│   └── test_score_service.py
├── .env.example
├── Dockerfile
├── requirements.txt
└── README.md
```

## API Endpoints

All routes are prefixed with `/api/v1`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/scores/{student_test_id}/calculate` | Calculate score for a student test attempt |
| `POST` | `/analytics/process-attempt` | Process a test attempt to update user analytics |

### `POST /scores/{student_test_id}/calculate`

Fetches the student test and its test definition, calculates scores, pushes the result JSON to GitHub, stores the result URL in Supabase, and triggers analytics processing.

**Path parameter:** `student_test_id` — UUID of the row in the `student_tests` table.

**Response:**
```json
{
  "student_test_id": "uuid",
  "github_url": "https://raw.githubusercontent.com/..."
}
```

### `POST /analytics/process-attempt`

Processes a completed test attempt to update chapter-wise analytics and user history.

**Request body:**
```json
{
  "test_attempt_id": "uuid"
}
```

**Response:** Updated analytics object.

## Setup

1. **Clone and create a virtual environment:**
   ```bash
   git clone <repo-url>
   cd <repo-name>
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   Fill in the values — see [Environment Variables](#environment-variables) below.

4. **Run:**
   ```bash
   uvicorn app.main:app --reload
   ```
   API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase `anon` key |
| `SUPABASE_SERVICE_ROLE_KEY` | No | Service role key — bypasses RLS for server-side operations |
| `SUPABASE_JWT_SECRET` | Yes | Found in Supabase Project Settings → API |
| `GITHUB_TOKEN` | Yes | Personal access token with repo write access |
| `GITHUB_REPO` | Yes | Target repo for storing results (e.g. `org/repo`) |
| `PROJECT_NAME` | No | Defaults to `prepAIred Backend` |
| `API_V1_STR` | No | API prefix, defaults to `/api/v1` |
| `BACKEND_CORS_ORIGINS` | No | Comma-separated list of allowed CORS origins |

## Database Schema (Supabase)

```sql
-- Stores test definitions
create table public.tests (
  "testID" text primary key,
  url text not null  -- GitHub raw URL to the test JSON
);

-- Stores individual student test attempts
create table public.student_tests (
  id uuid default gen_random_uuid() primary key,
  user_id uuid not null,
  test_id text references public.tests("testID"),
  answers jsonb,
  result_url text,  -- populated after score calculation
  created_at timestamp with time zone default now()
);

-- Stores per-user analytics
create table public.user_analytics (
  user_id uuid primary key,
  data jsonb
);
```

## Docker

```bash
docker build -t prepaired-backend .
docker run -p 8000:8000 --env-file .env prepaired-backend
```

## Running Tests

```bash
pytest tests/
```
