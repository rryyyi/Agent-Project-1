# Reliability contract and failure model

## What is durable

A new turn and its user message are created together with a unique `(session_id, request_id)`. Every state entry stores its checkpoint before the next step. At generation entry the checkpoint contains route, expert, evidence, bounded history, memory, hops and consumed generation attempts. Final response, assistant message, safe memory and terminal event commit together.

A cancellation such as process termination is not converted into success. The turn remains incomplete and is visible in session metadata. On restart, a caller can explicitly resume it. New unrelated messages return 409 until the unfinished turn is resolved.

## Recovery

```text
GET  /api/sessions/{sid}                         # inspect turns
POST /api/sessions/{sid}/turns/{tid}/resume       # explicit recovery
```

A terminal turn returns its original stored response. A pending turn continues from routing. Recommendation/retrieval checkpoints continue at the next incomplete node. Generation uses the persisted context rather than rerunning retrieval against potentially changed data. The deployment must keep compatible Skills, provider mode and schema available.

Explicit recovery renews the wall-clock deadline, but preserves the consumed hop and generation-attempt budgets. An interrupted final attempt cannot be retried indefinitely by repeatedly pressing resume; it becomes a visible degraded result. Recovery requires the same provider name. There is no cross-version compatibility guarantee for changed persona or checkpoint formats in v0.1.0.

## Exactly-once boundary

The service promises one locally committed assistant message per turn under the documented single-process model. It does **not** promise an upstream model call is billed once. If the provider generated an answer and the process died before the database commit, recovery may call the provider again. SQLite transactions cannot atomically commit a remote model response and a local record.

A production implementation would use provider idempotency when supported and distinguish work claimed, request sent, response received and result committed. Distributed retries also require leases and fencing tokens, not only unique keys.

## Error policy

| Trigger | Behavior | Category |
| --- | --- | --- |
| HTTP 429 / 5xx, transport errors | Finite retry, then degraded | `provider_transient` |
| Per-attempt timeout | Finite retry, then degraded | `provider_timeout` |
| Total deadline exhausted | Stop and degrade | `turn_deadline` |
| HTTP 401 / 403 | No retry, fail visibly | `provider_auth` |
| Other non-200 response | No retry, fail visibly | `provider_request` |
| Empty/malformed/oversized answer | No retry, fail visibly | `provider_response` |
| Handoff hops exhausted | Fail before model generation | `handoff_budget` |
| Unexpected exception | Sanitized failure, keep session | `runtime_error` |
| Invalid request | Reject at API boundary | HTTP 422 |
| Key reuse with a different body | Do not reuse another result | HTTP 409 |

No raw provider body or exception message is copied into public trace events. Live failures never silently switch to DemoProvider. A degraded/failed response is committed as an assistant status message to preserve conversation chronology; it is not a successful handoff and does not update training completion memory.

## Concurrency

`Harness.lock` supplies one weakly held lock per active session; message, resume and deletion share it. Separate sessions may concurrently await network I/O. The SQLite transaction itself remains short and synchronous.

This is not distributed concurrency control. Run exactly **one application process**. Two application instances can still race on recovery or deletion; unique constraints catch some duplicates but cannot provide the promised API behavior. Use a durable queue and database leases before horizontal scaling.

## Fault tests

Run `python -m pytest tests/test_harness.py tests/test_api.py -q`.

Tests exercise actual SQLite writes and orchestration. Only model behavior or external HTTP transport is replaced. They cover retry then success, timeout exhaustion, auth failure, bounded hops, idempotency, payload collision, process-style store reopening, generation cancellation/resume, pending-turn recovery, shared history after expert switching, context bounds, same-session serialization, cross-session isolation and deletion while a turn runs.

The evaluation suite includes four expected fault outcomes and keeps them in the task-completion denominator. This separates resilience correctness from the much less useful claim that every attempted operation succeeded.
