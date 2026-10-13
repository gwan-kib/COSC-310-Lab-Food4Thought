# First-Time Application Setup

Use this guide when setting up Food4Thought on a machine for the first time.

This document describes the application as it exists now. The repository currently contains a FastAPI backend serving customer and create-restaurant pages, JSON restaurant data, and a pytest test suite. It does not require a database, frontend build step, API keys, or other secrets.

For later sessions on a machine that is already configured, use [Quick Setup](QUICK_SETUP.md).

## 1. Prerequisites

Install:

- Git.
- Python 3.12.

The repository and CI currently use Python 3.12. The project dependencies are pinned in `requirements.txt`.

Verify Python before continuing:

```sh
python --version
```

If `python` is not Python 3.12, use `py -3.12` on Windows or `python3.12` on macOS/Linux in the commands below.

## 2. Clone the repository

```sh
git clone https://github.com/gwan-kib/COSC-310-Lab-Food4Thought.git
cd COSC-310-Lab-Food4Thought
```

Run the remaining commands from the repository root.

## 3. Create a virtual environment

Windows with the Python launcher:

```powershell
py -3.12 -m venv .venv
```

Or, when `python` already points to Python 3.12:

```sh
python -m venv .venv
```

macOS/Linux can also use:

```sh
python3.12 -m venv .venv
```

The `.venv/` directory is ignored by Git and should not be committed.

## 4. Activate the virtual environment

| Shell | Command |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |
| macOS/Linux | `source .venv/bin/activate` |

After activation, the terminal prompt normally begins with `(.venv)`.

If PowerShell blocks activation, you can either allow it for the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

or run commands directly through the virtual environment's Python executable, for example:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 5. Install project dependencies

With the virtual environment active:

```sh
python -m pip install -r requirements.txt
```

The current dependency file installs FastAPI, Uvicorn, Pydantic, pytest, and httpx2.

## 6. Verify the test suite

```sh
python -m pytest
```

The tests use temporary restaurant-data copies and are designed not to modify committed files under `data/`.

