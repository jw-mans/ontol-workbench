"""
RPQ-детекция помеченных циклов — ре-экспорт продакшен-модуля.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ONTOL_V3 = Path(__file__).resolve().parents[2] / 'src' / 'ontol-v3'
if str(_ONTOL_V3) not in sys.path:
    sys.path.insert(0, str(_ONTOL_V3))

from uml_dsl.rpq_cycles import (  # noqa: E402,F401
    ABAB_ACCEPT,
    ABAB_NFA,
    ABAB_START,
    ABAB_STATES,
    Edge,
    abab_cycle_vertices,
    diagram_to_labeled_graph,
    inheritance_cycle_vertices,
)
