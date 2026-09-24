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

- Student(s): Gwantana Kiboigo (`gwan-kib`), recorded author of the linked commit; attribution and responsibility for this historical entry await student confirmation. No other participating students are established by the available evidence.
- Artifact: `AGENTS.md`, `CONTRIBUTING.md`, `docs/TESTING.md`, `.github/ISSUE_TEMPLATE/user-story.md`, `.github/ISSUE_TEMPLATE/technical-task.md`, `.github/ISSUE_TEMPLATE/bug.md`, and `.github/PULL_REQUEST_TEMPLATE.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: On 2026-09-15, draft repository guidance from user-supplied project briefs and separate agent behaviour from team engineering workflow.
- Influence: Codex drafted the initial instructions and reorganized them into the seven documentation/template files. No application code or tests were generated.
- Validation: The retained assistance record reports checks of the seven documents, relative links, Markdown fences, whitespace, issue-template metadata, and `git diff --check`. During issue #9, the commit inventory and previous disclosure were inspected to verify scope. Historical checks were not rerun against the original working tree.
- PR or commit: [Project-planning commit 6826e6c](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/6826e6c191328dee82e66a83395ce735b66ad4e5), committed 2026-09-18 (America/Vancouver).
- Student review status: Pending; no student confirmation or peer approval is asserted.

### Entry 2: Test-first workflow and M0 documentation

- Student(s): Gwantana Kiboigo (`gwan-kib`), recorded author of the linked commit; historical attribution and responsibility await student confirmation.
- Artifact: `AGENTS.md`, `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/milestones/M0.md`, `README.md`, and the three issue templates and PR template under `.github/`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: On 2026-09-18, document the supplied test-first workflow, AI/provenance policy, and M0 foundational-gate requirements, with navigation links.
- Influence: Codex updated workflow documentation/templates and added the M0 checkpoint and documentation links, building on the earlier generated documentation. No application code or tests were generated. The README changes are included in the linked planning commit; student confirmation of the complete historical attribution remains pending.
- Validation: The previous `CONTRIBUTING.md` disclosure reports documentation-content and local-link checks. During issue #9, the planning commit and README diff were inspected. No application test results are claimed for these documentation changes.
- PR or commit: [Project-planning commit 6826e6c](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/6826e6c191328dee82e66a83395ce735b66ad4e5).
- Student review status: Pending; the record does not certify student understanding or approval.

### Entry 3: Initial Python development scaffold

- Student(s): Gwantana Kiboigo (`gwan-kib`), PR #1 author and implementation-commit author; responsible-student confirmation remains pending as recorded in the PR.
- Artifact: `.gitignore`, `requirements.txt`, `.github/workflows/ci.yml`, `app/main.py`, `app/__init__.py`, `app/api/__init__.py`, `app/api/routes/__init__.py`, `app/core/__init__.py`, `app/repositories/__init__.py`, `app/schemas/__init__.py`, `app/services/__init__.py`, `data/.gitkeep`, `tests/.gitkeep`, `README.md`, and `docs/TESTING.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Create the authorized initial Python package skeleton, dependency pins, ignore rules, CI configuration, and setup instructions.
- Influence: Codex created the scaffold and configuration and updated setup documentation. All eight Python files were empty; no feature implementation, representative data, or tests were generated. CI installed dependencies and compiled the scaffold only.
- Validation: PR #1 reports successful creation of two Python 3.12.13 environments, dependency installation (including an independent `python -m pip install -r requirements.txt`), `python -m pip check` with no broken requirements, `python -m compileall app`, imports of all four dependencies, `git diff --cached --check`, tracked-file/diff inspection, and ignore-rule checks. These are historical reported results, not checks rerun for issue #9. pytest, application startup, and endpoint checks were not performed because no application or tests existed. The implementation diff was inspected for this entry.
- PR or commit: [PR #1](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/1), merged; [implementation commit 0e9f6c8](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/0e9f6c893083a1a5a5c8080d675e1a9bf4e4d6c1).
- Student review status: Pending. PR #1's recorded disclosure leaves confirmation pending; its merged state does not prove student review. No submitted GitHub reviews were returned when inspected on 2026-09-22.

### Entry 4: Align provenance workflow with the course guide

- Student(s): `gwan-kib`, requester and issue #9 author; responsible-student review and confirmation of these entries remain pending.
- Artifact: `docs/PROVENANCE.md`, `CONTRIBUTING.md`, `AGENTS.md`, `docs/milestones/M0.md`, `.github/PULL_REQUEST_TEMPLATE.md`, the three `.github/ISSUE_TEMPLATE/` files, and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Implement issue #9 using the downloaded course guide and replace obsolete instructions to defer the provenance record.
- Influence: Codex extracted the guide's text, drafted the shared record and historical entries, and updated workflow instructions and links. Historical statements are limited to available disclosures, commit history, and PR evidence; no student approval is invented.
- Validation: Compared the required labels and fields with the downloaded guide and inspected documentation history and PR #1. A local Python documentation check passed for all 10 Markdown files (relative links/anchors, fences, whitespace, and obsolete wording), all three issue templates, and all four entries' required fields and labels. `git diff --check` passed. The complete changed documentation was inspected. No application tests are applicable to this documentation-only change.
- PR or commit: [Issue #9](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/9); [implementation commit `1ff670b`](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/1ff670b33599cc92cde73b05bb3b30751277b5a1), which added the shared provenance workflow to `main`.
- Student review status: Pending; student confirmation and peer review must be recorded only after they occur.

### Entry 5: Restaurant schema, sample data, and configuration

- Student(s): `Tc2006415`, contributor and issue #3 assignee; student review and responsibility for the generated work await confirmation.
- Artifact: `app/schemas/restaurant.py`, `app/core/config.py`, `data/restaurants.json`, `tests/test_restaurant_foundation.py`, and `README.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Establish the M0 restaurant response contract, representative JSON data, and configurable data location for issue #3.
- Influence: Codex drafted the Pydantic model, sample records, path-selection function, tests, and related README updates from the course requirements and issue acceptance criteria.
- Validation: On Python 3.12, all five foundation tests were observed failing before implementation because the model/configuration modules were missing; after implementation, `python -m pytest tests/test_restaurant_foundation.py -q` and `python -m pytest -q` each passed 5 tests, and `python -m compileall app` passed. Student review remains pending.
- PR or commit: [Issue #3](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/3); [implementation commit a333af4](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/a333af41265be2cafcb5b054299932239b76a238). [PR #11](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/11).
- Student review status: Pending; passing agent-run checks do not establish student understanding or approval.

### Entry 6: Restaurant repository layer

- Student(s): `Tc2006415`, recorded implementation-commit and PR author; student review and responsibility for the generated work await confirmation.
- Artifact: `app/repositories/restaurant.py`, `tests/test_restaurant_repository.py`, `README.md`, and `docs/TESTING.md`.
- Label: `AI-GENERATED`.
- AI tool: Codex.
- Purpose: Implement issue #4's persistence-access layer using the issue #3 restaurant model and configurable data path.
- Influence: Codex drafted the JSON-reading repository, typed results, clean persistence/validation errors, isolated-data tests, and documentation updates.
- Validation: On Python 3.12, all five repository tests were observed failing before implementation because the repository module was missing; after implementation, `python -m pytest tests/test_restaurant_repository.py -q` passed 5 tests, `python -m pytest -q` passed 10 tests, and `python -m compileall app` passed. Student review remains pending.
- PR or commit: [Issue #4](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/4); [implementation commit 91198fa](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/commit/91198faeb1424f6c4c5dc516de100f7e9221392b); [PR #12](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/12).
- Student review status: Pending; passing agent-run checks do not establish student understanding or approval.

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
