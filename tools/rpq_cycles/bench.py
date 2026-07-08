#!/usr/bin/env python3
"""
Сравнение RPQ-детектора с матричным CFPQ на онтологиях DiGR.

Оба получают один и тот же граф и ищут одно и то же (циклы a+ и антипаттерн a+ b+ a+ b+); 
сверяем, что множества нарушителей совпадают, и меряем время

`python tools/rpq_cycles/bench.py`
"""

from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ONTOL_V3 = _REPO / 'src' / 'ontol-v3'
if str(_ONTOL_V3) not in sys.path:
    sys.path.insert(0, str(_ONTOL_V3))
sys.path.insert(0, str(Path(__file__).resolve().parent))

_TDL_DIR = _REPO / 'src' / 'digr' / 'ontology-pipeline' / 'data' / 'tdl'
_REPEATS = 7

from rpq_detect import (  # noqa: E402
    abab_cycle_vertices,
    diagram_to_labeled_graph,
    inheritance_cycle_vertices,
)


def _load_graphs() -> list[tuple[str, list[str], list[tuple[int, str, int]]]]:
    """Разобрать все DiGR .tdl в помеченные графы (без семантической валидации)."""
    from uml_dsl.tdl_lexer import lex
    from uml_dsl.tdl_parser import parse_tdl
    from uml_dsl.tdl_build import build_diagram

    graphs = []
    for path in sorted(_TDL_DIR.glob('*.tdl')):
        diagram = build_diagram(parse_tdl(lex(path.read_text(encoding='utf-8'))))
        names, edges = diagram_to_labeled_graph(diagram)
        graphs.append((path.name, names, edges))
    return graphs


def _cfpq_setup():
    """Заранее построить WCNF-грамматики (вне замера, как и NFA у RPQ)."""
    from uml_dsl.cfpq_matrix import Grammar
    from uml_dsl.grammar_utils import to_wcnf

    inh = to_wcnf(Grammar.from_text('S -> S S\nS -> a'))
    abab = to_wcnf(Grammar.from_text(
        'S -> Ap1 MidMid\n'
        'MidMid -> Bk1 RightRight\n'
        'RightRight -> Ap2 Bp2\n'
        'Ap1 -> a\nAp1 -> A_term Ap1\n'
        'Bk1 -> b\nBk1 -> B_term Bk1\n'
        'Ap2 -> a\nAp2 -> A_term Ap2\n'
        'Bp2 -> b\nBp2 -> B_term Bp2\n'
        'A_term -> a\nB_term -> b'
    ))
    return inh, abab


def _cfpq_detect(n, edges, inh_grammar, abab_grammar) -> tuple[set, set]:
    """Диагонали CFPQ для обоих шаблонов (как в cfpq_validator)."""
    from uml_dsl.cfpq_matrix import LabeledGraph, cfpq_matrix

    graph = LabeledGraph(num_nodes=n, edges=list(edges))
    inh_res = cfpq_matrix(graph, inh_grammar, use_sparse=True)
    abab_res = cfpq_matrix(graph, abab_grammar, use_sparse=True)
    inh = {i for i, j in inh_res.get('S', []) if i == j}
    abab = {i for i, j in abab_res.get('S', []) if i == j}
    return inh, abab


def _rpq_detect(n, edges) -> tuple[set, set]:
    return inheritance_cycle_vertices(n, edges), abab_cycle_vertices(n, edges)


