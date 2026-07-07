#!/usr/bin/env python
"""load_qdrant.py — загрузка эталонных кусков в векторную БД Qdrant.

Берёт chunks_ontology_text.jsonl (выход build_chunks_dataset.py: пара понятий + истинный
тип связи + предсказанный тип + эталонный кусок) и кладёт каждую пару точкой в Qdrant:
  вектор  = эмбеддинг reference_chunk (multilingual-e5, косинус);
  payload = concept_a, concept_b, relation_type (истинный), predicted_relation_type (v3),
            predicted_relation_confidence, reference_chunk, index_a, index_b, source.

Дальше по этой коллекции можно искать: эмбеддить ответ студента (с префиксом "query: ")
и брать ближайший кусок/пару — для проверки понятийных знаний.

Локальный режим (--qdrant-path) — встроенный Qdrant в папке, без сервера. Для сервера
задайте --qdrant-url http://localhost:6333.

Зависимости (.venv-relations): qdrant-client, sentence-transformers (см. requirements-adapter.txt).
Запуск из корня:
    python load_qdrant.py --chunks chunks_ontology_text.jsonl --qdrant-path ./qdrant_db
    python load_qdrant.py --query "из чего состоит слово"     # демо-поиск по готовой БД
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

try:  # вывод в UTF-8, иначе на Windows-консоли cp1251 падает на '→', кириллице и т.п.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ID_NAMESPACE = uuid.UUID("8f1d2c5a-2b7e-4c3a-9d6f-0a1b2c3d4e5f")  # детерминированные id точек
PAYLOAD_FIELDS = (
    "concept_a", "concept_b", "relation_type", "predicted_relation_type",
    "predicted_relation_confidence", "reference_chunk", "index_a", "index_b", "source",
)


def point_id(rec: dict) -> str:
    """Стабильный id точки: УПОРЯДОЧЕННАЯ пара + тип связи (направление и разные типы —
    разные точки; повтор одной и той же тройки идемпотентен)."""
    key = f"{rec.get('source')}|{rec.get('index_a')}|{rec.get('index_b')}|{rec.get('relation_type')}"
    return str(uuid.uuid5(ID_NAMESPACE, key))


def load_rows(path: str) -> list[dict]:
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def make_client(qdrant_path: Optional[str], qdrant_url: Optional[str]):
    from qdrant_client import QdrantClient
    return QdrantClient(url=qdrant_url) if qdrant_url else QdrantClient(path=qdrant_path or "./qdrant_db")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Загрузка эталонных кусков в Qdrant")
    p.add_argument("--chunks", default="chunks_ontology_text.jsonl")
    p.add_argument("--qdrant-path", default="./qdrant_db", help="папка встроенного Qdrant (без сервера)")
    p.add_argument("--qdrant-url", default=None, help="URL сервера Qdrant (вместо --qdrant-path)")
    p.add_argument("--collection", default="concept_pairs")
    p.add_argument("--model", default="intfloat/multilingual-e5-base",
                   help="модель эмбеддингов (e5: 768-dim, косинус)")
    p.add_argument("--passage-prefix", default="passage: ", help="префикс кусков для e5")
    p.add_argument("--query-prefix", default="query: ", help="префикс запросов для e5")
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--query", default=None, help="только демо-поиск по существующей БД (без загрузки)")
    p.add_argument("--top", type=int, default=5, help="сколько результатов показать в демо-поиске")
    args = p.parse_args(argv)

    from sentence_transformers import SentenceTransformer
    from qdrant_client.models import Distance, PointStruct, VectorParams

    print(f"Загрузка модели эмбеддингов {args.model} ...")
    model = SentenceTransformer(args.model)

    # --- режим демо-поиска по уже загруженной коллекции ---
    if args.query:
        client = make_client(args.qdrant_path, args.qdrant_url)
        qv = model.encode([args.query_prefix + args.query], normalize_embeddings=True)[0]
        hits = client.query_points(args.collection, query=[float(x) for x in qv], limit=args.top).points
        print(f"\nЗапрос: {args.query!r}")
        for h in hits:
            pl = h.payload
            print(f"  {h.score:.3f}  {pl['concept_a']} -> {pl['concept_b']}  "
                  f"[{pl['relation_type']}]  {pl['reference_chunk'][:90]}...")
        client.close()
        return 0

    # --- загрузка: ПОЛНАЯ пересборка из JSONL (чистим локальную БД для воспроизводимости) ---
    if not args.qdrant_url and Path(args.qdrant_path).exists():
        import shutil
        shutil.rmtree(args.qdrant_path)
    client = make_client(args.qdrant_path, args.qdrant_url)

    rows = load_rows(args.chunks)
    print(f"Кусков для загрузки: {len(rows)}")
    texts = [args.passage_prefix + r["reference_chunk"] for r in rows]
    print("Считаю эмбеддинги ...")
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=args.batch)
    dim = len(vectors[0])

    if client.collection_exists(args.collection):
        client.delete_collection(args.collection)
    client.create_collection(args.collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

    points = [
        PointStruct(
            id=point_id(r),
            vector=[float(x) for x in v],
            payload={k: r.get(k) for k in PAYLOAD_FIELDS},
        )
        for r, v in zip(rows, vectors)
    ]
    client.upsert(args.collection, points=points)
    total = client.count(args.collection).count
    print(f"\nЗагружено точек: {total} в коллекцию '{args.collection}' (dim={dim}, cosine).")

    # демо-поиск для проверки
    demo = "из чего состоит слово"
    qv = model.encode([args.query_prefix + demo], normalize_embeddings=True)[0]
    hits = client.query_points(args.collection, query=[float(x) for x in qv], limit=3).points
    print(f"Демо-поиск {demo!r}:")
    for h in hits:
        pl = h.payload
        print(f"  {h.score:.3f}  {pl['concept_a']} -> {pl['concept_b']}  [{pl['relation_type']}]")
    target = args.qdrant_url or args.qdrant_path
    print(f"\nГотово. БД: {target} · коллекция: {args.collection}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
