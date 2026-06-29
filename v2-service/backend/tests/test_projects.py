"""Тесты CRUD проектов и изоляции по владельцу."""


async def test_projects_crud(auth_client):
    # пусто
    r = await auth_client.get('/projects')
    assert r.status_code == 200 and r.json() == []

    # создать
    r = await auth_client.post('/projects', json={'name': 'Proj1'})
    assert r.status_code == 201, r.text
    pid = r.json()['id']

    # дубликат имени
    r = await auth_client.post('/projects', json={'name': 'Proj1'})
    assert r.status_code == 409

    # список и get
    assert len((await auth_client.get('/projects')).json()) == 1
    assert (await auth_client.get(f'/projects/{pid}')).status_code == 200

    # переименовать
    r = await auth_client.patch(f'/projects/{pid}', json={'name': 'Renamed'})
    assert r.status_code == 200 and r.json()['name'] == 'Renamed'

    # удалить
    assert (await auth_client.delete(f'/projects/{pid}')).status_code == 204
    assert (await auth_client.get(f'/projects/{pid}')).status_code == 404


async def test_unauth_projects(client):
    assert (await client.get('/projects')).status_code == 401


async def test_cross_user_isolation(auth_client, other_client):
    pid = (await auth_client.post('/projects', json={'name': 'Mine'})).json()['id']

    # чужой пользователь не видит проект
    assert (await other_client.get(f'/projects/{pid}')).status_code == 404
    assert (await other_client.get('/projects')).json() == []
