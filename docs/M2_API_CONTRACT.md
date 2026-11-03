# Proposed M2 API and persistence contract

## Status, sources, and limits

Prepared for [#77](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/77)
on 2026-11-03. **Proposal for implementation and teammate review; not adopted,
not implemented, and not evidence that M2 is complete.** The requester authorized
drafting the interface decisions and opening a PR without requesting reviews.

Source review:

- [M2 assignment](https://canvas.ubc.ca/courses/196634/assignments/2501640),
  inspected from the text captured on 2026-10-22: §2 workflow; §3 customer,
  authentication, cart, checkout and order scope; §4 cross-subsystem rules;
  §6 persistence; §7 tests; §8 API documentation. The live course page could not
  be rechecked on 2026-11-03 because computer use could not verify the browser URL.
- Current `main`, `87ce91c1a28648f849063a46620a7321a6d2e637`:
  [routes](../app/api/routes/restaurants.py), [schemas](../app/schemas/restaurant.py),
  [services](../app/services/restaurant.py), [repository](../app/repositories/restaurant.py),
  [configuration](../app/core/config.py), [frontend](../frontend/app.js), and
  [test isolation](../tests/conftest.py). It implements M1, not customers/carts/orders.
- [M1 adopted contract](M1_API_CONTRACT.md), [workflow](../CONTRIBUTING.md),
  [testing](TESTING.md), and the live M2 issues. No open PRs existed at inspection.
  Live Project field values were unavailable; no board fields were changed.

**Unresolved source gap:** the original full project authentication/role and
customer-field specification was not recovered. M2 delegates the authentication
mechanism to that project source. Exact source-required profile/address fields,
role names, restaurant ownership provisioning, and management permissions therefore
remain unverified. The concrete minimal shapes below are proposed engineering
choices, not claims about those requirements. Reconcile them in
[#78](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/78) before adoption.
No administrator permissions or account reactivation are inferred.

All paths, status literals, transport choices, quantity semantics, money policy,
and retry details below are **proposed team decisions**. The assignment requires
the capabilities and rules, not these exact field names or routes. Keep the
proposal, examples, doubles and feature implementations aligned through review.

## Ownership and parallel work

| Owner | Implementation responsibility | Independent starting point |
| --- | --- | --- |
| Sreeram / `SreeramNara` | Customer identity/authentication (#78–#84); customer and cart repositories/services (#85–#90) | Customer/cart examples; fake catalog and order-receipt lookup |
| Thomas / `Tc2006415` | Order repository, checkout/retrieval (#91–#93), restaurant/menu availability (#94) | Fake customer/cart access; existing restaurant service |
| Gwantana / `gwan-kib` | Coordinate this contract, frontend/integration and evidence | JSON examples and test support; no duplicate customer/cart/order repository |

Each feature owner implements their own schemas, business rules and isolated
tests. The [test-only models and ports](../tests/contracts/m2.py) are a handoff
aid; production code must not import `tests/`. They are not a new application
framework or an alternative persistence implementation.

The proposed service boundaries return validated snapshots or `None` for absence;
storage failures remain exceptions, not absence. `CustomerAccess.get_customer(id)`
reloads identity/status. `CatalogAccess.get_restaurant(id)` and
`get_item(restaurant_id, item_id)` distinguish parent/item absence.
`CartAccess.get_cart(customer_id)` returns the stored ID/revision/items;
`reset_after_order(customer_id, cart_id, expected_revision)` returns true on a
matching reset, false when it no longer matches, and raises on storage failure.
`OrderAccess` supplies `find_for_cart(cart_id, revision)`, `save_order(order)`,
`get_order(id)` and `list_for_customer(customer_id)`. `save_order` returns only
after saving the validated snapshot; the service returns that same saved value.
These interfaces do not authorize callers: services enforce the matrix and
perform coordinated calls under the workflow lock. Routes map errors to HTTP.

## Customer identity and allowed changes

Proposed public customer fields: `id`, `name`, `email`, `delivery_address`,
`status`. Text is a nonempty string. New user text is trimmed; the address is
initially one string, not an invented postal-address schema. `id` is server-owned
and stable; `status` is `active` or `inactive`, initially `active`. Registration
also accepts `password`; it is never returned. Profile PATCH allows only `name`
and `delivery_address`: at least one supplied, no nulls or unknown fields.
`email`, `id`, `role`, `status`, and password are not profile-edit fields.

Proposed email identity: trim and casefold for unique login lookup, preserve the
trimmed original for display, require one nonempty local and domain part around
`@`, and reject whitespace/control characters. Passwords are case-sensitive and
never trimmed. Detailed credential validation, hashing/session library, expiry,
revocation and test vectors belong to #78/#79/#80; they must be settled against
the project source before authentication implementation is called conforming.
No plaintext passwords or tokens may enter public examples, logs or orders;
the example strings in [m2.json](examples/m2.json) are explicit dummy values.

Proposed HTTP identity boundary: `Authorization: Bearer <token>`. Authentication
resolves a server-trusted principal with `user_id` and server-owned role, then
customer operations reload current customer status. Never accept customer identity,
ownership, role, price, total or status from an editable request body. A token
does not freeze account status. Transport agreement does not select JWT, a
signing algorithm, or an authentication library.

### Proposed access matrix

| Operation | Anonymous | Active customer, own resource | Inactive customer, own resource | Other customer / noncustomer role |
| --- | --- | --- | --- | --- |
| M1 discovery/details/menu | Allow existing reads | Allow | Allow | Allow existing reads |
| Register/login | Public entry; credentials still validated | Login allowed | Login allowed for read-only access, proposed | No customer-role creation through body fields |
| Read own profile, existing cart, order history/detail | 401 | Allow | Allow, proposed | Deny; never expose another customer's record |
| Update own profile | 401 | Name/address only | 403, proposed | 403 |
| Deactivate own account | 401 | Set inactive; retain related records | 200, already inactive | 403 |
| Create cart, add/update/remove/clear, checkout | 401 | Allow subject to rules | 403 | 403 |
| Restaurant/menu management, including availability | Must become protected in M2 | No customer-role grant | No customer-role grant | Required role/ownership mapping unresolved against project source |

This is a conservative customer-only proposal, not a source-certified complete
role matrix. Restaurant mutation routes retain their paths and payload compatibility
but M2 must introduce source-grounded backend authorization in #78/#84/#94.
Until that mapping is resolved, no noncustomer role is granted new rights by
this document. Do not treat the existing unauthenticated M1 management routes
as proof that unauthenticated writes are acceptable for final M2 integration.
No public role-assignment, customer listing, deletion, password-reset, or
reactivation endpoint is proposed. Foreign order IDs return the same 404 as
missing IDs; role denials use 403.

## Cart, pricing, and availability

- One persisted active cart per customer. It is lazily created by an explicit
  create/retrieve operation; GET alone never writes. The cart keeps its ID when
  cleared or checked out. A nonnegative `revision` starts at 0 and increases by
  one for each actual content change, including a successful checkout reset.
  No-op quantity updates and clearing an already empty cart keep the revision.
- An empty cart has `restaurant_id: null`, `items: []`, and `"0.00"` totals.
  Adding the first item binds its restaurant. Clearing/removing the last item
  releases that binding. Adding a different restaurant to a nonempty cart is
  409; do not silently replace the cart.
- Identify each item by `(restaurant_id, item_id)`, preserving M1's scoped IDs.
  One line per scoped item. Add takes a **positive strict JSON integer** quantity
  and increments an existing line; quantity PATCH sets the absolute quantity.
  Reject zero, negative, fractional, boolean and string quantities with 422.
  Zero never means delete. Removal of a missing line is 404; clear is idempotent.
- Persist only item IDs and quantities in carts. Resolve names, prices and
  availability from current restaurant/menu data. Proposed menu `available: bool`
  defaults to `true` for valid legacy items and new requests omitting it. Explicit
  null/nonboolean values are invalid; unavailable items remain stored and visible.
  This single flag controls orderability; no separate deactivation lifecycle.
- Add and quantity increases/changes require the selected item to exist under
  the bound parent and be available. Decreasing an unavailable line is also
  rejected under this simple proposal; remove/clear are the recovery operations.
  Viewing an existing unavailable item is allowed: show `available: false` and
  its current price. It still contributes to displayed totals; checkout rejects it.
  No menu-delete operation is introduced. Missing stored references are storage
  inconsistency (500), never silently skipped or priced at zero.
- Unit prices retain M1's decimal-string input/normalization and inclusive
  `999.00` cap. Views/snapshots use exactly two decimal places. Calculate with
  integer cents or exact `Decimal` arithmetic, never binary floats. Line total =
  unit price × quantity; subtotal = sum of lines; **total = subtotal**. No tax,
  fee, currency conversion, discount or payment amount is introduced. Totals
  can exceed `999.00`; that limit applies to unit prices only.
- Recalculate on each view and checkout. A viewed quote is not a price promise;
  checkout uses current prices without trusting client totals. A price change
  alone does not increment cart revision. The frontend must state that current
  prices apply and show the returned order. Price acceptance/versioning is not
  added silently to this proposal.

## Minimum HTTP handoff

These are the proposed externally consumed operations; internal helpers and
additional endpoints are not prescribed. Success bodies are JSON. All mutation
bodies forbid unknown fields. IDs are opaque nonempty strings, not UUID-only.

| Method/path | Request | Success |
| --- | --- | --- |
| `POST /customers` | Proposed registration fields above | 201, public customer |
| `POST /auth/login` | `email`, `password` | 200, `access_token`, `token_type: "bearer"` |
| `GET /customers/me` | Bearer identity | 200, public customer |
| `PATCH /customers/me` | Changed `name` and/or `delivery_address` | 200, persisted customer |
| `POST /customers/me/deactivate` | No body | 200, inactive customer |
| `PUT /customers/me/cart` | No body | 201 new / 200 existing, cart view |
| `GET /customers/me/cart` | No body | 200, cart view; 404 if never created |
| `POST /customers/me/cart/items` | `restaurant_id`, `item_id`, `quantity` | 200, updated cart view; cart must already exist |
| `PATCH /customers/me/cart/items/{item_id}` | `quantity` | 200, updated cart view; parent comes from cart |
| `DELETE /customers/me/cart/items/{item_id}` | No body | 200, updated cart view |
| `DELETE /customers/me/cart/items` | No body | 200, empty cart view |
| `POST /customers/me/checkout` | `cart_id`, `cart_revision` | 201 new / 200 replay, checkout response |
| `GET /customers/me/orders` | No body | 200, own orders in persisted insertion order; `[]` if none |
| `GET /customers/me/orders/{order_id}` | No body | 200, own saved order |

Preserve all eight M1 restaurant/menu operations, response projections, paths,
decimal-string prices, filtering, partial-update and 404/422/500 semantics.
The planned #94 extension adds `available` to menu item create/read/update models;
old valid create/PATCH requests remain valid and omitted PATCH fields retain their
value. Legacy items read as available, with no read-time rewrite. Current M1
`MenuItem` forbids extra fields, so it **cannot yet accept persisted `available`**:
#94 must update the models and compatibility tests before adding the field to
data. Do not claim this proposal already changed OpenAPI or runtime behavior.

### Concrete examples

The machine-readable [example bundle](examples/m2.json) contains registration,
login, profile update, add/quantity/availability requests, a customer, a minimal
stored cart, a priced cart, an empty cart, a checkout request/response and errors.
Descriptive IDs are valid seed IDs; new entity IDs are collision-checked UUID4s.

Example checkout request: `{"cart_id":"cart-001","cart_revision":2}`.
The saved order has two Vegetable bowls at `"12.50"` and one Noodle bowl at
`"14.00"`: line totals `"25.00"` and `"14.00"`, subtotal/total `"39.00"`.
The response is `{"order": <saved order>, "cart_reset_pending": false}`.
If reset fails after the save, return the same persisted order with
`cart_reset_pending: true`; the customer has placed an order, not a failed purchase.

## Checkout ordering, failures, and retry contract

The durable attempt identity is **`(source_cart_id, source_cart_revision)`**,
unique across orders. No client-supplied order ID or arbitrary retry token.
Each order also has its own stable ID and customer/restaurant/item relationships;
snapshot and storage details are in [the proposed data model](DATA_MODEL.md).

1. Authenticate, enforce the customer role/ownership and reload current active
   customer status. Enter the shared single-process workflow mutation lock.
2. Look up an already saved order for the requested cart/revision. Verify its
   customer ownership. If present, return that order unchanged: do not recalculate
   historical prices/address or save another order. Try only the conditional
   reset described below; a later cart revision must remain untouched.
3. For a new attempt, load/validate the current owned cart and all required stores;
   require matching ID/revision, a nonempty single-restaurant cart, valid parent/
   item references, quantities and current availability. Re-read current customer
   address and menu prices. Build and validate the complete order snapshot before
   the first write. No cart mutation on rejected checkout.
4. Persist the order atomically, enforcing unique order ID and unique attempt.
   An order-save failure returns generic 500 and preserves the cart. If a write
   reports an uncertain result, do not reset the cart; retry checks the durable
   attempt record to discover whether the order was actually saved.
5. Only after order persistence succeeds, reset the cart **conditionally** using
   `(customer_id, cart_id, expected_revision)`. Set empty items and null restaurant,
   increment revision once. Return the persisted order with 201. Reset failure
   does not delete/compensate the order: 201 with `cart_reset_pending: true`.
6. Retry with the identical cart ID/revision returns 200 and the same order ID.
   This still works after restart, after cart reset, or after later menu/address
   changes. A repeated conditional reset that no longer matches is a no-op.
   `cart_reset_pending` is true only if the purchased revision remains uncleared
   or its current state cannot be read; a later revision is never cleared.

While a saved order's purchased revision remains in the cart, normal add/PATCH/
remove/clear requests return 409 `Cart checkout recovery required` without writes.
The frontend keeps the original checkout request for retry, displays the saved
order, and can also recover `checkout_order_id` from the cart view. A fresh page
can retry using that view's cart ID/revision. Do not create a second order or
let a cart edit relabel already purchased items as a new attempt.

This requires a read-only order-receipt lookup in Sreeram's cart mutation service,
injected behind the same `find_for_cart` boundary Thomas owns. Develop against
the fake until integration; final wiring must use real order persistence, not a
default "no receipts" stub. Lock order-receipt checks, cart edits, checkout and
customer/menu changes that affect checkout under one application workflow lock.
Always acquire workflow lock before repository locks; never the reverse or
reentrantly. Snapshot reads also use this boundary when multiple stores are read.
Repository implementations stay with their owners. This is a proposed small
single-process consistency boundary, not an assertion of cross-file atomicity,
multiple-worker safety, or full M3 crash-recovery infrastructure.

## Shared errors and precedence

Keep `{"detail":"..."}` for domain/storage errors and the existing FastAPI
`detail` **array** for request-validation 422s. Never expose credentials, file
paths, exception strings, private records or rejected passwords in diagnostics.
#78 must ensure credential validation errors redact secret input; do not reuse
the current general-purpose handler on passwords without that check.

| Condition | Status / exact proposed detail |
| --- | --- |
| Missing/invalid/expired identity, including unknown customer identity | 401 / `Authentication required`; `WWW-Authenticate: Bearer` |
| Wrong role | 403 / `Operation not permitted` |
| Inactive customer attempts a restricted mutation | 403 / `Customer is inactive` |
| Existing normalized email at registration | 409 / `Email is already registered` |
| Missing active cart / missing cart line | 404 / `Cart not found` / `Cart item not found` |
| Missing or foreign order | 404 / `Order not found` |
| Restaurant/item lookup absent for an add | 404 / M1 `Restaurant not found` / `Menu item not found` |
| Empty checkout / mixed restaurant / unavailable item | 409 / `Cart is empty` / `Cart belongs to another restaurant` / `Menu item is unavailable` |
| New checkout uses stale revision / mutation on purchased pending revision | 409 / `Cart revision changed` / `Cart checkout recovery required` |
| Invalid request, unknown fields, nonpositive quantity | 422 / validation `detail` array |
| Malformed/unreadable store, invalid stored references, save failure | 500 / operation-specific generic data error |

Generic storage details: `Customer data is unavailable`, `Cart data is unavailable`,
`Checkout data is unavailable`, `Order data is unavailable`; existing M1 routes
retain `Restaurant data is unavailable`. Do not map corruption to empty data.

Precedence for protected M2 operations: identity → role/current customer state →
structural request validation → required storage validation → resource ownership/
existence → business-state checks → writes. Native FastAPI dependency/body
validation ordering must be implemented and tested explicitly in #78/#84; a
handler-local check alone does not establish this order. Unknown/foreign order
responses must be indistinguishable, including with malformed unrelated input.
Unauthenticated requests must not load private resource stores. M1 request
validation-before-storage behavior stays as adopted. For cart additions, check
cart/receipt and mixed restaurant before selected restaurant/item existence;
inside that selected restaurant check parent before item, then availability.
For new checkout, check matching cart revision before empty cart, then parent,
items in persisted line order, availability, and calculations. A receipt replay
precedes current-cart/menu checks; authentication and customer-state checks still
apply. Failures after a persisted order use the success/recovery policy above.
An owned current cart whose ID differs from the supplied `cart_id` returns 404
`Cart not found`; only a matching cart with the wrong revision returns 409.

## Verification and adoption gate

[Contract checks](../tests/contracts/test_m2_contract.py) parse the example
customer/cart/order models, verify exact arithmetic and relationships, reject
invalid quantities/money/duplicate lines, and exercise isolated fake read/save/
conditional-reset behavior including a saved order plus failed reset. They do
**not** prove real authorization, checkout orchestration, locking, HTTP semantics,
atomic persistence, restart behavior or frontend integration. Feature owners
must add those tests; #95/#101 integrate real implementations and every store.

Before adoption and before #77 can close:

- [ ] Recover current project source; settle customer fields and complete the
  role/ownership/authentication matrix in #78 with exact source sections.
- [ ] Sreeram records agreement or corrections on customer/cart, identity,
  receipt lookup, mutation locking and isolation contracts.
- [ ] Thomas records agreement or corrections on availability, order snapshots,
  durable attempt uniqueness, errors and conditional cart reset.
- [ ] Update examples/ports/docs and dependent implementations for that feedback;
  record reviewer/date/comment or PR links, never inferred approval.
- [ ] Real integration/restart/failure tests, source reconciliation, green CI,
  peer review and merge evidence are linked from [M2 evidence](milestones/M2.md).

No teammate review has occurred for this proposal. None was requested, per the
requester. No issue is closed or marked Done by publishing it.
