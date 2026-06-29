"""Тесты эндпоинта сборки. Сам рендер выполняет воркер; здесь Redis/очередь
подменяются фейком, проверяется проводка эндпоинта (доступ, постановка задачи,
возврат результата)."""

import uuid

import pytest

from app.main import app
from app.queue import RENDER_BUILD

CANNED = {
    'ok': True,
    'json': '{}',
    'puml': '@startuml',
    'png_url': 'data:image/png;base64,AAAA',
    'warnings': [],
    'error': None,
}


class _FakeJob:
    def __init__(self, result):
        self._result = result

    async def result(self, timeout=None, poll_delay=None):
        return self._result


class _FakeRedis:
    def __init__(self, result):
        self._result = result
        self.calls = []

    async def enqueue_job(self, name, *args):
        self.calls.append((name, args))
        return _FakeJob(self._result)


@pytest.fixture
def fake_redis():
    fake = _FakeRedis(CANNED)
    app.state.redis = fake
    yield fake
    try:
        del app.state.redis
    except AttributeError:
        pass


async def test_build_enqueues_and_returns(auth_client, fake_redis):
    pid = (await auth_client.post('/projects', json={'name': 'B'})).json()['id']
    await auth_client.post(
        f'/projects/{pid}/files', json={'name': 'main', 'content': 'x'}
    )

    r = await auth_client.post(f'/projects/{pid}/build', json={'entry': 'main.ontol'})
    assert r.status_code == 200, r.text
    assert r.json() == CANNED

    # задача поставлена с именем контракта и id проекта + entry
    assert fake_redis.calls == [(RENDER_BUILD, (pid, 'main.ontol'))]


async def test_build_stranger_404(auth_client, other_client, fake_redis):
    pid = (await auth_client.post('/projects', json={'name': 'B2'})).json()['id']
    r = await other_client.post(f'/projects/{pid}/build', json={})
    assert r.status_code == 404
    assert fake_redis.calls == []  # до очереди не дошло


async def test_build_missing_project_404(auth_client, fake_redis):
    r = await auth_client.post(f'/projects/{uuid.uuid4()}/build', json={})
    assert r.status_code == 404
