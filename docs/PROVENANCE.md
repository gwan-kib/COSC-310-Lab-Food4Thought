# AI provenance

This is Food4Thought's shared record of generative AI contributions to project artifacts.

Record AI use when it affects work included in the project, including code, tests, documentation, diagrams, API specifications, and adopted design decisions. Interactions that do not affect an artifact need no entry; minor autocomplete that does not meaningfully affect work normally needs none. When in doubt, record it. A single artifact may have multiple entries for different contributions. Labels on every Git commit are not required.

## Labels

Use exactly one label per entry, based on AI's role rather than how much its output was edited.

| Label | Meaning |
| --- | --- |
| `AI-GENERATED` | AI produced content or a substantial part of it that was used or adapted. |
| `AI-ASSISTED` | AI supplied ideas, explanations, alternatives, or guidance; the student created the final content. |
| `AI-REVISED` | The student created the original work; AI later substantially changed, refactored, or rewrote it. |
| `NO-AI` | No generative AI produced or influenced the work described. |

Students remain responsible for understanding, validating, testing, correcting, and explaining submitted work. Git authorship and agent verification do not establish student review or understanding. The review-status field below is a repository convention for tracking that distinction, in addition to the guide's required fields.

## Entry template

Copy this template for each relevant contribution. Replace placeholders with evidence; explicitly identify unknown facts and outstanding checks. Link a PR or commit when practical, adding it later if the work is still local.

```markdown
### Entry N: Contribution title

- Student(s): Name(s) or known project identity; state any attribution awaiting confirmation.
- Artifact: Affected file(s), diagram, specification, or design decision.
- Label: One guide-defined label.
- AI tool: Tool used; do not guess model/version details.
- Purpose: What the tool was used for.
- Influence: How the output affected the project artifact.
- Validation: Checks actually performed and results; distinguish reported historical checks and remaining gaps.
- PR or commit: Relevant link when practical, or local/uncommitted status.
- Student review status: Confirmed review or explicit pending status; do not infer approval.
```

## Recorded contributions

