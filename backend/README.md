# NovaFDE Backend

Local-only FastAPI backend for the PydanticAI quality loop.

## Run

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --reload
```

Production storage is SQLite only. Provider credentials use the system keychain
when available and an encrypted local store otherwise.

## Key modules

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI routes and application factory |
| `service.py` | App-level orchestration and draft lifecycle |
| `orchestrator.py` | Staged generation pipeline and quality loop |
| `spec_builder.py` | Immutable SkillSpec construction and SHA256 trace |
| `renderer.py` | Deterministic SKILL.md and package rendering |
| `validator.py` | Validation, spec compliance, and skills-ref checks |
| `quality.py` | Score aggregation and candidate selection |
| `storage.py` | SQLite persistence for drafts, generations, and providers |
| `provider_runtime.py` | Model provider connection, test, and inference calls |
| `packager.py` | Manifest generation and zip packaging |
| `secret_store.py` | Keychain and encrypted local secret storage |
