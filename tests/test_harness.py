import asyncio

import pytest

from jewelmentor.catalog import Catalog
from jewelmentor.config import Settings
from jewelmentor.harness import Harness
from jewelmentor.models import ChatRequest, State
from jewelmentor.providers import DemoProvider, PermanentError, TransientError
from jewelmentor.store import Conflict, Store


def run(awaitable):
    return asyncio.run(awaitable)


def setup(tmp_path, provider=None, **options):
    store = Store(tmp_path / 'test.db')
    settings = Settings(node_timeout=0.05, turn_timeout=1, retry_delay=0, **options)
    harness = Harness(store, Catalog(), provider or DemoProvider(), settings)
    return store, harness, store.create_session()['id']


def request(text='顾客觉得太贵了', key='one', expert=None):
    return ChatRequest(message=text, request_id=key, expert_id=expert)


class Flaky:
    name = 'test-transient'

    def __init__(self, fail=1):
        self.left = fail

    async def generate(self, context):
        if self.left:
            self.left -= 1
            raise TransientError('temporary')
        return '示范：先确认预算。原因：理解需求。练习：请复述顾客顾虑。'


class Slow:
    name = 'test-slow'

    async def generate(self, context):
        await asyncio.sleep(1)
        return 'late'


class Broken:
    name = 'test-permanent'

    async def generate(self, context):
        raise PermanentError('provider_auth')


def test_happy_path_persists_messages_and_trace(tmp_path):
    store, h, sid = setup(tmp_path)
    result = run(h.chat(sid, request()))
    assert result.state == State.COMPLETED
    assert result.expert_id == 'chen'
    assert result.evidence[0].id == 'kb-objection'
    assert [m['role'] for m in store.session(sid)['messages']] == ['user', 'assistant']
    assert store.trace(sid)[-1]['state'] == 'completed'
    assert {e['node'] for e in store.trace(sid)} >= {'supervisor', 'recommendation', 'dialogue'}


def test_idempotent_replay_and_payload_conflict(tmp_path):
    store, h, sid = setup(tmp_path)
    first = run(h.chat(sid, request()))
    assert run(h.chat(sid, request())).turn_id == first.turn_id
    assert len(store.session(sid)['messages']) == 2
    with pytest.raises(Conflict):
        run(h.chat(sid, request('钻石4C是什么')))


def test_transient_retries_then_commits_once(tmp_path):
    store, h, sid = setup(tmp_path, Flaky())
    assert run(h.chat(sid, request())).state == State.COMPLETED
    events = store.trace(sid)
    assert any(e['state'] == 'retrying' for e in events)
    assert len(store.session(sid)['messages']) == 2


@pytest.mark.parametrize('provider,category,state', [
    (Slow(), 'provider_timeout', State.DEGRADED),
    (Flaky(10), 'provider_transient', State.DEGRADED),
    (Broken(), 'provider_auth', State.FAILED),
])
def test_failure_is_visible_and_bounded(tmp_path, provider, category, state):
    store, h, sid = setup(tmp_path, provider)
    result = run(h.chat(sid, request()))
    assert result.state == state
    assert result.error_category == category
    assert len([e for e in store.trace(sid) if e['state'] == 'retrying']) <= 1
    assert len(store.session(sid)['messages']) == 2


def test_hop_budget_stops_before_generation(tmp_path):
    store, h, sid = setup(tmp_path, max_hops=1)
    result = run(h.chat(sid, request()))
    assert result.state == State.FAILED
    assert result.error_category == 'handoff_budget'


def test_expert_switch_keeps_shared_history_and_safe_memory(tmp_path):
    seen = []

    class Recorder(DemoProvider):
        async def generate(self, context):
            seen.append(context)
            return await super().generate(context)

    store, h, sid = setup(tmp_path, Recorder())
    run(h.chat(sid, request('顾客预算一万元', 'a', 'lin')))
    result = run(h.chat(sid, request('继续练习价格异议', 'b', 'chen')))
    assert result.expert_id == 'chen'
    assert any('一万元' in m.content for m in seen[-1].messages)
    assert store.session(sid)['memory']['last_intent'] == 'objection'
    assert '顾客预算一万元' not in str(store.session(sid)['memory'])


def test_restart_reads_history_and_resume_does_not_duplicate_user(tmp_path):
    store, h, sid = setup(tmp_path)

    class Interrupted(DemoProvider):
        async def generate(self, context):
            raise asyncio.CancelledError()

    h.provider = Interrupted()
    with pytest.raises(asyncio.CancelledError):
        run(h.chat(sid, request()))
    pending = store.session(sid)['turns'][0]
    assert pending['state'] == 'generating'
    reopened = Store(tmp_path / 'test.db')
    recovered = Harness(reopened, Catalog(), DemoProvider(), Settings())
    result = run(recovered.resume(sid, pending['id']))
    assert result.state == State.COMPLETED
    assert len(reopened.session(sid)['messages']) == 2
    assert run(recovered.resume(sid, pending['id'])).turn_id == result.turn_id


def test_incomplete_turn_blocks_new_request_until_recovery(tmp_path):
    store, h, sid = setup(tmp_path)
    store.prepare(sid, request(), 'demo', 30)
    with pytest.raises(Conflict):
        run(h.chat(sid, request(key='another')))
    turn = store.session(sid)['turns'][0]
    assert run(h.resume(sid, turn['id'])).state == State.COMPLETED
    assert len(store.session(sid)['messages']) == 2


def test_same_session_serialization_and_cross_session_isolation(tmp_path):
    async def scenario():
        store, h, a = setup(tmp_path)
        b = store.create_session()['id']
        await asyncio.gather(h.chat(a, request(key='a1')), h.chat(a, request(key='a2')),
                             h.chat(b, request('售后回访', 'b1')))
        assert len(store.session(a)['messages']) == 4
        assert len(store.session(b)['messages']) == 2
        assert all('售后回访' != m['content'] for m in store.session(a)['messages'])
        await h.delete(a)
        with pytest.raises(KeyError):
            store.session(a)
        assert store.trace(a) == []
        assert len(store.session(b)['messages']) == 2
    run(scenario())


def test_context_is_bounded(tmp_path):
    seen = []

    class Recorder(DemoProvider):
        async def generate(self, context):
            seen.append(context)
            return '练习：请复述需求。' + 'x' * 5900

    store, h, sid = setup(tmp_path, Recorder())
    for i in range(6):
        run(h.chat(sid, request('预算' + 'a' * 1900, str(i))))
    assert len(seen[-1].messages) <= 12
    assert sum(len(m.content) for m in seen[-1].messages) <= 18000
