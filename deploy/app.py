"""Ontol V1 — личный кабинет (ЛК) с проектами и модульными онтологиями.

Streamlit-приложение поверх слоя проектов (`ontol.project`):

- проект = директория с несколькими `.ontol`-файлами;
- файлы в пределах проекта могут импортировать друг друга
  (`import { ... } from 'other.ontol'`);
- рендер выполняется in-process через `render_project` (JSON + PlantUML + PNG).

Запуск:
    streamlit run deploy/app.py

Каталог проектов берётся из переменной окружения ONTOL_PROJECTS_DIR
(по умолчанию — deploy/projects рядом с этим файлом).
"""

import os
import sys
import shutil
import tempfile
from zipfile import ZipFile

import streamlit as st

# Allow running straight from the repo (src layout) without installing the package.
# Позволяет запускать прямо из репозитория (src-layout) без установки пакета.
_SRC = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from ontol import ProjectStore, UserStore, render_project  # noqa: E402
from ontol.project import ONTOL_EXT  # noqa: E402
from ontol.auth import validate_username, validate_password  # noqa: E402

# streamlit-ace gives the editor syntax highlighting + line numbers. It is an
# optional component: fall back to a plain text area if it is not installed.
# streamlit-ace даёт редактору подсветку синтаксиса и номера строк. Это
# опциональный компонент: при его отсутствии откатываемся на обычное текстовое поле.
try:
    from streamlit_ace import st_ace  # noqa: E402

    _HAS_ACE = True
except ImportError:  # pragma: no cover - exercised only without the optional dep
    _HAS_ACE = False

DEFAULT_PROJECTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'projects'
)
PROJECTS_DIR = os.environ.get('ONTOL_PROJECTS_DIR', DEFAULT_PROJECTS_DIR)
USERS_FILE = os.environ.get(
    'ONTOL_USERS_FILE', os.path.join(PROJECTS_DIR, 'users.json')
)
DEMO_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'examples', 'multifile_demo'
)

st.set_page_config(page_title='Ontol — личный кабинет', layout='wide')

user_store = UserStore(USERS_FILE)


def new_file_template(title: str) -> str:
    return (
        "version: '1.0'\n"
        f"title: '{title}'\n"
        "author: ''\n"
        "description: ''\n\n"
        'types:\n'
    )


def editor_key(project_name: str, filename: str) -> str:
    return f'editor::{project_name}::{filename}'


def save_all(project, filenames: list[str]) -> None:
    for filename in filenames:
        key = editor_key(project.name, filename)
        if key in st.session_state:
            project.write_file(filename, st.session_state[key])


def render_editor(project, fname: str, ns: str) -> None:
    """Render a syntax-highlighted, auto-saving editor for one project file.

    ``st.session_state[editor_key]`` holds the last content written to disk and
    is the source of truth for "save all" / build. Edits are persisted as soon
    as the editor reports a change, so there is no need to press a save button.

    Рендерит редактор одного файла проекта с подсветкой и автосохранением.

    ``st.session_state[editor_key]`` хранит последнее записанное на диск
    содержимое и служит источником истины для «сохранить всё» / сборки. Правки
    сохраняются, как только редактор сообщает об изменении, поэтому отдельная
    кнопка сохранения не нужна.
    """
    key = editor_key(ns, fname)
    if key not in st.session_state:
        st.session_state[key] = project.read_file(fname)
    saved = st.session_state[key]

    if _HAS_ACE:
        # 'yaml' is the closest built-in Ace mode for the Ontol DSL (metadata
        # keys, quoted strings, hex colours and { ... } attribute maps).
        # 'yaml' — ближайший встроенный режим Ace для DSL Ontol (ключи метаданных,
        # строки в кавычках, hex-цвета и { ... }-карты атрибутов).
        current = st_ace(
            value=saved,
            language='yaml',
            theme='tomorrow_night',
            keybinding='vscode',
            font_size=14,
            tab_size=2,
            show_gutter=True,
            wrap=True,
            auto_update=True,  # stream edits back on change → enables autosave
            key=f'ace::{ns}::{fname}',
        )
    else:
        current = st.text_area(
            fname,
            value=saved,
            height=320,
            label_visibility='collapsed',
            key=f'ta::{ns}::{fname}',
        )

    if current is not None and current != saved:
        project.write_file(fname, current)
        st.session_state[key] = current


