# Authentication and authorization design (M2)

## Status

Proposed for [#78](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/78)
on 2026-11-05 by Sreeram (`SreeramNara`). **Needs review by Thomas and Gwantana
before adoption.** It changes their work: restaurant/menu management routes (#94)
become protected, and the frontends (#39, #69, #99) need sign-in.

This document decides **how** callers are identified and **who** may do what.
Registration, login, profile, deactivation and route protection are implemented in
#79–#84; menu availability protection is implemented in #94. This PR itself adds only:

- password redaction in the shared 422 handler (an actual finding, see
  [Credential handling](#credential-handling));
- the pinned password-hashing library;
- isolated test fixtures for two customers, a restaurant user and an administrator.

It extends the [M2 contract](M2_API_CONTRACT.md) and [data model](DATA_MODEL.md);
where they differ, this document is the newer proposal for authentication.

## What the sources require

| Source | Requirement |
| --- | --- |
| Project brief §3, *Authentication & roles* | "Support authentication and appropriate authorization for customers, restaurant users, and system administrators." |
| Project brief §3, *Menu management* | Customers browse menus; "authorized restaurant users" add, update, deactivate and manage menu-item availability. |
| Project brief §3, *Customer accounts* | Register, sign in, retrieve/update profile, update delivery address, deactivate, retrieve order history. |
| Project brief §5 | The backend is authoritative; "users can only perform operations permitted by their role". |
| M2 §3, *Customer Accounts* | "sign in using the authentication mechanism required by the project". |
| M2 §3, *Authentication and Authorization* | Backend identifies authenticated users and enforces role-restricted operations; unauthenticated and unauthorized requests return appropriate API responses; the team can explain where these decisions are enforced. |
| M2 §4 | A deactivated customer cannot create or modify a cart; checkout requires a valid customer state. |
| M2 §12 (demo) | The TA may attempt an operation with a deactivated customer, send an unauthorized request directly to the API, and change availability before checkout. |
| [CONTRIBUTING](../CONTRIBUTING.md#backend-authority-and-reliability) | Use established password-hashing/authentication libraries; never store plaintext passwords or invent cryptography. |

**Finding:** neither the brief nor M2 names a mechanism. There is no requirement for
JWT, cookies, OAuth or a particular token format, and nothing on token lifetime,
administrator powers, account reactivation, or how restaurant users are created and
linked to restaurants. The "mechanism required by the project" is therefore the
team's documented choice below. Sources: the project brief and M2 assignment text
supplied by Sreeram (M2 pasted on 2026-11-05).

**Not verified:** the [Figma mockup](https://saved-camp-64731504.figma.site/) could
not be opened from the drafting environment. A reviewer should check its sign-in
and account screens before adoption.

## Mechanism

| Decision | Choice | Why |
| --- | --- | --- |
| Credentials | Email and password for every account | Matches "register" and "sign in"; no source asks for anything else. |
| Password storage | [`pwdlib`](https://pypi.org/project/pwdlib/) `PasswordHash.recommended()` (Argon2id), pinned as `pwdlib[argon2]==0.3.1` | Established library; Argon2id is a current recommended password hash; we write no cryptography ourselves. Only the hash is stored. |
| Password rules (proposed) | 8–128 characters, case-sensitive, never trimmed | Team choice. The upper limit bounds hashing cost. |
| Login | `POST /auth/login` for customers, `POST /auth/staff/login` for restaurant users and administrators. Body `{"email", "password"}`, response `{"access_token", "token_type": "bearer"}` | Separate stores need no cross-store lookup at login. The response matches the M2 contract. |
| Token | `secrets.token_urlsafe(32)`: an opaque 256-bit random string, returned once | Nothing inside it to decode or forge. |
| Token storage | `data/sessions.json` (`SESSIONS_DATA_PATH`) keeps the token's SHA-256 digest, `account_id`, `account_type`, `issued_at`, `expires_at` | A leaked sessions file contains no usable tokens. SHA-256 is enough because the token is long and random; slow hashing is only needed for human-chosen passwords. |
| Lifetime (proposed) | 24 hours, then 401 and sign in again | Limits how long a stolen token works. Services take an injectable clock so tests are deterministic. |
| Transport | `Authorization: Bearer <token>` header | Agreed in the M2 contract; easy to send from tests, Swagger and the frontend. |
| Logout and session cleanup | Not in M2 | Not required. Deactivation does not depend on deleting sessions (see [lifecycle](#customer-state-lifecycle)). |

**Why not JWT?** A JWT needs a signing secret, which we would have to configure and
keep out of the repository. It also cannot be revoked before it expires. Server-side
tokens fit the project's JSON persistence, survive restart, and are simpler to explain.
The cost is one sessions-file read per protected request, which is fine at this scale.

**Why not cookies?** They add CSRF concerns and differ from the bearer transport already
agreed in the contract. How the frontend keeps the token in the browser is decided in #99.

## Roles, accounts and ownership

| Role | Created by | Stored in | Owns |
| --- | --- | --- | --- |
| `customer` | Self-registration, `POST /customers` (#79) | `customers.json` with `role: "customer"` | Their own profile, cart and orders |
| `restaurant_user` | Provisioning only; no public sign-up | `staff.json` (`STAFF_DATA_PATH`) | The restaurants listed in its `restaurant_ids` |
| `administrator` | Provisioning only | `staff.json` | Nothing; see below |

- The role always comes from the stored account, never from a request body. Registration
  forbids unknown fields, so `{"role": "administrator"}` is a 422.
- Staff accounts are created by a small local provisioning command. It prompts for the
  password and writes the hash, so no real credential is ever committed. No issue owns this
  yet: see [open questions](#open-questions-for-review).
- **Administrator in M2:** the only proposed power is creating restaurants (platform
  onboarding, brief §2/Workflow 5). The brief gives menu management to restaurant users,
  so administrators do not edit menus. There is no reactivation, customer management,
  role assignment, or reading of other customers' data. Reporting comes in M3.

## Access matrix

Customer resources use `/customers/me/...`, so ownership comes from the token, not from
an ID the client can change. The only client-supplied IDs are order IDs and restaurant IDs.

| Operation | Anonymous | Customer, active | Customer, inactive | Restaurant user | Administrator |
| --- | --- | --- | --- | --- | --- |
| M1 reads: list, filter, details, menu | Allow | Allow | Allow | Allow | Allow |
| Register (`POST /customers`) | Allow | Allow | Allow | Allow | Allow |
| Customer login | Allow (credentials checked) | — | Allowed, read-only access | — | — |
| Staff login | Allow (credentials checked) | — | — | — | — |
| Read own profile (`GET /customers/me`) | 401 | Allow | Allow | 403 | 403 |
| Update own name/address (`PATCH /customers/me`) | 401 | Allow | 403 inactive | 403 | 403 |
| Deactivate own account | 401 | Allow → inactive | 200, unchanged | 403 | 403 |
| Read own existing cart (`GET .../cart`) | 401 | Allow | Allow | 403 | 403 |
| Create cart, add/update/remove/clear items | 401 | Allow | 403 inactive | 403 | 403 |
| Checkout | 401 | Allow | 403 inactive | 403 | 403 |
| Own order list / own order detail | 401 | Allow | Allow | 403 | 403 |
| Another customer's order ID | 401 | 404, same as missing | 404 | 403 | 403 |
| Create restaurant (`POST /restaurants`) | 401 | 403 | 403 | 403 | Allow |
| Update restaurant, add/update menu item, change availability | 401 | 403 | 403 | Allow if in `restaurant_ids`; otherwise 403; missing restaurant 404 | 403 |

**M1 compatibility:** paths, request bodies and responses of the eight M1 operations do
not change. The four management writes now require a staff token. That is a breaking
change for unauthenticated clients: the M1 management tests and the Create/Edit
restaurant pages must send a token once #84/#94 land.

## Where identity ends and authorization begins

```text
Request ──▶ Route dependency: get_current_principal       (identity)
              reads Authorization header
              AuthService.resolve(token) ──▶ Principal(account_id, role)
              any failure ──▶ 401 + WWW-Authenticate: Bearer
        ──▶ Service method(principal, ...)                  (authorization)
              reloads current account/status under the workflow lock
              checks role, ownership, customer state ──▶ domain error
        ──▶ Route maps domain errors to 403 / 404 / 409
```

- **Identity (route layer):** a FastAPI dependency answers only "who is calling?". It
  checks the header, finds an unexpired session by digest, and confirms the account still
  exists. It returns `Principal(account_id, role)` and does **not** check status, role
  permissions or ownership.
- **Authorization (service layer):** every protected service method takes `principal`
  as an argument and decides "may this caller do this, now?". These are business rules,
  so they belong in services, where they can be tested without HTTP. Customer status must
  be re-read under the workflow lock: a checkout racing a deactivation must see the
  committed status, which a check made earlier in the request cannot guarantee.
- **Shared helpers** in `app/services/access.py` (#84) stop owners duplicating checks:
  - `require_customer(principal, customers, *, active)` returns the current `Customer`
    or raises `NotPermitted` or `CustomerInactive`;
  - `require_restaurant_manager(principal, staff, restaurant_id)` returns the
    `StaffAccount` or raises `NotPermitted`.
- **How Thomas receives identity:** his checkout and order routes declare the same
  `get_current_principal` dependency and pass the `Principal` to his services. Inside the
  workflow lock, checkout calls `require_customer(principal, customers, active=True)`;
  order reads use `active=False`. #94 calls `require_restaurant_manager`. He never parses
  tokens or reads `sessions.json`. These are the agreed interfaces:
  [`Principal`](../tests/contracts/auth.py), the existing `CustomerAccess`, and a new
  `StaffAccess.get_staff(id) -> StaffAccount | None`.

## Errors and precedence

| Condition | Status / `detail` |
| --- | --- |
| Missing header, wrong scheme, malformed, unknown or expired token, or account no longer exists | 401 `Authentication required`, `WWW-Authenticate: Bearer`. All cases look the same. |
| Login with unknown email or wrong password | 401 `Invalid email or password`, `WWW-Authenticate: Bearer`. The same message for both, so emails cannot be discovered. |
| Wrong role, or a restaurant the user does not manage | 403 `Operation not permitted` |
| Inactive customer attempts a restricted operation | 403 `Customer is inactive` |
| Missing restaurant on a management write | 404 `Restaurant not found` (restaurants are public, so existence is not secret) |
| Missing or another customer's order | 404 `Order not found` |
| Email already registered (case-insensitive, customers and staff) | 409 `Email is already registered` |
| Invalid request body | 422 validation `detail` array; password values are redacted |
| Unreadable or corrupt customers, staff or sessions store | 500 `Customer data is unavailable` / `Authentication data is unavailable`. Never 401: corruption must not look like "not signed in". |

**Precedence:** identity (401) → role and customer state (403) → body validation (422) →
existence (404) → ownership (403) → business state (409) → writes. This matches the
[M2 contract](M2_API_CONTRACT.md#shared-errors-and-precedence).

Two facts were checked against the pinned FastAPI with a probe app (results in the PR):

- A 401 raised by the auth dependency is returned **before** body-field validation, so
  an anonymous request with an invalid body gets 401, not 422.
- **Malformed JSON** (a body that does not parse) is rejected with 422 **before** the
  dependency runs. This is FastAPI's order. It leaks nothing about the account, and
  #84's tests should record it rather than work around it.

## Customer state lifecycle

1. Registration creates an `active` customer.
2. Deactivation sets `inactive` under the workflow lock. It keeps the ID, cart and orders.
   Deactivating again returns 200 unchanged. There is no reactivation or deletion.
3. **Tokens issued before deactivation keep identifying the customer, but cannot bypass
   it:** every protected request reloads the stored status, so cart changes and checkout
   return 403 `Customer is inactive` while profile, cart and order reads still work.
   Sessions do not need to be deleted for this to hold.
4. An inactive customer may still sign in, for read-only access (as the M2 contract
   proposed).
5. A token older than 24 hours returns 401. Staff accounts have no deactivation in M2;
   removing a staff record makes its tokens return 401.

## Credential handling

- Only Argon2id hashes are stored, in `customers.json` and `staff.json`. Public models
  (`Customer`) exclude `password_hash` and `role`. Responses, logs and orders never
  contain passwords, hashes or tokens.
- Tokens are returned once, at login. Only their SHA-256 digests are stored.
- **Finding fixed in this PR:** the shared 422 handler echoed rejected input back to the
  client. A probe showed that a too-short password was returned in the response. Worse,
  a **valid** password was returned whenever another field was missing, because
  Pydantic reports the whole body as that error's input. `app/api/errors.py` now replaces
  any `password` value (any letter case, at any nesting level) with `"[redacted]"` before
  responding. [Tests](../tests/test_credential_redaction.py) failed before the change and
  pass after it. Other fields are still reported as before.
- Committed data has no hashes or tokens: `data/` gets no seeded accounts. Demo staff
  accounts are provisioned locally. Example and fixture passwords are labelled dummies.
- Passwords are never sent in URLs or query strings.

## Test fixtures

[`tests/contracts/auth.py`](../tests/contracts/auth.py) and the `auth_accounts` fixture in
[`tests/contracts/conftest.py`](../tests/contracts/conftest.py) write isolated
`customers.json`, `staff.json` and `sessions.json` under `tmp_path`. They point
`CUSTOMERS_DATA_PATH`, `STAFF_DATA_PATH` and `SESSIONS_DATA_PATH` at those files.

| Key | Account | Use |
| --- | --- | --- |
| `customer_a` | `customer-001`, Ada, active | Owner in ownership tests; also has an expired session (`expired_token`) |
| `customer_b` | `customer-002`, Ben, active, mixed-case email | The "other customer" in ownership denials |
| `restaurant_user` | `staff-001`, manages `restaurant-001` only | Allowed on restaurant-001, denied on restaurant-002 |
| `administrator` | `staff-002`, manages nothing | Denied menu management |

Each account has a dummy password and an active session token. `auth_accounts.headers(key)`
builds the `Authorization` header. Sessions are issued relative to the fixed clock
`FIXED_NOW`, so implementations must accept an injected clock. The fixture's own tests
check isolation, unique identities, Argon2id hashes that verify only their own password,
that no password or token appears in any file, ownership of a real restaurant, and digest-only
sessions. Registered customers must still be created through the real API in #79's tests.

## Required direct-API denial tests

These bypass the frontend. Each must also check that stored files are unchanged after a denial.

| # | Request | Expected | Issue |
| --- | --- | --- | --- |
| 1 | Each protected route with no `Authorization` header | 401 + `WWW-Authenticate: Bearer` | #84 |
| 2 | `Token abc`, `Bearer` with nothing after it, unknown token, `expired_token` | 401, identical body | #80/#84 |
| 3 | No token and an invalid body | 401, not 422 | #84 |
| 4 | Login with wrong password vs unknown email | Identical 401 | #80 |
| 5 | Register `ben.example@example.invalid` when Ben exists | 409 | #79 |
| 6 | Register with `"role"` or `"status"` in the body | 422, no account created | #79 |
| 7 | Any 422 on register/login | No submitted password in the response | #79/#80 |
| 8 | `customer_b` reads `customer_a`'s order ID | 404, same as a missing order | #84/#93 |
| 9 | Deactivate `customer_a`, then reuse the old token for cart create/add/update/remove/clear and checkout | 403 `Customer is inactive`, files unchanged | #83/#84 |
| 10 | Same deactivated token for profile, cart and order reads; deactivate again | 200 | #83 |
| 11 | Customer or administrator token on `PATCH /restaurants/restaurant-001` and on availability | 403 | #84/#94 |
| 12 | `restaurant_user` on `restaurant-002`, and on a missing restaurant | 403, and 404 | #94 |
| 13 | Staff token on `/customers/me`, cart and checkout | 403 | #84 |
| 14 | Corrupt `sessions.json` with a valid-looking token | 500, not 401 | #80 |
| 15 | Checkout racing deactivation | Deactivation first → 403, no order, cart unchanged | #91/#95 |

## Documentation and setup changes

- **This PR:** `requirements.txt` adds `pwdlib[argon2]`. The install command is unchanged,
  so [Quick setup](QUICK_SETUP.md) needs no edit; the dependency list in
  [First-time setup](FIRST_TIME_SETUP.md) is updated. The contract, data model, example
  errors and M2 evidence link here.
- **When implemented (#79/#80/#84):** both setup guides document the new data-path
  variables and empty store files, plus the provisioning command. The README explains
  signing in. OpenAPI shows the bearer security scheme and 401/403 responses (#103).

## Open questions for review

1. Do the Figma sign-in/account screens match this design?
2. Should administrators create restaurants (proposed), or should restaurant users?
3. Who implements the staff provisioning command? It needs an issue; #84 is a candidate.
4. Are 8–128 character passwords and 24-hour tokens acceptable?
5. Should inactive customers still sign in for read-only access (current proposal), or be refused at login?
