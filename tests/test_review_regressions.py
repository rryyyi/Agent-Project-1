import asyncio

import pytest

from jewelmentor.catalog import Catalog
from jewelmentor.config import Settings
from jewelmentor.harness import Harness
from jewelmentor.models import ChatRequest
from jewelmentor.providers import DemoProvider
from jewelmentor.store import Conflict, Store


def test_total_deadline_is_not_reported_as_provider_timeout(tmp_path):
    class Slow(DemoProvider):
        async def generate(self, context):
            await asyncio.sleep(1)
            return "late"

    store = Store(tmp_path / "deadline.db")
    sid = store.create_session()["id"]
    h = Harness(
        store, Catalog(), Slow(), Settings(node_timeout=1, turn_timeout=0.3, max_attempts=1)
    )
    result = asyncio.run(h.chat(sid, ChatRequest(message="预算", request_id="deadline")))
    assert result.error_category == "turn_deadline"
    assert result.state.value == "degraded"


def test_recovery_keeps_consumed_attempt_budget(tmp_path):
    class Cancel(DemoProvider):
        async def generate(self, context):
            raise asyncio.CancelledError()

    store = Store(tmp_path / "attempt.db")
    sid = store.create_session()["id"]
    h = Harness(store, Catalog(), Cancel(), Settings(max_attempts=1))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.chat(sid, ChatRequest(message="预算", request_id="a")))
    h.provider = DemoProvider()
    tid = store.session(sid)["turns"][0]["id"]
    result = asyncio.run(h.resume(sid, tid))
    assert result.state.value == "degraded"
    assert len(store.session(sid)["messages"]) == 2


def test_recovery_refuses_provider_mode_change(tmp_path):
    store = Store(tmp_path / "mode.db")
    sid = store.create_session()["id"]
    turn = store.prepare(sid, ChatRequest(message="预算", request_id="a"), "openai", 30)
    h = Harness(store, Catalog(), DemoProvider(), Settings())
    with pytest.raises(Conflict):
        asyncio.run(h.resume(sid, turn["id"]))
