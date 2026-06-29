"""Тесты авторизации (регистрация, cookie-логин, /users/me, выход)."""

import uuid

from tests.conftest import PASSWORD


async def test_register_and_me(client):
    email = f'a_{uuid.uuid4().hex[:8]}@test.com'
    r = await client.post('/auth/register', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 201, r.text

    # дубликат email
    r = await client.post('/auth/register', json={'email': email, 'password': PASSWORD})
    assert r.status_code == 400

    # без cookie — 401
    assert (await client.get('/users/me')).status_code == 401

    # логин ставит cookie
    r = await client.post(
        '/auth/cookie/login', data={'username': email, 'password': PASSWORD}
    )
    assert r.status_code in (200, 204)
    assert 'ontolauth' in client.cookies

    r = await client.get('/users/me')
    assert r.status_code == 200
    assert r.json()['email'] == email


async def test_wrong_password(client):
    email = f'b_{uuid.uuid4().hex[:8]}@test.com'
    await client.post('/auth/register', json={'email': email, 'password': PASSWORD})
    r = await client.post(
        '/auth/cookie/login', data={'username': email, 'password': 'nope'}
    )
    assert r.status_code == 400


async def test_logout(auth_client):
    assert (await auth_client.get('/users/me')).status_code == 200
    r = await auth_client.post('/auth/cookie/logout')
    assert r.status_code in (200, 204)
    assert (await auth_client.get('/users/me')).status_code == 401
