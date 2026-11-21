# First-Time Application Setup

Use this guide when setting up Food4Thought on a machine for the first time.

This document describes the application as it exists now. The repository currently contains a FastAPI backend serving customer discovery, account, create-restaurant, and edit-restaurant pages, JSON restaurant data, and a pytest test suite. It does not require a database, frontend build step, API keys, or other secrets.

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

The current dependency file installs FastAPI, Uvicorn, Pydantic, pwdlib with Argon2 (password hashing; currently used by the authentication test fixtures), pytest, and httpx2.

## 6. Verify the test suite

```sh
python -m pytest
```

The tests use a temporary restaurant-data copy and disposable M2 store paths. Customers, carts, staff and sessions are initialized per test; orders are initialized only when a test requests `m2_store_paths`. See [test isolation](TESTING.md#one-default-for-file-isolation).

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
| `GET /app/account.html` | Customer frontend: register, sign in, inspect/update the own profile/address, and deactivate using the existing account API. |
| `GET /app/create-restaurant.html` | Management frontend: create a restaurant through the API, with validation/error feedback and a link to the saved restaurant. |
| `GET /app/edit-restaurant.html?id=restaurant-001` | Management frontend: edit an existing restaurant's name, cuisine, or description through GET and PATCH. |
| `GET /openapi.json` | Raw generated OpenAPI schema. |
| `GET /customers/me/orders/{order_id}` | Bearer-authenticated owner reads the saved transaction, including original prices and address. Active and inactive owners are allowed. |

Browse restaurant and menu GETs directly. For writes, use disposable stores and sign in through `POST /auth/login` with a provisioned staff account (create one with the [staff-account commands](#disposable-data-for-manual-experiments)). In Swagger UI (`/docs`), choose **Authorize** and enter the returned bearer token.

An administrator can call `POST /restaurants` with `{"name":"New Cafe","cuisine":"Cafe","description":"Fresh food"}`. The 201 response contains its stable ID. Creating a restaurant does not assign a manager. For edits, sign in as a restaurant user assigned to the selected restaurant and switch tokens in Swagger. Anonymous writes return 401. A caller with the wrong role or an unassigned manager receives 403. A manager editing a missing restaurant with a valid body receives 404.

To try accounts in the browser, first point **all six stores** at disposable copies using the commands below. Open `/app/account.html` (also linked as **My account** from restaurant browsing). Register, sign in, update the name or delivery address, and use **Check saved profile** to verify the server's current saved values. Refreshing keeps locally edited fields but updates untouched inputs to the newly saved server values; a profile save sends only fields you changed. Sign-out and expiry clear personal details and the confirmation checkbox. An interrupted registration should be checked by attempting sign-in before registering again; a lost profile update or deactivation response should be checked using **Check saved profile** before attempting another write. Deactivation requires a confirmation checkbox and leaves the account read-only. Tokens are kept in tab-scoped `sessionStorage` and sent only as bearer headers; signing out removes the browser copy, not the server session. A 401 prompts sign-in again. Browser-only controls do not replace backend 401/403 checks.

The Create and Edit pages load in a browser. Their authenticated submission workflow depends on [staff sign-in #108](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/108). Use Swagger for manual write checks on this branch.

For `PATCH /restaurants/{restaurant_id}`, use an ID from `GET /restaurants` and a body such as `{"description":"Seasonal bowls and noodles"}` in `/docs`, also with a disposable data copy. Supply at least one of `name`, `cuisine`, or `description`; supplied values must be nonblank strings. Nulls and unsupported fields are rejected. Re-list restaurants to check the saved result. See the [API contract](M1_API_CONTRACT.md#responses-and-failure-precedence) for the full update/error behavior.

With the disposable stores configured, sign in through `POST /auth/login` as a provisioned restaurant user assigned to the selected restaurant. In Swagger UI use **Authorize** with the returned bearer token, then try the add-menu-item operation in `/docs` using an existing restaurant ID and `{"name":"Soup","description":"Hot soup","price":"4.50"}`. It returns HTTP 201 with a generated item ID. Fetch that restaurant's menu to see the appended item; restart the server with the same data path and fetch it again to verify persistence. Unknown restaurants return 404 and invalid item bodies return 422. Create/update prices must be decimal strings from `0` through `999.00` inclusive; `"999.00"` is accepted and `"999.01"` returns 422.

To update that item, use its returned ID and the same restaurant ID in `PATCH /restaurants/{restaurant_id}/menu/items/{item_id}` with `{"price":"7.5"}`. The response contains the complete saved item with price `"7.50"`; its ID, name, and description remain unchanged. Fetch the menu after restarting with the same disposable data path to verify the update persisted. Supply at least one of `name`, `description`, `price`, or `available`. Availability accepts JSON `true` or `false`. Both menu item write operations require the assigned manager’s bearer token. A missing token returns 401, and a customer, administrator or manager assigned to a different existing restaurant receives 403. Omitting it on creation defaults to true, and omitting it on update preserves the saved value. Legacy menu reads return true without writing. A successful restaurant-file save can make that default explicit throughout the file. Nulls and unsupported fields are rejected. See the [API contract](M1_API_CONTRACT.md#pydantic-model-responsibilities) for validation and parent-scoping behavior.

## Current data configuration

Representative restaurant data is stored at:

```text
data/restaurants.json
```

No environment variable is required for normal local use.

The repository supports `RESTAURANTS_DATA_PATH` for another existing UTF-8 JSON file. Its parent directory must be writable for atomic replacement. The value is read per request; set it before starting the server. Tests configure their own temporary copies.

Active carts are stored in `data/carts.json` (committed as an empty array `[]`); `CARTS_DATA_PATH` selects another file in the same way. Signed-in customers use it through `PUT`/`GET /customers/me/cart`, `POST /customers/me/cart/items`, and `DELETE /customers/me/cart/items/{item_id}`; copy it with the customer and session files for manual experiments.

With disposable stores configured and an active customer token authorized in `/docs`,
create the cart with PUT, add a menu item with POST, then DELETE its returned `item_id`
without a request body. The 200 response contains the resulting cart and current totals.
Removing the last line keeps the cart/customer IDs, increments revision once, and returns
`restaurant_id: null`, empty items and `"0.00"` totals. Add an item from another restaurant
to verify the released binding; restart with the same paths and GET the cart to verify
persistence. A repeated removal returns 404 `Cart item not found`. Inactive customers
receive 403; a purchased revision awaiting checkout reset receives 409. See the
[removal contract](M2_API_CONTRACT.md#implemented-item-removal-88) for error details.

If the variable is not set, the application uses `data/restaurants.json`. Stored menu-item prices must also be at most `999.00`. An over-limit stored price makes the file invalid, causing generic HTTP 500 data errors without changing the file; correct it before starting normal use. The committed sample data already satisfies this rule.

### Disposable data for manual experiments

The order repository resolves `ORDERS_DATA_PATH` when constructed. Its default
is the included `data/orders.json`, initially an empty JSON array. For manual
repository experiments, copy that file to a writable temporary directory and
set `ORDERS_DATA_PATH` to the copy. A configured missing or invalid file is a
storage error. The focused checkout tests select their own disposable files:
`python -m pytest -q tests/test_order_repository.py tests/test_checkout_service.py`.
Checkout is currently available at the service layer only.

Order details are available through HTTP. In `/docs`, sign in with `POST /auth/login`,
click **Authorize** and paste the returned token, then call
`GET /customers/me/orders/{order_id}` with an owned persisted ID. Unknown and foreign
IDs both return `404 Order not found`; staff receive 403 and absent/invalid tokens
receive 401. No fixture order or customer is seeded into committed data. Use
`python -m pytest -q tests/test_order_details.py` for the isolated, reproducible
registration/login/cart/checkout-service/detail example. It verifies saved prices
and address after live changes; it does not imply the checkout HTTP route exists.

Customer accounts, sign-in sessions and provisioned staff accounts use `data/customers.json`
(`CUSTOMERS_DATA_PATH`), `data/sessions.json` (`SESSIONS_DATA_PATH`) and `data/staff.json`
(`STAFF_DATA_PATH`), all committed as `[]`. Registering or signing in writes to them, so use the
[disposable copies](#disposable-data-for-manual-experiments) for manual experiments. To try it in `/docs`: `POST /customers`, then
`POST /auth/login`, click **Authorize**, paste the `access_token`, and call `GET /customers/me`.

**HTTP experiments (restaurants, accounts, carts, orders)**

Stop any existing server first. Registering, signing in, editing a cart and changing restaurants all write to `data/`, so point every store at a disposable copy. From the repository root, with the virtual environment active, these commands copy each store that exists into a new temporary directory and set its `*_DATA_PATH` variable (`RESTAURANTS_DATA_PATH`, `CUSTOMERS_DATA_PATH`, `SESSIONS_DATA_PATH`, `STAFF_DATA_PATH`, `CARTS_DATA_PATH`, `ORDERS_DATA_PATH`). They create a new copy each time; to verify persistence after restarting, keep the same terminal instead of repeating the copy step. The steps below then optionally create staff accounts, start the server, and finally clear the overrides; follow them in order.

Windows PowerShell:

```powershell
$manualDataDir = Join-Path ([System.IO.Path]::GetTempPath()) ('food4thought-manual-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $manualDataDir | Out-Null
foreach ($store in 'restaurants', 'customers', 'sessions', 'staff', 'carts', 'orders') {
    if (Test-Path "data/$store.json") {
        Copy-Item -LiteralPath "data/$store.json" -Destination (Join-Path $manualDataDir "$store.json")
        Set-Item -Path "Env:$($store.ToUpper())_DATA_PATH" -Value (Join-Path $manualDataDir "$store.json")
    }
}
Write-Output $manualDataDir
```

macOS/Linux:

```sh
manual_data_dir=$(mktemp -d)
for store in restaurants customers sessions staff carts orders; do
  if [ -f "data/$store.json" ]; then
    cp "data/$store.json" "$manual_data_dir/$store.json"
    export "$(printf '%s' "$store" | tr '[:lower:]' '[:upper:]')_DATA_PATH=$manual_data_dir/$store.json"
  fi
done
printf '%s\n' "$manual_data_dir"
```

**Optional: staff accounts.** There is no public sign-up for restaurant users or
administrators; create them with the provisioning command, in the **same terminal** while the
overrides above are set, so it writes to the copies and not to `data/staff.json`. It asks for
the password twice with a hidden prompt and stores only its hash. Run these before starting the
server; if the server is already running, stop it with `Ctrl+C` first (keep the terminal and its
overrides), run them, then start the server again. The same commands work in PowerShell.

Create a demo manager for `restaurant-001`:

```sh
python -m app.scripts.create_staff_account create --name "Cedar Bowl Manager" --email manager@cedarbowl.invalid --role restaurant_user --restaurant restaurant-001
```

Create an administrator (administrators manage no restaurants):

```sh
python -m app.scripts.create_staff_account create --name "Platform Admin" --email admin@food4thought.invalid --role administrator
```

Give an existing manager another restaurant:

```sh
python -m app.scripts.create_staff_account assign --email manager@cedarbowl.invalid --restaurant restaurant-002
```

Emails must be unused by any customer or staff account, and unknown restaurant IDs are rejected
without writing anything. The command and a running server share a lock file beside the customer
store (for example `.customers.json.lock` in the temporary directory), so they never accept the
same email at once.

**Start the server** in the same terminal:

```sh
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/app/create-restaurant.html` or `/docs` and use the POST/PATCH examples above, or register with `POST /customers`, sign in with `POST /auth/login` (customers, or the staff accounts created above; the response's `role` is `customer`, `restaurant_user` or `administrator`), and click **Authorize** with the returned token. Confirm saved values with GET, stop with `Ctrl+C`, then run the same Uvicorn command in the same terminal to verify persistence. All experiments in that server use the copies.

**Finish:** only after stopping the experiment server, clear the overrides before returning to normal sample-data use:

```powershell
foreach ($store in 'restaurants', 'customers', 'sessions', 'staff', 'carts', 'orders') {
    Remove-Item -Path "Env:$($store.ToUpper())_DATA_PATH" -ErrorAction SilentlyContinue
}
```

```sh
unset RESTAURANTS_DATA_PATH CUSTOMERS_DATA_PATH SESSIONS_DATA_PATH STAFF_DATA_PATH CARTS_DATA_PATH ORDERS_DATA_PATH
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
- `/app/`, `/app/account.html`, `/app/create-restaurant.html`, and an edit page for a known restaurant load.
- Browser tests run successfully when their optional dependencies are installed and required-browser mode is selected.

For normal future sessions, continue with [Quick Setup](QUICK_SETUP.md).
