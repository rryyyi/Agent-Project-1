# Changelog

Changes use semantic versioning. Dates refer to this public implementation, not the employment dates of the source resume scenario.

## [0.1.0] - 2026-11-25

### Added

- Three-layer Supervisor / Recommendation / Dialogue orchestration with validated Handoff v1.
- Explicit finite state machine, bounded retries/timeouts, hop budgets and sanitized failure categories.
- SQLite sessions, messages, events, checkpoints, idempotency and explicit restart recovery.
- Three original fictional persona Skills, bounded short-term context and safe training memory.
- Original teaching corpus with explainable lexical retrieval and visible evidence IDs.
- Explicit offline template mode and server-side OpenAI-compatible generation adapter.
- Chinese responsive workbench, expert switching, trace inspection and session deletion.
- Versioned offline regression evaluation with fault injection and explicit proxy limitations.
- Tests, CI, package build, Docker configuration, contribution/security policies and bilingual documentation.

### Known scope

- Local single-process deployment; no user authentication or distributed locking.
- Small development fixtures and lexical retrieval; no production metric or live-model quality claim.
- Exactly-once local response commit does not imply exactly-once upstream model billing.
