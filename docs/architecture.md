# Architecture and engineering decisions

## Responsibilities

`Harness` is the Supervisor's control plane. It owns the finite state machine, intent classification, execution budgets, error policy and terminal commit. `Catalog.recommend` is the Recommendation Agent: a deterministic policy over validated persona Skills. The Dialogue Agent combines a selected Skill, persisted bounded context and retrieved records, then delegates text generation to a Provider. Each component has a narrow interface rather than independent unbounded reasoning loops.

The three layers deliberately do not each issue an LLM request. A small closed intent space and three original Skills make deterministic routing a useful baseline. This reduces cost and makes routing failures separable from generation failures. Production data may justify a learned or LLM classifier; it must be compared against this baseline on a held-out set.

## Request flow

1. The API validates `ChatRequest`; user input cannot specify system roles, arbitrary experts or additional fields.
2. A per-session lock serializes message submission, recovery and deletion.
3. `Store.prepare` atomically claims the idempotency key and appends the user message. An unfinished prior turn blocks unrelated new requests.
4. The Supervisor produces a route, validates the first handoff and checkpoints the recommendation state.
5. Recommendation chooses an explicit expert when supplied, otherwise matches the intent against Skill tags.
6. Retrieval returns up to three original records using tag and lexical scores.
7. The second handoff validates the conversation budget. The full generation context is persisted before any model I/O.
8. Generation uses a finite retry policy. Completion, degradation and failure are distinct outcomes.
9. Assistant message, terminal result, safe training memory and final event commit in one transaction.

## Handoff v1

| Field | Purpose |
| --- | --- |
| `schema_version` | Versioned contract, currently `1.0` |
| `trace_id`, `session_id`, `turn_id` | Correlate control flow and durable records |
| `source`, `target` | Only supervisor→recommendation and recommendation→dialogue are legal |
| `goal`, `intent`, `expert_id` | Explicit task and role selection |
| `recent_messages` | User/assistant messages only, at most 12 and 18,000 characters |
| `memory` | At most 1,000 characters, server-selected training fields |
| `evidence` | At most 3 validated records |
| `deadline`, `remaining_hops` | Bounded time and traversal |

The current topology is acyclic. The hop limit is a second guard against future control-flow expansion; it is not a claim that arbitrary tool loops have been solved. Handoff envelopes are validated in memory, while the resulting node inputs are stored in the checkpoint. Events do not serialize the full envelope to avoid copying conversation text into another log surface.

## Persona and prompt boundaries

Skills are original fictional teaching personas, not impersonations. Their biographies explain principles and teaching style; they are loaded from package data and validated with `Expert`.

`build_messages` supplies a server-owned system message, user/assistant history and a final user-level block containing the current request and untrusted reference data. The role Skill is controlled configuration. User text, memory and retrieved text cannot be promoted to system authority through API fields. Prompt instructions are only one layer: semantic prompt-injection resistance still needs live-model adversarial evaluation.

The current input appears in persisted history and in the final structured generation input, intentionally identifying both chronological context and the current task. For larger prompts, deduplicate that occurrence and measure its effect before changing behavior.

## Memory

History is persisted in full for the session but generation receives only a bounded suffix. Persistent training memory consists of `last_intent`, `preferred_expert`, `training_goal` and `completed_turns`. It does not infer sensitive attributes or store arbitrary user statements as durable instructions. `preferred_expert` records the last expert; automatic routing continues to use this turn's intent unless the caller explicitly chooses an expert.

This is intentionally a minimal memory design: no semantic memory retrieval, automatic summarization or measured mastery estimation. A future mastery model should be based on scored exercises, not the number of completed turns.

## Storage

SQLite tables: `sessions`, `turns`, `messages`, `events`. Foreign-key cascade implements session deletion. Unique request keys and `(turn_id, role)` guard local duplicate commits. WAL allows reads alongside a writer; all SQL uses parameters. Each synchronous transaction is short and performs no network I/O. At larger scale these synchronous operations would need a separate worker or async storage adapter.

The schema is initialized with `CREATE TABLE IF NOT EXISTS` and currently has no migration layer. Before changing stored formats, add schema versioning and an explicit migration strategy. Runtime databases are not repository assets.

## Retrieval

Five teaching records form a deliberately small corpus. Ranking adds an intent match score plus lengths of matching lexical tags, filters zero-score records and returns the top three. IDs are stable and surfaced through `/api/knowledge/{id}`. This is inspectable lexical retrieval, not a vector-search benchmark. Retrieved evidence may be related but does not prove the generated claim is supported. Future semantic citation validation must distinguish retrieval correctness from answer faithfulness.

## Why a modular monolith

The engineering target is a reproducible portfolio: one install, one service, no cloud infrastructure. FastAPI provides typed REST boundaries; SQLite supplies real transactions; a static frontend avoids a separate toolchain. Provider injection permits genuine orchestration fault tests without paid calls. Interfaces allow replacing the classifier, retrieval and model adapter independently.

For production, prioritize authentication/authorization, distributed leases, a transactional outbox, a durable queue and PostgreSQL before increasing worker count. Add metrics for each stage, queue wait, provider usage and p95/p99 latency using a stable deployment workload. Those systems are roadmap items, not implemented features.
