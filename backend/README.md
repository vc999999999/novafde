# NovaFDE Backend

Local-only FastAPI backend for the PydanticAI quality loop.

## Run

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --reload
```

## Test

```bash
.venv/bin/python -m pytest backend/tests -q
```

Production storage is SQLite only. Provider credentials use the system keychain
when available and an encrypted local store otherwise.
