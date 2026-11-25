"""Durable three-agent orchestration; state transitions are checkpointed before I/O."""

import asyncio
import json
import time
import weakref

from jewelmentor.catalog import Catalog
from jewelmentor.config import Settings
from jewelmentor.models import (
    ChatRequest,
    GenerationContext,
    Handoff,
    Route,
    State,
    TurnResult,
    advance,
)
from jewelmentor.providers import PermanentError, Provider, TransientError
from jewelmentor.routing import route
from jewelmentor.store import Conflict, Store


class Harness:
    def __init__(self, store: Store, catalog: Catalog, provider: Provider, settings: Settings):
        self.store, self.catalog, self.provider, self.settings = store, catalog, provider, settings
        self._locks = weakref.WeakValueDictionary()

    def lock(self, sid):
        lock = self._locks.get(sid)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[sid] = lock
        return lock

    async def delete(self, sid):
        async with self.lock(sid):
            self.store.delete_session(sid)

    async def chat(self, sid: str, request: ChatRequest) -> TurnResult:
        async with self.lock(sid):
            turn = self.store.prepare(sid, request, self.provider.name, self.settings.turn_timeout)
            if turn["result"]:
                return TurnResult.model_validate_json(turn["result"])
            if State(turn["state"]) != State.PENDING:
                raise Conflict("incomplete turn: use the recovery endpoint")
            return await self._execute(turn)

    async def resume(self, sid: str, tid: str) -> TurnResult:
        async with self.lock(sid):
            turn = self.store.turn(sid, tid)
            if turn["result"]:
                return TurnResult.model_validate_json(turn["result"])
            if turn["provider"] != self.provider.name:
                raise Conflict("recovery requires the original provider mode")
            # Explicit recovery renews the wall clock, but not hops or generation attempts.
            turn["deadline"] = time.time() + self.settings.turn_timeout
            with self.store.connect() as db:
                db.execute("UPDATE turns SET deadline=? WHERE id=?", (turn["deadline"], tid))
            return await self._execute(turn)

    def _transition(self, turn, target, checkpoint, node, **kwargs):
        advance(State(turn["state"]), target)
        self.store.update(turn, target, checkpoint, node, **kwargs)

    def _handoff(self, turn, cp, source, target, request):
        used = cp.get("hops", 0)
        remaining = self.settings.max_hops - used
        if remaining < 1:
            raise PermanentError("handoff_budget")
        messages, memory = self.store.context(turn["session_id"])
        Handoff(trace_id=turn["trace_id"], session_id=turn["session_id"], turn_id=turn["id"],
                source=source, target=target, goal=request.message,
                intent=cp["route"]["intent"], expert_id=cp.get("expert_id"),
                recent_messages=messages, memory=memory,
                evidence=cp.get("evidence", []), deadline=turn["deadline"], remaining_hops=remaining)
        cp["hops"] = used + 1

    async def _execute(self, turn):
        request = ChatRequest.model_validate_json(turn["request"])
        cp = json.loads(turn["checkpoint"])
        error = None
        final = State.COMPLETED
        answer = ""
        try:
            while True:
                if time.time() >= turn["deadline"]:
                    raise TransientError("turn_deadline")
                state = State(turn["state"])
                if state == State.PENDING:
                    self._transition(turn, State.ROUTING, cp, "supervisor")
                elif state == State.ROUTING:
                    cp["route"] = route(request.message).model_dump()
                    self._handoff(turn, cp, "supervisor", "recommendation", request)
                    self._transition(turn, State.RECOMMENDING, cp, "recommendation")
                elif state == State.RECOMMENDING:
                    cp["expert_id"] = self.catalog.recommend(cp["route"]["intent"], request.expert_id).id
                    self._transition(turn, State.RETRIEVING, cp, "retrieval")
                elif state == State.RETRIEVING:
                    cp["evidence"] = [e.model_dump() for e in self.catalog.search(request.message, cp["route"]["intent"])]
                    self._handoff(turn, cp, "recommendation", "dialogue", request)
                    messages, memory = self.store.context(turn["session_id"])
                    ctx = GenerationContext(text=request.message, route=cp["route"],
                        expert=self.catalog.expert(cp["expert_id"]), messages=messages,
                        memory=memory, evidence=cp["evidence"])
                    cp["context"] = ctx.model_dump()
                    self._transition(turn, State.GENERATING, cp, "dialogue")
                elif state in {State.GENERATING, State.RETRYING}:
                    answer = await self._generate(turn, cp)
                    break
                else:
                    raise PermanentError("runtime_state")
        except TransientError as exc:
            final = State.DEGRADED
            error = str(exc) if str(exc) in {"provider_timeout", "turn_deadline"} else "provider_transient"
            answer = "本轮生成暂时不可用，已保留会话上下文。请稍后发送新消息重试；本轮未计为成功交接。"
        except PermanentError as exc:
            final = State.FAILED
            allowed = {"handoff_budget", "provider_auth", "provider_request", "provider_response", "runtime_state"}
            error = str(exc) if str(exc) in allowed else "provider_error"
            answer = "本轮执行失败，已保留会话。请检查模型配置或查看轨迹中的错误类别。"
        except Exception:
            # Do not persist raw errors, provider bodies, user text or credentials in events.
            final, error = State.FAILED, "runtime_error"
            answer = "本轮遇到内部错误，已保留会话。请使用轨迹标识排查。"
        advance(State(turn["state"]), final)
        result = TurnResult(session_id=turn["session_id"], turn_id=turn["id"], trace_id=turn["trace_id"],
            state=final, answer=answer, expert_id=cp.get("expert_id", "lin"),
            route=Route.model_validate(cp.get("route", route(request.message).model_dump())),
            evidence=cp.get("evidence", []), provider=self.provider.name, error_category=error)
        memory = self.store.session(turn["session_id"])["memory"]
        if final == State.COMPLETED:
            memory = {"last_intent": result.route.intent, "preferred_expert": result.expert_id,
                      "training_goal": result.route.intent, "completed_turns": str(int(memory.get("completed_turns", "0")) + 1)}
        self.store.finish(turn, result, memory)
        return result

    async def _generate(self, turn, cp):
        while cp.get("attempts", 0) < self.settings.max_attempts:
            if State(turn["state"]) == State.RETRYING:
                self._transition(turn, State.GENERATING, cp, "dialogue")
            cp["attempts"] = cp.get("attempts", 0) + 1
            self.store.update(turn, State.GENERATING, cp, "dialogue", attempt=cp["attempts"])
            started = time.monotonic()
            timeout = min(self.settings.node_timeout, turn["deadline"] - time.time())
            if timeout <= 0:
                raise TransientError("turn_deadline")
            try:
                answer = await asyncio.wait_for(self.provider.generate(GenerationContext.model_validate(cp["context"])), timeout)
                if not isinstance(answer, str) or not answer.strip() or len(answer) > 6000:
                    raise PermanentError("provider_response")
                return answer
            except (TimeoutError, TransientError) as exc:
                category = "provider_timeout" if isinstance(exc, TimeoutError) else "provider_transient"
                if cp["attempts"] >= self.settings.max_attempts:
                    raise TransientError(category) from exc
                self._transition(turn, State.RETRYING, cp, "dialogue", attempt=cp["attempts"],
                    elapsed_ms=(time.monotonic() - started) * 1000, error=category)
                await asyncio.sleep(min(self.settings.retry_delay * cp["attempts"], max(0, turn["deadline"] - time.time())))
        raise TransientError("provider_transient")
