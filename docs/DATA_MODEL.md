# Data model: implemented M1 and proposed M2

## Authority and implementation status

The [M1 contract](M1_API_CONTRACT.md#persistence-and-layer-boundaries) describes
implemented restaurant/menu storage. The [M2 contract](M2_API_CONTRACT.md) proposes
the additions below for #77. **There are no customer, cart or order repositories
in the application yet.** These are design targets, not setup instructions or a
claim that the application accepts these files. Course traceability and unresolved
source/role questions are recorded in that contract and [M2 evidence](milestones/M2.md).

## Store ownership and configuration

| Store | Existing / proposed file and override | Owner / format |
| --- | --- | --- |
| Restaurant/menu | Implemented `data/restaurants.json`, `RESTAURANTS_DATA_PATH` | Existing repository; Thomas owns #94 availability extension; JSON array of complete restaurant records |
| Customer | Proposed `data/customers.json`, `CUSTOMERS_DATA_PATH` | Sreeram; JSON array of public profile fields plus private password hash and server-owned customer role |
| Cart | Proposed `data/carts.json`, `CARTS_DATA_PATH` | Sreeram; JSON array of `CartRecord` objects |
| Order | Proposed `data/orders.json`, `ORDERS_DATA_PATH` | Thomas; JSON array of immutable `Order` snapshots |

New repositories should match M1's explicit `path: Path | str | None` injection,
resolve overrides at construction rather than import time, and keep file I/O out
of routes/services. Customer credential hashing and any token/session storage are
unresolved #78 implementation choices; this document does not invent an auth
file or configure a working session store. Final tests must isolate such a store
as well if one is added.

Feature PRs must initialize deliberately empty new stores and explain first-run
configuration in both setup guides when implemented. Once configured, a missing,
malformed or unreadable file is an error, not an automatic empty database.
No new representative data files are introduced by #77. Keep private credentials
out of public projections; demo customers/addresses must be fictional.

## Identifiers and relationships

| Entity/key | Scope and invariant | Validation owner |
| --- | --- | --- |
| Restaurant `id` | Unique among restaurants, opaque and stable; M1 IDs retained | Existing restaurant repository |
| Menu item `(restaurant_id, id)` | ID unique inside its containing restaurant; no independently stored menu ID | Existing repository plus #94 |
| Customer `id` | Unique and stable; normalized login email also unique | Sreeram |
| Cart `id`, `customer_id` | Unique cart ID; at most one active cart record per customer; customer reference exists | Sreeram / integration #95 |
| Cart item `(cart.restaurant_id, item_id)` | One line per item; positive strict integer quantity; item belongs to that parent | Sreeram against catalog boundary |
| Order `id`, `customer_id`, `restaurant_id` | Unique stable order ID, valid customer and restaurant at creation | Thomas |
| Order `(source_cart_id, source_cart_revision)` | Unique durable checkout attempt; must correspond to the owned cart at initial save | Thomas against customer/cart boundary |
| Order item `(order.restaurant_id, item_id)` | Valid purchased parent/item at checkout; names/prices/quantity frozen | Thomas |

Services generate collision-checked UUID4s for new entity IDs. Seed IDs like
`customer-001` remain valid; never require UUID-only lookups, regenerate IDs on
reload, or derive them from mutable text/array positions. Duplicate IDs, duplicate
cart customers, duplicate scoped lines or duplicate attempt keys in stored data
are corruption, not a reason to choose the first record. Structural repository
validation precedes writes. Services validate cross-store references under the
workflow lock; repositories do not import each other to own business rules.

## Records and projections

`Customer`: proposed `id`, `name`, `email`, `delivery_address`, `status`.
The complete stored record additionally holds a library-produced `password_hash`
and server-assigned customer role. Never serialize the complete record through a
public response model. Proposed deactivation sets `inactive`, preserves the ID,
cart and orders, and does not support reactivation or cascade deletion. See the
contract's source gap before treating any field/permission as final.

`CartRecord`: `id`, `customer_id`, nonnegative integer `revision`, nullable
`restaurant_id`, `items: [{item_id, quantity}]`. Prices, names, totals and
`checkout_order_id` are read projections, not stored authorities. The empty state
requires null restaurant and empty items together. Normal edits and successful
checkout reset increment revision on actual change; reset preserves the cart ID.

`CartView` adds current line `name`, `unit_price`, `line_total`, `available`, and
`subtotal`, `total`, plus nullable `checkout_order_id`. The latter is derived by
querying orders for the current cart/revision. It signals an order already saved
whose cart reset needs recovery. Reads of inconsistent references fail; do not
silently omit items. A valid unavailable item stays visible with its current price.

`Order`: `id`, `customer_id`, `restaurant_id`, `restaurant_name`, `source_cart_id`,
`source_cart_revision`, `delivery_address`, `status: "placed"`,
`items: [{item_id, name, quantity, unit_price, line_total}]`, `subtotal`, `total`.
The order stores copied transaction values, not references to mutable display
values. Later profile/menu/restaurant changes never alter saved order responses.
No payment, driver, delivery, reporting, timestamp ordering or full lifecycle
fields are introduced without a source-grounded later contract change.

[m2.json](examples/m2.json) contains complete public/stored-cart/order examples;
there is deliberately no usable password-hash or session-token seed.

## Consistency and compatibility

Each repository reads and validates the complete store before a mutation and
validates the complete result before saving. Atomic same-directory replacement
and a process-shared repository mutation lock retain M1's failure guarantees.
Unknown complete restaurant fields remain preserved; do not write public read
models back over full stored records. Legacy omitted `menu_items` still means an
empty menu; the proposed omitted menu `available` means true only once #94 lands.
Explicit null/invalid values are corruption. Reads never migrate data implicitly.

Multiple files are not a transaction. The contract's workflow lock serializes
customer status/address changes, menu changes, cart changes, and checkout in one
process, acquiring repository locks only inside that boundary. Validate before
writing, save the immutable order first, then conditionally reset the exact cart
revision. The saved order is the durable receipt for lost responses or failed
reset. Cart mutations consult that receipt and reject edits until recovery.
The full [retry policy](M2_API_CONTRACT.md#checkout-ordering-failures-and-retry-contract)
also prevents clearing a later cart revision. No claim of multiworker/external
writer coordination, power-loss durability, or complete M3 recovery is made.

No existing runtime configuration or M1 schema changes in this PR. The two setup
guides therefore stay unchanged; implementing owners must update both when their
configuration/data files become operational.

## Verification responsibilities

Use the [disposable store fixture](../tests/contracts/conftest.py) as a starting
point for feature tests. It points all proposed customer/cart/order paths into
`tmp_path` and reuses the existing isolated restaurant copy. The root test guard
already hashes **all** files under `data/`, so it covers future stores without a
second guard; new owners must extend configuration assertions and any auth-store
isolation. Never execute a default-backed writer against committed seed data.

Feature repository tests verify serialization, corrupt/duplicate records,
preservation on failure, fresh-instance reload and ID stability. #95/#101 test
real cross-store relationships, concurrent edits/checkout and recovery after
restart. The current contract doubles exercise none of those file-backed
guarantees and are not final integration evidence.
