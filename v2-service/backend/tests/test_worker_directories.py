"""Тест для проверки _load_subtree_ontol с директориями."""

import uuid
from app.models.file import File
from app.models.project import Project
from app.models.directory import Directory
from app.worker import _load_subtree_ontol, _load_files


async def test_load_subtree_ontol_with_directories(session_maker):
    """Проверить, что файлы в директориях собираются с правильными путями."""
    
    # Создаем проект с директорией и файлом в ней
    async with session_maker() as session:
        owner = uuid.uuid4()
        project = Project(id=uuid.uuid4(), owner_id=owner, name='TestProject')
        session.add(project)
        await session.flush()
        
        # Создаем директорию
        dir1 = Directory(
            project_id=project.id,
            parent_directory_id=None,
            name='123'
        )
        session.add(dir1)
        await session.flush()
        
        # Создаем файл в директории
        file1 = File(
            project_id=project.id,
            directory_id=dir1.id,
            name='types.ontol',
            content="types:\ntype_list: 'TypeList', ''"
        )
        session.add(file1)
        
        # Создаем файл в корне
        file2 = File(
            project_id=project.id,
            directory_id=None,
            name='bootstrapping.ontol',
            content="import { type_list } from '123/types.ontol'\ntitle: 'Test'"
        )
        session.add(file2)
        
        await session.commit()
        pid = str(project.id)
    
    # Загружаем файлы
    files = await _load_subtree_ontol(pid)
    
    # Проверяем, что оба файла загружены с правильными путями
    assert 'bootstrapping.ontol' in files, f"Missing bootstrapping.ontol in {list(files.keys())}"
    assert '123/types.ontol' in files, f"Missing 123/types.ontol in {list(files.keys())}"
    
    # Проверяем содержимое
    assert "import { type_list } from '123/types.ontol'" in files['bootstrapping.ontol']
    assert "types:\ntype_list: 'TypeList', ''" in files['123/types.ontol']
    
    print("Test _load_subtree_ontol with directories passed!")
    print("Files collected:")
    for path in files:
        print(f"  - {path}")


async def test_load_subtree_ontol_nested_directories(session_maker):
    """Проверить вложенные директории."""
    
    async with session_maker() as session:
        owner = uuid.uuid4()
        project = Project(id=uuid.uuid4(), owner_id=owner, name='Nested')
        session.add(project)
        await session.flush()
        
        # Создаем структуру: dir1/dir2/file.ontol
        dir1 = Directory(
            project_id=project.id,
            parent_directory_id=None,
            name='dir1'
        )
        session.add(dir1)
        await session.flush()
        
        dir2 = Directory(
            project_id=project.id,
            parent_directory_id=dir1.id,
            name='dir2'
        )
        session.add(dir2)
        await session.flush()
        
        file1 = File(
            project_id=project.id,
            directory_id=dir2.id,
            name='nested.ontol',
            content="types:\nnested: 'Nested', ''"
        )
        session.add(file1)
        
        await session.commit()
        pid = str(project.id)
    
    files = await _load_subtree_ontol(pid)
    
    assert 'dir1/dir2/nested.ontol' in files, f"Missing dir1/dir2/nested.ontol in {list(files.keys())}"
    assert "types:\nnested: 'Nested', ''" in files['dir1/dir2/nested.ontol']
    
    print("Test nested directories passed!")
    print("Files collected:")
    for path in files:
        print(f"  - {path}")


async def test_load_files_with_directories(session_maker):
    """Проверить, что _load_files также учитывает пути."""
    
    async with session_maker() as session:
        owner = uuid.uuid4()
        project = Project(id=uuid.uuid4(), owner_id=owner, name='Test')
        session.add(project)
        await session.flush()
        
        # Создаем директорию и файл в ней
        dir1 = Directory(
            project_id=project.id,
            parent_directory_id=None,
            name='sub'
        )
        session.add(dir1)
        await session.flush()
        
        file1 = File(
            project_id=project.id,
            directory_id=dir1.id,
            name='types.ontol',
            content="types:\nA: 'A', ''"
        )
        session.add(file1)
        
        # Файл в корне
        file2 = File(
            project_id=project.id,
            directory_id=None,
            name='main.ontol',
            content="import { A } from 'sub/types.ontol'\ntitle: 'Main'"
        )
        session.add(file2)
        
        await session.commit()
        pid = str(project.id)
    
    files = await _load_files(pid)
    
    # Проверяем, что оба файла с путями
    assert 'main.ontol' in files
    assert 'sub/types.ontol' in files, f"Missing sub/types.ontol in {list(files.keys())}"
    
    # Проверяем, что точка входа main.ontol найдется в files
    assert 'main.ontol' in files
    
    print("Test _load_files with directories passed!")
    print("Files collected:")
    for path in files:
        print(f"  - {path}")
