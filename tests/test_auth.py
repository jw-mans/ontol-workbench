import pytest

from ontol.auth import UserStore, validate_username, validate_password


def _store(tmp_path) -> UserStore:
    return UserStore(str(tmp_path / 'users.json'))


def test_register_and_authenticate(tmp_path):
    store = _store(tmp_path)
    store.register('alice', 'secret1')

    assert store.exists('alice')
    assert store.list_users() == ['alice']
    assert store.authenticate('alice', 'secret1')
    assert not store.authenticate('alice', 'wrong')
    assert not store.authenticate('bob', 'secret1')  # unknown user


def test_password_is_not_stored_in_plaintext(tmp_path):
    store = _store(tmp_path)
    store.register('alice', 'secret1')
    with open(store.path, encoding='utf-8') as f:
        raw = f.read()
    assert 'secret1' not in raw
    assert 'hash' in raw and 'salt' in raw


def test_duplicate_registration_rejected(tmp_path):
    store = _store(tmp_path)
    store.register('alice', 'secret1')
    with pytest.raises(ValueError):
        store.register('alice', 'other1')


def test_persistence_across_instances(tmp_path):
    _store(tmp_path).register('alice', 'secret1')
    # A fresh instance pointed at the same file sees the user.
    # Новый экземпляр, указывающий на тот же файл, видит пользователя.
    assert _store(tmp_path).authenticate('alice', 'secret1')


@pytest.mark.parametrize('bad', ['', 'ab', 'has space', '../evil', 'a/b', 'x' * 33])
def test_invalid_usernames_rejected(bad):
    with pytest.raises(ValueError):
        validate_username(bad)


def test_short_password_rejected(tmp_path):
    with pytest.raises(ValueError):
        validate_password('abc')
    with pytest.raises(ValueError):
        _store(tmp_path).register('alice', 'abc')
