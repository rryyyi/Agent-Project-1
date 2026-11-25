# JewelMentor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver an inspectable, runnable jewelry-sales training agent portfolio with reproducible evidence and publish it to the authorized GitHub repository.

**Architecture:** A local-first modular Python service. Typed handoff envelopes connect supervisor, recommendation and dialogue; a SQLite-backed state machine owns durable turns, events and checkpoints. Provider injection keeps offline evaluation independent of paid models.

**Tech Stack:** Python >=3.11, FastAPI, Pydantic 2, httpx, SQLite, pytest, Ruff, vanilla browser UI, Docker, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-25-jewelmentor-design.md` (approved by user: 按方案做).

## Global Constraints

- Work in the user-designated current directory; it is a new repository without pre-existing product code. No separate worktree is needed for this initial implementation.
- Never stage the local resume PDF, environment secrets, runtime conversations or databases.
- Default provider is explicitly labeled offline demo; live provider failures must be visible.
- Synthetic persona biographies and knowledge records are original teaching examples.
- Resume metrics 94% / 96% / 98.2% are not repository measurements.
- Local single-process execution only; authentication and distributed locking are production extension work.
- User authorized implementation, testing, maintenance files and push. Execute inline with available tools; no additional workflow approval round.

## Review Focus

1. Duplicate request keys with a different payload must conflict rather than return somebody else's answer (Task 2).
2. Interrupted generation must resume from persisted evidence and context without duplicating the user message (Task 2).
3. Explicit expert switching must override previous preference while preserving shared conversation (Tasks 1–2).
4. Invalid provider configuration and non-retryable upstream responses must fail visibly without leaking secrets (Tasks 3–4).
5. Session deletion must remove memory, turns and trace rows and be serialized with in-flight messages (Tasks 2–4).

## File Structure

- `src/jewelmentor/models.py`: validated public schemas, state transitions, handoff contract.
- `src/jewelmentor/catalog.py`, `routing.py`, `data/*.json`: skills, knowledge and explainable routing/retrieval.
- `src/jewelmentor/store.py`: transactional sessions, messages, events, turn checkpoints and memory.
- `src/jewelmentor/harness.py`: orchestration, deadline/retry/hop budgets, resumption, idempotency and per-session locking.
- `src/jewelmentor/providers.py`, `config.py`: safe prompt assembly, demo/live generation and configuration.
- `src/jewelmentor/api.py`, `static/*`: local API and training workbench.
- `src/jewelmentor/evaluation.py`, `cli.py`, `data/eval.json`: reproducible offline reports and entry points.
- `tests/test_*.py`: behavior and fault-injection tests.
- `README.md`, `docs/*`, `.github/*`: walkthroughs, reference, deployment and maintenance.

### Task 1: Contracts, persona catalog, routing and retrieval

**Interfaces:** `route(text) -> Route`; `Catalog.expert(id) -> Expert`; `Catalog.recommend(intent, requested) -> Expert`; `Catalog.search(text, intent) -> list[Evidence]`; `Handoff` with source/target validation, `advance(state, target)`.

- [x] Write `tests/test_domain.py`: classify budget/objection/product/relationship/practice/clarify, reject bad target/empty goal/zero hop budget, expert override, unknown expert, evidence IDs and data validation.
- [x] Run `python -m pytest tests/test_domain.py -q`; confirm missing domain implementation fails.
- [x] Implement `models.py`, `catalog.py`, `routing.py` and original JSON data with bounded fields and deterministic low-confidence clarification.
- [x] Run domain tests and full available suite.

### Task 2: Durable orchestration and recovery

**Interfaces:** `Store(path)`, `create_session()`, `session(id)`, `trace(id)`, `delete_session(id)`; `Harness(store, catalog, provider, settings).chat(session_id, ChatRequest) -> TurnResult`; `.resume(session_id, turn_id) -> TurnResult`.

- [x] Write `tests/test_harness.py`: happy path, transient retry, timeout degradation, permanent failure, illegal state, handoff/hop budget, duplicate vs conflicting keys, parallel sessions, same-session serialization, shared context/expert switch, process restart session read, checkpoint resume, restart after user append, memory deletion, bounded context.
- [x] Run harness tests and observe missing implementation.
- [x] Implement transactional turn preparation/checkpoints, finite-state transitions/events and node retry loop. Persist before generation; commit assistant + terminal result atomically. Resume only incomplete turns and avoid repeating completed nodes.
- [x] Run harness tests and full suite.

### Task 3: Providers and configuration

**Interfaces:** async `Provider.generate(GenerationContext) -> str`; `DemoProvider`, `OpenAIProvider(settings, transport=None)`; `Settings.from_env()` with validated HTTPS/default localhost settings.

- [x] Write `tests/test_providers.py`: explicit demo wording, context/skill/evidence prompt assembly, HTTP completion, 429/5xx transient vs 401 permanent, malformed/empty response, secret-safe exception, bounded output, missing key rejection.
- [x] Run provider tests to verify red, implement provider/configuration, then run full suite.

### Task 4: API, browser UI and runnable package

**Interfaces:** `create_app(settings=None, provider=None) -> FastAPI`; REST routes from design plus explicit recovery endpoint; `jewelmentor serve`.

- [x] Write `tests/test_api.py`: creation/chat/history/traces/citations/deletion, validation/404/409, metadata, safe configuration, recovery, static page availability.
- [x] Verify failures; implement API, CLI serve and asset packaging. Build a responsive Chinese workspace with expert selection, scenario prompts, answer/evidence and node trace. Use textContent for all untrusted text; persist only session ID in browser.
- [x] Verify suite, launch service and issue real HTTP smoke requests; perform JavaScript syntax check.

### Task 5: Evaluation and reports

**Interfaces:** async `evaluate() -> dict`; `jewelmentor evaluate --output path` writes structured JSON; dataset version and hash included.

- [x] Write `tests/test_evaluation.py`: denominator consistency, regression failures, fault categories, role/learning proxy labeling and result output.
- [x] Verify red; implement versioned routing set and scenario suite, per-case failures, exact denominators and explicit no-human-rating disclaimer.
- [x] Run offline evaluation and record actual results in committed `docs/evaluation/demo-report.json`; provide reproduction and interpretation.

### Task 6: Professional delivery and publication

- [x] Add Chinese README, English overview, architecture/reliability/operations/evaluation docs and screenshot or original SVG overview.
- [x] Add Dockerfile, .env.example, CI Python 3.11–3.13, dependency updates, LICENSE, SECURITY, CONTRIBUTING, CHANGELOG, templates.
- [x] Run `python -m pytest`, `ruff check .`, `ruff format --check .`, package build/install and CLI/API smoke tests. Run fault checks and review actual results, source/data inclusion and ignored files.
- [x] Read requesting-code-review and verification-before-completion; available-tool self-review explicitly described as such.
- [x] Commit logical slices with configured repository-local author identity tied to GitHub account; push without force. If Git transport fails, diagnose connectivity/credential availability without exposing tokens.
- [x] Verify remote main commit and CI using GitHub API, then report implementation, commands/results and any remaining limitations. Evidence: CI run 45542105890, all four jobs successful.

## Self-review

All spec sections map to tasks above. Recovery API is added to make the specified checkpoint behavior actionable. Restart recovery provides at-least-once model calls and exactly-once local response commit; it cannot promise exactly-once upstream billing. No independent reviewer tool is available; inline review and fault tests are the supported execution path.
