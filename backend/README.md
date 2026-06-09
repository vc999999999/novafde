# SkillForge Backend

FastAPI backend for the local-first SkillForge MVP.

## Run

```bash
python3 -m uvicorn app.main:app --app-dir backend --reload
```

## Test

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
```
