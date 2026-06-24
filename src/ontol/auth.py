"""Authentication layer for the Ontol web UI (личный кабинет).

A minimal, dependency-free user store: usernames with salted PBKDF2 password
hashes persisted to a single JSON file. Each user owns a private set of projects
(the web app maps a user to ``<projects_dir>/<username>`` via ``ProjectStore``).

This module is UI-agnostic — the Streamlit app builds the login screen on top.

Слой авторизации для веб-ЛК Ontol.

Минимальное хранилище пользователей без внешних зависимостей: имена с солёными
PBKDF2-хешами паролей сохраняются в один JSON-файл. У каждого пользователя свой
приватный набор проектов (веб-приложение сопоставляет пользователя каталогу
``<projects_dir>/<username>`` через ``ProjectStore``).

Модуль не зависит от UI — экран входа Streamlit-приложение строит поверх него.
"""

import hashlib
import hmac
import json
import os
import re
import secrets

# Usernames double as directory names for per-user project storage, so keep them
# to a safe, filesystem-friendly character set.
# Имена пользователей служат и именами каталогов для хранения проектов, поэтому
# ограничиваем их безопасным, дружественным к файловой системе набором символов.
_USERNAME_RE = re.compile(r'^[A-Za-z0-9_-]{3,32}$')
_MIN_PASSWORD_LEN = 4
_PBKDF2_ITERATIONS = 240_000


def validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username or ''):
        raise ValueError(
            'Имя пользователя: 3–32 символа, латиница/цифры/дефис/подчёркивание.'
        )


def validate_password(password: str) -> None:
    if not password or len(password) < _MIN_PASSWORD_LEN:
        raise ValueError(
            f'Пароль должен содержать не менее {_MIN_PASSWORD_LEN} символов.'
        )


def _hash_password(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)


class UserStore:
    """Stores users (username + salted password hash) in a JSON file.

    Хранит пользователей (имя + солёный хеш пароля) в JSON-файле.
    """

    def __init__(self, path: str) -> None:
        self.path: str = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _load(self) -> dict:
        if not os.path.isfile(self.path):
            return {}
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('users', {})

    def _save(self, users: dict) -> None:
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'users': users}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list_users(self) -> list[str]:
        return sorted(self._load().keys())

    def exists(self, username: str) -> bool:
        return username in self._load()

    def register(self, username: str, password: str) -> None:
        """Create a new user. Raises ``ValueError`` on invalid input or clash.

        Создаёт нового пользователя. Бросает ``ValueError`` при некорректном
        вводе или конфликте имён.
        """
        validate_username(username)
        validate_password(password)

        users = self._load()
        if username in users:
            raise ValueError(f'Пользователь «{username}» уже существует.')

        salt = secrets.token_bytes(16)
        digest = _hash_password(password, salt, _PBKDF2_ITERATIONS)
        users[username] = {
            'salt': salt.hex(),
            'hash': digest.hex(),
            'iterations': _PBKDF2_ITERATIONS,
        }
        self._save(users)

    def authenticate(self, username: str, password: str) -> bool:
        """Return ``True`` iff the username exists and the password matches.

        Возвращает ``True`` тогда и только тогда, когда пользователь существует
        и пароль совпадает.
        """
        record = self._load().get(username)
        if record is None:
            return False
        salt = bytes.fromhex(record['salt'])
        expected = bytes.fromhex(record['hash'])
        actual = _hash_password(password, salt, record['iterations'])
        return hmac.compare_digest(actual, expected)
