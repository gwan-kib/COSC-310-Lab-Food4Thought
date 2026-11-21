# Clear shopping cart implementation plan

> Execute inline with `superpowers:executing-plans`; user authorized the recommended implementation without an interview. Use a fresh final code review.

**Goal:** Implement issue #89's authenticated, idempotent cart clear.

**Architecture:** Add `CartService.clear_cart(customer_id: str) -> CartView`
and a thin `DELETE /customers/me/cart/items` route. Reuse the existing customer,
cart, catalog and order stores, shared workflow lock and atomic cart save.
Keep checkout's conditional reset unchanged.

**Tech stack:** Existing Python 3.12, FastAPI, Pydantic, pytest, JSON stores;
required Chromium regression tests. No new dependency or storage format.

**Spec:** [Issue #89](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/89),
[M2 contract](../../M2_API_CONTRACT.md), [auth design](../../AUTH_DESIGN.md),
[data model](../../DATA_MODEL.md), [M2 evidence](../../milestones/M2.md).

## Constraints and source review

- Start from refreshed main `9474129`; isolated branch `feature/89-clear-shopping-cart`.
- Live #77/#78 are closed; auth design PR #106 is merged. Some documentation still
  says proposed/pending: use the integrated code and reviewed behavior.
- #89 is assigned to Thomas; its issue body still names Sreeram as coordinator.
  Native assignment and this handoff authorize Thomas's scoped service extension.
- PR #123 (#88) and #125 (#87) edit the same cart modules. Keep changes additive;
  do not copy their methods, schemas or repositories. Reconcile at integration.
- Canvas and full live board fields were inaccessible. Use captured course text;
  the visible issue board status is Todo. No board edits or peer approval claimed.
- Customer ID comes only from the bearer principal. Recheck active status under
  the workflow lock. Missing cart is 404; a saved purchased revision is 409.
- Validate existing references before clearing: unavailable items can be cleared,
  missing restaurant/items remain storage errors under the shared contract.
- Preserve cart/customer IDs; nonempty clear advances revision once and releases
  restaurant; already empty clear returns the same view without saving.
- Build the entire validated empty response before one save. Never mutate a
  loaded cart in place. No new checkout route or frontend in this issue.

## Review focus

Tests must catch partial deletion on save failure, foreign-cart writes through
spoofed identity, bypassing checkout recovery, a write on repeated clear, and
clearing corrupt references as though they were a valid empty cart.

## Task 1: Service and API with integration evidence

- [x] Run the unchanged suite with required Chromium tests; record baseline.
- [x] Add `tests/test_clear_cart.py` using real temporary stores and auth fixtures.
  Verify two-line clear, zero totals, stable IDs, revision +1, one complete save,
  restart, repeat/no-write, new restaurant selection, missing cart, auth/role/state
  denials, foreign-customer isolation, corrupt stores/references and failed save.
  Exercise real CheckoutService save/reset failure, blocked clear, replay recovery,
  and later clear without altering the saved order. Pin OpenAPI response/security.
- [x] Run `python -m pytest -q tests/test_clear_cart.py` and observe missing-route
  or missing-service failures before implementation.
- [x] Add service method and route using existing error translation and models;
  validate the original and resulting views before saving, under workflow lock.
- [x] Run focused tests; then compile, run full required-browser pytest, and check
  `git status --porcelain --untracked-files=all --ignored -- data/` is empty.
- [x] Update M2 contract, both setup guides, testing/evidence and provenance.
  No schema or data migration. Record exact results and pending student review.
- [x] Inspect all changes and obtain agent code review (not human peer approval).
  Prepare a PR description from the repository template; leave publishing,
  human review and merge explicit in the handoff.

## Execution record

Baseline: Python 3.12 virtual environment with requirements and Chromium installed;
`python -m pytest -q` with `REQUIRE_BROWSER_TESTS=1`: 704 passed in 44.15s.

Red: `python -m pytest -q tests/test_clear_cart.py --tb=short`: 27 failed for
missing DELETE route, `clear_cart` service method and OpenAPI operation.
Green: the same focused module passed all 27 after implementation.

Agent review identified a real inconsistent-backup case: an older restored cart
could be cleared into a revision already in durable order history, returning the
old receipt and preventing the next clear. Added
`test_clear_rejects_a_restored_cart_whose_next_revision_was_already_purchased`;
its first run failed (200 vs 500). Rejecting the proposed view's non-null receipt
before save fixed it. All 28 focused cases then passed in 3.63s.

Ruling: keep the optional duplicate receipt-read optimization out of this patch;
it would refactor a shared service with no demonstrated performance problem.
Sibling #87/#88 need textual reconciliation at integration; all distinct methods
and routes must survive. Agent review is not human peer approval.

Verification limitation: full-suite runs intermittently stalled and were interrupted.
Two quiet runs, a later verbose run and an uncaptured run did not complete;
an additional asyncio-debug diagnostic run was stopped without a result.
The captured 30-second faulthandler dumps point to existing
`test_profile_update_with_a_raw_or_form_body_never_echoes_a_password`, waiting in
Starlette's TestClient/AnyIO portal teardown on Windows. No assertion failure was
reported; its cause is unresolved. A verbose diagnostic run before the receipt
regression completed all 731 tests in 43.31s. No unrelated test was weakened or
skipped. Final post-fix verification splits the existing customer-account API
module into its own process and runs every other test with Chromium required.
The separate account module passed 57 tests in 2.75s, including both raw/form
profile-validation cases. This is not proof that the single-process hang is fixed.

Final commands from the issue worktree (Python 3.12 virtual environment):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_clear_cart.py
.\.venv\Scripts\python.exe -m compileall -q app
$env:REQUIRE_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -u -m pytest -q --ignore=tests/test_customer_accounts_api.py -o faulthandler_timeout=30
.\.venv\Scripts\python.exe -u -m pytest -vv tests/test_customer_accounts_api.py -o faulthandler_timeout=30
git status --porcelain --untracked-files=all --ignored -- data/
git diff --cached --check
```

Results: 28 focused passed; compilation exit 0; 675 tests passed in 43.01s
(Chromium required) plus all 57 account API tests passed in 2.75s. Together these
cover every one of the 732 collected cases, with no skips. Data status was empty
and whitespace checks passed. Logs stay local in the ignored virtual environment.
The complete staged diff was inspected. A PR body was prepared locally outside
the checkout. At the initial implementation handoff, nothing had been pushed,
posted, merged or marked Done.

Task 1: implementation and split-process local verification complete. Human peer
review, remote CI, single-process test-run reliability and integration remain pending.

Publication follow-up: Thomas requested the push, PR creation and CI monitoring.
Branch `feature/89-clear-shopping-cart` was pushed and [PR #126](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/126)
was opened against `main` with the prepared description. Remote check results
are tracked on the PR; human peer approval, student explanation and merge are
not implied by publication or agent verification.

During publication, #119 merged into main at `c2d4aa8`. The branch merged that
revision, retaining both README endpoint rows and all provenance entries. The
automatic setup/contract/testing/milestone merges were inspected. No feature code
needed conflict resolution. `python -m compileall -q app` succeeded and
`python -m pytest -q tests/test_clear_cart.py tests/test_order_details.py` passed
59 tests in 5.86s; whitespace and committed-data guards passed. The hosted full
suite for this integrated revision is recorded in [PR #126 checks](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/126/checks).