def _time_best(fn, repeats=_REPEATS) -> float:
    """Минимум по прогонам, сек; stdout заглушён (CFPQ печатает отладку)."""
    best = float('inf')
    for _ in range(repeats):
        with contextlib.redirect_stdout(io.StringIO()):
            t0 = time.perf_counter()
            fn()
            best = min(best, time.perf_counter() - t0)
    return best


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding='utf-8')

    graphs = _load_graphs()
    inh_g, abab_g = _cfpq_setup()

    rows = []
    total_cfpq = total_rpq = 0.0
    all_match = True
    for name, names, edges in graphs:
        n = len(names)
        ea = sum(1 for _, l, _ in edges if l == 'a')
        eb = len(edges) - ea

        with contextlib.redirect_stdout(io.StringIO()):
            cfpq_inh, cfpq_abab = _cfpq_detect(n, edges, inh_g, abab_g)
        rpq_inh, rpq_abab = _rpq_detect(n, edges)

        match = (cfpq_inh == rpq_inh) and (cfpq_abab == rpq_abab)
        all_match &= match

        t_cfpq = _time_best(lambda: _cfpq_detect(n, edges, inh_g, abab_g))
        t_rpq = _time_best(lambda: _rpq_detect(n, edges))
        total_cfpq += t_cfpq
        total_rpq += t_rpq

        rows.append({
            'file': name, 'n': n, 'ea': ea, 'eb': eb,
            'inh': len(rpq_inh), 'abab': len(rpq_abab),
            't_cfpq': t_cfpq * 1000, 't_rpq': t_rpq * 1000,
            'speedup': (t_cfpq / t_rpq) if t_rpq > 0 else float('inf'),
            'match': match,
        })

    _write_report(rows, total_cfpq, total_rpq, all_match)
    for r in rows:
        print(
            f"{r['file'][:44]:46} n={r['n']:4} инас={r['inh']:3} abab={r['abab']:3}"
            f"  CFPQ {r['t_cfpq']:8.2f}ms  RPQ {r['t_rpq']:7.2f}ms"
            f"  x{r['speedup']:<7.1f} {'OK' if r['match'] else 'РАСХОЖДЕНИЕ'}"
        )
    print(
        f"\nИтого: CFPQ {total_cfpq*1000:.1f}ms, RPQ {total_rpq*1000:.1f}ms, "
        f"ускорение x{total_cfpq/total_rpq:.1f}; "
        f"результаты {'совпали на всех файлах' if all_match else 'РАЗОШЛИСЬ!'}"
    )
    print(f"Отчёт: {Path(__file__).parent / 'results.md'}")
    return 0 if all_match else 1


def _write_report(rows, total_cfpq, total_rpq, all_match) -> None:
    lines = [
        '# RPQ (произведение + SCC) против матричного CFPQ',
        '',
        'Оба шаблона регулярны, поэтому детектятся линейно от размера',
        'произведения граф x NFA — кубический CFPQ для них избыточен.',
        f'Время — минимум из {_REPEATS} прогонов; множества нарушителей',
        'проверены на равенство (диагональ CFPQ == результат RPQ).',
        '',
        '| Файл | Вершин | a-рёбер | b-рёбер | На цикле a+ | На abab | CFPQ, мс | RPQ, мс | Ускорение | Совпало |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|',
    ]
    for r in rows:
        lines.append(
            f"| {r['file']} | {r['n']} | {r['ea']} | {r['eb']} | {r['inh']} "
            f"| {r['abab']} | {r['t_cfpq']:.2f} | {r['t_rpq']:.2f} "
            f"| x{r['speedup']:.1f} | {'да' if r['match'] else 'НЕТ'} |"
        )
    lines += [
        '',
        f'**Итого**: CFPQ {total_cfpq*1000:.1f} мс, RPQ {total_rpq*1000:.1f} мс, '
        f'ускорение **x{total_cfpq/total_rpq:.1f}**. '
        + ('Результаты совпали на всех файлах.' if all_match
           else '**ВНИМАНИЕ: есть расхождения!**'),
        '',
        'Замечания к методике: CFPQ считает на scipy (разреженные булевы',
        'матрицы, C-код), RPQ — чистый Python; выигрыш достигается алгоритмом',
        '(линейность), а не константами. Конструкция грамматик/NFA вынесена',
        'за замер у обеих сторон.',
    ]
    (Path(__file__).parent / 'results.md').write_text(
        '\n'.join(lines) + '\n', encoding='utf-8'
    )


if __name__ == '__main__':
    raise SystemExit(main())
