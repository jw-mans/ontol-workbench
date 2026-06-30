"""Тесты CRUD файлов проекта и изоляции по владельцу."""

import pytest_asyncio


@pytest_asyncio.fixture
async def project_id(auth_client) -> str:
    r = await auth_client.post('/projects', json={'name': 'FilesProj'})
    return r.json()['id']


async def test_files_crud(auth_client, project_id):
    base = f'/projects/{project_id}/files'

    assert (await auth_client.get(base)).json() == []

    # создание: расширение .ontol добавляется само
    r = await auth_client.post(base, json={'name': 'main', 'content': '// hi'})
    assert r.status_code == 201, r.text
    fid = r.json()['id']
    assert r.json()['name'] == 'main.ontol'

    # дубликат имени
    r = await auth_client.post(base, json={'name': 'main.ontol'})
    assert r.status_code == 409

    # path traversal в имени
    r = await auth_client.post(base, json={'name': '../evil'})
    assert r.status_code == 422

    # обновление контента
    r = await auth_client.put(f'{base}/{fid}', json={'content': '// updated'})
    assert r.status_code == 200 and r.json()['content'] == '// updated'

    # get отдаёт сохранённый контент
    assert (await auth_client.get(f'{base}/{fid}')).json()['content'] == '// updated'

    # список без поля content
    listing = (await auth_client.get(base)).json()
    assert len(listing) == 1 and 'content' not in listing[0]

    # удаление
    assert (await auth_client.delete(f'{base}/{fid}')).status_code == 204
    assert (await auth_client.get(base)).json() == []


async def test_files_rename(auth_client, project_id):
    base = f'/projects/{project_id}/files'
    fid = (await auth_client.post(base, json={'name': 'main'})).json()['id']
    await auth_client.post(base, json={'name': 'other'})

    # переименование: расширение .ontol добавляется само
    r = await auth_client.patch(f'{base}/{fid}', json={'name': 'renamed'})
    assert r.status_code == 200, r.text
    assert r.json()['name'] == 'renamed.ontol'

    # конфликт с существующим именем
    r = await auth_client.patch(f'{base}/{fid}', json={'name': 'other.ontol'})
    assert r.status_code == 409

    # невалидное имя (traversal)
    r = await auth_client.patch(f'{base}/{fid}', json={'name': '../evil'})
    assert r.status_code == 422


async def test_files_cross_user(auth_client, other_client, project_id):
    fid = (
        await auth_client.post(
            f'/projects/{project_id}/files', json={'name': 'main'}
        )
    ).json()['id']

    # чужой не читает и не пишет файлы проекта
    assert (
        await other_client.get(f'/projects/{project_id}/files')
    ).status_code == 404
    assert (
        await other_client.put(
            f'/projects/{project_id}/files/{fid}', json={'content': 'hack'}
        )
    ).status_code == 404