def zip_dir(directory: str) -> str:
    zip_path = os.path.join(directory, 'results.zip')
    with ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(directory):
            for file in files:
                if file == 'results.zip':
                    continue
                full = os.path.join(root, file)
                zf.write(full, os.path.relpath(full, directory))
    return zip_path


def render_auth() -> None:
    """Render the login / registration screen and stop until a user is in.

    Рисует экран входа / регистрации и останавливает выполнение, пока
    пользователь не авторизуется.
    """
    st.title('Ontol — вход')
    login_tab, register_tab = st.tabs(['Вход', 'Регистрация'])

    with login_tab:
        with st.form('login'):
            username = st.text_input('Имя пользователя', key='login_user')
            password = st.text_input('Пароль', type='password', key='login_pass')
            if st.form_submit_button('Войти', use_container_width=True):
                if user_store.authenticate(username.strip(), password):
                    st.session_state['user'] = username.strip()
                    st.rerun()
                else:
                    st.error('Неверное имя пользователя или пароль.')

    with register_tab:
        with st.form('register', clear_on_submit=False):
            username = st.text_input('Имя пользователя', key='reg_user')
            password = st.text_input('Пароль', type='password', key='reg_pass')
            confirm = st.text_input(
                'Повторите пароль', type='password', key='reg_pass2'
            )
            if st.form_submit_button('Зарегистрироваться', use_container_width=True):
                name = username.strip()
                try:
                    validate_username(name)
                    validate_password(password)
                    if password != confirm:
                        raise ValueError('Пароли не совпадают.')
                    user_store.register(name, password)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state['user'] = name
                    st.success('Аккаунт создан.')
                    st.rerun()


# --------------------------------------------------------------------------- #
# Auth gate — всё ниже доступно только авторизованному пользователю
# --------------------------------------------------------------------------- #
if 'user' not in st.session_state:
    render_auth()
    st.stop()

user: str = st.session_state['user']
# Projects are namespaced per user: <projects_dir>/<username>/<project>.
# Проекты разделены по пользователям: <projects_dir>/<username>/<project>.
store = ProjectStore(os.path.join(PROJECTS_DIR, user))


# --------------------------------------------------------------------------- #
# Sidebar — управление проектами
# --------------------------------------------------------------------------- #
st.sidebar.caption(f'👤 {user}')
if st.sidebar.button('Выйти', use_container_width=True):
    st.session_state.clear()
    st.rerun()
st.sidebar.divider()

st.sidebar.title('📁 Проекты')

projects = store.list_projects()

if not projects:
    st.sidebar.info('Пока нет ни одного проекта. Создайте новый ниже.')

selected = st.sidebar.selectbox(
    'Текущий проект',
    options=projects,
    index=0 if projects else None,
    placeholder='— нет проектов —',
)

with st.sidebar.form('create_project', clear_on_submit=True):
    st.caption('Новый проект')
    new_name = st.text_input('Имя проекта', key='new_project_name')
    if st.form_submit_button('Создать', use_container_width=True):
        name = new_name.strip()
        if not name:
            st.sidebar.warning('Введите имя проекта.')
        elif store.exists(name):
            st.sidebar.warning(f'Проект «{name}» уже существует.')
        else:
            store.create(name)
            st.session_state['_select_project'] = name
            st.rerun()

# Honour a freshly created/seeded project as the active selection.
# Делаем только что созданный/засеянный проект активным выбором.
if st.session_state.get('_select_project') in store.list_projects():
    selected = st.session_state.pop('_select_project')

if not os.path.isdir(DEMO_DIR):
    pass
elif st.sidebar.button('Загрузить демо (multifile_demo)', use_container_width=True):
    demo = store.get('multifile_demo') if store.exists('multifile_demo') else store.create('multifile_demo')
    for fname in os.listdir(DEMO_DIR):
        if fname.endswith(ONTOL_EXT):
            with open(os.path.join(DEMO_DIR, fname), encoding='utf-8') as f:
                demo.write_file(fname, f.read())
    st.session_state['_select_project'] = 'multifile_demo'
    st.rerun()

