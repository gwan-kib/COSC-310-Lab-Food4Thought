# Quick Setup

Use this guide after the [first-time setup](FIRST_TIME_SETUP.md) has already been completed on your machine.

This is intentionally short and only covers what the current repository needs to get back into development.

## 1. Open the repository

```sh
cd path/to/COSC-310-Lab-Food4Thought
```

## 2. Activate the existing virtual environment

| Shell | Command |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |
| macOS/Linux | `source .venv/bin/activate` |

If `.venv` does not exist or no longer works, return to [First-Time Application Setup](FIRST_TIME_SETUP.md).

## 3. Sync the code when starting new work

Before creating a new task branch:

```sh
git checkout main
git pull
```

Then follow the branch and pull-request workflow in [CONTRIBUTING.md](../CONTRIBUTING.md).

If you are continuing work on an existing feature branch, stay on that branch and sync it according to the team workflow rather than switching away from unfinished work.

## 4. Refresh dependencies after repository updates

If `requirements.txt` changed since your last session, run:

```sh
python -m pip install -r requirements.txt
```

Running this command again is also safe when you are unsure whether dependencies changed.

## 5. Run the tests

```sh
python -m pytest
```

## 6. Start the application

```sh
python -m uvicorn app.main:app --reload
```

Current local URL:

```text
http://127.0.0.1:8000
```

Useful implemented checks:

- `GET /health`
- `GET /restaurants`
- `POST /restaurants` (creates a persistent record; use `/docs` with an isolated data copy for experiments)
- `GET /docs`
- `GET /openapi.json`

Stop the server with `Ctrl+C`.

## Short version

For a normal returning session, the sequence is:

```text
open repo
→ activate .venv
→ sync the branch you need
→ install requirements if they changed
→ run tests
→ start Uvicorn
```

No database, frontend build step, API keys, or secrets are currently required.
