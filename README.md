# fastapi-audit

FastAPI service with SQLAlchemy, **model change auditing** (decorators, sanitization, session listeners), and HTML audit panels for inspection during development.

## Requirements

- Python 3.12+
- PostgreSQL (or SQLite for local tests; see `tests/conftest.py`)

## Run locally

Set `DATABASE_URL` (for example in a `.env` file loaded by your process manager). Then:

```bash
uvicorn fastapi_audit.main:app --reload
```

Open `/docs` for the interactive OpenAPI UI.

## Docker (development)

```bash
docker compose -f docker-compose.dev.yml up --build
```

The API is exposed on port `8000` by default. Adjust `env.dev` and compose settings as needed.

## Use this repo as a package in another project

The installable distribution name is `fastapi-audit`. Imports use the top-level package **`fastapi_audit`** (Python module names cannot contain hyphens).

**Public audit API** (single entry point for other projects):

```python
from fastapi_audit.audit import (
    audited,
    AuditBase,
    Audit,
    attach_audit_request_context,
    set_audit_request_context,
    validate_audit_models,
    register_audit_strategy,
    AuditRequestContext,
)
```

- `attach_audit_request_context(session, request, changed_by=...)` — FastAPI/sync or async session + `Request`; optional `changed_by` (defaults to anonymous).
- `set_audit_request_context(session, AuditRequestContext(...))` — scripts, workers, or tests without an HTTP request.

Deeper imports (e.g. `fastapi_audit.models.audit.decorators`) still work but are optional.

### Editable install (recommended while you develop)

From this repository’s root (your own venv):

```bash
pip install -e .
pip install -e ".[dev]"   # optional: pytest, ruff, mypy, etc.
```

From **another** project’s virtual environment, point at this checkout:

```bash
pip install -e /absolute/path/to/fastapi-audit
```

On Windows (PowerShell), use a path like `C:\Users\you\repos\fastapi-audit`. Edits in that folder are visible to Python immediately; you do not copy the code into the other project.

With development tools:

```bash
pip install -e "/absolute/path/to/fastapi-audit[dev]"
```

### Non-editable install

```bash
pip install /absolute/path/to/fastapi-audit
```

Or build a wheel and install it:

```bash
pip install build
python -m build
pip install dist/fastapi_audit-0.1.0-py3-none-any.whl
```

### Integrating in your own FastAPI app

You typically import the pieces you need (audit mixins, `audited` decorator, sanitize helpers, optional panel router) and wire your own `FastAPI` instance, database session, and models. This repository’s `fastapi_audit/main.py` shows one full wiring example (lifespan, routers, static files).

## Tests

Unit tests (default collection skips Docker integration tests):

```bash
python -m pytest tests -v
```

Integration tests (PostgreSQL via Testcontainers; Docker must be running):

```bash
python -m pytest tests/integration -v
```

Examples:

```bash
python -m pytest tests/unit/audit/test_sanitize.py -v
python -m pytest tests/unit/audit/test_sanitize.py::test_mask_none_and_scalar -v
```

## Project layout (high level)

| Path | Role |
|------|------|
| `fastapi_audit/main.py` | FastAPI app factory and router registration |
| `fastapi_audit/models/audit/` | Audit ORM base, decorators, validation, listeners |
| `fastapi_audit/services/audit/` | Sanitization, request context, custom strategies |
| `fastapi_audit/panels/` | Optional audit HTML panel (Jinja + static assets under `fastapi_audit/templates`, `fastapi_audit/static`) |