The real-browser frontend tests in `tests/browser/` skip if Playwright or Chromium is unavailable locally. CI always runs them. To run them locally as well:

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest
```

Set `REQUIRE_BROWSER_TESTS=1` to fail instead of skip when the browser cannot run; see [Testing](TESTING.md#current-setup-and-commands) for shell-specific commands. On Linux, if Chromium reports missing system libraries, CI's `python -m playwright install --with-deps chromium` installs them where supported.

## 7. Run the application

```sh
python -m uvicorn app.main:app --reload
```

The development server starts at:

```text
http://127.0.0.1:8000
```

Stop it with `Ctrl+C`.

## 8. Verify the current application

With the server running, the currently implemented HTTP surfaces are:

| Method / path | Current purpose |
| --- | --- |
| `GET /health` | Liveness check. Returns `{"status": "ok"}`. |
| `GET /restaurants` | Returns the current restaurant list from JSON data. Add `?cuisine=japanese` to filter by cuisine (whole value, case-insensitive). |
| `POST /restaurants` | Creates and persists a restaurant from `name`, `cuisine`, and `description`; returns HTTP 201 with a generated ID. |
| `GET /restaurants/{restaurant_id}` | Returns one restaurant by ID, e.g. `/restaurants/restaurant-001`; unknown IDs return 404. |
| `PATCH /restaurants/{restaurant_id}` | Updates supplied restaurant fields and returns HTTP 200 after saving; preserves omitted fields, ID, and menu items. Unknown IDs return 404; invalid input returns 422. |
| `GET /restaurants/{restaurant_id}/menu` | Returns one restaurant's menu items, e.g. `/restaurants/restaurant-001/menu`; unknown restaurants return 404. |
| `POST /restaurants/{restaurant_id}/menu/items` | Adds a menu item from `name`, `description`, and a decimal-string `price`; returns HTTP 201 with its generated ID. |
| `PATCH /restaurants/{restaurant_id}/menu/items/{item_id}` | Updates supplied item fields and returns HTTP 200 with the saved item; unknown parent/item returns 404 and invalid input returns 422. |
| `GET /docs` | FastAPI's interactive OpenAPI documentation. |
| `GET /app/` | Customer frontend: restaurant list, cuisine filter, and the selected restaurant's details and menu. `GET /` redirects here. |
| `GET /app/create-restaurant.html` | Management frontend: create a restaurant through the API, with validation/error feedback and a link to the saved restaurant. |
| `GET /openapi.json` | Raw generated OpenAPI schema. |

A simple browser check is enough for the GET operations. To try `POST /restaurants`, use the interactive form at `/docs` with a body such as `{"name":"New Cafe","cuisine":"Cafe","description":"Fresh food"}`. It writes to the configured JSON file, so use a disposable copy through `RESTAURANTS_DATA_PATH` when experimenting.

With a disposable data copy configured, open `/app/` and follow **Create restaurant**. Fill all three fields and submit; confirm the success message, then follow **View restaurant** to see the saved details. Restart with the same data path and verify that the restaurant remains in the list. Whitespace-only values show backend validation feedback; errors keep the form values. Correct a rejected field to a nonblank value and confirm its error clears before submitting again. A stalled request times out after 15 seconds and restores the controls. If creation cannot be confirmed because the connection or response failed or timed out, check **Browse restaurants** before trying again to avoid duplicates.

For `PATCH /restaurants/{restaurant_id}`, use an ID from `GET /restaurants` and a body such as `{"description":"Seasonal bowls and noodles"}` in `/docs`, also with a disposable data copy. Supply at least one of `name`, `cuisine`, or `description`; supplied values must be nonblank strings. Nulls and unsupported fields are rejected. Re-list restaurants to check the saved result. See the [API contract](M1_API_CONTRACT.md#responses-and-failure-precedence) for the full update/error behavior.

With that disposable data copy configured, try the add-menu-item operation in `/docs` using an existing restaurant ID and `{"name":"Soup","description":"Hot soup","price":"4.50"}`. It returns HTTP 201 with a generated item ID. Fetch that restaurant's menu to see the appended item; restart the server with the same data path and fetch it again to verify persistence. Unknown restaurants return 404 and invalid item bodies return 422. Create/update prices must be decimal strings from `0` through `999.00` inclusive; `"999.00"` is accepted and `"999.01"` returns 422.

To update that item, use its returned ID and the same restaurant ID in `PATCH /restaurants/{restaurant_id}/menu/items/{item_id}` with `{"price":"7.5"}`. The response contains the complete saved item with price `"7.50"`; its ID, name, and description remain unchanged. Fetch the menu after restarting with the same disposable data path to verify the update persisted. Supply at least one of `name`, `description`, or `price`; nulls and unsupported fields are rejected. See the [API contract](M1_API_CONTRACT.md#pydantic-model-responsibilities) for validation and parent-scoping behavior.

## Current data configuration

Representative restaurant data is stored at:

```text
data/restaurants.json
```

No environment variable is required for normal local use.

The repository supports `RESTAURANTS_DATA_PATH` for another existing UTF-8 JSON file. Its parent directory must be writable for atomic replacement. The value is read per request; set it before starting the server. Tests configure their own temporary copies.

If the variable is not set, the application uses `data/restaurants.json`. Stored menu-item prices must also be at most `999.00`. An over-limit stored price makes the file invalid, causing generic HTTP 500 data errors without changing the file; correct it before starting normal use. The committed sample data already satisfies this rule.

### Disposable data for manual experiments

Stop any existing server first. From the repository root, with the virtual environment active, make a uniquely named temporary directory and copy the sample into it. These commands create a new copy each time; to verify persistence after restarting, reuse the printed path instead of repeating the copy step.

Windows PowerShell:

```powershell
$manualDataDir = Join-Path ([System.IO.Path]::GetTempPath()) ('food4thought-manual-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $manualDataDir | Out-Null
$manualDataPath = Join-Path $manualDataDir 'restaurants.json'
Copy-Item -LiteralPath 'data/restaurants.json' -Destination $manualDataPath
$env:RESTAURANTS_DATA_PATH = $manualDataPath
Write-Output $env:RESTAURANTS_DATA_PATH
python -m uvicorn app.main:app --reload
```

macOS/Linux:

```sh
manual_data_dir=$(mktemp -d)
cp data/restaurants.json "$manual_data_dir/restaurants.json"
export RESTAURANTS_DATA_PATH="$manual_data_dir/restaurants.json"
printf '%s\n' "$RESTAURANTS_DATA_PATH"
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/app/create-restaurant.html` or `/docs` and use the POST/PATCH examples above. Confirm saved values with GET, stop with `Ctrl+C`, then run the same Uvicorn command in the same terminal to verify persistence. All experiments in that server use the copy.

After stopping the experiment server, clear the override before returning to normal sample-data use:

```powershell
Remove-Item Env:RESTAURANTS_DATA_PATH
```

```sh
unset RESTAURANTS_DATA_PATH
```

The temporary directory remains available for inspection; these instructions do not delete data. New terminals need the same data-path setting to reuse an experiment.

## Setup complete

A first-time setup is complete when:

- Python 3.12 is being used.
- `.venv` exists and can be activated.
- `requirements.txt` installs successfully.
- `python -m pytest` completes successfully.
- `python -m uvicorn app.main:app --reload` starts the API.
- `/health`, `/restaurants`, `/docs`, and `/openapi.json` respond successfully.
- Both `/app/` and `/app/create-restaurant.html` load.
- Browser tests run successfully when their optional dependencies are installed and required-browser mode is selected.

For normal future sessions, continue with [Quick Setup](QUICK_SETUP.md).
