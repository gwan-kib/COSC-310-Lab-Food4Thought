# COSC-310-Lab-Food-4-Thought

Food4Thought is a COSC 310 food-delivery project. The FastAPI backend serves a health check, a restaurant list backed by representative JSON data, and interactive API documentation.

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
- `GET /restaurants` returns HTTP 200 with a JSON array of restaurants (`id`, `name`, `cuisine`, and `description`). An empty data array returns `[]`; unreadable or invalid data returns HTTP 500 with `{"detail": "Restaurant data is unavailable"}`.
- `/docs` serves the interactive OpenAPI documentation.

## Structure and validation

- `app/main.py`: FastAPI application entry point; registers the API routers.
- `app/api/routes/health.py`: `GET /health` liveness endpoint.
- `app/api/routes/restaurants.py`: `GET /restaurants` route and service dependency; declares the Pydantic restaurant response model.
- `app/schemas/restaurant.py`: provisional typed restaurant response model.
- `app/core/config.py`: selects the restaurant JSON path.
- `app/repositories/restaurant.py`: reads and validates restaurant JSON; raises `RestaurantDataError` for persistence failures.
- `app/services/restaurant.py`: restaurant discovery service; delegates storage access to the repository.
- `data/restaurants.json`: committed representative restaurant records with stable IDs.
- `tests/test_restaurant_foundation.py` and `tests/test_restaurant_repository.py`: model, data-path, repository, and failure-case tests.
- `tests/test_health.py`: health endpoint and `/docs` tests.
- `tests/test_restaurants.py` and `tests/test_restaurant_service.py`: restaurant response, service, OpenAPI contract, isolated configuration, and failure tests.
- `tests/conftest.py`: shared fixtures that isolate test data and guard committed `data/` files.
- `.github/workflows/ci.yml`: installs dependencies on Python 3.12, compiles `app/`, and runs pytest for pushes and pull requests to `main`.

The repository reads `data/restaurants.json` by default. Set `RESTAURANTS_DATA_PATH` to another JSON file path, or pass a path to `RestaurantRepository`, to use isolated data; tests use temporary locations rather than modifying the committed sample file.

Run the tests from the repository root with `python -m pytest`. Each test automatically uses a temporary copy of the restaurant data (see `tests/conftest.py`). CI runs the same command on pushes and pull requests to `main`.

Restaurant requests follow `GET /restaurants` → route → `RestaurantService.list_restaurants()` → `RestaurantRepository.list_restaurants()` → configured JSON file. Only the repository reads persistence; the route translates repository data failures into the generic HTTP error above. M0 team agreement, review, demonstration, and submission requirements remain tracked in the [M0 checkpoint](docs/milestones/M0.md).
