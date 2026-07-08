#!/usr/bin/env python3
"""
То же, что kron_parallel, но на SuiteSparse:GraphBLAS — разреженно и на CPU.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Set, Tuple

import graphblas as gb

from kron_parallel import ABAB, APLUS

Edge = Tuple[int, str, int]


def _label_matrices(n: int, edges: Sequence[Edge]) -> Dict[str, gb.Matrix]:
    """Разреженные булевы матрицы смежности по каждой метке."""
    by_label: Dict[str, Tuple[List[int], List[int]]] = {}
    for u, label, v in edges:
        rows, cols = by_label.setdefault(label, ([], []))
        rows.append(u)
        cols.append(v)
    return {
        label: gb.Matrix.from_coo(
            rows, cols, True, dtype=bool, nrows=n, ncols=n
        )
        for label, (rows, cols) in by_label.items()
    }


def _nfa_matrices(nfa: dict) -> Dict[str, gb.Matrix]:
    """Матрицы переходов НКА по каждой метке."""
    Q = nfa['Q']
    out: Dict[str, gb.Matrix] = {}
    for label, trans in nfa['delta'].items():
        rows = [q for q, _ in trans]
        cols = [q2 for _, q2 in trans]
        out[label] = gb.Matrix.from_coo(
            rows, cols, True, dtype=bool, nrows=Q, ncols=Q
        )
    return out


def _product_matrix(
    n: int, mats: Dict[str, gb.Matrix], nfa: dict
) -> gb.Matrix:
    """M = SUM_l A_l (x) N_l — настоящий GrB_kronecker, нумерация (v,q)=v*Q+q."""
    Q = nfa['Q']
    nfa_mats = _nfa_matrices(nfa)
    M = gb.Matrix(bool, n * Q, n * Q)
    for label, N in nfa_mats.items():
        A = mats.get(label)
        if A is None:
            continue
        M(gb.binary.lor) << A.kronecker(N, gb.binary.land)
    return M


def _closure(M: gb.Matrix) -> Tuple[gb.Matrix, int]:
    """Замыкание (M+I) через mxm lor_land, пока растёт nvals."""
    size = M.nrows
    T = M.ewise_add(
        gb.Matrix.from_coo(range(size), range(size), True, dtype=bool),
        gb.binary.lor,
    ).new()
    mults = 0
    while True:
        T2 = T.mxm(T, gb.semiring.lor_land).new()
        mults += 1
        if T2.nvals == T.nvals:
            return T2, mults
        T = T2


def gb_cycle_vertices(n: int, edges: Sequence[Edge], nfa: dict) -> Set[int]:
    """Вершины на замкнутом обходе, чья метка принимается НКА."""
    if n == 0:
        return set()
    Q = nfa['Q']
    M = _product_matrix(n, _label_matrices(n, edges), nfa)
    T, _ = _closure(M)
    starts = [v * Q + nfa['start'] for v in range(n)]
    violators: Set[int] = set()
    for qf in nfa['accept']:
        accepts = [v * Q + qf for v in range(n)]
        S = T[starts, accepts].new()  # n x n; нарушители — диагональ
        rows, cols, _vals = S.to_coo()
        violators.update(int(i) for i, j in zip(rows, cols) if i == j)
    return violators


def gb_detect_both(n: int, edges: Sequence[Edge]) -> Tuple[Set[int], Set[int]]:
    """(циклы наследования a+, антипаттерн a+b+a+b+) — как в rpq_detect."""
    return (
        gb_cycle_vertices(n, edges, APLUS),
        gb_cycle_vertices(n, edges, ABAB),
    )


def set_threads(k: int | None) -> int:
    """Выставить число OpenMP-потоков SuiteSparse; None — все ядра."""
    import os

    k = k or (os.cpu_count() or 1)
    gb.ss.config['nthreads'] = k
    return int(gb.ss.config['nthreads'])
