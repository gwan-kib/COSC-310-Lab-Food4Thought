# Food4Thought

**Team:** Agents Anonymous

Food4Thought is a food-delivery application for the COSC 310 team term project. The current M1 slice lets customers list restaurants, filter by cuisine, and browse restaurant details and menus. The API supports creating/updating restaurants and adding/updating menu items. Management pages support creating a restaurant and editing an existing restaurant's information. Data is persisted in JSON.

The M0 foundation and M1 feature PRs are merged; final verification, the Decision Receipt, collaboration/submission checks, and demonstration readiness remain tracked in [the M1 checkpoint](docs/milestones/M1.md).

## Requirements

- Python 3.12 (the version used by CI).
- Git.

Python dependencies are pinned in `requirements.txt`; browser-test dependencies are in `requirements-dev.txt`. The frontend pages are served by FastAPI without Node.js or a build step. No database, API keys, or external services are required.

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
| Customer: register, sign in, edit profile/address, deactivate | [Customer account](http://127.0.0.1:8000/app/account.html) |
| Management: Staff sign-in | [Staff sign-in](http://127.0.0.1:8000/app/staff-sign-in.html) |
| Management: Create restaurant | [Create restaurant](http://127.0.0.1:8000/app/create-restaurant.html) |
| Management: Edit restaurant | Select a restaurant in the [customer frontend](http://127.0.0.1:8000/app/) and follow **Edit restaurant** |
| Interactive API documentation | [Swagger UI](http://127.0.0.1:8000/docs) |
| Generated API schema | [OpenAPI JSON](http://127.0.0.1:8000/openapi.json) |

The root URL redirects to the customer page. Select a restaurant to view its details and menu; selection is retained in the URL. A menu-loading failure leaves successfully loaded details visible; selecting the restaurant again retries.

Follow **Create restaurant**, enter name, cuisine, and description, then submit. Success offers **View restaurant**. Validation/server errors preserve entered values. If creation times out or its response is lost, check **Browse restaurants** before submitting again: the server may have saved the record, and retrying can create duplicates. The form does not retry automatically. To edit an existing restaurant, select it on the customer page and follow **Edit restaurant**. The form loads the current name, cuisine, and description, sends only changed fields with `PATCH /restaurants/{restaurant_id}`, and links back to the updated details. Validation errors preserve input. If the response is lost, check the details page before retrying. Authentication remains outside the historical M1 slice; the M2 customer-account page below provides it.

Management forms now use a staff sign-in page. First provision a staff account using the documented command and disposable data paths. Open **Staff sign-in**, enter the account credentials, then continue to Create or Edit restaurant. The returned bearer token stays in this browser tab (sessionStorage), not in a URL; it is sent on restaurant and menu-management writes. Administrators can create restaurants, while assigned restaurant users can edit their restaurants and toggle menu-item availability. The backend checks every request: a missing/expired token gives a sign-in-again message, and an unauthorized role or unassigned restaurant gives a not-permitted message. Signing in again replaces the tab's stored staff token. The token remains valid on the server until its 24-hour expiry even when browser storage is cleared. This does not change customer-account sign-in or public restaurant browsing.

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
| `POST /customers` | Register a customer (name, email, delivery address, password) |
| `POST /auth/login` | Sign in; returns a bearer token valid for 24 hours |
| `GET /customers/me` | Read the signed-in customer's profile (`Authorization: Bearer <token>`) |
| `PATCH /customers/me` | Update the signed-in customer's name and/or delivery address |
| `POST /customers/me/deactivate` | Deactivate the signed-in account (it can still sign in and read, but not change the cart) |
| `PUT /customers/me/cart` | Create the cart (201) or return the existing one (200) |
| `GET /customers/me/cart` | Cart items with backend-calculated subtotal and total |
| `POST /customers/me/cart/items` | Add `restaurant_id`, `item_id`, `quantity`; one restaurant per cart |

For browser-based account management, open [Customer account](http://127.0.0.1:8000/app/account.html) or follow **My account** from restaurant browsing. Register with a name, email, delivery address and password, then sign in. You can view/update your own name and address, check the saved profile to verify an uncertain update, and deactivate after explicitly confirming the permanent inactive state. A profile refresh preserves fields you are editing and updates untouched fields from the server; saving sends only edited fields. Signing out or session expiration clears displayed personal information and the deactivation confirmation. Passwords are never stored in the browser's account profile; the bearer token is kept in tab-scoped `sessionStorage`. **Sign out of this tab** removes that local copy but does not revoke the server session, which expires after 24 hours. On an expired token, sign in again. Inactive customers can read their profiles but cannot edit or order. For manual browser experiments, use disposable copies of **all** six JSON stores (see [First-Time Setup](docs/FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments)).

In `/docs`, sign in with `POST /auth/login`, then click **Authorize** and paste the `access_token` to call the `/customers/me` endpoints. The [authentication design](docs/AUTH_DESIGN.md) explains tokens, roles and errors. Restaurant users and administrators are created with `python -m app.scripts.create_staff_account` (see the [disposable-data steps](docs/FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments)).

Use IDs returned by the API. The [adopted API/data contract](docs/M1_API_CONTRACT.md) maintains request/response models, cuisine matching, validation, decimal-string prices, partial updates, error precedence, and persistence decisions. `/docs` shows interactive forms and generated schemas.

## Data

Representative data lives in `data/restaurants.json`. Customer accounts and sign-in sessions are stored in `data/customers.json` and `data/sessions.json` (committed empty; `CUSTOMERS_DATA_PATH` and `SESSIONS_DATA_PATH` select other files). Passwords are stored only as Argon2id hashes and tokens only as SHA-256 digests. Set `RESTAURANTS_DATA_PATH` before starting the server to use another JSON file; no environment variable is required for normal use. For manual POST/PATCH experiments, follow the [disposable data-copy procedure](docs/FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments) so the committed sample stays unchanged.

Menu items are stored inside their restaurant record. Writes persist before returning success and use atomic replacement with a process-wide mutation lock. This supports a single application process; multiple workers and external writers are not coordinated. Invalid/unavailable data produces generic HTTP 500 errors. Stored menu prices above `999.00` are invalid and must be corrected before data operations can succeed; the sample data satisfies the limit.

## Running tests

From the repository root with the virtual environment active:

```sh
python -m pytest
```

Tests use temporary data copies and check that committed `data/` files remain unchanged. Browser tests exercise the frontend pages (including account API workflows) in Chromium against a local test server. Without Playwright/Chromium they skip locally; CI installs both and requires them to run.

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
app/services/           Restaurant/menu rules and checkout orchestration
app/repositories/       JSON loading, validation, and persistence
app/schemas/            Pydantic request, response, and persistence models
app/core/config.py      Configurable restaurant and order data paths
frontend/               Customer discovery, account, staff sign-in, Create/Edit restaurant pages and shared styles
data/restaurants.json   Representative restaurant/menu data
data/orders.json        Empty order store for the checkout service
tests/                  Backend/API tests; tests/browser/ for customer and management pages
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
- [M2 API/persistence contract](docs/M2_API_CONTRACT.md), [data model](docs/DATA_MODEL.md), and [M2 evidence/status](docs/milestones/M2.md). The checkout service and order store are implemented. The HTTP checkout workflow awaits integration.
- [M1 Engineering Decision Receipt — menu-item price validation](docs/DECISION_RECEIPT.md)
- [Shared AI provenance record](docs/PROVENANCE.md)
- [M1 sprint plan](scrum/SPRINT-Planning-M1.md) and [signed team agreement](scrum/team-agreement.md)
- [Agent instructions](AGENTS.md)
