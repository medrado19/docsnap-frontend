# Revnio Backend (FastAPI)

Basic backend structure with FastAPI + PostgreSQL.

## Run

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variable (or use `.env`):

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/revnio
```

4. Start API:

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `POST /upload-invoice`
- `GET /invoices`
- `DELETE /invoice/{id}`
- `POST /income`
- `GET /income`
- `DELETE /income/{id}`
