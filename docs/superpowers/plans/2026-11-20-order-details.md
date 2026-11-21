# Order details implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Implement #93's authenticated, owner-scoped order detail API.
**Architecture:** A thin route uses existing bearer authentication and delegates to a separate OrderDetailsService. The service checks role, reloads the customer and checks order ownership under the workflow lock, using existing repositories and immutable snapshots.
**Tech stack:** Python 3.12, FastAPI, Pydantic, JSON, pytest, existing Playwright suite.
**Spec:** [Issue #93](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/93), [auth design](../../AUTH_DESIGN.md), [M2 contract](../../M2_API_CONTRACT.md).

## Constraints and decisions

- Thomas authorized implementation and a PR after the dependency review; no further interview gate.
- Original base: main `95c7c8e`; synchronized with main `9474129` after the merge-blocker review. Reuse #91 storage; do not modify #92's separate service.
- Active and inactive customers may read their own saved orders. Staff get 403; invalid identity gets 401; missing/foreign order gets identical 404.
- Existing `active_customer_for` cannot serve order reads. The proposed generic access helper does not exist in this main, so the small read-specific service checks role and current customer existence directly.
- No new fields, storage format, dependencies, frontend or checkout endpoint. Real checkout service integration is in scope; checkout HTTP integration awaits #91.
- Every test uses disposable stores. Preserve committed data and document AI provenance and pending human review.

## Review focus

Denials before private order reads; inactive and removed accounts; corrupt/unreadable stores; opaque IDs and identical missing/foreign responses; historical values after profile/menu changes and repository reload.

## Tasks

1. [x] Add `tests/test_order_details.py` with independent stored-order fixtures, service authorization tests, API error/security/OpenAPI checks, and a real registration/login/cart/checkout-service/detail/reload scenario. Observe missing-feature failures.
2. [x] Create `app/services/order_details.py`: `OrderDetailsService(customers, orders).get_order(principal, order_id) -> Order`. Reuse `AuthenticationRequiredError` for vanished identity; define permission and not-found domain errors. Preserve repository storage failures.
3. [x] Create `app/api/routes/order_details.py`, register in `app/main.py`, document 200/401/403/404/500 and bearer security. Add the opaque-ID operation to the OpenAPI no-422 list. Observe focused tests pass.
4. [x] Update README, both setup guides, M2/API/data/testing evidence and provenance. Run `python -m compileall app`, required-browser `python -m pytest -q`, whitespace and committed-data checks. Review the complete diff independently, resolve findings, commit/push and open a PR referencing #93 without claiming full checkout HTTP integration or human approval.

## Execution evidence

Commands and results are recorded in [provenance](../../PROVENANCE.md#issue-93-owner-scoped-order-details) and [PR #119](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/119).

Implementation, documentation and local verification are complete: initial 28 expected failures; 31 focused passes; 648 full-suite passes with browser tests required; compileall, diff/data guards and 117 local documentation links checked. Independent agent review found no actionable issues. Commit `5b05a59` was pushed on `feature/93-order-details` and PR #119 is open.

The [agent-submitted GitHub review](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/119#pullrequestreview-6002388506), initiated by repository owner Gwantana and authored/submitted through ChatGPT using `gwan-kib`'s connected account, requested the plan-status correction and reported no functional defect in the new detail path. As clarified in the [follow-up review](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/119#pullrequestreview-6002430412), this is AI-assisted review evidence, not independent human peer review or confirmation of student understanding.

## CI, review and integration status

- [x] Hosted CI on PR #119 revision `8811eea`: [`validate` succeeded](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/actions/runs/44858630232/job/136706602018). This is evidence for that revision, not a new test run for the subsequent documentation correction.
- [x] Synchronize current main `9474129`, retaining both sides' setup, milestone and provenance additions. Adapt the historical-snapshot integration test to sign in as the restaurant manager before protected menu/restaurant edits. The merged tree initially produced 1 failed / 30 passed detail cases (401 on anonymous menu edit); after the test update, all 31 passed. Compilation and the complete required-browser suite passed: 735 tests, no skips or warnings. Existing order-detail application code is unchanged.
- Hosted CI for the current revision is recorded in [PR #119 checks](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/119/checks). Verify that revision before re-review; the older successful run does not certify the synchronized tree.
- [ ] Independent human peer review and approval of the implementation and documentation; responsible-student understanding confirmation. The agent-submitted reviews do not satisfy this gate.
- [ ] Complete HTTP checkout-to-detail integration in #91/#101. The implemented test uses the real checkout service; no checkout HTTP endpoint is added by this PR.
- [ ] Merge and final issue-completion checks. PR #119 references #93 without closing it.
