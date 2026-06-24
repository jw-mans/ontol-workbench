import os

import pytest

from ontol import Parser, Project, ProjectStore, render_project


BASE_ONTOL = """version: '1.0'
title: 'Base'
author: ''
description: ''

types:
set: 'Set', '', { color: '#E6B8B7' }
element: 'Element', '', { color: '#E6B8B7' }
"""

MAIN_ONTOL = """version: '1.0'
title: 'Subsets'
author: ''
description: ''

import { set, element } from 'base.ontol'

types:
subset: 'Subset', '', { color: '#E6B8B7' }

hierarchy:
subset inheritance set
"""


def _make_project(tmp_path) -> Project:
    store = ProjectStore(str(tmp_path / 'projects'))
    project = store.create('demo')
    project.write_file('base.ontol', BASE_ONTOL)
    project.write_file('main.ontol', MAIN_ONTOL)
    return project


def test_store_create_list_delete(tmp_path):
    store = ProjectStore(str(tmp_path / 'projects'))
    assert store.list_projects() == []

    store.create('alpha')
    store.create('beta')
    assert store.list_projects() == ['alpha', 'beta']
    assert store.exists('alpha')

    store.delete('alpha')
    assert store.list_projects() == ['beta']

    with pytest.raises(ValueError):
        store.create('beta')  # already exists


def test_store_rename(tmp_path):
    store = ProjectStore(str(tmp_path / 'projects'))
    store.create('old')
    store.rename('old', 'new')
    assert store.list_projects() == ['new']


def test_project_file_operations(tmp_path):
    project = _make_project(tmp_path)
    assert project.list_files() == ['base.ontol', 'main.ontol']
    assert 'subset' in project.read_file('main.ontol')

    # extension is added automatically
    # расширение добавляется автоматически
    project.write_file('extra', 'types:\n')
    assert 'extra.ontol' in project.list_files()

    project.delete_file('extra.ontol')
    assert 'extra.ontol' not in project.list_files()


def test_path_traversal_is_rejected(tmp_path):
    store = ProjectStore(str(tmp_path / 'projects'))
    project = store.create('demo')
    for bad in ('../escape.ontol', 'sub/dir.ontol', '..'):
        with pytest.raises(ValueError):
            project.file_path(bad)
    with pytest.raises(ValueError):
        store.get('../evil')


def test_cross_file_import_resolves(tmp_path):
    """Imports between project files resolve against the project directory.

    Импорты между файлами проекта разрешаются относительно каталога проекта.
    """
    project = _make_project(tmp_path)
    content = project.read_file('main.ontol')
    ontology, _warnings = Parser().parse(content, project.file_path('main.ontol'))

    names = [t.name for t in ontology.types]
    assert names == ['set', 'element', 'subset']  # imported + local
    rels = [
        (r.parent.name, r.relationship.value, r.children[0].name)
        for r in ontology.hierarchy
    ]
    assert ('subset', 'inheritance', 'set') in rels


def test_render_project_produces_json_and_puml(tmp_path):
    project = _make_project(tmp_path)
    out = str(tmp_path / 'out')
    result = render_project(project, 'main.ontol', out)

    assert result.ok, result.error
    assert os.path.isfile(result.json_path)
    assert os.path.isfile(result.puml_path)
    # JSON reflects the imported term
    # JSON отражает импортированный терм
    with open(result.json_path, encoding='utf-8') as f:
        assert 'subset' in f.read()


def test_render_reports_error_for_bad_file(tmp_path):
    project = _make_project(tmp_path)
    project.write_file('broken.ontol', "import { nope } from 'missing.ontol'\n")
    result = render_project(project, 'broken.ontol', str(tmp_path / 'out2'))
    assert not result.ok
    assert result.error


def test_direct_circular_import_is_detected(tmp_path):
    """a -> b -> a must raise a clear error, not RecursionError.

    a -> b -> a должно вызывать понятную ошибку, а не RecursionError.
    """
    project = ProjectStore(str(tmp_path / 'projects')).create('cycle')
    project.write_file('a.ontol', "import * from 'b.ontol'\n\ntypes:\nx: 'X', ''\n")
    project.write_file('b.ontol', "import * from 'a.ontol'\n\ntypes:\ny: 'Y', ''\n")

    with pytest.raises(ValueError) as excinfo:
        Parser().parse(project.read_file('a.ontol'), project.file_path('a.ontol'))
    assert 'circular import' in str(excinfo.value).lower()


