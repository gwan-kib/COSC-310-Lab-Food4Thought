# First-Time Application Setup

Use this guide when setting up Food4Thought on a machine for the first time.

This document describes the application as it exists now. The repository currently contains a FastAPI backend, JSON restaurant data, and a pytest test suite. It does not require a database, frontend build step, API keys, or other secrets.

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
| `GET /restaurants` | Returns the current restaurant list from JSON data. |
| `POST /restaurants` | Creates and persists a restaurant from `name`, `cuisine`, and `description`; returns HTTP 201 with a generated ID. |
| `GET /restaurants/{restaurant_id}/menu` | Returns one restaurant's menu items, e.g. `/restaurants/restaurant-001/menu`; unknown restaurants return 404. |
| `POST /restaurants/{restaurant_id}/menu/items` | Adds a menu item from `name`, `description`, and a decimal-string `price`; returns HTTP 201 with its generated ID. |
| `GET /docs` | FastAPI's interactive OpenAPI documentation. |
| `GET /openapi.json` | Raw generated OpenAPI schema. |

A simple browser check is enough for the GET operations. To try `POST /restaurants`, use the interactive form at `/docs` with a body such as `{"name":"New Cafe","cuisine":"Cafe","description":"Fresh food"}`. It writes to the configured JSON file, so use a disposable copy through `RESTAURANTS_DATA_PATH` when experimenting.

With that disposable data copy configured, try the add-menu-item operation in `/docs` using an existing restaurant ID and `{"name":"Soup","description":"Hot soup","price":"4.50"}`. It returns HTTP 201 with a generated item ID. Fetch that restaurant's menu to see the appended item; restart the server with the same data path and fetch it again to verify persistence. Unknown restaurants return 404 and invalid item bodies return 422.

## Current data configuration

Representative restaurant data is stored at:

```text
data/restaurants.json
```

No environment variable is required for normal local use.

The implemented repository layer also supports overriding that file with `RESTAURANTS_DATA_PATH`. This is used by the test suite for isolated temporary data and can also be set manually when needed:

Windows PowerShell:

```powershell
$env:RESTAURANTS_DATA_PATH = "C:\path\to\restaurants.json"
```

macOS/Linux:

```sh
export RESTAURANTS_DATA_PATH=/path/to/restaurants.json
```

If the variable is not set, the application uses `data/restaurants.json`.

## Setup complete

A first-time setup is complete when:

- Python 3.12 is being used.
- `.venv` exists and can be activated.
- `requirements.txt` installs successfully.
- `python -m pytest` completes successfully.
- `python -m uvicorn app.main:app --reload` starts the API.
- `/health` responds successfully.

For normal future sessions, continue with [Quick Setup](QUICK_SETUP.md).
