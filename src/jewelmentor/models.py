"""Typed boundaries shared by API, agents, checkpoints and evaluation."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class State(StrEnum):
    PENDING = "pending"
    ROUTING = "routing"
    RECOMMENDING = "recommending"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    RETRYING = "retrying"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"


TERMINAL = {State.COMPLETED, State.DEGRADED, State.FAILED}
_EDGES = {
    State.PENDING: {State.ROUTING},
    State.ROUTING: {State.RECOMMENDING},
    State.RECOMMENDING: {State.RETRIEVING},
    State.RETRIEVING: {State.GENERATING},
    State.GENERATING: {State.COMPLETED, State.RETRYING},
    State.RETRYING: {State.GENERATING},
}


def advance(current: State, target: State) -> State:
    allowed = _EDGES.get(current, set()) | (
        {State.FAILED, State.DEGRADED} if current not in TERMINAL else set()
    )
    if target not in allowed:
        raise ValueError(f"illegal transition: {current.value} -> {target.value}")
    return target


Intent = Literal["discovery", "objection", "product", "relationship", "practice", "clarify"]


class Route(StrictModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    reason: str


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class Evidence(StrictModel):
    id: str
    title: str
    content: str
    tags: list[str]
    source: str


class Expert(StrictModel):
    id: str
    name: str
    title: str
    version: str
    fictional: Literal[True]
    tags: list[str]
    biography: list[str]
    principles: list[str]
    style: list[str]
    boundaries: list[str]
    few_shots: list[dict[str, str]]


class Handoff(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    trace_id: str
    session_id: str
    turn_id: str
    source: Literal["supervisor", "recommendation"]
    target: Literal["recommendation", "dialogue"]
    goal: str = Field(min_length=1, max_length=2000)
    intent: Intent = "clarify"
    expert_id: str | None = None
    recent_messages: list[Message] = Field(default_factory=list, max_length=12)
    memory: dict[str, str] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list, max_length=3)
    deadline: float = 0
    remaining_hops: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def legal_edge(self):
        if (self.source, self.target) not in {
            ("supervisor", "recommendation"),
            ("recommendation", "dialogue"),
        }:
            raise ValueError("handoff edge is not authorized")
        if sum(len(m.content) for m in self.recent_messages) > 18000:
            raise ValueError("handoff context exceeds budget")
        if sum(len(v) for v in self.memory.values()) > 1000:
            raise ValueError("memory exceeds budget")
        return self


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    expert_id: Literal["lin", "chen", "zhou"] | None = None
    request_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()


class GenerationContext(StrictModel):
    text: str
    route: Route
    expert: Expert
    messages: list[Message]
    memory: dict[str, str]
    evidence: list[Evidence]


class TurnResult(StrictModel):
    session_id: str
    turn_id: str
    trace_id: str
    state: State
    answer: str
    expert_id: str
    route: Route
    evidence: list[Evidence]
    provider: str
    error_category: str | None = None
