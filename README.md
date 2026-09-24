# COSC-310-Lab-Food-4-Thought

Food4Thought is a COSC 310 food-delivery project. The restaurant response model, representative data, configurable data path, and JSON repository are available. The FastAPI application starts and serves a health check and OpenAPI docs; the restaurant endpoint is not implemented yet.

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

## Running the application

From the repository root with the virtual environment active:

```sh
python -m uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000`:

- `GET /health` returns `{"status": "ok"}` with HTTP 200.
- `/docs` serves the interactive OpenAPI documentation.

## Structure and validation

- `app/main.py`: FastAPI application entry point; registers the API routers.
- `app/api/routes/health.py`: `GET /health` liveness endpoint.
- `app/schemas/restaurant.py`: provisional typed restaurant response model.
- `app/core/config.py`: selects the restaurant JSON path.
- `app/repositories/restaurant.py`: reads and validates restaurant JSON; raises `RestaurantDataError` for persistence failures.
- `app/services/`: package skeleton for the service layer.
- `data/restaurants.json`: committed representative restaurant records with stable IDs.
- `tests/test_restaurant_foundation.py` and `tests/test_restaurant_repository.py`: model, data-path, repository, and failure-case tests.
- `tests/test_health.py`: health endpoint and `/docs` tests.
- `.github/workflows/ci.yml`: installs dependencies on Python 3.12 and compiles `app/` for pushes and pull requests to `main`.

The repository reads `data/restaurants.json` by default. Set `RESTAURANTS_DATA_PATH` to another JSON file path, or pass a path to `RestaurantRepository`, to use isolated data; tests use temporary locations rather than modifying the committed sample file.

Run the current tests from the repository root with `python -m pytest`. CI currently checks Python syntax only; adding pytest to CI is tracked in issue #6.

The restaurant endpoint and the remaining M0 test coverage are tracked in subsequent issues. This foundation is not yet sufficient for an M0 demonstration.
