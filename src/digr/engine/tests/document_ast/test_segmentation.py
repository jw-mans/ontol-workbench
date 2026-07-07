from __future__ import annotations

import pytest

from document_ast.segmentation.text_segmenter import TextSegmenter, resolve_flags


def test_resolve_flags_supports_named_regex_flags() -> None:
    flags = resolve_flags({"flags": ["IGNORECASE", "DOTALL"]})

    assert flags != 0


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"flags": [123]}, "Regex flag must be a string"),
        ({"flags": ["NOPE"]}, "Unsupported regex flag"),
    ],
)
def test_resolve_flags_rejects_invalid_entries(config: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_flags(config)


def test_text_segmenter_split_trims_and_drops_empty_segments() -> None:
    segmenter = TextSegmenter()
    segments = segmenter.segment(
        "  one \n\n two \n\n   ",
        0,
        {"kind": "split", "boundary_pattern": r"\n\n", "trim": True, "drop_empty": True},
    )

    assert [segment.text for segment in segments] == ["one", "two"]
    assert segments[0].start == 2
    assert segments[0].end == 5


def test_text_segmenter_match_returns_word_like_segments() -> None:
    segmenter = TextSegmenter()
    segments = segmenter.segment(
        "alpha beta",
        10,
        {"kind": "match", "pattern": r"\w+", "trim": True, "drop_empty": True},
    )

    assert [(segment.text, segment.start, segment.end) for segment in segments] == [
        ("alpha", 10, 15),
        ("beta", 16, 20),
    ]


def test_text_segmenter_supports_custom_strategy_registration() -> None:
    class StaticStrategy:
        def segment(self, text: str, base_start: int, segmenter_config: dict[str, object]):
            del text, segmenter_config
            from document_ast.segmentation.text_segment import TextSegment

            return [TextSegment(text="custom", start=base_start, end=base_start + 6)]

    segmenter = TextSegmenter()
    segmenter.register("custom", StaticStrategy())

    segments = segmenter.segment("ignored", 3, {"kind": "custom", "trim": False, "drop_empty": False})

    assert [segment.text for segment in segments] == ["custom"]


def test_text_segmenter_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unsupported segmenter kind"):
        TextSegmenter().segment("text", 0, {"kind": "unknown"})
