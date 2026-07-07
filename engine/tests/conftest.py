from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from document_ast import ActorAstParser, ConfigLoader
from dsl import ActorDslEngine, ActorDslParser
from dsl.execution.document_index import DocumentIndex


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def config_dir(repo_root: Path) -> Path:
    return repo_root / "config" / "formats"


@pytest.fixture(scope="session")
def sample_text_path(repo_root: Path) -> Path:
    return repo_root / "text.txt"


@pytest.fixture(scope="session")
def txt_config(config_dir: Path):
    return ConfigLoader().load(config_dir / "txt.yaml", expected_format_name="txt")


@pytest.fixture(scope="session")
def sample_document(sample_text_path: Path, config_dir: Path):
    parser = ActorAstParser.from_config_dir(config_dir)
    return parser.parse(sample_text_path, format_name="txt")


@pytest.fixture(scope="session")
def document_index(sample_document):
    return DocumentIndex(sample_document)


@pytest.fixture(scope="session")
def dsl_parser():
    return ActorDslParser()


@pytest.fixture(scope="session")
def dsl_engine():
    return ActorDslEngine()


@pytest.fixture
def workspace_tmp(repo_root: Path) -> Path:
    path = repo_root / ".test_tmp" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path
