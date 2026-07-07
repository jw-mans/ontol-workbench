from __future__ import annotations

from collections import defaultdict

from document_ast.model.ast_document import AstDocument
from document_ast.model.ast_node import AstNode


class DocumentIndex:
    def __init__(self, document: AstDocument) -> None:
        self._document = document
        self._all_nodes: list[AstNode] = []
        self._nodes_by_entity: dict[str, list[AstNode]] = defaultdict(list)
        self._parent_by_id: dict[int, AstNode | None] = {}
        self._walk(document.root, parent=None)
        self._all_nodes.sort(key=lambda node: (node.start, node.end, node.entity))
        for nodes in self._nodes_by_entity.values():
            nodes.sort(key=lambda node: (node.start, node.end, node.entity))

    @property
    def document(self) -> AstDocument:
        return self._document

    def entities(self) -> set[str]:
        return set(self._nodes_by_entity)

    def nodes_of_entity(self, entity_name: str) -> list[AstNode]:
        return list(self._nodes_by_entity.get(entity_name, ()))

    def children(self, node: AstNode) -> list[AstNode]:
        return list(node.children)

    def descendants(self, node: AstNode) -> list[AstNode]:
        items: list[AstNode] = []
        for child in node.children:
            items.append(child)
            items.extend(self.descendants(child))
        return items

    def ancestors(self, node: AstNode) -> list[AstNode]:
        node_id = id(node)
        if node_id in self._parent_by_id:
            items: list[AstNode] = []
            parent = self._parent_by_id[node_id]
            while parent is not None:
                items.append(parent)
                parent = self._parent_by_id.get(id(parent))
            return items
        return self.container_nodes_for_span(node.start, node.end, strict=True)

    def nodes_within_span(
            self,
            start: int,
            end: int,
            entity_name: str | None = None,
    ) -> list[AstNode]:
        candidates = self._all_nodes if entity_name is None else self._nodes_by_entity.get(entity_name, ())
        return [node for node in candidates if node.start >= start and node.end <= end]

    def container_nodes_for_span(
            self,
            start: int,
            end: int,
            entity_name: str | None = None,
            *,
            strict: bool = False,
    ) -> list[AstNode]:
        candidates = self._all_nodes if entity_name is None else self._nodes_by_entity.get(entity_name, ())
        items = []
        for node in candidates:
            if node.start <= start and node.end >= end:
                if strict and node.start == start and node.end == end:
                    continue
                items.append(node)
        items.sort(key=lambda node: (node.end - node.start, node.start, node.entity))
        return items

    def previous_node(self, start: int, entity_name: str) -> AstNode | None:
        previous = None
        for node in self._nodes_by_entity.get(entity_name, ()):
            if node.end <= start:
                previous = node
                continue
            break
        return previous

    def next_node(self, end: int, entity_name: str) -> AstNode | None:
        for node in self._nodes_by_entity.get(entity_name, ()):
            if node.start >= end:
                return node
        return None

    def _walk(self, node: AstNode, parent: AstNode | None) -> None:
        self._all_nodes.append(node)
        self._nodes_by_entity[node.entity].append(node)
        self._parent_by_id[id(node)] = parent
        for child in node.children:
            self._walk(child, node)
