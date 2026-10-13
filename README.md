# Food4Thought

**Team:** Agents Anonymous

Food4Thought is a food-delivery application for the COSC 310 team term project. The current M1 slice lets customers list restaurants, filter by cuisine, and browse restaurant details and menus. The API supports creating/updating restaurants and adding/updating menu items. A basic management page exposes Create restaurant. Data is persisted in JSON.

The M0 foundation and M1 feature PRs are merged; final verification, the Decision Receipt, collaboration/submission checks, and demonstration readiness remain tracked in [the M1 checkpoint](docs/milestones/M1.md).

## Requirements

- Python 3.12 (the version used by CI).
- Git.

Python dependencies are pinned in `requirements.txt`; browser-test dependencies are in `requirements-dev.txt`. Both frontends are served by FastAPI without Node.js or a build step. No database, API keys, or external services are required.

## Setup

For a new machine or first clone, follow [First-Time Application Setup](docs/FIRST_TIME_SETUP.md). For later sessions, use [Quick Setup](docs/QUICK_SETUP.md).

From the repository root, create and activate a Python 3.12 virtual environment, then install dependencies:

```sh
python -m venv .venv
```

If `python` is not 3.12, use `py -3.12 -m venv .venv` on Windows or `python3.12 -m venv .venv` on macOS/Linux.

| Shell | Activate |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |
| macOS/Linux | `source .venv/bin/activate` |

```sh
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python`. The full guide includes cloning, prerequisites, troubleshooting, and setup verification.

## Running the application

With the virtual environment active, run from the repository root:

```sh
python -m uvicorn app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`; stop it with `Ctrl+C`.

| Page | URL |
| --- | --- |
| Customer: list, cuisine filter, details, menu | [Customer frontend](http://127.0.0.1:8000/app/) |
| Management: Create restaurant | [Management frontend](http://127.0.0.1:8000/app/create-restaurant.html) |
| Interactive API documentation | [Swagger UI](http://127.0.0.1:8000/docs) |
| Generated API schema | [OpenAPI JSON](http://127.0.0.1:8000/openapi.json) |

The root URL redirects to the customer page. Select a restaurant to view its details and menu; selection is retained in the URL. A menu-loading failure leaves successfully loaded details visible; selecting the restaurant again retries.

Follow **Create restaurant**, enter name, cuisine, and description, then submit. Success offers **View restaurant**. Validation/server errors preserve entered values. If creation times out or its response is lost, check **Browse restaurants** before submitting again: the server may have saved the record, and retrying can create duplicates. The form does not retry automatically. Authentication is outside this M1 slice.

## API endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Liveness check; HTTP 200 with `{"status":"ok"}` |
| `GET /restaurants` | List restaurants; optional `?cuisine=japanese` filter |
| `GET /restaurants/{restaurant_id}` | Retrieve restaurant details |
| `GET /restaurants/{restaurant_id}/menu` | Retrieve a restaurant's menu and items |
| `POST /restaurants` | Create a restaurant |
| `PATCH /restaurants/{restaurant_id}` | Update supplied restaurant fields |
| `POST /restaurants/{restaurant_id}/menu/items` | Add a menu item |
| `PATCH /restaurants/{restaurant_id}/menu/items/{item_id}` | Update supplied menu-item fields |

Use IDs returned by the API. The [adopted API/data contract](docs/M1_API_CONTRACT.md) maintains request/response models, cuisine matching, validation, decimal-string prices, partial updates, error precedence, and persistence decisions. `/docs` shows interactive forms and generated schemas.

## Data

Representative data lives in `data/restaurants.json`. Set `RESTAURANTS_DATA_PATH` before starting the server to use another JSON file; no environment variable is required for normal use. For manual POST/PATCH experiments, follow the [disposable data-copy procedure](docs/FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments) so the committed sample stays unchanged.

Menu items are stored inside their restaurant record. Writes persist before returning success and use atomic replacement with a process-wide mutation lock. This supports a single application process; multiple workers and external writers are not coordinated. Invalid/unavailable data produces generic HTTP 500 errors. Stored menu prices above `999.00` are invalid and must be corrected before data operations can succeed; the sample data satisfies the limit.

## Running tests

From the repository root with the virtual environment active:

```sh
python -m pytest
```

Tests use temporary data copies and check that committed `data/` files remain unchanged. Browser tests exercise both pages in Chromium against a local test server. Without Playwright/Chromium they skip locally; CI installs both and requires them to run.

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest
```

See [Testing](docs/TESTING.md) for required-browser mode, focused commands, isolation, and the actual CI steps. These are instructions, not a claim of a test run.

## Repository structure

```text
app/main.py             FastAPI entry point, routers, frontend serving
app/api/                Routes, error responses, OpenAPI handling
app/services/           Restaurant/menu rules and orchestration
app/repositories/       JSON loading, validation, and persistence
app/schemas/            Pydantic request, response, and persistence models
app/core/config.py      Configurable restaurant-data path
frontend/               Customer and Create restaurant pages and shared styles
data/restaurants.json   Representative restaurant/menu data
tests/                  Backend/API tests; tests/browser/ for both frontends
scrum/                  Signed team agreement and M1 sprint planning
docs/                   Setup, testing, API contract, milestones, provenance
.github/                CI, issue templates, and PR template
requirements.txt        Pinned application/backend-test dependencies
requirements-dev.txt    Pinned browser-test dependencies
```

## Contributing and documentation

- [Contributor workflow and AI/provenance policy](CONTRIBUTING.md)
- [Testing conventions](docs/TESTING.md)
- [M0 checkpoint](docs/milestones/M0.md) and [M1 checkpoint](docs/milestones/M1.md)
- [M1 API/data contract](docs/M1_API_CONTRACT.md)
- [Shared AI provenance record](docs/PROVENANCE.md)
- [M1 sprint plan](scrum/SPRINT-Planning-M1.md) and [signed team agreement](scrum/team-agreement.md)
- [Agent instructions](AGENTS.md)
