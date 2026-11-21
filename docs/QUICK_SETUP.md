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

Before creating a new task branch, inspect the tree and preserve unrelated changes. Switch to `main` only when safe:

```sh
git status
git diff
git diff --cached
git checkout main
git pull --ff-only
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

Browser tests skip locally if Playwright or Chromium is unavailable; refresh `requirements-dev.txt` if it changed (see [first-time setup](FIRST_TIME_SETUP.md#6-verify-the-test-suite)); CI always runs them.

## 6. Start the application

```sh
python -m uvicorn app.main:app --reload
```

Current local URL:

```text
http://127.0.0.1:8000
```

| Check | URL |
| --- | --- |
| Customer frontend | `http://127.0.0.1:8000/app/` |
| Create restaurant frontend | `http://127.0.0.1:8000/app/create-restaurant.html` |
| Edit restaurant frontend | Select a restaurant at `http://127.0.0.1:8000/app/` and follow **Edit restaurant** |
| Health | `http://127.0.0.1:8000/health` |
| Restaurant list/filter | `http://127.0.0.1:8000/restaurants?cuisine=japanese` |
| Restaurant details/menu | `/restaurants/restaurant-001` and `/restaurants/restaurant-001/menu` |
| API documentation/schema | `http://127.0.0.1:8000/docs` and `/openapi.json` |

Before trying the form, registering, signing in, or any other POST/PATCH operation, stop the server and follow the [disposable data-copy commands](FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments). They point every store (`RESTAURANTS_DATA_PATH`, `CUSTOMERS_DATA_PATH`, `SESSIONS_DATA_PATH`, `STAFF_DATA_PATH`, and the cart and order paths) at new temporary copies before running the same startup command. Reuse that path on restart to verify persistence, and clear the override afterward. Full mutation examples and data validation are in [first-time setup](FIRST_TIME_SETUP.md#8-verify-the-current-application) and the [API contract](M1_API_CONTRACT.md).

Menu reads include `available`. For manual writes, sign in with a provisioned staff account through `POST /auth/login` and use **Authorize** in `/docs`. Restaurant creation requires an administrator. Editing a restaurant or writing its menu requires a restaurant user assigned to it. Staff sign-in on the forms is tracked in #108.

Stop the server with `Ctrl+C`.

To change a cart quantity on disposable data, authorize as the active cart owner in
`/docs` and send `PATCH /customers/me/cart/items/{item_id}` for an existing available
line. The body `{"quantity": 3}` sets its quantity to three.

For order repository experiments, set `ORDERS_DATA_PATH` to a disposable copy
of the empty `data/orders.json` before constructing the repository. Run
`python -m pytest -q tests/test_order_repository.py tests/test_checkout_service.py`
to exercise checkout with isolated storage. The checkout HTTP route is pending.

To sign in as a restaurant user or administrator, create the account after setting the disposable data paths and **before** clearing them, in the same terminal with the server stopped: `python -m app.scripts.create_staff_account create --name "Cedar Bowl Manager" --email manager@cedarbowl.invalid --role restaurant_user --restaurant restaurant-001`, then start the server again. The [disposable-data steps](FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments) show the full order, administrators and assigning restaurants.

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
