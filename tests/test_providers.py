import asyncio
import json

import httpx
import pytest

from jewelmentor.catalog import Catalog
from jewelmentor.config import Settings
from jewelmentor.models import GenerationContext, Message
from jewelmentor.providers import DemoProvider, OpenAIProvider, PermanentError, TransientError, build_messages
from jewelmentor.routing import route


def context():
    c = Catalog()
    return GenerationContext(text='顾客说太贵了', route=route('太贵了'), expert=c.expert('chen'),
        messages=[Message(role='user', content='我的预算是八千')], memory={'last_intent': 'discovery'},
        evidence=c.search('太贵了', 'objection'))


def test_demo_and_prompt_preserve_boundary_and_context():
    ctx = context()
    answer = asyncio.run(DemoProvider().generate(ctx))
    assert '离线演示' in answer
    assert '[kb-objection]' in answer
    messages = build_messages(ctx)
    assert messages[0]['role'] == 'system'
    assert all(m['role'] in {'system', 'user', 'assistant'} for m in messages)
    assert '八千' in json.dumps(messages, ensure_ascii=False)
    assert '陈砺' in messages[0]['content']
    assert '不可信' in messages[0]['content']


def test_live_success_uses_server_side_key_and_context():
    def handle(req):
        data = json.loads(req.content)
        assert req.headers['authorization'] == 'Bearer test-secret'
        assert data['model'] == 'test-model'
        assert '八千' in json.dumps(data, ensure_ascii=False)
        return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': '示范：先澄清需求。'}}]})
    p = OpenAIProvider(Settings(provider='openai', api_key='test-secret', model='test-model'), httpx.MockTransport(handle))
    assert asyncio.run(p.generate(context())).startswith('示范')


@pytest.mark.parametrize('status,kind', [(429, TransientError), (503, TransientError), (401, PermanentError), (400, PermanentError)])
def test_upstream_error_classification_and_secret_redaction(status, kind):
    p = OpenAIProvider(Settings(provider='openai', api_key='DO_NOT_LEAK'),
        httpx.MockTransport(lambda req: httpx.Response(status, text='DO_NOT_LEAK')))
    with pytest.raises(kind) as exc:
        asyncio.run(p.generate(context()))
    assert 'DO_NOT_LEAK' not in str(exc.value)


@pytest.mark.parametrize('body', [{}, {'choices': []}, {'choices': [{'message': {'content': ''}}]}, {'choices': [{'message': {'content': 'x' * 6001}}]}])
def test_malformed_or_oversized_completion_is_not_success(body):
    p = OpenAIProvider(Settings(provider='openai', api_key='x'), httpx.MockTransport(lambda req: httpx.Response(200, json=body)))
    with pytest.raises(PermanentError):
        asyncio.run(p.generate(context()))


def test_config_rejects_missing_secret_and_insecure_remote_url(monkeypatch):
    with pytest.raises(ValueError):
        Settings(provider='openai')
    with pytest.raises(ValueError):
        Settings(provider='openai', api_key='x', base_url='http://remote.example/v1')
    monkeypatch.setenv('JEWELMENTOR_PROVIDER', 'demo')
    monkeypatch.setenv('JEWELMENTOR_DB', 'runtime/custom.db')
    assert str(Settings.from_env().db_path).endswith('custom.db')
