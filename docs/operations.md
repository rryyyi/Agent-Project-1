# Local operation and deployment

## Supported execution model

Python >=3.11, one Uvicorn process, a writable local SQLite path. The default listener is `127.0.0.1:8000`. The workbench has no CDN scripts, frontend package installation or browser-held API keys. `/docs` uses FastAPI's Swagger CDN assets and may require Internet access; the workbench itself does not.

Install with `python -m pip install -e '.[dev]'`. Start with `jewelmentor serve --port 8000`; the module equivalent is `python -m jewelmentor.cli serve`. Settings are read when the application is created. Changing environment variables requires restarting the service. `.env.example` is a reference, not an automatic dotenv loader.

## Persistence and privacy

By default `runtime/jewelmentor.db` stores conversation text, checkpoints and structured training memory. The browser stores only `jewelmentor-session` in localStorage. Treat the database as private data; `.gitignore` and `.dockerignore` exclude it. Session IDs are bearer-like resource identifiers in the unauthenticated demo, not an access-control system.

Use the “清除并新建” button or `DELETE /api/sessions/{id}` to remove related records. SQLite can retain deleted bytes in free pages or backups; deletion is logical and does not claim forensic erasure. Establish retention, secure deletion and backup policy before handling real customer data.

For a consistent backup stop the server, then copy the database. If copying a live WAL database, use the SQLite backup API instead of copying only the `.db` file. There are no migrations yet; preserve a backup before changing versions.

## Docker

```bash
docker build -t jewelmentor:0.1.0 .
docker run --rm -p 127.0.0.1:8000:8000 -v jewelmentor-data:/app/runtime jewelmentor:0.1.0
```

The container runs as a non-root application user and stores data under `/app/runtime`. Named volumes created by Docker use the directory's initial ownership; bind mounts need write permissions for UID 10001. Production secrets should be injected through a secrets manager. For a local experiment, an environment file can be passed to Docker with `--env-file .env`; Docker, rather than the Python application, loads that file.

The Dockerfile binds inside the container to `0.0.0.0`; publishing with `127.0.0.1:8000:8000` limits the host listener. Do not publish this unauthenticated service directly on the Internet.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `jewelmentor` command not found | Activate the virtual environment or use `.venv/Scripts/python -m jewelmentor.cli serve` on Windows |
| Key missing on startup | Set `JEWELMENTOR_PROVIDER=demo`, or supply `OPENAI_API_KEY` for live mode |
| `provider_auth` | Check key validity and permissions; do not paste secrets into an Issue |
| `provider_request` | Check base URL, model identifier and support for `max_tokens`/`temperature` |
| `provider_timeout` | Check connectivity and model speed; cautiously increase node/turn budgets |
| HTTP 409 for a new message | Inspect unfinished turns and use the recovery endpoint |
| HTTP 409 on repeated key | Use the same payload for retries, or a fresh request key for a new task |
| `database is locked` | Ensure one process and writable local storage; stop duplicate servers |
| Page has old session ID | If the session was deleted, reload; startup handles 404 by creating a new session |
| Port already used | `jewelmentor serve --port 8001` |
| Offline answer feels repetitive | DemoProvider is an explicit template baseline; configure a live model for open-ended coaching |

## Public deployment checklist

Public deployment is outside v0.1.0's contract. Required changes include authenticated resource ownership, tenant isolation, rate limits, request-body limits, CSRF/origin policy as appropriate, TLS, retention controls, stable schema migrations, monitoring and tested backups. Replace process-local locks with durable leases before adding processes. Model safety, semantic citation correctness and prompt-injection resistance require their own online evaluation.
