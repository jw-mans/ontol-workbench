"""Поиск помеченных циклов через произведение графа с автоматом.

Оба шаблона, которые проверяет cfpq_validator, регулярны, так что достаточно
обычного RPQ вместо КС-запроса:

    цикл наследования         a+  — нетривиальные SCC по рёбрам 'a';
    антипаттерн               a+ c+ a+ c+  — путь (v, q0) ->* (v, q_f) в G x НКА.

Метки рёбер:
    'a' — обобщение (generalization)
    'b' — зависимость (dependency)
    'c' — ассоциация (association, aggregation, composition, assoc. class)
    'r' — реализация (realization)
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Sequence, Set, Tuple

Edge = Tuple[int, str, int]  # (откуда, метка, куда)


def diagram_to_labeled_graph(diagram) -> Tuple[List[str], List[Edge]]:
    """Собрать (имена классов по индексам, рёбра (u, метка, v)) из диаграммы."""
    names: Set[str] = set()

    classifiers = getattr(diagram, 'classifiers', {}) or {}
    names.update(classifiers.keys() if hasattr(classifiers, 'keys') else [])

    generalizations = getattr(diagram, 'generalizations', [])
    dependencies = getattr(diagram, 'dependencies', [])
    realizations = getattr(diagram, 'realizations', [])
    associations = getattr(diagram, 'associations', [])

    for g in generalizations:
        names.add(g.specific.name)
        names.add(g.general.name)
    for d in dependencies:
        names.add(d.client.name)
        names.add(d.supplier.name)
    for r in realizations:
        names.add(r.implementer.name)
        names.add(r.interface_.name)
    for a in associations:
        for end in getattr(a, 'ends', []):
            names.add(end.participant.name)

    ordered = sorted(names)
    idx = {name: i for i, name in enumerate(ordered)}

    edges: List[Edge] = []
    for g in generalizations:
        edges.append((idx[g.specific.name], 'a', idx[g.general.name]))
    for d in dependencies:
        edges.append((idx[d.client.name], 'b', idx[d.supplier.name]))
    for r in realizations:
        edges.append((idx[r.implementer.name], 'r', idx[r.interface_.name]))
    for a in associations:
        ends = getattr(a, 'ends', [])
        for i in range(len(ends)):
            for j in range(len(ends)):
                if i != j:
                    edges.append(
                        (idx[ends[i].participant.name], 'c',
                         idx[ends[j].participant.name])
                    )
    return ordered, edges


def cycle_vertices(n: int, edges: Sequence[Edge], label: str) -> Set[int]:
    """Возвращает вершины, участвующие в нетривиальных SCC подграфа с меткой label."""
    adj: List[List[int]] = [[] for _ in range(n)]
    radj: List[List[int]] = [[] for _ in range(n)]
    self_loops: Set[int] = set()
    for u, edge_label, v in edges:
        if edge_label != label:
            continue
        if u == v:
            self_loops.add(u)
            continue
        adj[u].append(v)
        radj[v].append(u)

    # порядок завершения обхода (итеративный DFS, чтобы не упереться в рекурсию)
    visited = [False] * n
    order: List[int] = []
    for s in range(n):
        if visited[s]:
            continue
        stack: List[Tuple[int, int]] = [(s, 0)]
        visited[s] = True
        while stack:
            v, i = stack[-1]
            if i < len(adj[v]):
                stack[-1] = (v, i + 1)
                w = adj[v][i]
                if not visited[w]:
                    visited[w] = True
                    stack.append((w, 0))
            else:
                order.append(v)
                stack.pop()

    # компоненты на обратном графе в обратном порядке завершения
    comp = [-1] * n
    comp_size: Dict[int, int] = {}
    c = 0
    for s in reversed(order):
        if comp[s] != -1:
            continue
        comp[s] = c
        comp_size[c] = 1
        stack2 = [s]
        while stack2:
            v = stack2.pop()
            for w in radj[v]:
                if comp[w] == -1:
                    comp[w] = c
                    comp_size[c] += 1
                    stack2.append(w)
        c += 1

    on_cycle = {v for v in range(n) if comp_size[comp[v]] > 1}
    return on_cycle | self_loops


def inheritance_cycle_vertices(n: int, edges: Sequence[Edge]) -> Set[int]:
    """Вершины, участвующие в циклах обобщения (a+)."""
    return cycle_vertices(n, edges, 'a')


def dependency_cycle_vertices(n: int, edges: Sequence[Edge]) -> Set[int]:
    """Вершины, участвующие в циклах зависимостей (b+)."""
    return cycle_vertices(n, edges, 'b')


def association_cycle_vertices(n: int, edges: Sequence[Edge]) -> Set[int]:
    """Вершины, участвующие в циклах ассоциаций/агрегаций/композиций (c+)."""
    return cycle_vertices(n, edges, 'c')


def realization_cycle_vertices(n: int, edges: Sequence[Edge]) -> Set[int]:
    """Вершины, участвующие в циклах реализаций (r+)."""
    return cycle_vertices(n, edges, 'r')


# НКА для a+ c+ a+ c+: старт 0, приём 4.
#   0 -a-> 1 -a-> 1 -c-> 2 -c-> 2 -a-> 3 -a-> 3 -c-> 4 -c-> 4
# Вершина v нарушает, если (v,0) достижимо до (v,4) в произведении с графом.
ABAB_NFA: Dict[int, Dict[str, Tuple[int, ...]]] = {
    0: {'a': (1,)},
    1: {'a': (1,), 'c': (2,)},
    2: {'c': (2,), 'a': (3,)},
    3: {'a': (3,), 'c': (4,)},
    4: {'c': (4,)},
}
ABAB_START = 0
ABAB_ACCEPT = frozenset({4})
ABAB_STATES = 5


def abab_cycle_vertices(n: int, edges: Sequence[Edge]) -> Set[int]:
    adj: List[List[Tuple[str, int]]] = [[] for _ in range(n)]
    for u, label, v in edges:
        adj[u].append((label, v))

    violators: Set[int] = set()
    for s in range(n):
        # BFS по произведению из (s, старт); ищем возврат в s в принимающем.
        seen = [False] * (n * ABAB_STATES)
        seen[s * ABAB_STATES + ABAB_START] = True
        queue: deque[Tuple[int, int]] = deque([(s, ABAB_START)])
        found = False
        while queue and not found:
            u, q = queue.popleft()
            trans = ABAB_NFA.get(q)
            if not trans:
                continue
            for label, v in adj[u]:
                for q2 in trans.get(label, ()):
                    if v == s and q2 in ABAB_ACCEPT:
                        found = True
                        break
                    key = v * ABAB_STATES + q2
                    if not seen[key]:
                        seen[key] = True
                        queue.append((v, q2))
                if found:
                    break
        if found:
            violators.add(s)
    return violators
