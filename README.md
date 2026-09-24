# COSC-310-Lab-Food-4-Thought

Food4Thought is a COSC 310 food-delivery project. The restaurant response model, representative data, and data-path configuration are available. `app/main.py` is still empty; there is no runnable application or endpoint yet.

- [M0 checkpoint and submission requirements](docs/milestones/M0.md)
- [Contributing and AI/provenance policy](CONTRIBUTING.md)
- [Shared AI provenance record](docs/PROVENANCE.md)
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
- `app/schemas/restaurant.py`: provisional typed restaurant response model.
- `app/core/config.py`: selects the restaurant JSON path.
- `app/api/routes/`, `app/services/`, `app/repositories/`: package skeletons for the remaining layers.
- `data/restaurants.json`: committed representative restaurant records with stable IDs.
- `tests/test_restaurant_foundation.py`: model, sample-data, and configuration tests.
- `.github/workflows/ci.yml`: installs dependencies on Python 3.12 and compiles `app/` for pushes and pull requests to `main`.

By default, restaurant data is read from `data/restaurants.json`. Set `RESTAURANTS_DATA_PATH` to another JSON file path to use isolated data; tests use temporary locations rather than modifying the committed sample file.

Run the current tests from the repository root with `python -m pytest`. CI currently checks Python syntax only; adding pytest to CI is tracked in issue #6.

Application startup, endpoint paths, and the remaining M0 test coverage are tracked in subsequent issues. This foundation is not yet sufficient for an M0 demonstration.
