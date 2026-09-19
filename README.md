# COSC-310-Lab-Food-4-Thought

Food4Thought is a COSC 310 food-delivery project. This checkout contains the initial Python scaffold and development dependencies. `app/main.py` is intentionally empty; there is no runnable application, endpoint, representative data, or test suite yet.

- [M0 checkpoint and submission requirements](docs/milestones/M0.md)
- [Contributing and AI/provenance policy](CONTRIBUTING.md)
- [Testing conventions](docs/TESTING.md)
- [Agent instructions](AGENTS.md)

## Development setup

Use Python 3.12 (verified with 3.12.13). From the repository root, create an isolated environment:

```sh
python -m venv .venv
```

Ensure `python` selects Python 3.12; on Windows, `py -3.12 -m venv .venv` can select it explicitly. Activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on macOS/Linux, then run:

```sh
python -m pip install -r requirements.txt
python -m compileall app
```

If PowerShell activation is restricted, invoke `.venv\Scripts\python.exe` directly for the pip and compileall commands.

## Structure and validation

- `app/main.py`: empty application entrypoint reserved for the next implementation issue.
- `app/api/routes/`, `app/services/`, `app/repositories/`, `app/schemas/`, `app/core/`: package skeletons for the agreed layers.
- `data/`, `tests/`: empty directories retained with `.gitkeep`.
- `.github/workflows/ci.yml`: installs dependencies on Python 3.12 and compiles `app/` for pushes and pull requests to `main`.

Compilation checks Python syntax only; it does not verify application behaviour. Once real tests are committed, add a separate `python -m pytest` step to CI and run that command locally. pytest is intentionally not run by scaffold CI because no tests exist yet.

Application startup, endpoint paths, representative data, and M0 test coverage remain for subsequent issues. This scaffold is not yet sufficient for an M0 demonstration.
