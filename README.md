# FastAPI Supabase Boilerplate

This is a production-ready boilerplate for building a backend with **FastAPI** and **Supabase**. It includes authentication, CRUD operations, and a modular structure.

## Features

- **FastAPI** for high performance and easy API building.
- **Supabase** integration for Database and Auth.
- **Async/Await** for all database operations.
- **Pydantic** models for validation.
- **JWT Authentication** middleware.
- **Modular Architecture**.
- **Docker** support.

## Project Structure

```
.
├── app
│   ├── api
│   │   ├── deps.py          # Dependencies (Auth, etc.)
│   │   ├── endpoints        # API Routes
│   │   │   └── items.py
│   │   └── api.py           # Route Aggregation
│   ├── core
│   │   ├── config.py        # Environment Configuration
│   │   ├── security.py      # Auth Utils
│   │   └── supabase.py      # Supabase Client
│   ├── schemas
│   │   ├── common.py        # Shared Schemas
│   │   └── item.py          # Item Schemas
│   ├── services
│   │   └── item_service.py  # Business Logic
│   ├── main.py              # App Entrypoint
│   └── __init__.py
├── .env.example
├── Dockerfile
├── requirements.txt
└── README.md
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repo-url>
    cd <repo-name>
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    Copy `.env.example` to `.env` and fill in your Supabase credentials.
    ```bash
    cp .env.example .env
    ```
    - `SUPABASE_URL`: Your project URL.
    - `SUPABASE_KEY`: Your `service_role` key (for admin access) or `anon` key depending on your RLS policies. This boilerplate generally expects a key that can perform the operations defined in `ItemService`.
    - `SUPABASE_JWT_SECRET`: Found in Project Settings -> API.

5.  **Run the application:**
    ```bash
    uvicorn app.main:app --reload
    ```
    The API will be available at `http://localhost:8000`.
    Documentation: `http://localhost:8000/docs`.

## Database Setup (Supabase)

To use the `Items` example, run the following SQL in your Supabase SQL Editor:

```sql
create table public.items (
  id uuid default gen_random_uuid() primary key,
  title text not null,
  description text,
  owner_id uuid not null, -- references auth.users(id) if you want to link strictly
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now())
);

-- Enable RLS
alter table public.items enable row level security;

-- Policy: Allow read access to everyone (example)
create policy "Enable read access for all users" on public.items for select using (true);

-- Policy: Allow full access to authenticated users for their own items
create policy "Enable all access for owners" on public.items for all using (auth.uid() = owner_id);
```

## Docker

Build and run using Docker:

```bash
docker build -t fastapi-supabase .
docker run -p 8000:8000 --env-file .env fastapi-supabase
```
