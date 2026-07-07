from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "engine" / "src"))
sys.path.insert(0, str(ROOT.parent / "relation-classifier"))

from build_chunks_dataset import ConceptOccurrence  # noqa: E402
from build_primary_ontology import BlockIndex, clean_index, pairs_within_blocks  # noqa: E402


def test_clean_index_strips_english_gloss_and_hierarchy() -> None:
    assert clean_index("Область (domain)!интерпретации (of interpretation)") == "Область интерпретации"
    assert clean_index("Моноид (monoid)") == "Моноид"


def test_pairs_within_blocks_uses_two_block_window() -> None:
    from build_chunks_dataset import SemanticBlock

    blocks = [SemanticBlock(start=0, end=10, kind=None), SemanticBlock(start=10, end=20, kind=None),
              SemanticBlock(start=20, end=30, kind=None)]
    block_index = BlockIndex(blocks)
    odmkeys = [
        ConceptOccurrence(index="a", name="a", start=1, end=2),
        ConceptOccurrence(index="b", name="b", start=11, end=12),
        ConceptOccurrence(index="c", name="c", start=21, end=22),
    ]
    pairs = pairs_within_blocks(odmkeys, block_index, window_blocks=2)
    assert ("a", "b") in pairs
    assert ("b", "c") in pairs
    assert ("a", "c") not in pairs
