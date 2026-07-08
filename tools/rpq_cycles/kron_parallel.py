#!/usr/bin/env python3
"""
Та же детекция, что в rpq_detect, но матрицами — чтобы упиралось в BLAS.

`python kron_parallel.py --bench <n> --seed <s>`
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np

Edge = Tuple[int, str, int]

# НКА в матричной форме: {метка: список переходов (q, q')}

# a+ b+ a+ b+ (антипаттерн): 5 состояний, старт 0, принимает 4.
ABAB = {
    'Q': 5, 'start': 0, 'accept': (4,),
    'delta': {'a': ((0, 1), (1, 1), (2, 3), (3, 3)),
              'b': ((1, 2), (2, 2), (3, 4), (4, 4))},
}
# a+ (цикл наследования): 2 состояния, старт 0, принимает 1.
APLUS = {
    'Q': 2, 'start': 0, 'accept': (1,),
    'delta': {'a': ((0, 1), (1, 1))},
}


def _label_matrices(n: int, edges: Sequence[Edge]) -> Dict[str, np.ndarray]:
    """Булевы матрицы смежности по каждой метке (float32 под BLAS)."""
    mats: Dict[str, np.ndarray] = {}
    for u, label, v in edges:
        if label not in mats:
            mats[label] = np.zeros((n, n), dtype=np.float32)
        mats[label][u, v] = 1.0
    return mats


def _product_matrix(n: int, mats: Dict[str, np.ndarray], nfa: dict) -> np.ndarray:
    """M = сумма A_l (x) N_l, но без np.kron: блок q->q' — это срез M[q::Q, q'::Q]."""
    Q = nfa['Q']
    M = np.zeros((n * Q, n * Q), dtype=np.float32)
    for label, trans in nfa['delta'].items():
        A = mats.get(label)
        if A is None:
            continue
        for q, q2 in trans:
            np.maximum(M[q::Q, q2::Q], A, out=M[q::Q, q2::Q])
    return M


def _closure(M: np.ndarray) -> Tuple[np.ndarray, int]:
    """Замыкание (M+I) повторным булевым квадратом до стабилизации; matmul — BLAS."""
    T = (M + np.eye(M.shape[0], dtype=np.float32)) > 0
    T = T.astype(np.float32)
    mults = 0
    while True:
        T2 = (T @ T) > 0
        mults += 1
        T2 = T2.astype(np.float32)
        if np.array_equal(T2, T):
            return T2.astype(bool), mults
        T = T2


def kron_cycle_vertices(
    n: int, edges: Sequence[Edge], nfa: dict
) -> Set[int]:
    """Вершины на замкнутом обходе, чья метка принимается НКА."""
    if n == 0:
        return set()
    Q = nfa['Q']
    M = _product_matrix(n, _label_matrices(n, edges), nfa)
    T, _ = _closure(M)
    rows = np.arange(n) * Q + nfa['start']
    violators: Set[int] = set()
    for qf in nfa['accept']:
        cols = np.arange(n) * Q + qf
        violators.update(np.nonzero(T[rows, cols])[0].tolist())
    return violators


def kron_detect_both(n: int, edges: Sequence[Edge]) -> Tuple[Set[int], Set[int]]:
    """(циклы наследования a+, антипаттерн a+b+a+b+) — как в rpq_detect."""
    return (
        kron_cycle_vertices(n, edges, APLUS),
        kron_cycle_vertices(n, edges, ABAB),
    )


# синтетика: лес a-рёбер + поперечные b-дуги + посаженные abab-циклы, по сиду
def synthetic_ontology(
    n: int, seed: int, planted: int = 5
) -> Tuple[List[Edge], Set[int]]:
    rng = random.Random(seed)
    edges: List[Edge] = []
    for v in range(1, n):  # лес: родитель — более ранний узел
        if rng.random() < 0.9:
            edges.append((v, 'a', rng.randrange(v)))
    for _ in range(n // 2):  # поперечные зависимости
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v:
            edges.append((u, 'b', v))
    expected: Set[int] = set()
    for _ in range(planted):  # посаженные нарушители
        u, v, w, x = rng.sample(range(n), 4)
        edges += [(u, 'a', v), (v, 'b', w), (w, 'a', x), (x, 'b', u)]
        expected.add(u)
    return edges, expected


def _bench(n: int, seed: int) -> dict:
    """Один замер для сабпроцесса: собрать синтетику, прогнать оба шаблона."""
    edges, expected = synthetic_ontology(n, seed)
    t0 = time.perf_counter()
    inh, abab = kron_detect_both(n, edges)
    seconds = time.perf_counter() - t0
    return {
        'n': n,
        'edges': len(edges),
        'seconds': round(seconds, 4),
        'inh': len(inh),
        'abab': len(abab),
        'planted_found': expected <= abab,
        'threads': os.environ.get('OPENBLAS_NUM_THREADS', 'default'),
        'cpu_count': os.cpu_count(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--bench', type=int, metavar='N', required=True)
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()
    print(json.dumps(_bench(args.bench, args.seed)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