if selected:
    with st.sidebar.expander('Управление проектом'):
        rename_to = st.text_input('Переименовать в', key='rename_to')
        if st.button('Переименовать', use_container_width=True):
            target = rename_to.strip()
            if target and not store.exists(target):
                store.rename(selected, target)
                st.session_state['_select_project'] = target
                st.rerun()
            else:
                st.warning('Пустое или занятое имя.')

        st.divider()
        confirm = st.checkbox('Подтверждаю удаление проекта')
        if st.button('🗑 Удалить проект', use_container_width=True, disabled=not confirm):
            store.delete(selected)
            st.rerun()

# --------------------------------------------------------------------------- #
# Main — файлы проекта и сборка
# --------------------------------------------------------------------------- #
st.title('Ontol — личный кабинет')

if not selected:
    st.info(
        'Создайте проект в левой панели или загрузите демо, '
        'чтобы начать работу с модульными онтологиями.'
    )
    st.stop()

project = store.get(selected)
files = project.list_files()

st.subheader(f'Проект: {selected}')

# --- добавление файла ---
add_col, entry_col = st.columns([2, 2])
with add_col:
    with st.form('add_file', clear_on_submit=True):
        new_file = st.text_input('Новый файл (имя без пути)', key='new_file_name')
        if st.form_submit_button('Добавить файл'):
            base = os.path.basename(new_file.strip())
            if not base:
                st.warning('Введите имя файла.')
            else:
                fname = base if base.endswith(ONTOL_EXT) else base + ONTOL_EXT
                if fname in files:
                    st.warning(f'Файл «{fname}» уже есть.')
                else:
                    title = os.path.splitext(fname)[0]
                    project.write_file(fname, new_file_template(title))
                    st.rerun()

files = project.list_files()
if not files:
    st.warning('В проекте пока нет файлов. Добавьте первый файл выше.')
    st.stop()

with entry_col:
    default_entry = 'main.ontol' if 'main.ontol' in files else files[0]
    entry = st.selectbox(
        'Точка входа для сборки',
        options=files,
        index=files.index(default_entry),
    )

# --- редакторы по файлам (вкладки) ---
tabs = st.tabs(files)
for tab, fname in zip(tabs, files):
    with tab:
        render_editor(project, fname, selected)
        if st.button(f'🗑 Удалить {fname}', key=f'del::{fname}'):
            project.delete_file(fname)
            st.session_state.pop(editor_key(selected, fname), None)
            st.rerun()

# --- действия ---
st.caption(
    '💾 Изменения сохраняются автоматически.'
    if _HAS_ACE
    else '💾 Изменения сохраняются при выходе из поля. '
    '(Установите streamlit-ace для подсветки синтаксиса.)'
)
build = st.button('🛠 Собрать', use_container_width=True, type='primary')

# --- сборка ---
if build:
    save_all(project, files)
    out_dir = tempfile.mkdtemp(prefix='ontol_build_')
    try:
        result = render_project(project, entry, out_dir)
        if not result.ok:
            st.error(f'Ошибка сборки: {result.error}')
        else:
            left, right = st.columns([3, 2])
            with left:
                if result.png_path and os.path.isfile(result.png_path):
                    st.image(result.png_path, use_container_width=True)
                else:
                    st.warning(
                        'PNG не отрисован (нужен доступ к серверу PlantUML). '
                        'JSON и .puml сформированы.'
                    )
            with right:
                with open(result.json_path, encoding='utf-8') as f:
                    st.json(f.read())
                with open(result.puml_path, encoding='utf-8') as f:
                    with st.expander('PlantUML (.puml)'):
                        st.code(f.read(), language='text')

            zip_path = zip_dir(out_dir)
            with open(zip_path, 'rb') as f:
                st.download_button(
                    '📥 Скачать результаты (zip)',
                    f,
                    file_name=f'{selected}_{os.path.splitext(entry)[0]}.zip',
                    mime='application/zip',
                )

        if result.warnings:
            with st.expander(f'Предупреждения ({len(result.warnings)})'):
                for w in result.warnings:
                    st.text(w)
    finally:
        # Keep the dir until the download button is read within this run; Streamlit
        # serves the bytes eagerly above, so cleanup here is safe.
        # Держим каталог до чтения кнопки скачивания в этом проходе; Streamlit
        # отдаёт байты выше сразу, поэтому очистка здесь безопасна.
        shutil.rmtree(out_dir, ignore_errors=True)
