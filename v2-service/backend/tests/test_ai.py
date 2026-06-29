"""Тесты опциональной AI-генерации связей: гейтинг по флагу, проводка эндпоинта
(с фейковым Redis) и юнит задачи воркера (с подменённым AI-сервисом)."""

import uuid

from app.config import settings
from app.queue import AI_HIERARCHY

AI_RESULT = {
    'ok': True,
    'relationships': [
        {
            'parent': 'a',
            'child': 'b',
            'relationship': 'inheritance',
            'title': None,
            'bidirectional': False,
            'comment': 'b is a kind of a',
        }
    ],
    'snippet': 'hierarchy:\n  # b is a kind of a\n  a inheritance b',
    'error': None,
}


async def test_ai_disabled_by_default(auth_client):
    pid = (await auth_client.post('/projects', json={'name': 'A'})).json()['id']
    r = await auth_client.post(f'/projects/{pid}/ai/hierarchy', json={})
    assert r.status_code == 503


async def test_ai_enabled_enqueues_and_returns(auth_client, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, 'ai_enabled', True)
    fake_redis.result = AI_RESULT
    pid = (await auth_client.post('/projects', json={'name': 'A2'})).json()['id']

    r = await auth_client.post(
        f'/projects/{pid}/ai/hierarchy', json={'entry': 'main.ontol'}
    )
    assert r.status_code == 200, r.text
    assert r.json() == AI_RESULT

    # задача поставлена: имя контракта, id проекта, entry, модель по умолчанию
    assert fake_redis.calls == [
        (AI_HIERARCHY, (pid, 'main.ontol', settings.ai_model))
    ]


async def test_ai_stranger_404(auth_client, other_client, fake_redis, monkeypatch):
    monkeypatch.setattr(settings, 'ai_enabled', True)
    pid = (await auth_client.post('/projects', json={'name': 'A3'})).json()['id']
    r = await other_client.post(f'/projects/{pid}/ai/hierarchy', json={})
    assert r.status_code == 404
    assert fake_redis.calls == []


async def test_config_endpoint(client):
    r = await client.get('/config')
    assert r.status_code == 200
    assert 'ai_enabled' in r.json()


# --- Юнит задачи воркера ---------------------------------------------------- #
async def test_worker_ai_hierarchy_reads_files(session_maker, monkeypatch):
    import app.worker as worker_mod
    from app.models.file import File
    from app.models.project import Project
    from app.services.ai import AIHierarchyResult

    async with session_maker() as session:
        project = Project(id=uuid.uuid4(), owner_id=uuid.uuid4(), name='W')
        session.add(project)
        session.add(File(project_id=project.id, name='main.ontol', content='x'))
        await session.commit()
        pid = str(project.id)

    monkeypatch.setattr(worker_mod, 'async_session_maker', session_maker)

    captured = {}

    def fake_generate(files, entry, model, base_url, temperature=0.0):
        captured.update(files=files, entry=entry, model=model, base_url=base_url)
        return AIHierarchyResult(ok=True, snippet='hierarchy:')

    monkeypatch.setattr(worker_mod, 'generate_hierarchy', fake_generate)

    result = await worker_mod.ai_hierarchy({}, pid, None, 'llama3')

    assert result['ok'] is True
    assert captured['files'] == {'main.ontol': 'x'}  # воркер прочитал из БД
    assert captured['entry'] == 'main.ontol'
    assert captured['model'] == 'llama3'
