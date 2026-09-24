# Food4Thought

**Team:** Agents Anonymous

Food4Thought is a food-delivery application built for the COSC 310 team term project: a FastAPI REST backend with JSON persistence, tested with pytest. This version is the Milestone 0 foundation.

- [M0 checkpoint and submission requirements](docs/milestones/M0.md)
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

Run every command from the repository root.

1. Clone the repository and enter it:

   ```sh
   git clone https://github.com/gwan-kib/COSC-310-Lab-Food4Thought.git
   cd COSC-310-Lab-Food4Thought
   ```

2. Create a virtual environment with Python 3.12:

   ```sh
   python -m venv .venv
   ```

   If `python` is not 3.12 on your machine, use `py -3.12 -m venv .venv` on Windows or `python3.12 -m venv .venv` on macOS/Linux.

3. Activate it:

   | Shell | Command |
   | --- | --- |
   | macOS/Linux | `source .venv/bin/activate` |
   | Windows PowerShell | `.venv\Scripts\Activate.ps1` |
   | Windows Command Prompt | `.venv\Scripts\activate.bat` |

   If PowerShell blocks activation, run the commands below with `.\.venv\Scripts\python.exe` in place of `python`.

4. Install dependencies:

   ```sh
   python -m pip install -r requirements.txt
   ```

## Running the application

```sh
python -m uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`. Stop it with `Ctrl+C`.

## API endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /restaurants` | Restaurant list; HTTP 200 with a JSON array of `id`, `name`, `cuisine`, and `description`. |
| `GET /health` | Liveness check; returns `{"status": "ok"}` with HTTP 200. |
| `GET /docs` | Interactive OpenAPI (Swagger) documentation. |
| `GET /openapi.json` | Raw OpenAPI schema. |

An empty restaurant data array returns `[]`. Missing, malformed, or invalid data returns HTTP 500 with `{"detail": "Restaurant data is unavailable"}`, without exposing file paths or validation details.

Restaurant requests follow `GET /restaurants` → route → `RestaurantService.list_restaurants()` → `RestaurantRepository.list_restaurants()` → configured JSON file. Only the repository reads persistence; the route translates data failures into HTTP errors.

## Data

Representative restaurant data is stored in `data/restaurants.json`. `RestaurantRepository` (`app/repositories/restaurant.py`) reads it by default. To use a different file, set the `RESTAURANTS_DATA_PATH` environment variable to that file's path before starting the application, or pass a path to `RestaurantRepository`. Missing, malformed, or invalid data raises `RestaurantDataError`. Tests always use a temporary copy and never modify the committed file.

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
