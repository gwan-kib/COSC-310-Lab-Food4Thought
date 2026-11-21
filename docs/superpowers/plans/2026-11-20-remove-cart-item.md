# Remove cart item implementation plan

> Execute this focused change inline using test-driven development, then obtain a fresh code review. Thomas authorized recommended interview choices on 2026-11-20.

**Goal:** Implement issue #88's authenticated removal and return the current priced cart.

**Architecture:** Extend the existing `CartService` and cart router. Reuse the cart repository's atomic save, workflow lock, current-menu pricing and durable order receipts. Keep the storage schema unchanged.

**Stack:** Existing Python 3.12, FastAPI/Pydantic, JSON, pytest and Playwright.

**Sources:** [Issue #88](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/88), [M2 contract](../../M2_API_CONTRACT.md), [auth design](../../AUTH_DESIGN.md), [M2 evidence](../../milestones/M2.md).

## Dependency check and decisions

- Base: `95c7c8ed289d15f4b05de098bae5608f7c6c52f3`. #77/#78 are closed; PRs #105/#106/#113/#114/#115 are merged. The issue shows Thomas as assignee and Todo. Full board fields and live Canvas assignment could not be accessed; captured course evidence is used.
- #86 remains open for availability integration, but real add-item and auth/cart routes are merged. #109's real availability model is still pending. Exercise unavailable removal through the established catalog seam, without importing that PR's implementation.
- PR #116 changes repository internals; retain `CartRepository`'s public interface. #97's concurrent pricing work must retain this operation's use of the shared cart view. Do not duplicate repositories or pricing rules.
- Existing cart APIs pass the server-resolved customer ID to services; preserve that boundary and recheck current customer state under the workflow lock. The design document's proposed `app/services/access.py` does not exist on this base.
- Use `DELETE /customers/me/cart/items/{item_id}` with no body, returning 200 `CartView`. Missing cart/line gives 404; opaque IDs are not UUID-only. A successful removal increments revision exactly once, preserves IDs/other quantities, and releases restaurant binding on the last line.
- Check active customer, owned cart and selected line before purchased-revision business-state denial. Validate stored menu references from one snapshot before writing; unavailable is valid, missing references remain corruption. Build the resulting response before atomic save.
- Recommended scope: backend, tests, API/data/setup documentation and provenance. Frontend, quantity update, clear-cart, shared-pricing refactor and GitHub publication remain separate work.

## Task 1: Remove one cart line across the existing layers

Files: `app/services/cart.py`, `app/api/routes/carts.py`, new `tests/test_cart_remove.py`; affected API/data/setup/evidence/provenance docs. No repository or dependency changes.

Interface: `CartService.remove_item(customer_id: str, item_id: str) -> CartView`; new `CartItemNotFoundError` maps to 404 `Cart item not found`.

- [x] Run the existing suite in the worktree-local virtual environment with `REQUIRE_BROWSER_TESTS=1` before editing implementation.
- [x] Write tests that DELETE one of two lines, then the last, preserving IDs and quantities and asserting exact current totals. Reload through fresh services/repositories and add a different restaurant's item afterward.
- [x] Cover missing cart/line, opaque or foreign item IDs, caller isolation, absent/invalid/expired tokens, staff roles, old token after deactivation, service-side status recheck, unavailable lines, missing references, corrupt stores, failed atomic replacement and purchased-revision recovery.
- [x] Assert OpenAPI's response model, bearer security, no request body and error descriptions. Run `python -m pytest -q tests/test_cart_remove.py`: expect missing route/method failures before implementation.
- [x] Add the service mutation under `workflow_lock`, construct a validated `CartRecord` and priced `CartView` before `save_cart`, and add the thin protected route/error mapping.
- [x] Run `python -m pytest -q tests/test_cart_remove.py tests/test_cart_api.py tests/test_cart_service.py tests/test_cart_repository.py tests/test_cart_checkout_integration.py`: expect all passing.
- [x] Update both setup guides with the implemented endpoint, M2 contract/data/evidence links and AI provenance with actual validation and pending student review.
- [x] Run `python -m compileall -q app`, full `python -m pytest -q` with required browser tests, `git diff --check`, and CI's `git status --porcelain --untracked-files=all --ignored -- data/` guard. Inspect every changed/new file and obtain an agent review; human teammate review remains pending.

## Execution record

- Initial shared-venv baseline could not collect: `ModuleNotFoundError: pwdlib`. Create an isolated environment from the pinned requirements; this is an environment failure, not a product test result.
- No commit, push, PR, board change or human review is implied by local implementation.
- Baseline: 617 passed, required browser mode. RED: all 30 removal tests failed for missing implementation. GREEN: 106 focused cart tests passed. Full verification: compileall passed; 647 tests passed with required Chromium and no skips; pip check, diff whitespace check and CI's committed-data guard passed. Commands are recorded in the #88 provenance entry.
- Final agent review: no actionable findings; independently reran all 30 removal tests, diff check and data guard. Scope rulings: frontend/quantity/clear are separate tasks; persisted availability awaits #94; trusted customer-ID service boundaries and single-process locking remain the existing implementation conventions. Human review, hosted CI and student understanding cannot be certified by agent checks. Keep the branch/worktree with uncommitted changes for review; no publication or integration performed.

## Publication follow-up

Thomas subsequently authorized commit, push, PR creation and CI monitoring. The
implementation was committed as `55f8e94`. Main advanced to `67417bb`, incorporating
#94 availability and #96's shared JSON helper, so publication integrates that revision.
The provenance conflict retained both contributors' records. One removal test initially
failed because its atomic-replacement injection targeted the old repository module;
it now targets the shared helper. Unavailable-line tests now use the real manager API,
including last-line removal, replacing the earlier catalog double. No removal production
logic changed. The focused integration suite passed 138 tests and the full required-browser
suite passed 700; compileall and data/diff checks passed. A second agent review found no
integration defects and independently passed all 31 removal cases. Publication status
and hosted CI evidence belong to the PR; human review and merge remain separate steps.

[PR #123](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/123) was opened.
Main advanced again to `aaca156` (staff provisioning #117), so both provenance records
were retained in a second merge. The new pinned filelock dependency was installed.
One local Windows run stalled and was terminated; a diagnostic rerun with
`REQUIRE_BROWSER_TESTS=1` and `python -m pytest -vv -o faulthandler_timeout=30` passed
715 tests in 34.35 seconds. The nearby 50-test group also passed independently.
No application change was made for the unreproduced stall. Final compilation,
dependency, whitespace and committed-data checks passed.

## Review check and current-main refresh

On Thomas's follow-up, PR #123 had no submitted reviews, inline review comments or
conversation comments. There were no reviewer requests to implement. The PR conflicted
with newer main, so `9474129` (shared pricing/account frontend) and then `c2d4aa8`
(order details) were integrated. Provenance and README conflicts retained both features;
the #88 record moved before the later appended records to reduce repeated append conflicts.
Removal behavior and tests are unchanged. The focused cart/checkout suite passed 130
tests; the intermediate full suite passed 735. Final compileall and required-browser
`python -m pytest -vv -o faulthandler_timeout=30` passed 766 tests in 44.88 seconds,
without skips. Diff, dependency and committed-data checks passed. CI is verified on
the pushed head separately; a reviewer has not approved this work.
