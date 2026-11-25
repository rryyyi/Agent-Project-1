# Verification record

This file distinguishes executed checks from configured checks. Initial public implementation date: 2026-11-25. Local environment: Windows, Python 3.14.4, Node 24.14.1, Chrome headless. The CI matrix independently targets Python 3.11, 3.12 and 3.13 on Linux.

## Local evidence

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 44 tests passed; no warnings in the final supported dependency configuration |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed |
| `node --check src/jewelmentor/static/app.js` | Passed |
| `jewelmentor evaluate --output docs/evaluation/demo-report.json` | Routing 30/30; completed 6/10; expected scenario contracts 10/10; zero unexpected failures |
| `python -m build --no-isolation` | Source distribution and wheel built |
| Wheel package-data inspection | Persona/knowledge/evaluation JSON and static UI present |
| Installed-wheel evaluation outside repository | Passed locally in a separate environment; GitHub CI also passed artifact installation/evaluation on Python 3.11–3.13 |
| Real browser + actual local HTTP service | Scenario chat, evidence, explicit expert switch, reload, mobile width, delete and sidebar reset passed; zero page errors |
| Docker CLI | Local Linux daemon not running; local image build/run not executed. GitHub Linux CI built the image and passed container health/API checks |
| Live external model | Not executed; no user model key configured or consumed |

Reproduce the browser check with:

```bash
python -m pip install -e '.[browser]'
playwright install chromium
python scripts/browser_smoke.py --screenshot runtime/workbench.png
```

For an installed Chrome/Edge, pass `--executable` with its path. The script launches a disposable local service and database and cleans them up. Its desktop screenshot generated the README image.

## Review

Author self-review was performed using the code-review checklist because no independent subagent tool was available. This is not an independent review. The pass checked the approved design, request-key conflicts, recovery semantics, expert/context switching, provider error boundaries, deletion and package inclusion.

Two behavioral findings were reproduced before fixing:

1. A total deadline reached during a generation wait was reported as `provider_timeout`. `test_total_deadline_is_not_reported_as_provider_timeout` failed first, then passed after classification was corrected.
2. Clearing a session left old inspector fields on screen. The real-browser reset assertion failed first, then passed after empty-session inspector reset was added.

Additional tests pin consumed-attempt recovery, provider-mode recovery refusal and validation-error secret masking. No claim of production readiness, independent security audit or live-model quality is made.

## GitHub CI evidence

[Initial complete CI run](https://github.com/rryyyi/Agent-Project-1/actions/runs/45542105890), commit `e2729eab4b211a819fd0fa919b66e647a7c8174c`: **success**.

- Python 3.11: tests, lint/format, evaluation, build and installed-wheel checks passed.
- Python 3.12: all checks passed.
- Python 3.13: all checks passed.
- Browser and container: Chromium training flow passed; Docker image built and container health/session API checks passed.

Later documentation/formatting commits have their own CI runs linked from the repository's Actions tab. The badge always reflects the latest workflow status; the run above is a fixed evidence link, not a claim that every future commit passes.

## Repository checks

Before staging, the local resume PDF, environment files, virtual environment, databases and private scratch are verified ignored. Only explicit project paths are staged. Commits use the GitHub account's public noreply identity. Remote main is checked after push and CI status is reported separately from local test status.

## Known limitations

The classifier and role/learning checks are narrow development baselines. No distributed locking, authorization, semantic citation validation, database migrations or live-model adversarial benchmark is included. These are documented design boundaries, not passing tests for unimplemented production capabilities.
