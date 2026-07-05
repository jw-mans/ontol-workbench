"""Тонкий клиент объектного хранилища (S3/MinIO) для артефактов рендера.

Ленивый синглтон boto3-клиента: создаётся при первом обращении, чтобы отсутствие
MinIO не роняло старт процесса. Для MinIO — path-style адресация и подпись s3v4.

Заливка вызывается в воркере (там рендер); ``presigned_get`` даёт браузеру
временную ссылку на объект без своей авторизации. Ключи неймспейсятся по проекту:
``projects/{project_id}/{hash}.{ext}``.
"""

from __future__ import annotations

import threading

from app.config import settings

# boto3/botocore импортируются лениво внутри функций: сам импорт модуля не должен
# требовать boto3 (в образе он есть; в среде хоста/юнит-тестах без S3 — нет).

_client = None
_presign_client = None
_lock = threading.Lock()


def _build_client(endpoint_url: str):
    import boto3
    from botocore.config import Config

    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'},  # MinIO — path-style
            retries={'max_attempts': 3, 'mode': 'standard'},
        ),
    )


def get_client():
    """Ленивый потокобезопасный S3-клиент для заливки/HEAD (внутренний адрес)."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = _build_client(settings.s3_endpoint_url)
    return _client


def _get_presign_client():
    """Клиент для presigned-ссылок: подписывает под ПУБЛИЧНЫЙ адрес (доступный из
    браузера). Подпись оффлайн — соединения нет, важен только host в URL. Если
    публичный адрес не задан, берём внутренний."""
    global _presign_client
    if _presign_client is None:
        with _lock:
            if _presign_client is None:
                endpoint = (
                    settings.s3_public_endpoint_url or settings.s3_endpoint_url
                )
                _presign_client = _build_client(endpoint)
    return _presign_client


def artifact_key(digest: str, ext: str) -> str:
    """Content-addressed ключ артефакта: ``artifacts/{hash}.{ext}``.

    Ключ зависит только от контента (см. ``render.content_digest``): одинаковая
    сборка → один объект (дедуп между проектами) и готовая основа для кэша (шаг 4).
    """
    return f'artifacts/{digest}.{ext.lstrip(".")}'


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Залить объект в бакет артефактов."""
    get_client().put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def get_bytes(key: str) -> bytes | None:
    """Прочитать объект (или None, если его нет). Для чтения meta кэша сборок."""
    from botocore.exceptions import ClientError

    try:
        resp = get_client().get_object(Bucket=settings.s3_bucket, Key=key)
        return resp['Body'].read()
    except ClientError as error:
        code = error.response.get('Error', {}).get('Code')
        if code in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise


def exists(key: str) -> bool:
    """Есть ли объект в бакете (HEAD). Для кэша сборок по контенту."""
    from botocore.exceptions import ClientError

    try:
        get_client().head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError as error:
        code = error.response.get('Error', {}).get('Code')
        if code in ('404', 'NoSuchKey', 'NotFound'):
            return False
        raise


def presigned_get(key: str) -> str:
    """Временная (settings.s3_presign_expire_seconds) ссылка на объект для браузера."""
    return _get_presign_client().generate_presigned_url(
        'get_object',
        Params={'Bucket': settings.s3_bucket, 'Key': key},
        ExpiresIn=settings.s3_presign_expire_seconds,
    )
