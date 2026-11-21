# Cross-subsystem persistence and relationship verification (#95)

## Scope and authority

This is the issue #95 verification record for the implemented Milestone 2 workflow, not
a second customer, cart or order persistence implementation. It traces the
[persisted relationships](DATA_MODEL.md#identifiers-and-relationships) and the
[checkout consistency policy](M2_API_CONTRACT.md#checkout-ordering-failures-and-retry-contract)
to actual routes, repositories and executable checks. The Milestone 2 source
sections are indexed in [M2 evidence](milestones/M2.md). The adopted
[M1 restaurant/menu contract](M1_API_CONTRACT.md) remains unchanged.

Subsystem ownership is retained: Sreeram owns customer/cart and authentication
repositories; Thomas owns order/checkout and menu availability; Gwantana
coordinates integration evidence, test configuration and defects. The test suite
uses their *real* services/repositories and isolated copies of the stores.
It does not claim teammate review, student understanding or a successful CI run
until those results are observed.

## Identifier and relationship assertion matrix

| Key and relationship | Authority / owner | Observable assertion and test |
| --- | --- | --- |
| Restaurant `id` remains stable; item `id` is scoped to its containing restaurant | Restaurant/menu repository; Thomas for availability | `test_two_customers_two_orders_reopen_with_stable_relationships` checks original and second restaurant/item references across purchases; `test_invalid_cart_relationships_never_trigger_checkout_writes[wrong_parent_item]` rejects an item belonging to the other restaurant |
| Customer `id` is stable; a request cannot select another customer | Customer/auth, Sreeram | Two fixture customers keep separate carts and order histories after fresh-app reload; order and cart customer IDs are checked against authenticated owners |
| Cart `id` is stable, `customer_id` refers to its owner and there is at most one active cart per customer | Cart repository/service, Sreeram | Repeated PUT, purchase/reset, new purchase, full reloaded cart inventory and duplicate-customer-cart injection |
| Cart `restaurant_id` and `item_id` are valid together; line quantity is a positive integer | Cart service and catalog adapter, Sreeram / Thomas | Two valid purchases plus missing restaurant, missing item, wrong-parent item injection. Existing `test_cart_api.py` and `test_cart_repository.py` cover request quantity and structural invalidity |
| Order `id` is stable and unique; `customer_id` and `restaurant_id` identify the purchasing customer and chosen restaurant | Checkout and order repository, Thomas | Two distinct orders from the same cart, checked against JSON store and customer-owned history after reload; foreign-owner protection remains covered by `test_checkout_api.py` and `test_order_details.py` |
| `(source_cart_id, source_cart_revision)` uniquely identifies a purchase attempt | Order repository and checkout, Thomas | Both orders bind to different revisions of one stable cart; duplicate requests return the original order without another save; failed-reset replay returns exactly one saved order |
| Purchased `(restaurant_id, item_id)`, item name, price, quantity, totals and delivery address are copied, not live references | Checkout, Thomas | First order retains its original `12.50` price, `25.00` total, item name and address after menu/profile edits; second order from another restaurant has its own snapshot |
| Session token digest resolves to an account/role; staff and customer identity are separate | Authentication, Sreeram | The real authenticated API is exercised with distinct customer/staff tokens; `test_corrupt_store_returns_its_public_error_without_other_writes` checks invalid customer, session and staff files |

The test functions above live in
[`tests/test_cross_subsystem_persistence.py`](../tests/test_cross_subsystem_persistence.py).
Existing [checkout HTTP tests](../tests/test_checkout_api.py),
[checkout service tests](../tests/test_checkout_service.py),
[order repository tests](../tests/test_order_repository.py) and
[cart API tests](../tests/test_cart_api.py) remain the feature-owner evidence.
This table coordinates that coverage instead of recreating their repositories.

## Persistence paths and isolation

| Store | Environment override | Implementation / owner |
| --- | --- | --- |
| `restaurants.json` | `RESTAURANTS_DATA_PATH` | `app/repositories/restaurant.py` / existing M1, Thomas for #94 |
| `customers.json` | `CUSTOMERS_DATA_PATH` | `app/repositories/customer.py` / Sreeram |
| `carts.json` | `CARTS_DATA_PATH` | `app/repositories/cart.py` / Sreeram |
| `orders.json` | `ORDERS_DATA_PATH` | `app/repositories/order.py` / Thomas |
| `staff.json` | `STAFF_DATA_PATH` | `app/repositories/staff.py` / Sreeram |
| `sessions.json` | `SESSIONS_DATA_PATH` | `app/repositories/customer.py` / Sreeram |

[`tests/conftest.py`](../tests/conftest.py) sets a disposable path for every
store on *every* test and leaves the order store absent until explicitly
initialized. The new six-case `test_fresh_repository_configuration_uses_only_disposable_store`
asserts fresh implicit repositories resolve exactly to those paths.
`committed_data_is_unchanged` hashes files in `data/` before/after the
pytest session. [CI](../.github/workflows/ci.yml) additionally fails on tracked,
untracked **or ignored** changes under that directory. These checks enforce
test isolation, not global production multi-process serialization.

## Failure and resulting-state matrix

| Injection or condition | Expected observable error | Required stored state / check |
| --- | --- | --- |
| Stored cart points at missing restaurant, missing item or item in a different restaurant | Cart GET: `500 Cart data is unavailable`; checkout: `500 Checkout data is unavailable` | No store replacement is attempted; byte-for-byte all six stores unchanged |
| Two active cart records for the same customer | Same two 500 errors | No automatic cart selection, repair or write; original malformed file remains unchanged |
| Malformed JSON in any of the six stores | Public `500`, with authentication, restaurant, cart or checkout boundary's documented generic detail | All six stores byte-for-byte unchanged; no implicit reset to `[]` |
| Unreadable cart, order or restaurant store (injected `PermissionError`) | Relevant public `500` | No file recreated or changed; existing state preserved |
| Order file's atomic replacement fails | `500 Checkout data is unavailable` | Order and cart unchanged, no cart-reset attempt, no temporary artifact |
| Order save succeeds but cart replacement fails | First checkout returns `201`, original saved order, `cart_reset_pending: true` | Exactly one order saved; original cart and all unrelated stores unchanged. Cart edits return `409 Cart checkout recovery required`. Replay returns `200` with same ID and completes conditional reset |
| Both saves succeed, then original attempt is replayed from a fresh application | `200`, original order and `cart_reset_pending: false` | Current cart revision and second order are untouched; no duplicate attempt |
| Invalid checkout body, stale/empty cart, unavailable item or inactive/wrong owner | `422`, `409`, `403`, `404` or `401` under the documented precedence | No new order and no cart mutation; covered by existing `test_checkout_api.py` and `test_customer_resource_protection.py` |

The new failure tests inspect *responses and stored state*, not merely raised
exceptions. Every new checkout snapshot is fully validated before the first write.
The order is written before a conditional cart reset; a cart-reset failure does
not roll back the saved immutable receipt. Recovery uses the same cart ID/revision,
not a new order. See the shared [policy](M2_API_CONTRACT.md#checkout-ordering-failures-and-retry-contract).

## Verification and owner handoff

Run from the repository root, with the Python 3.12 environment and pinned
requirements from [first-time setup](FIRST_TIME_SETUP.md):

```sh
python -m pytest -q tests/test_cross_subsystem_persistence.py
python -m compileall app
REQUIRE_BROWSER_TESTS=1 python -m pytest
git status --porcelain --untracked-files=all --ignored -- data/
```

The [hosted diagnostic run 44877528951](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/actions/runs/44877528951)
on Python 3.12 completed with:

- `python -m pytest -q tests/test_cross_subsystem_persistence.py`: **22 passed** (0.63s).
- `REQUIRE_BROWSER_TESTS=1 timeout --signal=INT 120s python -m pytest -vv --tb=short`:
  **943 passed** (27.85s), including Chromium browser tests.
- `python -m compileall app`: success; CI's `git status --porcelain
  --untracked-files=all --ignored -- data/` guard: success, no data writes.

The first focused diagnostic run found one test-injection error: the unreadable
restaurant test intercepted `Path.read_bytes()`, while the real repository
uses `Path.read_text()`. The final test injects both readers, and all cases pass.
No implementation change or reproducible subsystem defect was required.
The temporary CI diagnostic commands were restored to the repository's normal
workflow; verify the final standard run from [PR #132](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/132).
The tests were executed by hosted CI, not locally in the current assistant runtime.

The last command must print nothing. Confirm hosted GitHub Actions results on
the PR rather than presuming a local run proves the hosted environment works.
The source/repository contracts and original per-owner tests were inspected
for this task. A student and peer must still independently review the matrix,
important design decisions and final code. Any reproducible defect discovered
in a subsystem should be filed against its owner with steps, affected version,
expected/actual state and a regression assertion; do not create a second
customer/cart/order repository as a shortcut.

**Supported boundary:** the application serializes participating operations
with a single-process workflow lock plus repository atomic-file replacement.
It does not promise transactions across JSON files, coordination across
multiple workers/processes, durable power-loss recovery, or later delivery
states. This issue does not introduce those capabilities.
