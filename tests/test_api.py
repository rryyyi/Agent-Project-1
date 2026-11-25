import asyncio

from fastapi.testclient import TestClient

from jewelmentor.api import create_app
from jewelmentor.config import Settings
from jewelmentor.models import ChatRequest
from jewelmentor.providers import DemoProvider


def client(tmp_path):
    return TestClient(create_app(Settings(db_path=tmp_path / 'api.db')))


def test_complete_api_flow_and_delete(tmp_path):
    with client(tmp_path) as c:
        health = c.get('/health').json()
        assert health['provider'] == 'demo'
        assert 'api_key' not in str(health)
        assert len(c.get('/api/experts').json()) == 3
        sid = c.post('/api/sessions').json()['id']
        response = c.post(f'/api/sessions/{sid}/messages', json={'message': '顾客觉得太贵了', 'request_id': 'a'})
        assert response.status_code == 200
        result = response.json()
        assert result['state'] == 'completed'
        assert result['provider'] == 'demo'
        assert c.get('/api/knowledge/kb-objection').json()['title']
        assert len(c.get(f'/api/sessions/{sid}').json()['messages']) == 2
        assert c.get(f'/api/sessions/{sid}/traces').json()[-1]['state'] == 'completed'
        assert c.delete(f'/api/sessions/{sid}').status_code == 204
        assert c.get(f'/api/sessions/{sid}').status_code == 404
        assert c.get(f'/api/sessions/{sid}/traces').status_code == 404


def test_validation_conflicts_and_static_ui(tmp_path):
    with client(tmp_path) as c:
        assert c.get('/').status_code == 200
        assert c.get('/static/app.js').status_code == 200
        assert c.get('/api/knowledge/missing').status_code == 404
        sid = c.post('/api/sessions').json()['id']
        for payload in [{'message': ' ', 'request_id': 'a'}, {'message': 'x' * 2001, 'request_id': 'a'},
                        {'message': 'hi', 'request_id': 'a', 'system': 'bypass'},
                        {'message': 'hi', 'request_id': 'a', 'expert_id': 'unknown'}]:
            assert c.post(f'/api/sessions/{sid}/messages', json=payload).status_code == 422
        c.post(f'/api/sessions/{sid}/messages', json={'message': '预算', 'request_id': 'same'})
        conflict = c.post(f'/api/sessions/{sid}/messages', json={'message': '别的', 'request_id': 'same'})
        assert conflict.status_code == 409
        assert conflict.json()['error']['code'] == 'conflict'
        assert c.post('/api/sessions/missing/messages', json={'message': '预算', 'request_id': 'b'}).status_code == 404


def test_recovery_endpoint_exposes_durable_resume(tmp_path):
    app = create_app(Settings(db_path=tmp_path / 'resume.db'), DemoProvider())
    with TestClient(app) as c:
        sid = c.post('/api/sessions').json()['id']
        turn = app.state.store.prepare(sid, ChatRequest(message='预算怎么问', request_id='crash'), 'demo', 30)
        result = c.post(f'/api/sessions/{sid}/turns/{turn["id"]}/resume')
        assert result.status_code == 200
        assert result.json()['state'] == 'completed'
        assert len(c.get(f'/api/sessions/{sid}').json()['messages']) == 2


def test_delete_waits_for_inflight_message(tmp_path):
    # Removing the shared session lock would make generation commit into a deleted session.
    class Delayed(DemoProvider):
        async def generate(self, context):
            await asyncio.sleep(0.02)
            return await super().generate(context)

    app = create_app(Settings(db_path=tmp_path / 'lock.db'), Delayed())
    h = app.state.harness
    sid = app.state.store.create_session()['id']

    async def scenario():
        chat = asyncio.create_task(h.chat(sid, ChatRequest(message='预算', request_id='a')))
        await asyncio.sleep(0.005)
        deletion = asyncio.create_task(h.delete(sid))
        assert (await chat).state.value == 'completed'
        await deletion
    asyncio.run(scenario())
    with TestClient(app) as c:
        assert c.get(f'/api/sessions/{sid}').status_code == 404
