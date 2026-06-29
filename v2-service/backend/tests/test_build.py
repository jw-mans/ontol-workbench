"""Тесты эндпоинта сборки. Сам рендер выполняет воркер; здесь Redis/очередь
подменяются фейком (fake_redis из conftest), проверяется проводка эндпоинта
(доступ, постановка задачи, возврат результата)."""

import uuid

from app.queue import RENDER_BUILD

CANNED = {
    'ok': True,
    'json': '{}',
    'puml': '@startuml',
    'png_url': 'data:image/png;base64,AAAA',
    'warnings': [],
    'error': None,
}


async def test_build_enqueues_and_returns(auth_client, fake_redis):
    fake_redis.result = CANNED
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
