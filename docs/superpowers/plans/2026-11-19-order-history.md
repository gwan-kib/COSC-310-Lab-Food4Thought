# Customer order history implementation plan

## Endpoint integration continuation — 2026-11-20

Thomas authorized finishing the endpoint against the merged auth foundation and
creating a PR. The earlier service-only scope and dependency notes below are
historical. Main `95c7c8e` includes #114/#115: bearer resolution, customer storage,
customer-role prechecks, and real cart/catalog/checkout services. #84 remains
open for broader rollout; it does not block history. #93 is being implemented
in separate `order_details` modules; preserve that parallel work.

- [x] Merge current main, retaining both provenance histories, and run the baseline suite.
- [x] Add failing `tests/test_order_history_api.py` cases using real tokens/stores for scoped insertion-order responses, empty results, inactive reads, missing/invalid identities, wrong roles, damaged stores and OpenAPI.
- [x] Bind the existing history service to a service-layer customer resolver using `CustomerRepository`; role denial precedes customer/order reads, missing customers use `AuthenticationRequiredError`, and inactive customers remain readable.
- [x] Add a thin `app/api/routes/order_history.py` router using `CurrentCustomer`, register it in `app/main.py`, and map 401/403/500 without exposing store errors.
- [x] Verify real registration/login → cart API → real checkout service → history HTTP, plus fresh application/repository reads and unchanged snapshots after current profile/menu changes. Checkout's HTTP route remains #91's scope; no doubles replace its service or participating stores.
- [x] Update README, both setup guides, API/testing/milestone docs and provenance; run focused tests, compileall, required-browser full suite, data isolation and diff/link checks.
- [x] Obtain an independent agent review, commit, push, create and attach [PR #120](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/120). Human review and merge remain pending; published-head CI is tracked in the PR checks.

The production callback interface stays intact. Its new resolver adapts the
merged customer repository and principal to read authorization; token parsing
and session verification remain exclusively in the shared auth foundation.

Continuation results: 636 baseline tests passed; 24 API tests failed before the
endpoint existed; 80 focused tests and 660 required-browser tests passed afterward,
with no skips. Compilation, data isolation, whitespace and 113 local documentation
links passed. Independent agent review found no blocking defects. Human review
and merge are separate from these checks.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Track verification below.

**Goal:** Start #92 with a customer-scoped history service using the merged order repository, while keeping missing HTTP/auth integration explicit.

**Architecture:** `OrderHistoryService.list_orders(principal)` acquires the existing workflow lock, calls an injected customer authorization helper, then delegates filtering to `OrderRepository.list_for_customer(customer.id)`. Bind #84's `require_customer(principal, customers, active=False)` when available, following the callback pattern used by `CheckoutService`. Return saved `Order` snapshots unchanged, in persisted insertion order.

**Tech stack:** Existing Python 3.12, Pydantic, pytest, JSON repository and Playwright regression suite; no new dependencies.

**Spec:** [Issue #92](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/92), [M2 contract](../../M2_API_CONTRACT.md), [auth access matrix](../../AUTH_DESIGN.md#access-matrix), and [M2 source record](../../milestones/M2.md).

## Scope and dependency decision

Thomas requested waiting for #111, then starting when prerequisites permit. PR #111 merged into `31e4320` on 2026-11-19. Issues #77/#78 are closed; #92 remains assigned to Thomas with no overlapping PR. #93 is a coordination dependency, not a prerequisite. Reuse #111's model/repository without changing its persistence format.

#79/#80/#84 still lack runtime implementations. Independent persisted fixtures are explicitly allowed by #92. Implement the service now; leave `GET /customers/me/orders`, real bearer authentication, 401/403 mapping and full real checkout workflow verification pending. Do not add placeholder production authentication or import test contracts into application code. PR #113's cart implementation is also unmerged; #110 touches shared test isolation. Avoid modifying those shared fixtures.

The earlier option was to stack on draft #111. Thomas chose waiting for its merge; that gate is now satisfied. Scope remains backend only, without #93's detail route or the frontend owner's screens.

The captured M2 assignment remains the available course source; live Canvas could not be reverified. The contract's older unchecked adoption notes lag closed #77/#78 and merged #106. A post-merge #106 review still requests confirmation of unified login and a credential-redaction fix (#110); this change does not settle those decisions or change the documented order-read permissions.

## Global constraints

- Only a trusted, authorized customer's ID selects history; inactive customers retain read access.
- No orders means `[]`; missing, unreadable, malformed or inconsistent storage remains an error.
- Read operations preserve snapshots, stable relationships and current cart bytes.
- Authorization runs under the shared workflow lock before reading order storage.
- File I/O stays in the existing repository; all tests use isolated paths.
- No endpoint/OpenAPI additions until real identity and access dependencies can be wired.

## Review focus

- A1/B1/A2 interleaving must filter B1 without sorting A's snapshots by ID.
- A customer with no orders must not mask corruption elsewhere in the store.
- Denied or missing identity must stop before private order storage is read.
- Fresh-instance reads must preserve snapshots after current profile/catalog changes.
- A newly persisted checkout receipt must appear on the next history read without caching.

## Task 1: Service and persisted-history tests

**Files:** create `app/services/order_history.py` and `tests/test_order_history_service.py`. Reuse existing repository, models and test-only boundary doubles.

**Interfaces:** consume `OrderRepository.list_for_customer(customer_id: str) -> list[Order]`; produce `OrderHistoryService(require_customer, orders).list_orders(principal) -> list[Order]`. The callback returns a current customer with `id` or raises the access/customer-store error unchanged.

- [x] Run baseline `python -m pytest -q` with `REQUIRE_BROWSER_TESTS=1`.
- [x] Write independent A1/B1/A2 JSON fixtures and tests for filtering, insertion order, empty results, fresh reloads, unchanged files and corrupt/missing/unreadable storage. Use nonlexical order IDs to detect accidental sorting.
- [x] Add authorization-boundary tests proving the original principal reaches the helper under the workflow lock and denial precedes any order read. These test delegation, not real authentication.
- [x] Run `python -m pytest -q tests/test_order_history_service.py` and confirm missing service behavior fails before implementation.
- [x] Implement the small service, then rerun focused tests to green.
- [x] Exercise real `CheckoutService` plus `OrderRepository` followed by history reload; label remaining customer/cart/catalog/auth doubles explicitly.

## Task 2: Documentation, verification and handoff

**Files:** update `docs/M2_API_CONTRACT.md`, `docs/TESTING.md`, `docs/milestones/M2.md`, and `docs/PROVENANCE.md`. Review both setup guides; change them only if operational instructions change.

- [x] Document the service boundary and pending HTTP/auth work without claiming a working endpoint.
- [x] Run focused history/repository/checkout tests, `python -m compileall app`, and the full required-browser suite.
- [x] Verify `git diff --exit-code -- data/`, `git diff --check`, all new files, and local documentation links.
- [x] Obtain an independent agent code review; this does not replace human peer review.
- [x] Record actual test results and AI provenance. Keep the work local and #92 open; no GitHub writes or merge are part of this request.

## Execution record

The initial baseline attempt ran before dependency installation finished and failed on missing packages; that was an environment timing failure, not a product result. After installation, baseline required-browser pytest passed 462 tests. The initial history run (`python -m pytest -q tests/test_order_history_service.py --tb=short`) failed all 19 tests on the missing service before implementation. The focused history/repository/checkout run passed 56 tests; the final required-browser suite passed 481 tests with no skips. Compilation, data-file isolation, whitespace and 65 local documentation-link checks passed. Commands used the new worktree's `.venv/Scripts/python.exe` (Python 3.12.10).

Tasks 1 and 2 are complete within service scope. The independent agent review found no blocking correctness or security defects. Its optional suggestion is a future successful-call test using an opaque principal whose helper-resolved customer ID is the only available owner ID; current successful tests use matching principal/customer IDs. No production defect was identified, so that extra regression test was deferred. The protected endpoint, real authentication and full purchase workflow remain blocked on the explicitly named dependencies above. This is local, uncommitted work; it does not close #92 or constitute human peer approval.
