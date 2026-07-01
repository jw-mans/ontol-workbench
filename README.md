# Ontol DSL Parser

[![Build Status](https://github.com/vladimir-skvortsov/ontol/actions/workflows/check-tests.yaml/badge.svg)](https://github.com/vladimir-skvortsov/ontol/actions)
[![PyPi downloads](https://img.shields.io/pypi/dm/ontol.svg?label=Pypi%20downloads)](https://pypi.org/project/ontol)

**Authors:**
[Skvortsov Vladimir](https://github.com/vladimir-skvortsov),
[Aptukov Mikhail](https://github.com/LuckyAm20),
[Markov Mikhail](https://github.com/eagerbeaver04),
[Khamidullin Ilsaf](https://github.com/Ilsaffff),
[Afanasyev Andrew](https://github.com/afafos).

Ontol DSL Parser is a tool for parsing and visualizing ontology files written in the Ontol DSL. It generates JSON representations and PlantUML diagrams from `.ontol` files, and ships with a web personal workspace ("личный кабинет") for working with modular, multi-file ontologies in the browser.

[Explore Ontol DSL in the Online REPL](https://ontol-repl.streamlit.app)

## Features

- Parse `.ontol` files to extract ontology structures.
- Serialize ontology to JSON format.
- Generate PlantUML diagrams from ontology.
- Automatically render PlantUML diagrams to PNG images.
- Watch files for changes and re-parse them automatically.
- **Modular ontologies:** split an ontology across several `.ontol` files with `import ... from`, with circular-import detection and diamond-import deduplication.
- **Web personal workspace (личный кабинет):** Streamlit app with user accounts and per-user projects, a syntax-highlighted editor with autosave, and in-process build to JSON / PlantUML / PNG.
- **Optional AI:** LLM-based hierarchy generation (`--gen-hierarchy`) via Ollama / langchain — installed separately, see Requirements.
- Display version and help information.

## Requirements

- Python 3.9 or higher.

Dependencies are split so the heavy AI stack stays optional:

- `src/ontol-v1/requirements-core.txt` — parsing, visualization, CLI, web UI and tests.
- `src/ontol-v1/requirements-ai.txt` — optional LLM stack (`--gen-hierarchy`), on top of core.

The same split is exposed via the package itself: `pip install -e src/ontol-v1`
installs the core only; `pip install -e src/ontol-v1[ai]` adds the optional AI stack.

## Installation

Install from PyPi:

```bash
pip install ontol
```

Or, to run from a clone (v1 lives in `src/ontol-v1`):

```bash
pip install -e src/ontol-v1
# optional, only for --gen-hierarchy:
pip install -e src/ontol-v1[ai]
```

## Usage

### Parse a file

To parse an `.ontol` file and generate JSON and PlantUML files:

```bash
ontol path/to/yourfile.ontol
```

### Watch Mode

To watch a file for changes and automatically re-parse it:

```bash
ontol path/to/yourfile.ontol --watch
```

### Debug mode

To enable debug mode, which retranslates the output back to the .ontol file:

```bash
ontol path/to/yourfile.ontol --debug
```

### Display Version

To display the version of the program:

```bash
ontol --version
```

### Help

To display help information:

```bash
ontol --help
```

### Generate hierarchy with AI (optional)

To let an LLM suggest relationships between terms (requires `src/ontol-v1/requirements-ai.txt` and a running [Ollama](https://ollama.com) model):

```bash
ontol path/to/yourfile.ontol --gen-hierarchy --model llama3 --temperature 0.0
```

### Tests

To display run tests:

```bash
pytest tests
```

## Modular ontologies (imports)

An ontology can be split across several `.ontol` files that import each other:

```ontol
import { set, element as elem } from 'base.ontol'   (* selective, with aliases *)
import * from 'base.ontol'                           (* everything *)
```

- Paths are resolved relative to the importing file's directory; URLs are supported.
- **Circular imports** (`a -> b -> a`) raise a clear error instead of crashing.
- **Diamond imports** (the same definition reached via two paths) are deduplicated; only genuinely different definitions sharing a name are reported as a conflict.

See [src/ontol-v1/examples/multifile_demo/](src/ontol-v1/examples/multifile_demo/) for a minimal cross-file example.

## Web personal workspace (личный кабинет)

Two web apps live side by side on top of the shared `ontol` core:

- **V1 — [v1-streamlit/](v1-streamlit/)** — the current Streamlit workspace (prototype).
- **V2 — [v2-service/](v2-service/)** — the full multi-user service (FastAPI + React), in progress; see [docs/V2_PLAN.md](docs/V2_PLAN.md).

Run V1 (the core is installed editable from the repo root):

```bash
pip install -e .
pip install -r v1-streamlit/requirements.txt
streamlit run v1-streamlit/app.py
```

- User accounts (registration / login); projects are private per user.
- Tabbed, syntax-highlighted editor with **autosave**; add / delete files; pick a build entry point.
- **Build** renders the chosen entry file in-process to JSON + PlantUML + PNG, with a downloadable zip.

Configuration via environment variables:

- `ONTOL_PROJECTS_DIR` — where projects are stored (default: `v1-streamlit/projects`).
- `ONTOL_USERS_FILE` — path to the user database (default: `<projects_dir>/users.json`).

## Documentation

- [docs/GRAMMAR.md](docs/GRAMMAR.md) — the Ontol DSL grammar (EBNF).
- [docs/SETUP.md](docs/SETUP.md) — build / run instructions.
- [docs/REPORT.md](docs/REPORT.md) — design notes for the V1 personal workspace.
- [docs/V2_PLAN.md](docs/V2_PLAN.md) — implementation plan for the V2 multi-user service.

## Output

- **JSON File**: A JSON representation of the ontology is saved with the same basename as the `.ontol` file.
- **PlantUML File**: A `.puml` file is generated for visualization.
- **PNG Image**: A PNG image is rendered from the PlantUML file.

## Debug mode

When the `--debug` flag is used, the parser retranslates the output back to the .ontol file. This is particularly useful for debugging, as it allows you to verify the accuracy and consistency of the parsing process. The retranslated file is saved with the same name as the original .ontol file, enabling easy comparison between the original and retranslated versions.

## Contributing

Contributions are welcome! If you'd like to contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Commit your changes.
4. Ensure all tests pass by running `pytest tests`.
5. Submit a pull request.

## License

This project is licensed under the Apache-2.0 License. See the LICENSE file for details.

## Acknowledgments

* Thanks to the [PlantUML team](https://github.com/plantuml) for providing an excellent tool for diagram generation.
* Special thanks to all contributors and users of the Ontol DSL Parser.
* A heartfelt thank you to [Danil Pestryakov](https://github.com/DanilPestryakov) and [Nikita Motorny](https://github.com/motorny) for their inspiration and support.
