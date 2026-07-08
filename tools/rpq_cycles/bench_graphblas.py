#!/usr/bin/env python3
"""
Замер GraphBLAS-детектора: корректность на DiGR + масштабирование по потокам.

1) сверяем с rpq_detect на онтологиях DiGR, 
2) гоняем синтетику на 1 потоке и на всех ядрах (nthreads меняется на лету). 

`python tools/rpq_cycles/bench_graphblas.py`
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_ONTOL_V3 = _REPO / 'src' / 'ontol-v3'
for p in (str(_ONTOL_V3), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

_TDL_DIR = _REPO / 'src' / 'digr' / 'ontology-pipeline' / 'data' / 'tdl'
_SIZES = (1200, 5000, 20000)
_PY_BASELINE_MAX_N = 20000  # дальше квадратичный чистый Python не ждём
_SEED = 42
_REPEATS = 3

from rpq_detect import (  # noqa: E402
    abab_cycle_vertices,
    diagram_to_labeled_graph,
    inheritance_cycle_vertices,
)
from kron_parallel import synthetic_ontology  # noqa: E402
from graphblas_impl import gb_detect_both, set_threads  # noqa: E402


def _check_digr() -> bool:
    from uml_dsl.tdl_lexer import lex
    from uml_dsl.tdl_parser import parse_tdl
    from uml_dsl.tdl_build import build_diagram

    ok_all = True
    for path in sorted(_TDL_DIR.glob('*.tdl')):
        with contextlib.redirect_stdout(io.StringIO()):
            diagram = build_diagram(
                parse_tdl(lex(path.read_text(encoding='utf-8')))
            )
        names, edges = diagram_to_labeled_graph(diagram)
        n = len(names)
        g_inh, g_abab = gb_detect_both(n, edges)
        ok = (g_inh == inheritance_cycle_vertices(n, edges)
              and g_abab == abab_cycle_vertices(n, edges))
        ok_all &= ok
        print(f'  {path.name[:44]:46} n={n:4} '
              f'{"совпало" if ok else "РАСХОЖДЕНИЕ!"}')
    return ok_all


def _best(fn) -> float:
    best = float('inf')
    for _ in range(_REPEATS):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding='utf-8')

    print('1) Корректность на онтологиях DiGR (GraphBLAS == эталон):')
    if not _check_digr():
        print('ЕСТЬ РАСХОЖДЕНИЯ — бенчмарк не имеет смысла')
        return 1
    print('Корректность: совпало на всех файлах')

    cpu = os.cpu_count() or 1
    print(f'\n2) Масштабирование (SuiteSparse OpenMP: 1 против {cpu} потоков; '
          f'min из {_REPEATS}):')
    rows = []
    for n in _SIZES:
        edges, expected = synthetic_ontology(n, _SEED)

        set_threads(cpu)
        _inh, abab = gb_detect_both(n, edges)  # прогрев + проверка посадки
        assert expected <= abab, 'посаженные циклы не найдены'

        t_many = _best(lambda: gb_detect_both(n, edges))
        set_threads(1)
        t_one = _best(lambda: gb_detect_both(n, edges))
        set_threads(cpu)

        if n <= _PY_BASELINE_MAX_N:
            t_py = _best(lambda: (
                inheritance_cycle_vertices(n, edges),
                abab_cycle_vertices(n, edges),
            ))
            py_str = f'{t_py:8.3f}s'
        else:
            t_py = None
            py_str = '   (пропущен)'

        speedup = t_one / t_many if t_many else 0.0
        rows.append({'n': n, 'edges': len(edges), 't1': t_one,
                     'tN': t_many, 'speedup': speedup, 'py': t_py})
        print(f'  n={n:6} рёбер={len(edges):6}  1 поток: {t_one:8.3f}s  '
              f'{cpu} потоков: {t_many:8.3f}s  x{speedup:4.1f}  '
              f'Python BFS: {py_str}')

    _write_report(rows, cpu)
    print(f'\nОтчёт: {_HERE / "results_graphblas.md"}')
    return 0


def _write_report(rows, cpu) -> None:
    import graphblas as gb

    ver = '.'.join(map(str, gb.ss.about['library_version']))
    lines = [
        '# RPQ-детекция на SuiteSparse:GraphBLAS (разреженно, OpenMP)',
        '',
        f'SuiteSparse:GraphBLAS {ver}, {cpu} ядер. Та же матричная форма,',
        'что в плотной BLAS-версии (Кронекер + замыкание булевым квадратом),',
        'но разреженные матрицы: не платим за нули. Потоки переключаются',
        "на лету (`gb.ss.config['nthreads']`).",
        '',
        '| Вершин | Рёбер | 1 поток, с | Все ядра, с | Ускорение | Чистый Python (BFS), с |',
        '|---:|---:|---:|---:|---:|---:|',
    ]
    for r in rows:
        py = f"{r['py']:.3f}" if r['py'] is not None else '—'
        lines.append(
            f"| {r['n']} | {r['edges']} | {r['t1']:.3f} | {r['tN']:.3f} "
            f"| x{r['speedup']:.1f} | {py} |"
        )
    lines += [
        '',
        'Корректность: GraphBLAS-детектор сверен с эталонным BFS по',
        'произведению на всех 11 онтологиях DiGR — множества нарушителей',
        'совпали по обоим шаблонам.',
        '',
        'Замечание: чистый Python считает диагональ per-source BFS-ом',
        '(квадратично по n), GraphBLAS — всё отношение достижимости разом;',
        'на больших n baseline пропущен из-за квадратичности.',
    ]
    (_HERE / 'results_graphblas.md').write_text(
        '\n'.join(lines) + '\n', encoding='utf-8'
    )


if __name__ == '__main__':
    sys.exit(main())
