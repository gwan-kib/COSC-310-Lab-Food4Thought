# M1 restaurant and menu contract

## Status and authority

Adopted contract for [issue #30](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/30). The team agreed to the contract by merging [PR #48](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/48) on 2026-10-02 at revision [d4850b8](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/d4850b8caece7098fbaa3b660e8d7769984fda77), as the user clarified on 2026-10-04. The previous pending-adoption wording was stale. The contract was drafted and checked against the user-supplied **Milestone 1 – First Vertical Slice** specification on 2026-10-02.

[PR #51](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/51) merged the #35 subset and the mutation-result clarification below. [PR #52](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/52) merged menu browsing. [PR #53](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/53) merged #37's menu-item creation. The #36 feature branch implements restaurant updates using that shared foundation; its review and integration remain pending. Contract adoption does not mean every endpoint is implemented. Merged code and generated OpenAPI describe implemented behavior.

The [M1 checkpoint](milestones/M1.md) records the supplied course source and its scope. Sections 1–2, Required Vertical Slice, Pydantic Models, Persistence, and API Documentation ground this contract. Trace implementation through [discovery epic #27](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/27), [management epic #28](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/28), [quality epic #29](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/29), and their child stories. The pasted specification was verified directly; its linked downloads and live Canvas page were not supplied or inspected.

Exact paths, field shapes, filtering, identifiers, and update semantics are **agreed team engineering decisions**, not additional course requirements. This document is the shared contract for child implementations. Change it through review before dependent branches adopt a different contract.

When #30 was drafted, only `GET /health`, unfiltered `GET /restaurants`, and FastAPI documentation routes existed. `Restaurant` had `id`, `name`, `cuisine`, and `description`; `data/restaurants.json` was a JSON array. PR #48 added documentation only. Feature stories add models, data, code, tests, and matching OpenAPI declarations.

## Endpoint inventory

Use the existing unprefixed `/restaurants` collection. Path identifiers are opaque, nonempty strings, compared exactly; callers must not assume UUID-only IDs because existing IDs such as `restaurant-001` remain valid. Every success body is JSON. Collection results preserve persisted order.

| Operation / owner | Method and path | Input | Success body | Expected errors |
| --- | --- | --- | --- | --- |
| List restaurants / existing #5 | `GET /restaurants` | None | `200`, `list[Restaurant]`; `[]` when empty | `500` |
| Filter restaurants / #32 | `GET /restaurants?cuisine=Japanese` | Optional `cuisine` query string | `200`, `list[Restaurant]`; `[]` when no match | `422`, `500` |
| Restaurant details / #31 | `GET /restaurants/{restaurant_id}` | Restaurant ID | `200`, `Restaurant` | `404`, `500` |
| Menu and its items / #33 | `GET /restaurants/{restaurant_id}/menu` | Restaurant ID | `200`, `Menu`; empty `items` for an existing restaurant with no items | `404`, `500` |
| Create restaurant / #35 | `POST /restaurants` | `RestaurantCreate` | `201`, persisted `Restaurant` | `422`, `500` |
| Update restaurant / #36 | `PATCH /restaurants/{restaurant_id}` | Restaurant ID; `RestaurantUpdate` | `200`, complete updated `Restaurant` | `404`, `422`, `500` |
| Add menu item / #37 | `POST /restaurants/{restaurant_id}/menu/items` | Restaurant ID; `MenuItemCreate` | `201`, persisted `MenuItem` | `404`, `422`, `500` |
| Update menu item / #38 | `PATCH /restaurants/{restaurant_id}/menu/items/{item_id}` | Restaurant ID and item ID; `MenuItemUpdate` | `200`, complete updated `MenuItem` | `404`, `422`, `500` |

The menu response contains the items: no additional menu-item GET endpoint or independently managed menu resource is needed for the flow described in #33. Item identity for updates is available in that response. Restaurant creation starts with an empty menu. There is no menu-creation operation or menu ID to supply.

### Filtering

One cuisine filter satisfies the search-or-filter choice described in #32 without introducing new restaurant fields. When absent, return the existing unfiltered list. When present, strip surrounding whitespace and compare the entire cuisine value case-insensitively using `casefold()` on both query and stored value. Do not change stored spelling. A query containing only whitespace or an empty string returns `422`. For example, `?cuisine=%20JAPANESE%20` matches `Japanese`; `?cuisine=Japan` does not. Unknown cuisine values return `200` with `[]`.

`cuisine` is the only supported filter in this contract. Pagination, ranking, free-text search, and extra query-driven behavior are not introduced here. Unrecognized query parameters retain FastAPI's existing ignored-parameter behavior; they do not become filters.

## Pydantic model responsibilities

Keep models in the existing `app/schemas/` layer. Names below are the agreed shared names; introduce the shared persistence models in #35 as specified below, and other models with their consuming features, not as unused placeholders in #30.

| Model | Fields and responsibilities |
| --- | --- |
| `Restaurant` (existing read model) | Required nonempty strings: `id`, `name`, `cuisine`, `description`. Preserve the existing list/detail response shape without embedding menu data. |
| `RestaurantCreate` | Required strings: `name`, `cuisine`, `description`. No client-supplied ID or menu. |
| `RestaurantUpdate` | The same three mutable fields, each omittable. At least one must be supplied; supplied values cannot be null. |
| `MenuItem` | Required nonempty strings: `id`, `name`, `description`; `price` as a finite nonnegative decimal with at most two fractional digits. Price is serialized as a JSON string, for example `"12.50"`. |
| `MenuItemCreate` | Required `name`, `description`, `price`. No client-supplied ID or parent identifier. |
| `MenuItemUpdate` | The same three mutable fields, each omittable. At least one must be supplied; supplied values cannot be null. |
| `Menu` | Required `restaurant_id: str` and `items: list[MenuItem]`. It is a read projection for one restaurant, not a separate persisted entity. |
| `RestaurantRecord` | Persistence model with the four `Restaurant` fields and `menu_items: list[MenuItem]`, defaulting to a fresh empty list for legacy records. Project explicitly to `Restaurant` for list/detail responses. |
| `ErrorResponse` | Required `detail: str` for the documented `404` and `500` responses. Keep FastAPI's validation-error model separate. |

Menu item name, description, and price are the agreed minimal display/edit shape. The two-decimal nonnegative price representation is an engineering choice, not a milestone pricing rule; no taxes, currency conversion, totals, discounts, or checkout semantics are defined here. Accept price input only as a decimal string matching `^[0-9]+(\.[0-9]{1,2})?$`; reject JSON numbers, signs, exponent notation, whitespace, NaN, and infinity with `422`. Convert to `Decimal` for validation and serialize/persist with exactly two fractional digits. Thus `"12"` and `"12.5"` become `"12.00"` and `"12.50"`. Do not use binary floating-point arithmetic for this field.

For new write requests, reject unknown fields (`extra="forbid"`), including `id`, `restaurant_id`, `menu_id`, and `menu_items`. String fields accept strings only, are stripped of surrounding whitespace, and must remain nonempty. Existing persisted restaurant strings and read behavior are not silently normalized or tightened; preserve valid M0 records. New menu records use the same content constraints as their write models.

Updates are partial: omitted fields keep their stored values. Apply only explicitly supplied fields (Pydantic `model_fields_set` / `model_dump(exclude_unset=True)`), distinguish omission from explicit null, and validate the complete result before persistence. `{}`, null-valued fields, and unsupported fields return `422`. A valid update supplying an unchanged value succeeds with `200`. Neither update operation creates a missing resource, replaces its ID, moves an item to a different parent, nor changes unrelated fields/items.

## Relationships and identifier ownership

Each restaurant has exactly one logical menu, identified by the restaurant's existing ID. It contains zero or more menu items. A menu item belongs to the restaurant record that contains it. Do not persist a second `restaurant_id` or `menu_id` on the item: containment is the single parent relationship. The `Menu.restaurant_id` response value is derived from the enclosing restaurant.

Preserve all existing restaurant IDs. For new restaurants and items, the service generates lowercase UUID4 strings, and the repository verifies uniqueness before saving: restaurant IDs across restaurants, and item IDs within their restaurant. Retry a generated collision rather than overwriting a record. IDs are persisted once, never regenerated on reads/restarts or derived from a mutable name, array position, or record count. Item lookups always use `(restaurant_id, item_id)`; an item under another restaurant is not a match. Representative seed items may use descriptive stable string IDs.

Duplicate restaurant IDs or duplicate item IDs within a restaurant in stored data are corruption (`500`), not a client conflict or a reason to select the first match. Repeated names/cuisines are permitted; this contract adds no business uniqueness constraint on display fields.

## Persistence and layer boundaries

Continue using UTF-8 JSON at `data/restaurants.json`, the `RESTAURANTS_DATA_PATH` override, and explicit repository path injection. Keep one top-level array and add `menu_items` to each restaurant record when menu support is implemented. No second file, environment variable, database, or schema-version mechanism is required by this contract.

Illustrative stored record (not a change to committed representative data in #30):

```json
[
  {
    "id": "restaurant-001",
    "name": "Cedar Bowl",
    "cuisine": "Japanese",
    "description": "Rice bowls and noodles",
    "menu_items": [
      {
        "id": "item-001",
        "name": "Vegetable bowl",
        "description": "Rice and vegetables",
        "price": "12.50"
      }
    ]
  }
]
```

A missing `menu_items` key on a valid M0 record means an empty menu. An explicit null, wrong type, or invalid item is invalid data, not an empty menu. Reads must not rewrite legacy records. Writes may materialize `menu_items: []`; they must preserve all existing identifiers, restaurant information, and menu items. **Shared foundation ownership:** #35 introduces `MenuItem`, `RestaurantRecord`, and repository loading/saving of complete records as the prerequisite portion of restaurant creation. This foundation must land before #33 or #36; it can be reviewed and merged separately within #35 without waiting for the create endpoint. Those stories integrate the foundation rather than redefining its models. #33 then adds menu browsing and representative menu data; #36 adds restaurant updates; #37 and #38 reuse the same persistence contract. No restaurant writer may serialize the four-field read model back to storage, even before menu browsing lands. #35 must test creating a restaurant alongside existing nonempty menu data and reloading without losing item fields or IDs; #36 must test preserving that data during updates. This assigns scope to stories, not new student assignees.

The route parses HTTP input, declares response/error models, and maps application failures to HTTP responses. The service performs cuisine matching, parent/item existence checks, ID generation, and update orchestration. The repository alone loads, validates, and saves records. There is no frontend or service file access.

The repository validates the full result before saving. Its mutation boundary returns the validated records that were saved, and services derive write responses from that result rather than from a callback's pre-validation object. A successful write response means persistence completed; a new repository/application instance must see the result. Write operations must preserve unrelated records and items. Implement replacement through a temporary file in the same directory and atomic replacement, with cleanup on failure; serialize each read-modify-write operation within the supported single-process application to avoid lost updates. Do not claim cross-process locking or crash durability beyond the implemented/tested guarantees. The feature PR must document this execution limit; atomic replacement alone does not coordinate multiple writers. An unsuccessful save must not truncate or silently reset the existing file.

**Synchronization across requests:** #35 introduces one module-level `threading.Lock` in the repository module, shared by all repository instances and all restaurant/menu mutations in the process. Do not allocate it in the constructor or per-request dependency. A single lock across configured paths is sufficient for this small application; requests still resolve their own storage paths. Hold it across the entire mutation: load current records, check parent/item existence and ID uniqueness, apply the service-defined change, validate, and atomically replace the file. A repository mutation boundary runs the service change operation under this lock. Do not save a stale collection read before locking; repeat any earlier existence check against the locked current state. Release the lock on success or exception using a context manager, and do not reacquire the non-reentrant lock inside the boundary.

The #35 foundation tests overlapping mutations through two independently constructed repositories sharing one temporary file, verifies both changes survive reload, and verifies a failed mutation releases the lock. The same foundation supports #37's menu-item creation. The #36 tests also cover overlapping updates to different fields of one restaurant through independent services/repositories. Atomic replacement protects file contents; the shared lock protects the read-modify-write sequence. Multiple worker processes and external file writers are outside the guarantee.

One file keeps parent relationships and writes together and reuses the existing test-isolation configuration. The trade-off is reading/writing the whole dataset and needing write coordination. Separate restaurant/menu files would isolate data types but introduce cross-file consistency and additional configuration without a current requirement. Revisit this choice if later requirements need independently managed menus or multiple processes.

## Responses and failure precedence

| Condition | HTTP response |
| --- | --- |
| Existing restaurant, including no menu items | `200`; restaurant or menu read response |
| Unknown restaurant on any restaurant-scoped operation | `404`, `{"detail":"Restaurant not found"}` |
| Known restaurant but unknown item under that parent on item update | `404`, `{"detail":"Menu item not found"}` |
| Invalid write body or blank cuisine filter rejected by request validation | `422`, FastAPI validation-error body with a `detail` array |
| Missing/unreadable file, malformed JSON, invalid stored records/relationships, or save failure | `500`, `{"detail":"Restaurant data is unavailable"}` |

Request validation happens first. For valid requests, load and validate storage before distinguishing existing from missing resources. Check restaurant existence before item existence. Do not convert a storage failure into `404`, an empty list/menu, or success. Return generic storage errors without local paths, exception messages, or stored data. An arbitrary nonempty opaque ID is a valid lookup value; an unknown one is `404`, not a UUID-format validation failure. A missing URL segment may fail route matching rather than model validation.

The shared request-validation handler preserves the `422` response's `detail` array even when rejected input contains non-finite numbers or invalid Unicode. Non-finite numbers in error diagnostics are represented as strings (`"nan"`, `"inf"`, or `"-inf"`); Unicode is JSON-escaped. This affects error serialization only and does not make those values valid request data.

The details and menu GET operations have no body or validated query input and impose no ID constraint beyond a nonempty path segment. They define no `422` case: an unknown opaque ID returns `404`, and a missing segment fails route matching. Their feature PRs must align generated OpenAPI with these responses, removing an automatically inserted `422` response if necessary. Write operations retain `422` for body validation; the filtered list retains it for a blank cuisine value.

Creation returns the server-assigned ID in its read response only after saving. This contract does not promise idempotency for repeated POST requests: callers must not assume a retry cannot create another record. No `401`/`403` contract is added because the M1 issue plan excludes authentication/authorization.

### API examples

Restaurant creation request:

```json
{"name":"Cedar Bowl","cuisine":"Japanese","description":"Rice bowls and noodles"}
```

Example `201` response (ID is illustrative, not fixed):

```json
{"id":"9d2e8f04-8753-4c0f-961d-e2f9b4b8fa5d","name":"Cedar Bowl","cuisine":"Japanese","description":"Rice bowls and noodles"}
```

`PATCH /restaurants/restaurant-001` with `{"description":"Bowls and seasonal noodles"}` returns all four restaurant fields, preserving `id`, `name`, and `cuisine`.

`GET /restaurants/restaurant-001/menu` for the stored example above returns:

```json
{"restaurant_id":"restaurant-001","items":[{"id":"item-001","name":"Vegetable bowl","description":"Rice and vegetables","price":"12.50"}]}
```

`POST /restaurants/restaurant-001/menu/items` accepts `{"name":"Vegetable bowl","description":"Rice and vegetables","price":"12.50"}` and returns `201` with those fields plus a generated `id`. `PATCH /restaurants/restaurant-001/menu/items/item-001` with `{"price":"13.00"}` returns the complete updated item and preserves its identity and parent.

## Child implementation and verification checklist

| Story | Contract sections to use | Required evidence to add in the feature PR |
| --- | --- | --- |
| [#31](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/31) details | Inventory, `Restaurant`, failures | Known/unknown ID; storage failure; unchanged response fields |
| [#32](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/32) filter | Filtering, inventory | Unfiltered parity; case/whitespace handling; exact match; no match; blank query; storage failure |
| [#33](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/33) menu | Models, relationships, persistence; consumes #35's foundation | Representative menu data; parent scoping; empty legacy menu; unknown parent; corrupt/duplicate data; unchanged list shape |
| [#35](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/35) create restaurant | Owns shared persistence models and mutation lock, then create model and IDs | Cross-instance overlapping writes; lock release after failure; nonempty menus preserved; `201`; reload survival; generated ID; invalid/extra fields; save failure; existing records preserved |
| [#36](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/36) update restaurant | Partial updates, persistence | Omitted fields/ID/menu preserved; empty/null/invalid payload; unknown ID; reload; save failure |
| [#37](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/37) add item | Item model, parent, IDs | Correct parent; price/text validation; unknown parent; generated ID; reload; existing items preserved; save failure |
| [#38](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/38) update item | Partial updates, scoped lookup | Correct item updated; wrong parent/missing item; ID/parent preserved; invalid payload; reload; save failure |

The customer frontend in [#34](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/34) consumes list and detail responses. [#39](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/39) still owns choosing the management frontend operation; this backend contract does not select it on the team's behalf.

For every feature, follow [TESTING.md](TESTING.md): tests first, isolated temporary storage, and no writes to committed data. Verify the declared Pydantic response model and generated OpenAPI descriptions, parameters, request bodies, success statuses, and error responses against the relevant row above. Frontend callers can use the stated schemas without depending on JSON file structure. Cross-feature verification belongs to [#40](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/40).

## Adoption and future changes

- The team adopted the menu fields and combined menu/items response through PR #48. The supplied M1 source requires menu and item retrieval but prescribes neither separate endpoints nor exact fields; the menu response exposes both.
- Use the agreed cuisine filter, PATCH semantics, single logical menu, item price representation, ID ownership, and persistence guarantees. Review future changes together before dependent feature branches use them.
- Source conflict resolved: the earlier full-project brief treated filtering as optional, while the supplied M1 Functional Scope explicitly requires search **or** filter. The newer M1 source takes precedence; `CONTRIBUTING.md` now records that exception.
- PR #48's merge records team adoption; no separate adoption confirmation is required for #30. The user's clarification corrects the earlier pending-status interpretation. Individual provenance review and feature PR approval remain separate.

Authentication/authorization, carts, checkout, orders, deliveries, additional management operations, and frontend framework selection remain outside #30. This contract does not fulfill the implemented-design Decision Receipt in #41 or the integration/submission work in #42.