def test_self_import_is_detected(tmp_path):
    project = ProjectStore(str(tmp_path / 'projects')).create('selfcycle')
    project.write_file('a.ontol', "import * from 'a.ontol'\n\ntypes:\nx: 'X', ''\n")

    with pytest.raises(ValueError) as excinfo:
        Parser().parse(project.read_file('a.ontol'), project.file_path('a.ontol'))
    assert 'circular import' in str(excinfo.value).lower()


def test_render_reports_circular_import(tmp_path):
    project = ProjectStore(str(tmp_path / 'projects')).create('cycle2')
    project.write_file('a.ontol', "import * from 'b.ontol'\n\ntypes:\nx: 'X', ''\n")
    project.write_file('b.ontol', "import * from 'a.ontol'\n\ntypes:\ny: 'Y', ''\n")

    result = render_project(project, 'a.ontol', str(tmp_path / 'out'))
    assert not result.ok
    assert 'circular import' in result.error.lower()


def test_diamond_import_is_allowed(tmp_path):
    """a imports b and c, both import (different terms from) d.

    d is parsed via two distinct paths but is not part of a single import
    chain, so it must not be flagged as a circular import.

    a импортирует b и c, оба импортируют (разные термы из) d.

    d разбирается по двум разным путям, но не входит в одну цепочку импортов,
    поэтому не должен помечаться как циклический импорт.
    """
    project = ProjectStore(str(tmp_path / 'projects')).create('diamond')
    project.write_file('d.ontol', "types:\nfoo: 'Foo', ''\nbar: 'Bar', ''\n")
    project.write_file('b.ontol', "import { foo } from 'd.ontol'\n")
    project.write_file('c.ontol', "import { bar } from 'd.ontol'\n")
    project.write_file(
        'a.ontol', "import * from 'b.ontol'\nimport * from 'c.ontol'\n"
    )

    ontology, _ = Parser().parse(
        project.read_file('a.ontol'), project.file_path('a.ontol')
    )
    names = [t.name for t in ontology.types]
    assert 'foo' in names and 'bar' in names


def test_diamond_import_same_term_is_deduplicated(tmp_path):
    """The *same* term reaching a file through two paths must be deduplicated,
    not rejected as 'already declared'.

    Один и тот же терм, пришедший в файл по двум путям, должен дедуплицироваться,
    а не отвергаться как 'already declared'.
    """
    project = ProjectStore(str(tmp_path / 'projects')).create('diamond_same')
    project.write_file('base.ontol', "types:\nset: 'Set', ''\n")
    project.write_file('b.ontol', "import { set } from 'base.ontol'\n")
    project.write_file('c.ontol', "import { set } from 'base.ontol'\n")
    project.write_file(
        'a.ontol', "import { set } from 'b.ontol'\nimport { set } from 'c.ontol'\n"
    )

    ontology, _ = Parser().parse(
        project.read_file('a.ontol'), project.file_path('a.ontol')
    )
    names = [t.name for t in ontology.types]
    assert names.count('set') == 1


def test_conflicting_definitions_still_error(tmp_path):
    """Two *different* definitions sharing a name remain a hard error.

    Два *разных* определения с одинаковым именем остаются жёсткой ошибкой.
    """
    project = ProjectStore(str(tmp_path / 'projects')).create('conflict')
    project.write_file('one.ontol', "types:\nset: 'Set', ''\n")
    project.write_file('two.ontol', "types:\nset: 'OTHER', 'different'\n")
    project.write_file(
        'a.ontol', "import { set } from 'one.ontol'\nimport { set } from 'two.ontol'\n"
    )

    with pytest.raises(ValueError) as excinfo:
        Parser().parse(project.read_file('a.ontol'), project.file_path('a.ontol'))
    assert 'already been declared' in str(excinfo.value)
