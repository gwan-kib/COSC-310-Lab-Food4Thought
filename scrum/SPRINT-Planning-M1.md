# Sprint Planning — M1 Completion Sprint

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

- [ ] Agree on exact M1 endpoint paths and HTTP methods.
- [ ] Define restaurant/menu/menu-item identifiers and relationships.
- [ ] Define Pydantic request, update, and response model responsibilities.
- [ ] Define expected success and error responses.
- [ ] Define persistence format/location and stable-ID behaviour.
- [ ] Ensure all M1 feature stories implement the same contract.
- [ ] Review the contract as a team before parallel implementation diverges.

### Customer Discovery & Menu Browsing — #31–#34

- [ ] Retrieve a restaurant by stable identifier.
- [ ] Handle unknown-restaurant behaviour.
- [ ] Implement at least one documented restaurant search/filter mechanism.
- [ ] Implement restaurant → menu/menu-item relationships.
- [ ] Persist representative menu/menu-item data.
- [ ] Retrieve menu/menu items for a known restaurant.
- [ ] Build the basic restaurant-list/detail frontend through the REST API.
- [ ] Add automated tests for successful and failure cases.
- [ ] Confirm OpenAPI documentation matches the implemented endpoints.

### Restaurant Management — #35–#39

- [x] Management stories #35–#39 are assigned to Thomas Chen.
- [ ] Implement create-restaurant behaviour with stable persisted identifiers.
- [ ] Implement update-restaurant behaviour while preserving stable identifiers.
- [ ] Implement add-menu-item behaviour with correct restaurant/menu relationships.
- [ ] Implement update-menu-item behaviour without corrupting relationships.
- [ ] Confirm create/update changes survive reload/restart.
- [ ] Select which required management operation will be exposed in the M1 frontend.
- [ ] Build the basic management frontend operation through the REST API.
- [ ] Add automated tests for successful and representative invalid/failure cases.
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

- [ ] Restaurant list functionality continues to work.
- [ ] A customer can search/filter restaurants.
- [ ] A customer can retrieve a specific restaurant's details.
- [ ] A customer can retrieve that restaurant's menu/menu items.
- [ ] Restaurant-management create/update functionality required by M1 is implemented.
- [ ] The selected management operation is available through a basic frontend.
- [ ] Customer discovery functionality is available through a basic frontend.
- [ ] Frontends communicate through the REST API rather than hard-coded/persistence-file edits.

### Architecture and Persistence

- [ ] Route → Service → Repository → JSON/CSV boundaries are respected.
- [ ] Pydantic models are used appropriately for request/response validation.
- [ ] Stable identifiers are preserved.
- [ ] Restaurant/menu/menu-item relationships remain consistent.
- [ ] Required create/update operations persist after reload/restart.
- [ ] No M1-excluded authentication, cart, checkout, order, or delivery functionality is required for completion.

### Testing and Quality

- [ ] Appropriate unit tests are included with code changes.
- [ ] Appropriate integration/API tests are included.
- [ ] Meaningful invalid/failure cases are covered.
- [ ] Test data is isolated from committed application data.
- [ ] Full pytest suite passes.
- [ ] CI passes.
- [ ] No known critical M1 defects remain.

### Review and Documentation

- [ ] All implementation work is integrated through pull requests.
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
- [ ] Agree the shared API/data contract in #30.
- [ ] Choose the M1 restaurant search/filter mechanism.
- [ ] Choose the M1 management frontend operation.
- [ ] Identify a real engineering decision suitable for the Decision Receipt once implementation establishes one.

### Scope Reminder

M1 is focused on the **first vertical slice**. Authentication/authorization, carts, checkout, orders, and deliveries are outside this sprint's required implementation scope unless a newer authoritative course source says otherwise.

### Progress Updates

Use this section for important sprint-level changes, decisions, blockers, or scope clarifications.

Routine check-ins should update the relevant GitHub issues/Project Board rather than creating a new Sprint Planning file.
