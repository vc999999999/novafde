# Model Evals

Run this suite only when a tested real Provider is configured locally:

```bash
PYTHONPATH=backend .venv/bin/python backend/evals/run_model_evals.py --repeat 3
```

The suite uses Pydantic Evals and real PydanticAI generation calls. It is
separate from deterministic unit and integration tests so normal test runs work
offline and do not consume model tokens.
