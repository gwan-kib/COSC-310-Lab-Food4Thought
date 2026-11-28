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
| Customer account (registration, sign-in, profile, deactivation) | `http://127.0.0.1:8000/app/account.html` |
| Customer cart and checkout | `http://127.0.0.1:8000/app/cart.html` |
| Staff sign-in | `http://127.0.0.1:8000/app/staff-sign-in.html` |
| Create restaurant frontend | `http://127.0.0.1:8000/app/create-restaurant.html` |
| Edit restaurant frontend | Sign in as staff, select a restaurant under **Browse restaurants**, and follow **Edit restaurant** |
| Health | `http://127.0.0.1:8000/health` |
| Restaurant list/filter | `http://127.0.0.1:8000/restaurants?cuisine=japanese` |
| Restaurant details/menu | `/restaurants/restaurant-001` and `/restaurants/restaurant-001/menu` |
| API documentation/schema | `http://127.0.0.1:8000/docs` and `/openapi.json` |

Before trying the form, registering, signing in, or any other mutation, stop the server and follow the [disposable data-copy commands](FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments). They point every store (`RESTAURANTS_DATA_PATH`, `CUSTOMERS_DATA_PATH`, `SESSIONS_DATA_PATH`, `STAFF_DATA_PATH`, and the cart and order paths) at new temporary copies before running the same startup command. Reuse that path on restart to verify persistence, and clear the override afterward. Full mutation examples and data validation are in [first-time setup](FIRST_TIME_SETUP.md#8-verify-the-current-application) and the [API contract](M1_API_CONTRACT.md).

In the browser, sign in as a customer at **My account** in the same tab, browse a menu, select **Add to cart**, then open **My cart**. Edit or clear the server-priced cart and use **Place order** to display its saved receipt. If checkout is uncertain, check order status before explicitly replaying the original cart ID/revision. Use disposable data paths for every manual write.

To check cart removal in `/docs`, authorize an active customer token, PUT
`/customers/me/cart`, POST an item, then DELETE `/customers/me/cart/items/{item_id}`
without a body. Expect 200 with current totals; the last removal empties the cart and
releases its restaurant while retaining IDs. GET after restarting with the same
disposable paths verifies persistence. [Removal details](M2_API_CONTRACT.md#implemented-item-removal-88).

For cart clear, authorize as an active customer in `/docs`, create/add to the cart,
then call `DELETE /customers/me/cart/items` without a body. Expect 200, the same ID,
empty items, null restaurant and `"0.00"` totals. Repeating it keeps the revision
without saving; GET after restart preserves the empty state. Missing carts return
404 and purchased revisions awaiting checkout recovery return 409. See the
[clear contract](M2_API_CONTRACT.md#implemented-cart-clear-89).

Menu reads include `available`. For manual writes, sign in with a provisioned staff account through `POST /auth/login` and use **Authorize** in `/docs`. Restaurant creation requires an administrator. Editing a restaurant or writing its menu requires a restaurant user assigned to it. For the management forms, use **Staff sign-in** first. Open **Edit restaurant** for the restaurant you manage and change availability in **Menu availability**. The browser keeps its bearer token in sessionStorage for that tab and sends it on create, edit, and menu-availability PATCH requests. A 401 means sign in again; a 403 means the backend rejected the requested operation. The browser never decides management permissions by itself.

Stop the server with `Ctrl+C`.

To change a cart quantity on disposable data, authorize as the active cart owner in
`/docs` and send `PATCH /customers/me/cart/items/{item_id}` for an existing available
line. The body `{"quantity": 3}` sets its quantity to three.

For order repository experiments, set `ORDERS_DATA_PATH` to a disposable copy
of the empty `data/orders.json` before constructing the repository. Run
`python -m pytest -q tests/test_order_repository.py tests/test_checkout_service.py tests/test_checkout_api.py`
to exercise checkout with isolated storage. In `/docs`, authorize as the active
owner of a populated cart and send its `id` and `revision` as `cart_id` and
`cart_revision` to `POST /customers/me/checkout`. Expect 201 for a new order.
Retry the identical request for a 200 receipt or to finish a pending cart reset.

After signing in through `/docs`, use **Authorize** with the returned token and
call `GET /customers/me/orders`: it returns your saved snapshots, or `[]` when
you have no orders. Inactive customers retain read access. Run
`python -m pytest -q tests/test_order_history_api.py` for isolated real-auth and
purchase-to-history checks; no manual seed edits are required.

`GET /customers/me/orders/{order_id}` is implemented. In `/docs`, sign in and
use **Authorize** with the returned token, then supply an owned ID already saved
in the disposable order store. The empty seed has no orders; an unknown ID returns
404. Active and inactive owners can read snapshots. Run
`python -m pytest -q tests/test_order_details.py` for fixture-based API checks and
the real account/cart/checkout-service/detail integration.

To sign in as a restaurant user or administrator, create the account after setting the disposable data paths and **before** clearing them, in the same terminal with the server stopped: `python -m app.scripts.create_staff_account create --name "Cedar Bowl Manager" --email manager@cedarbowl.invalid --role restaurant_user --restaurant restaurant-001`, then start the server again. The [disposable-data steps](FIRST_TIME_SETUP.md#disposable-data-for-manual-experiments) show the full order, administrators and assigning restaurants.

## Start the local demo

```sh
python -m app.scripts.run_demo
```

Open [My account](http://127.0.0.1:8000/app/account.html), choose **Demo customer**, **Demo manager**, or **Demo administrator**, then click **Sign in**. Run the same command after stopping the demo to reuse `.demo-data/`. See [first-time demo setup](FIRST_TIME_SETUP.md#run-with-reusable-demo-accounts) for role destinations and signup rehearsal.

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
