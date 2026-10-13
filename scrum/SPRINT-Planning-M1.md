# Sprint Planning — M1 Completion Sprint

The backlog, meeting dates, ownership, and commitments below preserve the original plan. Task checkboxes reflect the dated [progress update](#2026-10-13-documentation-reconciliation); unchecked final audits and human commitments remain pending.

## Sprint Information

- **Sprint / Milestone:** Milestone 1 — First Vertical Slice
- **Sprint dates:** 2026-10-02 to 2026-10-16
- **Planning meeting dates:** 2026-10-02, 2026-10-08
- **M1 deadline:** 2026-10-16 at 11:59 p.m.
- **Target release / tag:** `m1-vertical-slice`
- **Facilitator:** TBD

### Team Members

- [x] Gwantana Kiboigo
- [x] Sreeram Nara
- [x] Thomas Chen

---

## 1. Sprint Goal

> What should the team have working by the end of this sprint?

Complete and integrate the full Milestone 1 first vertical slice.

By the end of the sprint, the team should have:

- the required customer restaurant-discovery and menu-browsing flow;
- restaurant-management create/update functionality;
- the required basic frontend integration;
- persistent data;
- automated tests;
- accurate API documentation; and
- all M1 release/submission artifacts ready for the live demonstration and immutable `m1-vertical-slice` tag.

The team should prioritize **working end-to-end behaviour and M1 acceptance criteria over visual polish or later-milestone features**.

---

## 2. Sprint Backlog

The GitHub issues below form the sprint backlog for reaching the end of M1.

| Issue | Work Item | Priority | Primary Owner | Dependencies |
|---|---|---|---|---|
| #30 | Define restaurant/menu API and data contract | High | Gwantana Kiboigo | M0 foundation |
| #31 | View restaurant details | High | Sreeram Nara | #30 |
| #32 | Search or filter restaurants | High | Sreeram Nara | #30, existing restaurant list |
| #33 | Browse restaurant menus and menu items | High | Sreeram Nara | #30, shared menu/data relationship |
| #34 | Build basic restaurant discovery frontend | High | Sreeram Nara | #30, #31, existing restaurant list |
| #35 | Create restaurant | High | Thomas Chen | #30 |
| #36 | Update restaurant information | High | Thomas Chen | #30 |
| #37 | Add menu item | High | Thomas Chen | #30, #33 |
| #38 | Update menu item | High | Thomas Chen | #30, #33, #37 where applicable |
| #39 | Build basic management frontend operation | High | Thomas Chen | #30 and one of #35–#38 |
| #40 | Verify tests, persistence, errors, and API docs | High | Gwantana Kiboigo | #30, #31–#39 sufficiently integrated |
| #41 | Record engineering design decision | High | Gwantana Kiboigo | Meaningful M1 design/implementation decision exists |
| #42 | Prepare integration, submission, and demo | High | Gwantana Kiboigo | #27, #28, #30, #40, #41 |

### M1 Epics

- #27 — **Restaurant Discovery & Menu Browsing**
- #28 — **Restaurant Management**
- #29 — **Engineering Quality & Release Readiness**

> **Note:** Primary ownership means responsibility for coordinating the work. It does not prevent other team members from contributing or reviewing.

---

## 3. Task Decomposition

### Shared Contract — #30

- [x] Agree on exact M1 endpoint paths and HTTP methods.
- [x] Define restaurant/menu/menu-item identifiers and relationships.
- [x] Define Pydantic request, update, and response model responsibilities.
- [x] Define expected success and error responses.
- [x] Define persistence format/location and stable-ID behaviour.
- [x] Ensure all M1 feature stories implement the same contract.
- [x] Review the contract as a team before parallel implementation diverges.

### Customer Discovery & Menu Browsing — #31–#34

- [x] Retrieve a restaurant by stable identifier.
- [x] Handle unknown-restaurant behaviour.
- [x] Implement at least one documented restaurant search/filter mechanism.
- [x] Implement restaurant → menu/menu-item relationships.
- [x] Persist representative menu/menu-item data.
- [x] Retrieve menu/menu items for a known restaurant.
- [x] Build the basic restaurant-list/detail frontend through the REST API.
- [x] Add automated tests for successful and failure cases.
- [ ] Confirm OpenAPI documentation matches the implemented endpoints.

### Restaurant Management — #35–#39

- [x] Management stories #35–#39 are assigned to Thomas Chen.
- [x] Implement create-restaurant behaviour with stable persisted identifiers.
- [x] Implement update-restaurant behaviour while preserving stable identifiers.
- [x] Implement add-menu-item behaviour with correct restaurant/menu relationships.
- [x] Implement update-menu-item behaviour without corrupting relationships.
- [x] Confirm create/update changes survive reload/restart.
- [x] Select which required management operation will be exposed in the M1 frontend.
- [x] Build the basic management frontend operation through the REST API.
- [x] Add automated tests for successful and representative invalid/failure cases.
- [ ] Confirm OpenAPI documentation matches the implemented endpoints.

### Quality, Documentation, and Release — #40–#42

- [ ] Run the full pytest suite from the repository root.
- [ ] Confirm tests use isolated data and do not modify committed application data.
- [ ] Verify persistent writes reload correctly.
- [ ] Verify stable IDs and relationships remain valid.
- [ ] Verify representative error/failure behaviour.
- [ ] Audit generated OpenAPI documentation for every implemented endpoint.
- [ ] Confirm CI passes on the integrated M1 version.
- [ ] Record at least one meaningful M1 engineering design decision.
- [ ] Update README for the M1 implementation.
- [ ] Update `docs/PROVENANCE.md`.
- [ ] Ensure required Scrum notes are present under `scrum/`.
- [ ] Agree contribution percentages that total 100%.
- [ ] Prepare the Canvas submission PDF.
- [ ] Verify the final assessed commit.
- [ ] Create the immutable `m1-vertical-slice` tag/release.
- [ ] Record the full tagged commit SHA.
- [ ] Prepare every team member for the 6–8 minute live demonstration.

---

## 4. Dependencies and Integration

| Dependency | Related User Stories | Responsible | Planned Resolution |
|---|---|---|---|
| Shared API/data contract must be agreed before feature branches diverge | #30–#39 | Gwantana coordinates; whole team reviews | Complete and review #30 first |
| Menu write operations depend on an agreed menu/data relationship | #33, #37, #38 | Team | Resolve in #30 and use the same model everywhere |
| Management frontend operation has not yet been selected | #39 | Thomas / Team | Choose one implemented operation from #35–#38 and record the decision |
| Final quality audit depends on integrated feature work | #40 | Gwantana | Run after required stories are merged |
| Release/submission work depends on all required M1 functionality | #42 | Gwantana coordinates | Integrate early; do not leave tagging/submission to the deadline |

### Integration Plan

1. Complete and review #30 before substantial parallel feature implementation.
2. Implement customer and restaurant-management stories on separate feature branches.
3. Keep branches focused and short-lived.
4. Every implementation change goes through a pull request and peer review.
5. Include tests with code changes and record verification evidence in PRs.
6. Merge completed stories into `main` incrementally instead of waiting until the end of the sprint.
7. Run regression tests after integrations that affect shared models, persistence, routes, or API contracts.
8. Complete #40 once the required features are sufficiently integrated.
9. Complete #41 using a real M1 engineering decision.
10. Complete #42 against the exact commit that will receive the final M1 tag.

---

## 5. Risks and Potential Blockers

| Risk / Blocker | Impact | Planned Action | Owner |
|---|---|---|---|
| Shared API/data contract is delayed | Blocks or causes rework across most M1 stories | Prioritize #30 first and review it as a team | Gwantana / Team |
| Different branches implement incompatible data/API shapes | Integration failures and rework | Treat #30 as the shared contract | Team |
| Management frontend operation is not selected | #39 remains blocked | Select one required create/update operation early | Thomas / Team |
| Persistence changes corrupt IDs or relationships | M1 requirements and tests fail | Use repository layer, isolated tests, and reload verification | Feature owners |
| Frontend work starts before backend contracts stabilize | Rework and integration delays | Implement against the agreed API contract | Feature owners |
| Testing/documentation is deferred until the end | Release readiness becomes a bottleneck | Update tests/docs with each PR | All |
| M1 integration/tag/submission is left to the final hours | Risk of missing a no-late-credit project deadline | Finish integration and submission checks before Oct. 16 | Team |

---

## 6. Definition of Done

For the **M1 completion sprint** to be considered done:

### Functionality

- [x] Restaurant list functionality continues to work.
- [x] A customer can search/filter restaurants.
- [x] A customer can retrieve a specific restaurant's details.
- [x] A customer can retrieve that restaurant's menu/menu items.
- [x] Restaurant-management create/update functionality required by M1 is implemented.
- [x] The selected management operation is available through a basic frontend.
- [x] Customer discovery functionality is available through a basic frontend.
- [x] Frontends communicate through the REST API rather than hard-coded/persistence-file edits.

### Architecture and Persistence

- [x] Route → Service → Repository → JSON/CSV boundaries are respected.
- [x] Pydantic models are used appropriately for request/response validation.
- [x] Stable identifiers are preserved.
- [x] Restaurant/menu/menu-item relationships remain consistent.
- [x] Required create/update operations persist after reload/restart.
- [x] No M1-excluded authentication, cart, checkout, order, or delivery functionality is required for completion.

### Testing and Quality

- [x] Appropriate unit tests are included with code changes.
- [x] Appropriate integration/API tests are included.
- [x] Meaningful invalid/failure cases are covered.
- [x] Test data is isolated from committed application data.
- [ ] Full pytest suite passes.
- [ ] CI passes.
- [ ] No known critical M1 defects remain.

### Review and Documentation

- [x] All implementation work is integrated through pull requests.
- [ ] Required PRs are reviewed by another team member.
- [ ] Review feedback is addressed.
- [ ] Generated OpenAPI documentation matches the implementation.
- [ ] README is current.
- [ ] `docs/PROVENANCE.md` is current.
- [ ] Required Scrum notes are current.
- [ ] At least one meaningful engineering design decision is documented and explainable.

### Submission and Demo

- [ ] Contribution percentages are agreed and total 100%.
- [ ] Final assessed commit is verified.
- [ ] Immutable `m1-vertical-slice` tag/release is created.
- [ ] Full tagged commit SHA is recorded.
- [ ] Canvas PDF contains all required M1 submission information.
- [ ] Every team member is ready for the live demonstration.
- [ ] The submitted tag is not moved after the deadline.

---

## 7. Sprint Commitment

Before ending the planning meeting, each team member should confirm the sprint plan and ownership.

| Team Member | Initial Responsibilities | Confirmed |
|---|---|---|
| Gwantana Kiboigo | Coordinate shared API/data contract, cross-cutting verification, engineering decision, integration, release, and submission readiness (#30, #40–#42) | ☐ |
| Sreeram Nara | Coordinate customer-facing restaurant discovery, search/filter, menu browsing, and discovery frontend (#31–#34) | ☐ |
| Thomas Chen | Coordinate restaurant-management create/update functionality, menu-item functionality, and the management frontend (#35–#39) | ☐ |

---

## Meeting Notes

### Decisions Needed

- [x] Ownership confirmed: Thomas Chen owns #35–#39.
- [x] Agree the shared API/data contract in #30.
- [x] Choose the M1 restaurant search/filter mechanism.
- [x] Choose the M1 management frontend operation.
- [ ] Identify a real engineering decision suitable for the Decision Receipt once implementation establishes one.

### Scope Reminder

M1 is focused on the **first vertical slice**. Authentication/authorization, carts, checkout, orders, and deliveries are outside this sprint's required implementation scope unless a newer authoritative course source says otherwise.

### Progress Updates

Use this section for important sprint-level changes, decisions, blockers, or scope clarifications.

Routine check-ins should update the relevant GitHub issues/Project Board rather than creating a new Sprint Planning file.


### 2026-10-13 documentation reconciliation

This is a repository/GitHub evidence update, not a new meeting or sign-off. Planning dates, owners, member markers, facilitator TBD, and unconfirmed sprint commitments above are preserved. Task checkmarks indicate implementation or recorded feature-level verification; final assessed-version checks remain pending.

- The team adopted #30 through [PR #48](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/48) on 2026-10-02. Cuisine filtering was selected in that contract and integrated into `main` through [PR #59](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/59), following reviewed PR #57.
- The user selected **Create restaurant** for #39 on 2026-10-12; [PR #61](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/61) merged it. The dependency/risk entries about an unselected operation above describe the original planning state and are resolved at implementation level.
- Refreshed `main` at `09638a9` contains all eight API operations and both frontends. See the [M1 evidence table](../docs/milestones/M1.md#source-and-status) for issues and merged PRs #16, #51–#56, #58, #59, and #61. [PR #50](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/50) merged this sprint plan.
- [Provenance Entries 21–41](../docs/PROVENANCE.md#entry-21-create-restaurant-and-shared-persistence-foundation) retain test-first, isolated-data, persistence/restart, validation, and review-fix evidence. PR #61 reports 373 passing tests with no skips after its fixes. This historical run was not repeated for #62; the latest integrated-main CI was in progress when checked.
- Live reviews establish final approvals for PRs #48, #51–#58, and #61. PR #50 and integration PR #59 have no submitted formal GitHub review; the #42 collaboration audit must resolve the gaps without invented retrospective approvals.
- #62 reconciles documentation on a separate branch; its PR still requires teammate review and merge. Live Role/Workstream/Status options could not be inspected because the token lacks `read:project`. Signed Team Agreement V1 lists three students versus the earlier brief's four-person requirement; obtain team/instructor confirmation without rewriting the agreement.

Outstanding release work remains:

- [ ] Finish [#40](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/40): integrated full-suite/CI results, complete generated OpenAPI audit, and any traced defects.
- [ ] Finish [#41](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/41): an actual Decision Receipt, teammate verification, and team explanation.
- [ ] Finish [#42](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/42): clean setup/demo verification, collaboration/Scrum/board audit, individual confirmations, and agreed contributions totaling 100%.
- [ ] Verify the assessed commit, create the immutable `m1-vertical-slice` tag/release, record its full SHA, prepare/submit the Canvas PDF, and confirm each member's demonstration readiness. No submission or grading is established here.
- [ ] Confirm the course deadline timezone and the native milestone metadata discrepancy recorded in [M1](../docs/milestones/M1.md#source-and-status).