Historical entries below transfer the disclosures previously in `CONTRIBUTING.md` and [PR #1](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/1). The documentation commit groups work performed on more than one date. These entries describe contributions, not a label for every commit. `AI-GENERATED` reflects recorded Codex drafting/creation; the earlier informal wording “AI-assisted” was not a classification under the newly supplied guide.

### Entry 1: Initial repository workflow documentation

- Student(s): Gwantana Kiboigo (`gwan-kib`), recorded author of the linked commit; Gwantana confirmed responsibility for this historical entry on 2026-09-24. No other participating students are established by the available evidence.
- Artifact: `AGENTS.md`, `CONTRIBUTING.md`, `docs/TESTING.md`, `.github/ISSUE_TEMPLATE/user-story.md`, `.github/ISSUE_TEMPLATE/technical-task.md`, `.github/ISSUE_TEMPLATE/bug.md`, and `.github/PULL_REQUEST_TEMPLATE.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: On 2026-09-15, draft repository guidance from user-supplied project briefs and separate agent behaviour from team engineering workflow.
- Influence: Codex drafted the initial instructions and reorganized them into the seven documentation/template files. No application code or tests were generated.
- Validation: The retained assistance record reports checks of the seven documents, relative links, Markdown fences, whitespace, issue-template metadata, and `git diff --check`. During issue #9, the commit inventory and previous disclosure were inspected to verify scope. Historical checks were not rerun against the original working tree.
- PR or commit: [Project-planning commit 6826e6c](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/6826e6c191328dee82e66a83395ce735b66ad4e5), committed 2026-09-18 (America/Vancouver).
- Student review status: Confirmed by Gwantana Kiboigo on 2026-09-24 through explicit instruction to update his pending provenance review confirmations. No separate peer approval of this historical documentation change is asserted.

### Entry 2: Test-first workflow and M0 documentation

- Student(s): Gwantana Kiboigo (`gwan-kib`), recorded author of the linked commit; Gwantana confirmed the historical attribution and responsibility on 2026-09-24.
- Artifact: `AGENTS.md`, `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/milestones/M0.md`, `README.md`, and the three issue templates and PR template under `.github/`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: On 2026-09-18, document the supplied test-first workflow, AI/provenance policy, and M0 foundational-gate requirements, with navigation links.
- Influence: Codex updated workflow documentation/templates and added the M0 checkpoint and documentation links, building on the earlier generated documentation. No application code or tests were generated. The README changes are included in the linked planning commit; Gwantana confirmed the historical attribution on 2026-09-24.
- Validation: The previous `CONTRIBUTING.md` disclosure reports documentation-content and local-link checks. During issue #9, the planning commit and README diff were inspected. No application test results are claimed for these documentation changes.
- PR or commit: [Project-planning commit 6826e6c](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/6826e6c191328dee82e66a83395ce735b66ad4e5).
- Student review status: Confirmed by Gwantana Kiboigo on 2026-09-24 through explicit instruction to update his pending provenance review confirmations.

### Entry 3: Initial Python development scaffold

- Student(s): Gwantana Kiboigo (`gwan-kib`), PR #1 author and implementation-commit author; Gwantana confirmed responsibility for this generated scaffold on 2026-09-24.
- Artifact: `.gitignore`, `requirements.txt`, `.github/workflows/ci.yml`, `app/main.py`, `app/__init__.py`, `app/api/__init__.py`, `app/api/routes/__init__.py`, `app/core/__init__.py`, `app/repositories/__init__.py`, `app/schemas/__init__.py`, `app/services/__init__.py`, `data/.gitkeep`, `tests/.gitkeep`, `README.md`, and `docs/TESTING.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Create the authorized initial Python package skeleton, dependency pins, ignore rules, CI configuration, and setup instructions.
- Influence: Codex created the scaffold and configuration and updated setup documentation. All eight Python files were empty; no feature implementation, representative data, or tests were generated. CI installed dependencies and compiled the scaffold only.
- Validation: PR #1 reports successful creation of two Python 3.12.13 environments, dependency installation (including an independent `python -m pip install -r requirements.txt`), `python -m pip check` with no broken requirements, `python -m compileall app`, imports of all four dependencies, `git diff --cached --check`, tracked-file/diff inspection, and ignore-rule checks. These are historical reported results, not checks rerun for issue #9. pytest, application startup, and endpoint checks were not performed because no application or tests existed. The implementation diff was inspected for this entry.
- PR or commit: [PR #1](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/1), merged; [implementation commit 0e9f6c8](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/0e9f6c893083a1a5a5c8080d675e1a9bf4e4d6c1).
- Student review status: Confirmed by Gwantana Kiboigo on 2026-09-24 through explicit instruction to update his pending provenance review confirmations. PR #1 still has no separate submitted peer review recorded.

### Entry 4: Align provenance workflow with the course guide

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #9 author; Gwantana confirmed responsibility for this provenance-workflow update on 2026-09-24.
- Artifact: `docs/PROVENANCE.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/milestones/M0.md`, `.github/PULL_REQUEST_TEMPLATE.md`, the three `.github/ISSUE_TEMPLATE/` files, and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Implement issue #9 using the downloaded course guide and replace obsolete instructions to defer the provenance record.
- Influence: Codex extracted the guide's text, drafted the shared record and historical entries, and updated workflow instructions and links. Historical statements are limited to available disclosures, commit history, and PR evidence; no student approval is invented.
- Validation: Compared the required labels and fields with the downloaded guide and inspected documentation history and PR #1. A local Python documentation check passed for all 10 Markdown files (relative links/anchors, fences, whitespace, and obsolete wording), all three issue templates, and all four entries' required fields and labels. `git diff --check` passed. The complete changed documentation was inspected. No application tests are applicable to this documentation-only change.
- PR or commit: [Issue #9](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/9); [implementation commit `1ff670b`](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/1ff670b33599cc92cde73b05bb3b30751277b5a1), which added the shared provenance workflow to `main`.
- Student review status: Confirmed by Gwantana Kiboigo on 2026-09-24 through explicit instruction to update his pending provenance review confirmations. No separate peer review of this historical documentation change is asserted.

### Entry 5: Restaurant schema, sample data, and configuration

- Student(s): Thomas Chen (`Tc2006415`), contributor and issue #3 assignee; Gwantana Kiboigo reports that Thomas confirmed review and responsibility for the generated work on 2026-09-24.
- Artifact: `app/schemas/restaurant.py`, `app/core/config.py`, `data/restaurants.json`, `tests/test_restaurant_foundation.py`, and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Establish the M0 restaurant response contract, representative JSON data, and configurable data location for issue #3.
- Influence: Codex drafted the Pydantic model, sample records, path-selection function, tests, and related README updates from the course requirements and issue acceptance criteria.
- Validation: On Python 3.12, all five foundation tests were observed failing before implementation because the model/configuration modules were missing; after implementation, `python -m pytest tests/test_restaurant_foundation.py -q` and `python -m pytest -q` each passed 5 tests, and `python -m compileall app` passed. PR #11 was peer-reviewed and approved by Gwantana Kiboigo on 2026-09-24. Gwantana Kiboigo also reports that Thomas Chen confirmed he reviewed this generated work on 2026-09-24.
- PR or commit: [Issue #3](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/3); [implementation commit a333af4](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/a333af41265be2cafcb5b054299932239b76a238). [PR #11](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/11).
- Student review status: Confirmed. Peer review is recorded from Gwantana Kiboigo on PR #11, and Gwantana reports that Thomas Chen (`Tc2006415`) confirmed his own review on 2026-09-24.

### Entry 6: Restaurant repository layer

- Student(s): Thomas Chen (`Tc2006415`), recorded implementation-commit and PR author; Gwantana Kiboigo reports that Thomas confirmed review and responsibility for the generated work on 2026-09-24.
- Artifact: `app/repositories/restaurant.py`, `tests/test_restaurant_repository.py`, `README.md`, and `docs/TESTING.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Implement issue #4's persistence-access layer using the issue #3 restaurant model and configurable data path.
- Influence: Codex drafted the JSON-reading repository, typed results, clean persistence/validation errors, isolated-data tests, and documentation updates.
- Validation: On Python 3.12, all five repository tests were observed failing before implementation because the repository module was missing; after implementation, `python -m pytest tests/test_restaurant_repository.py -q` passed 5 tests, `python -m pytest -q` passed 10 tests, and `python -m compileall app` passed. PR #12 was peer-reviewed and approved by Gwantana Kiboigo on 2026-09-24. Gwantana Kiboigo also reports that Thomas Chen confirmed he reviewed this generated work on 2026-09-24.
- PR or commit: [Issue #4](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/4); [implementation commit 91198fa](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/91198faeb1424f6c4c5dc516de100f7e9221392b); [PR #12](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/12).
- Student review status: Confirmed. Peer review is recorded from Gwantana Kiboigo on PR #12, and Gwantana reports that Thomas Chen (`Tc2006415`) confirmed his own review on 2026-09-24.

### Entry 7: FastAPI application entry point and health endpoint

- Student(s): Sreeram Nara (`SreeramNara`), System Administrator and issue #2 owner.
- Artifact: `app/main.py`, `app/api/routes/health.py`, `tests/test_health.py`, `requirements.txt` (added `httpx2`), and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Claude (Anthropic), via claude.ai.
- Purpose: Implement issue #2: a runnable FastAPI app exposing `GET /health` and `/docs`.
- Influence: Claude wrote the tests first, then the application entry point, health router, README run instructions, and identified that the pinned FastAPI/Starlette `TestClient` requires the `httpx2` package, which was missing from `requirements.txt`.
- Validation: On Python 3.12.3, `tests/test_health.py` first failed at collection because `httpx2` was missing, then failed 4/4 with `ImportError` because `app.main` had no application. After implementation, `python -m pytest -q` passed 9 tests (14 after rebasing onto `main` with the issue #4 repository tests). `python -m uvicorn app.main:app` was started and `GET /health` returned `{"status":"ok"}` (HTTP 200) and `GET /docs` returned HTTP 200. `git diff --check` passed.
- PR or commit: [Issue #2](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/2); [PR #13](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/13).
- Student review status: Reviewed by Sreeram Nara on 2026-09-24, who ran the test suite and the application locally on Windows with Python 3.12. Peer review is recorded on the PR.

### Entry 8: Test isolation fixtures and pytest in CI

- Student(s): Sreeram Nara (`SreeramNara`), System Administrator and issue #6 owner.
- Artifact: `tests/conftest.py`, `tests/test_test_isolation.py`, `.github/workflows/ci.yml`, `docs/TESTING.md`, and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Claude (Anthropic), via claude.ai.
- Purpose: Implement the test-infrastructure and CI parts of issue #6.
- Influence: Claude wrote isolation tests first, then an autouse fixture giving every test a temporary copy of the restaurant data, a session check that fails if committed `data/` files change, a CI pytest step with a `git diff --exit-code -- data/` check, and matching documentation.
- Validation: The three isolation tests first errored because the fixture did not exist; after implementation `python -m pytest -q` passed 12 tests (17 after rebasing onto `main` with the issue #4 repository tests). A temporary test that wrote to `data/restaurants.json` made the session check fail as intended (the file was then restored and the test deleted). A fresh Python 3.12 environment installed `requirements.txt` and ran compileall, pytest, and the `data/` diff check successfully. The workflow was not run on GitHub Actions from this environment.
- PR or commit: [Issue #6](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/6); [PR #14](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/14).
- Student review status: Reviewed by Sreeram Nara on 2026-09-24, who ran the test suite and the application locally on Windows with Python 3.12. Peer review is recorded on the PR.

### Entry 9: M0 README

- Student(s): Sreeram Nara (`SreeramNara`), System Administrator and issue #7 owner.
- Artifact: `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Claude (Anthropic), via claude.ai.
- Purpose: Implement the README part of issue #7 so it covers every M0 documentation item.
- Influence: Claude restructured the README: team name, Python version, setup, virtual environments, dependencies, start command, endpoints, `/docs`, data location, test command, and repository structure.
- Validation: README install and test commands were followed in a fresh Python 3.12 environment on Linux; pytest passed 17 tests, the app served `/health` and `/docs` with HTTP 200, and committed `data/` was unchanged. Windows activation commands were not executed. Relative links were checked to exist. The restaurant endpoint is intentionally not listed until issue #5 merges.
- PR or commit: [Issue #7](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/7); [PR #15](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/15).
- Student review status: Reviewed by Sreeram Nara on 2026-09-24, who ran the test suite and the application locally on Windows with Python 3.12. Peer review is recorded on the PR.

### Entry 10: Team agreement Markdown conversion

- Student(s): Gwantana Kiboigo, Sreeram Nara, and Thomas Chen wrote and signed the agreement on 15/9/2026; Sreeram Nara (`SreeramNara`) added it to the repository for issue #7.
- Artifact: `scrum/team-agreement.md`.
- Label: `AI-REVISED`.
- AI tool: Claude (Anthropic), via claude.ai.
- Purpose: Convert the team's signed agreement into Markdown at the path M0 requires.
- Influence: Formatting only, plus the explicit "V1" version label and a version-history table that M0 requires. The agreement's wording, decisions, and signatures are the team's and were not changed.
- Validation: The Markdown text was compared against the signed agreement for unchanged wording. `git diff --check` passed.
- PR or commit: [Issue #7](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/7); [PR #15](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/15).
- Student review status: Confirmed by all three team members. Sreeram Nara confirmed the Markdown matches the signed agreement on 2026-09-24; Gwantana Kiboigo confirmed his review and agreement with the Markdown/version-history addition on 2026-09-24; Gwantana also reports that Thomas Chen confirmed his review and agreement on 2026-09-24.

### Entry 11: Restaurant discovery endpoint

- Student(s): Gwantana Kiboigo (`gwan-kib`), issue #5 assignee and requester; Gwantana confirmed responsibility for this generated endpoint work on 2026-09-24.
- Artifact: `app/api/routes/restaurants.py`, `app/services/restaurant.py`, `app/main.py`, `tests/test_restaurants.py`, `tests/test_restaurant_service.py`, and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Implement issue #5 using the merged model, configuration, repository, application, and test-isolation interfaces from issues #2, #3, #4, and #6.
- Influence: Codex wrote tests before implementation, added the service and typed GET route, registered it with FastAPI, and documented the endpoint and request path. No new business rules or persistence schema were introduced. The route maps repository data failures to a generic HTTP 500 response without exposing file paths or validation details.
- Validation: The baseline passed 17 tests. `.venv/Scripts/python.exe -m pytest -q tests/test_restaurants.py tests/test_restaurant_service.py` failed all 10 new tests before implementation because the route/service did not exist. After implementation, `.venv/Scripts/python.exe -m pytest -q` passed all 27 tests; `-m compileall app`, `-m pip check`, `git diff --check`, and `git diff --exit-code -- data/` passed. A temporary Uvicorn process returned HTTP 200 for `/health`, `/restaurants` (two records), `/docs`, and `/openapi.json`. The initial sandboxed pytest run failed on filesystem permissions; the successful runs used normal filesystem access. One existing Starlette/AnyIO deprecation warning remains.
- PR or commit: [Issue #5](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/5); [PR #16](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/16), branch `feature/5-restaurant-list`.
- Student review status: Confirmed by Gwantana Kiboigo on 2026-09-24 through explicit instruction to update his pending provenance review confirmations. Peer review is also recorded from Sreeram Nara on PR #16 on 2026-09-24.
### Entry 12: M0 provenance review-status audit

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #17 owner.
- Artifact: `docs/PROVENANCE.md`.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Audit the remaining M0 provenance review-status statements and update them using explicit student confirmation and recorded GitHub review evidence.
- Influence: ChatGPT drafted the review-status edits, converted Gwantana-attributable pending statements to confirmed based on his explicit instruction, and recorded existing peer approvals for PR #11, PR #12, and PR #16. Thomas Chen's self-review was left pending at that time because no confirmation had yet been reported to the assistant; issue #19 later records Gwantana's report that Thomas confirmed his review.
- Validation: The edited statements were checked against issue #17, the existing provenance record, and recorded GitHub reviews. No application code, tests, or runtime behaviour were changed. Unsupported teammate self-review was not inferred.
- PR or commit: [Issue #17](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/17); [status-update commit acbf8d8](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/acbf8d80119fedeb37b8ff1b57ee6450ed5fa382). [PR #18](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/18).
- Student review status: Gwantana Kiboigo explicitly authorized this provenance-status audit and instructed that it be merged without requesting peer review; no separate post-edit peer review is asserted.


### Entry 13: Thomas Chen M0 review confirmation

- Student(s): Gwantana Kiboigo (`gwan-kib`) reporting Thomas Chen's confirmation for the M0 artifacts attributed to `Tc2006415`.
- Artifact: `docs/PROVENANCE.md`.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Update the M0 provenance record after Gwantana reported that Thomas Chen had confirmed review of his generated M0 work and the Team Agreement Markdown/version-history addition.
- Influence: ChatGPT changed Entries 5, 6, and 10 from pending to confirmed while preserving the source of the confirmation as Gwantana's report, and updated Entry 12 so it no longer implies Thomas's confirmation is unresolved.
- Validation: The edits were limited to provenance documentation. Existing PR #11 and PR #12 peer-review evidence was retained, and the responsible-student confirmation was attributed to Gwantana's report rather than represented as a direct GitHub review from Thomas.
- PR or commit: [Issue #19](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/19). [PR #20](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/20).
- Student review status: Gwantana Kiboigo explicitly supplied the confirmation information used for this update.

### Entry 14: First-time and returning setup documentation

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #21 owner.
- Artifact: `docs/FIRST_TIME_SETUP.md`, `docs/QUICK_SETUP.md`, `README.md`, and `AGENTS.md`.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Add separate setup instructions for a first-time application setup and for quick setup on an already-configured machine, and require future agents to keep those instructions aligned with implementation.
- Influence: ChatGPT drafted both setup guides from the current repository state, replaced duplicated README setup instructions with links to the guides, and added AGENTS.md maintenance rules requiring setup documentation to change alongside setup-relevant implementation changes. The documentation intentionally excludes planned or unimplemented features.
- Validation: The documentation was checked against the current `requirements.txt`, `app/main.py`, health and restaurant routes, restaurant data configuration/repository, pytest isolation fixture, README, and CI workflow. The documented runtime surface is limited to the currently implemented `/health`, `/restaurants`, `/docs`, and `/openapi.json` endpoints. No application code changed. Runtime commands were not executed by ChatGPT; CI and human review remain required before merge.
- PR or commit: [Issue #21](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/21); [PR #22](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/22); branch `chore/21-setup-docs`.
- Student review status: Pending. Gwantana requested the documentation work, but no post-change student review is inferred from that request.

### Entry 15: Epic issue template

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #23 owner.
- Artifact: `.github/ISSUE_TEMPLATE/epic.md`, `CONTRIBUTING.md`, and `docs/PROVENANCE.md`.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Add a reusable epic planning template based on the supplied Milestone 1 specification and the repository's existing issue workflow.
- Influence: ChatGPT drafted the epic template, added contributor guidance describing when to use it, and recorded this provenance entry. The template keeps feature-level acceptance criteria in child user stories rather than duplicating them at epic level.
- Validation: The template was checked against the existing user-story, technical-task, and bug templates and against Milestone 1's requirement that implemented features originate from user stories with acceptance criteria. YAML front matter, Markdown structure, repository paths, and the intended issue-to-epic hierarchy were reviewed. No application code or runtime behaviour changed.
- PR or commit: [Issue #23](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/23); [PR #24](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/24); branch `chore/23-epic-template`.
- Student review status: Pending. Gwantana requested the change, but no post-change student review is inferred from that request.

### Entry 16: M0/M1 epic and issue planning

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester of the M1 planning work.
- Artifact: GitHub issues #25–#42, including the retrospective M0 epics, M1 epics, M1 user stories, and M1 technical tasks.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Translate the supplied `Milestone 1 – First Vertical Slice` specification and the repository's completed M0 issue history into a traceable epic → user-story/technical-task plan for M1.
- Influence: ChatGPT created two retrospective M0 epics (#25–#26), three M1 epics (#27–#29), a shared API/data-contract task (#30), the required M1 customer and restaurant-management user stories (#31–#39), and cross-cutting M1 verification/design-decision/submission tasks (#40–#42). The issue bodies include source-grounded scope, acceptance criteria, dependencies, testing expectations, and explicit M1 exclusions. No application code or runtime behaviour was changed.
- Validation: The issue set was checked against the supplied M1 sections for Functional Scope, Required Vertical Slice, Pydantic Models, Persistence, Automated Tests, API Documentation, Frontend, GitHub Collaboration Expectations, Canvas Submission, and Live Demonstration. Existing M0 issues #2–#8 and the current repository tree were inspected so already-implemented M0 work was grouped retrospectively rather than recreated. M1-excluded authentication/authorization, carts, checkout, orders, and deliveries were kept out of implementation scope.
- PR or commit: [M0 Platform epic #25](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/25), [M0 Restaurant epic #26](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/26), [M1 Discovery epic #27](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/27), [M1 Management epic #28](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/28), [M1 Quality epic #29](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/29), and child issues #30–#42; [PR #43](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/43).
- Student review status: Pending. Gwantana requested the planning work, but no post-creation student review of all issue contents is inferred from that request.

### Entry 17: Structured issue metadata workflow

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #44 owner.
- Artifact: `.github/ISSUE_TEMPLATE/epic.md`, `.github/ISSUE_TEMPLATE/user-story.md`, `.github/ISSUE_TEMPLATE/technical-task.md`, `.github/ISSUE_TEMPLATE/bug.md`, `CONTRIBUTING.md`, `AGENTS.md`, and `docs/PROVENANCE.md`.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Implement the team's agreed convention for shorter issue titles and structured GitHub/Project metadata before migrating the existing issues.
- Influence: ChatGPT updated all issue templates to separate title text from Type, Role, Workstream, Assignee, Milestone, Parent epic, and Status metadata; changed the epic title prefix to `EPIC: `; made GitHub Relationships the canonical epic hierarchy; documented technical-label usage; and updated contributor/agent guidance to prevent future bracket-prefixed titles.
- Validation: The four issue templates, `CONTRIBUTING.md`, and `AGENTS.md` were checked for consistent terminology and for the distinction between Role and Assignee. The change is documentation/planning configuration only; no application code, tests, API behaviour, or persistence changed.
- PR or commit: [Issue #44](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/44); [PR #45](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/45); branch `chore/44-issue-metadata-docs`.
- Student review status: Gwantana Kiboigo explicitly instructed implementation and merge without waiting for peer review. No separate post-change peer review is asserted.

### Entry 18: Open issue metadata migration

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #46 owner.
- Artifact: GitHub issues #27–#42 and issue #46; `docs/PROVENANCE.md`.
- Label: `AI-GENERATED`.
- AI tool: ChatGPT.
- Purpose: Migrate the currently open M1 epics, user stories, and technical tasks to the structured issue-metadata convention adopted in issue #44.
- Influence: ChatGPT removed role/milestone bracket prefixes from open issue titles, retained `EPIC: ` as the only planning prefix, shortened selected technical-task titles, and added consistent Project Metadata sections recording Type, Role, Workstream, Assignee state, M1 delivery target, parent epic, and board-status reference. Existing requirements, acceptance criteria, dependencies, testing expectations, and implementation scope were preserved.
- Validation: All open issues were re-queried after the migration. Issues #27–#29 use `EPIC: `; regular issues #30–#42 and #46 have concise titles without bracket prefixes. Project Metadata sections were fetched and checked for the expected Type, Role, Workstream, unassigned state, M1 target, and parent-epic mapping. No assignee, label, implementation behaviour, API contract, test, or persistence change was invented.
- PR or commit: [Issue #46](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/46); [PR #47](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/47); branch `docs/46-issue-metadata-migration`.
- Student review status: Pending. Gwantana requested the migration, but no separate post-migration review is inferred from that request.

### Entry 19: M1 restaurant and menu contract

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #30 assignee.
- Artifact: `docs/M1_API_CONTRACT.md`, `docs/milestones/M1.md`, `README.md`, `CONTRIBUTING.md`, and this entry.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Prepare the shared M1 API/data contract before the dependent restaurant and menu stories are implemented.
- Influence: Codex drafted the endpoint inventory, request/read/update model responsibilities, cuisine filter, partial-update semantics, identifier ownership, menu containment, JSON persistence compatibility, errors, examples, and child-story verification mapping. Codex summarized the user-supplied M1 specification and recorded that its required search/filter operation supersedes the earlier brief's optional-filtering wording. Engineering choices are explicitly proposed for team review; no feature code, models, tests, or persisted data were changed.
- Validation: Compared the contract with issue #30, child stories #31–#39, the supplied M1 source, and the existing restaurant route/service/repository/schema/configuration/data. A Python documentation check validated 31 relative links, four fenced JSON examples, all eight operation rows, and seven backend child-story mappings. `git diff --check` and `git diff --exit-code -- app tests data requirements.txt` passed. Application tests and test-first failing/passing evidence are not applicable to this documentation-only change. Both setup guides were inspected; current setup behavior remains unchanged. Board status was unavailable because the token lacks `read:project`.
- PR or commit: [Issue #30](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/30); [PR #48](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/48); branch `chore/30-restaurant-menu-contract`.
- Student review status: The user clarified on 2026-10-04 that merging PR #48 on 2026-10-02 recorded team adoption. Individual responsible-student review and understanding remain unconfirmed.


### Entry 20: M1 contract review revisions

- Student(s): Gwantana Kiboigo (`gwan-kib`), requester and issue #30 assignee; the supplied review does not identify its author.
- Artifact: `docs/M1_API_CONTRACT.md` and this entry.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Resolve the three ambiguities supplied in review before team adoption.
- Influence: Codex assigned the shared persistence foundation to #35 before #33/#36 merge, specified a module-level lock covering complete mutations across per-request repository instances, and removed unsupported GET 422 responses. Added future preservation/concurrency checks and explicit adoption evidence requirements.
- Validation: Inspected the current per-request dependency and complete documentation diff. Relative-link and JSON-example checks, `git diff --check`, and `git diff --exit-code -- app tests data requirements.txt` passed. No application behavior or setup changed; application tests are not applicable locally to this documentation-only revision.
- PR or commit: [PR #48](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/48), issue #30, branch `chore/30-restaurant-menu-contract`.
- Student review status: Review feedback supplied by the user on 2026-10-02. The user clarified on 2026-10-04 that merging PR #48 recorded adoption of the revised contract. Individual responsible-student confirmation remains pending.

### Entry 21: Create restaurant and shared persistence foundation

- Student(s): `Tc2006415`, verified issue #35 assignee and PR #51 author; responsible-student review and confirmation remain pending.
- Artifact: `app/schemas/restaurant.py`, `app/repositories/restaurant.py`, `app/services/restaurant.py`, `app/api/routes/restaurants.py`, `tests/test_restaurant_create.py`, `tests/test_restaurants.py`, `README.md`, `docs/FIRST_TIME_SETUP.md`, `docs/QUICK_SETUP.md`, and `docs/milestones/M1.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Implement issue #35's create-restaurant vertical slice and the shared complete-record persistence foundation described in the M1 contract adopted through PR #48.
- Influence: Codex created the request, menu-item, stored-record, and error models; added full-record validation, a process-wide mutation lock and atomic file replacement; added server-generated IDs and the create route; and wrote isolated behavior, failure, concurrency, and OpenAPI tests plus README updates. After PR #51 review, Codex changed the mutation boundary to return the final validated records and made the create response derive from that saved result. The user subsequently clarified that PR #48's merge recorded team adoption; Entry 22 records the status correction.
- Validation: The new tests were run before implementation and failed for the missing POST operation and repository/model methods. A legacy-field regression test then failed with HTTP 500 before the compatibility fix and passed afterward. Using this worktree's Python 3.12 virtual environment, `python -m pytest tests/test_restaurant_create.py -q` passed 24 tests before that added regression, and `python -m pytest -q` passed 51 tests after it. A new review regression test failed with `TypeError` because `mutate_records()` returned the callback's `None`; after the change, `python -B -m pytest -p no:cacheprovider -q tests/test_restaurant_create.py` passed 26 tests and `python -B -m pytest -p no:cacheprovider -q` passed 52 tests. `python -m compileall -q app`, `python -m pip check`, `git diff --check`, and `git diff --exit-code -- data/` passed. A separate Codex review found the legacy-field regression and a concurrency-test timing weakness; both were addressed. GitHub review by `gwan-kib` requested changes; no approval or responsible-student validation is inferred.
- PR or commit: [PR #51](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/51); branch `feature/35-create-restaurant`.
- Student review status: Pending. PR #51 has a requested-changes review by `gwan-kib`; the follow-up correction is on this branch, and re-review remains pending. Passing agent-run checks do not establish student understanding or approval.

### Entry 22: M1 contract status follow-up and correction

- Student(s): Pending confirmation. Issue #30 is assigned to `gwan-kib`, and PR #51 is authored by `Tc2006415`; neither assignment proves review of this follow-up.
- Artifact: [Issue #30](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/30), PR #51 description, `docs/M1_API_CONTRACT.md`, `docs/milestones/M1.md`, `README.md`, `CONTRIBUTING.md`, and this entry.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Address PR #51's contract-status review comment and correct Codex's mistaken interpretation that adoption was still pending.
- Influence: Codex initially reopened #30 because the documentation still said adoption was pending. The user then clarified that PR #48's merge meant the team agreed to the contract. Codex corrected the contract, README, CONTRIBUTING, M1 checkpoint, provenance statuses, and PR #51 description to record adoption at merge revision d4850b8; corrected the issue-body follow-up; and restored #30 to closed. The separate persistence correction in PR #51 is unchanged.
- Validation: The GitHub API verified PR #48 merged on 2026-10-02 at d4850b8. Adoption is recorded from the user's explicit clarification on 2026-10-04. Documentation diff and relative-link checks passed; application code, tests, and data were unchanged in this correction, so application tests were not rerun. Individual student understanding remains unverified.
- PR or commit: [PR #51](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/51); [issue #30](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/30).
- Student review status: Pending; issue ownership, PR authorship, and agent checks do not establish approval of this follow-up.

### Entry 23: Restaurant menu browsing

- Student(s): Sreeram Nara (`SreeramNara`), issue #33 assignee.
- Artifact: `app/schemas/restaurant.py` (`Menu`), `app/repositories/restaurant.py` (`get_record`), `app/services/restaurant.py` (`get_menu`, `RestaurantNotFoundError`), `app/api/routes/restaurants.py`, `app/api/openapi.py`, `app/main.py`, `data/restaurants.json`, `tests/test_restaurant_menu.py`, `tests/test_openapi.py`, `tests/test_restaurants.py`, `tests/test_restaurant_repository.py`, `tests/test_restaurant_create.py`, `README.md`, `docs/FIRST_TIME_SETUP.md`, and `docs/QUICK_SETUP.md`.
- Label: `AI-GENERATED`.
- AI tool: Claude (Anthropic), via claude.ai.
- Purpose: Implement issue #33 against the adopted M1 contract so a customer can retrieve a restaurant's menu and items through Route → Service → Repository → JSON, building on the #35 persistence foundation.
- Influence: Claude wrote the tests first, then added the `Menu` read projection, `RestaurantRepository.get_record`, `RestaurantService.get_menu` with `RestaurantNotFoundError`, and the documented `GET /restaurants/{restaurant_id}/menu` route (404 `Restaurant not found`, generic 500). A small OpenAPI post-processing step removes FastAPI's automatic 422 from the menu operation, as the contract requires. After Gwantana's review on PR #52 pointed out that the first version removed 422 from every path-only GET (which would hide a real 422 from a future validated path parameter), Claude restricted it to an explicit list of contract-defined operations and added a regression test with a validated `int` path parameter. Claude added two representative menu items to each committed restaurant record. Two existing tests that implicitly assumed menu-less committed data were changed to state their intent explicitly: the M0 repository test now compares the four-field projection, and the #35 legacy-record test now writes its own record without `menu_items`. README and both setup guides were updated.
- Validation: On Python 3.12.3, the baseline on `main` passed 52 tests. The new test modules then failed at collection because `Menu` and `app.api.openapi` did not exist; after implementing the code, 72 passed and the 2 representative-data tests failed until menu data was added. After the data change, the 2 data-dependent existing tests failed as described and were updated. `python -m pytest -q` then passed 74 tests; `python -m compileall app` and `git diff --check` passed, and the session guard confirmed no test modified committed `data/`. A running Uvicorn server returned 200 with Harbour Slice's two items for `/restaurants/restaurant-002/menu`, 404 for an unknown restaurant, 200 for `/docs`, and OpenAPI listed exactly 200/404/500 for the menu operation while `POST /restaurants` kept its 422. For the review fix, the rewritten helper tests failed first because the explicit operation list did not exist; running the regression scenario against the original helper showed a real 422 from `/things/abc` that the original helper omitted from OpenAPI. After the fix, `python -m pytest -q` passed 75 tests, `python -m compileall app` and `git diff --check` passed, and live OpenAPI still listed 200/404/500 for the menu operation.
- PR or commit: [Issue #33](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/33); [PR #52](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/52); branch `feature/33-menu-browsing`.
- Student review status: Reviewed by Sreeram Nara on 2026-10-05, who confirmed he read the route, service, repository, `Menu` model, OpenAPI helper, and tests, can explain them, and ran the endpoints locally on Windows with Python 3.12. Peer review: Gwantana Kiboigo requested changes on PR #52 (OpenAPI helper scope, this entry); both were addressed.
