"""Тесты storage-клиента (S3/MinIO). Сеть не нужна: проверяем формирование ключа
и оффлайн-подпись presigned-ссылки. boto3 может отсутствовать в среде хоста —
тогда весь модуль пропускается (в образе api/worker boto3 есть)."""

import pytest

pytest.importorskip('boto3')

from app.services import storage  # noqa: E402


def test_artifact_key_content_addressed():
    assert storage.artifact_key('abc123', 'png') == 'artifacts/abc123.png'
    # ведущая точка в расширении срезается
    assert storage.artifact_key('abc', '.svg') == 'artifacts/abc.svg'


def test_presigned_get_signs_offline():
    # generate_presigned_url подписывает локально, без обращения к MinIO.
    url = storage.presigned_get('projects/pid/abc.png')
    assert url.startswith(storage.settings.s3_endpoint_url)
    assert storage.settings.s3_bucket in url  # path-style: /{bucket}/{key}
    assert 'projects/pid/abc.png' in url
    assert 'X-Amz-Signature' in url
