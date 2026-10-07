# Food4Thought

**Team:** Agents Anonymous

Food4Thought is a food-delivery application built for the COSC 310 team term project: a FastAPI REST backend with JSON persistence, tested with pytest. The backend includes the Milestone 0 foundation and the M1 create-restaurant, menu-browsing, and add-menu-item operations. The rest of the M1 slice is still in progress.

- [First-time application setup](docs/FIRST_TIME_SETUP.md)
- [Quick setup for returning contributors](docs/QUICK_SETUP.md)
- [M0 checkpoint and submission requirements](docs/milestones/M0.md)
- [M1 checkpoint and source requirements](docs/milestones/M1.md)
- [M1 restaurant/menu API and data contract](docs/M1_API_CONTRACT.md) (adopted through PR #48)
- [Contributing and AI/provenance policy](CONTRIBUTING.md)
- [Shared AI provenance record](docs/PROVENANCE.md)
- [Testing conventions](docs/TESTING.md)
- [Team agreement](scrum/team-agreement.md)
- [Agent instructions](AGENTS.md)

## Requirements

- Python 3.12 (verified with 3.12.3 and 3.12.13). If it is not installed, get it from [python.org](https://www.python.org/downloads/) or, on Windows, run `winget install --id Python.Python.3.12 -e`, then open a new terminal.
- Git

All Python dependencies are pinned in `requirements.txt`.

## Setup

Use the dedicated setup guides so installation instructions have one source of truth:

- **New machine / first clone:** [First-Time Application Setup](docs/FIRST_TIME_SETUP.md)
- **Already configured:** [Quick Setup](docs/QUICK_SETUP.md)

Both guides describe only the application's current implementation.

## Running the application

```sh
python -m uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`. Stop it with `Ctrl+C`.

## API endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /restaurants` | Restaurant list; HTTP 200 with a JSON array of `id`, `name`, `cuisine`, and `description`. |
| `POST /restaurants` | Create a restaurant; HTTP 201 with its server-generated ID and the same four-field response shape. |
| `GET /restaurants/{restaurant_id}/menu` | A restaurant's menu, e.g. `/restaurants/restaurant-001/menu`; HTTP 200 with `restaurant_id` and `items` (each item has `id`, `name`, `description`, and a two-decimal `price` string). A restaurant with no items returns `"items": []`; an unknown restaurant returns HTTP 404 with `{"detail": "Restaurant not found"}`. |
| `POST /restaurants/{restaurant_id}/menu/items` | Add a menu item to an existing restaurant; HTTP 201 with `id`, `name`, `description`, and a two-decimal `price` string. Unknown restaurants return HTTP 404. |
| `GET /health` | Liveness check; returns `{"status": "ok"}` with HTTP 200. |
| `GET /docs` | Interactive OpenAPI (Swagger) documentation. |
| `GET /openapi.json` | Raw OpenAPI schema. |

Restaurant-create requests require nonempty `name`, `cuisine`, and `description` strings. Surrounding whitespace is removed; unknown fields and invalid values return HTTP 422. A new restaurant starts with an empty menu. An empty restaurant data array returns `[]`. Missing, malformed, or invalid data and failed saves return HTTP 500 with `{"detail": "Restaurant data is unavailable"}`, without exposing file paths or validation details.

Menu-item creation requires `name`, `description`, and `price`, for example `{"name":"Soup","description":"Hot soup","price":"4.50"}`. Text is trimmed and must remain nonempty. Price must be a nonnegative decimal string with at most two fractional digits; `"4.5"` is saved as `"4.50"`. JSON numbers, unsupported fields (including client-supplied IDs), and invalid values return HTTP 422 before storage is read. A valid request against unavailable storage returns HTTP 500; otherwise an unknown parent returns HTTP 404 with `{"detail":"Restaurant not found"}`. Repeated POSTs create separate items; retries are not idempotent.

Validation errors keep the `detail` array of error locations, types, messages, and rejected inputs. The shared error handler encodes non-finite numeric inputs as diagnostic strings and escapes Unicode so malformed input cannot break the HTTP 422 response itself. This also applies to restaurant creation.

Restaurant requests follow route → `RestaurantService` → `RestaurantRepository` → configured JSON file. The repository owns file access, and the route translates data failures into HTTP errors. `POST /restaurants` persists before returning success; a new repository instance can reload the created record. Menu requests follow `GET /restaurants/{restaurant_id}/menu` → route → `RestaurantService.get_menu()` → `RestaurantRepository.get_record()` → configured JSON file; the service raises `RestaurantNotFoundError` for an unknown restaurant, which the route maps to HTTP 404. The restaurant list keeps its four-field shape and never includes menu items.

`RestaurantService.add_menu_item()` checks the parent, generates a UUID4 ID unique within that restaurant, and appends the item inside `RestaurantRepository.mutate_records()`. The shared lock covers this entire change. The service returns the validated saved item only after persistence succeeds; existing items and other restaurants are preserved. The new item is then available through the menu GET operation.

## Data

Representative restaurant data is stored in `data/restaurants.json`. `RestaurantRepository` (`app/repositories/restaurant.py`) reads it by default. To use a different file, set the `RESTAURANTS_DATA_PATH` environment variable to that file's path before starting the application, or pass a path to `RestaurantRepository`. The file remains one JSON array. Each representative restaurant stores its menu items in a `menu_items` array inside its record, so items belong to the restaurant that contains them. Existing records without `menu_items` load with an empty menu; creation writes complete records and preserves existing menu items. Missing, malformed, or invalid data raises `RestaurantDataError`. Writes use a temporary file and atomic replacement, with one lock shared by repository instances in the application process. This does not coordinate multiple worker processes or external writers. Tests always use a temporary copy and never modify the committed file.

## Running tests

```sh
python -m pytest
```

`tests/conftest.py` gives each test a temporary copy of the restaurant data and fails the run if any committed file under `data/` changes. GitHub Actions runs the same command on pushes and pull requests to `main`.

## Repository structure

```text
app/
  main.py               FastAPI application; registers routers
  api/routes/           HTTP routes (health.py, restaurants.py)
  api/openapi.py        OpenAPI post-processing (removes 422 only from contract-listed operations)
  services/             Restaurant discovery service (restaurant.py)
  repositories/         Data access for JSON files (restaurant.py)
  schemas/              Pydantic models (restaurant.py)
  core/config.py        Configurable data-file location
data/restaurants.json   Representative restaurant data
tests/                  pytest suite and shared fixtures
scrum/                  Team agreement
docs/                   Milestones, testing, and provenance records
.github/                CI workflow, issue and PR templates
requirements.txt        Pinned dependencies
```

The repository contains no passwords, tokens, or API keys, and none are needed to run it.
