# Testing

These are team testing conventions. The supplied course brief specifies pytest for backend tests; current authoritative course material takes precedence. See [CONTRIBUTING.md](../CONTRIBUTING.md) for workflow and completion criteria.

## M0 minimum coverage

The supplied [M0 specification](milestones/M0.md) requires a working pytest suite covering the health endpoint, the restaurant-list operation, restaurant data/repository behaviour, and at least one meaningful invalid or failure case. Tests must use temporary or isolated data and must not modify committed representative data. Document the verified test command in the root README.

The test-first cycle below is a team convention; the supplied M0 specification requires tests but does not explicitly require that development order. This checklist does not mean these tests currently exist or pass.

## Current setup and commands

At drafting, this repository has no Python application, dependency file, pytest configuration, or tests. No passing test suite or working application is claimed. The following are invocation patterns to use **after** project dependencies and tests exist, from the repository root in its virtual environment:

```sh
python -m pytest
```

Target a real test path/node or behaviour name while developing:

```text
python -m pytest <actual-test-file>
python -m pytest <actual-test-file>::<actual-test-name>
python -m pytest -k <actual-behaviour-name>
```

Replace placeholders; do not run them literally. Document verified commands here when the suite is established. Use the project's interpreter so pytest and application dependencies resolve from the same environment. No tests collected is not successful feature verification.

No exact test directory structure is adopted yet. Group tests by the responsibilities they exercise, following the structure established when implementation begins. Do not create empty route/service/repository directories just to match an example.

## Write tests before implementation

**Team convention:** use a test-first cycle for new or changed behaviour and bug fixes. Tests come before the implementation code they verify.

1. Derive expected behaviour from the acceptance criteria and confirmed requirements.
2. Write a focused automated test using isolated data, then run it before implementing the behaviour. Confirm it fails because the behaviour is missing or incorrect; unrelated environment or setup failures are not evidence of this.
3. Write the smallest implementation needed to make the test pass, then run it again.
4. Repeat for relevant edge and failure cases. Refactor only with passing tests, and re-run affected tests after refactoring.
5. Run broader applicable checks before review and record the actual failing-before and passing-after commands/results in the PR.

For behaviour-preserving refactoring, run existing tests first and add any missing characterization tests before changing implementation. Those tests should pass against the existing behaviour; do not manufacture a failure.

Documentation-only changes do not require application tests. If a behaviour cannot reasonably be automated, explain the limitation, define reproducible manual checks before implementation, and record their outcomes afterward. Missing test infrastructure is a setup task to resolve before implementing testable behaviour, not a reason to defer tests until after the code.

## Naming and assertions

Use behaviour-oriented names, such as `test_add_item_rejects_unavailable_item` when that rule is confirmed. Keep arrange, action, and meaningful assertions clear. A test should verify observable behaviour, not mirror every implementation step.

Ask: **If this behaviour were broken, would this test fail?** Avoid assertions that only prove a mock returned its configured value. Mock external boundaries where useful, but do not mock away the rule, storage operation, or authorization being tested.

## Coverage by responsibility

| Test focus | Verify where relevant |
| --- | --- |
| Services | Business rules, calculations, current-state validation, ownership, permitted transitions, orchestration. |
| Routes/API | Parsing, status/response contracts, authentication and authorization, direct requests that bypass frontend restrictions. |
| Repositories | Serialization, stable IDs, relationships, isolated reads/writes, malformed data, failure behaviour, restart survival. |
| Integration | Important workflows across actual layers, persisted outcomes, historical integrity, and partial failures. |
| Frontend/manual | User workflows, loading/error feedback, keyboard/interaction behaviour, and relevant responsive states. |

Cover normal behaviour, invalid input, boundary values, missing resources, wrong roles or resource owners, invalid state transitions, persistence, and failures as appropriate. Derive expected results from requirements; do not invent rules to justify test cases.

## One default for file isolation

**Team convention:** file-backed tests use pytest's `tmp_path` and a fresh repository instance configured to use that temporary location. Copy required fixture data into it before invoking application code. Tests must never write to representative committed JSON/CSV data.

- Provide an explicit storage-path injection mechanism when implementing repositories; its API is not prescribed here.
- For route/integration tests, use the application's actual dependency mechanism to inject the isolated repository. Verify that no default path falls back to application data.
- Treat committed fixtures as read-only sources, even when testing an edit or migration.
- Ensure every write in a multi-step workflow uses isolated storage.
- Avoid shared mutable fixtures, test-order dependencies, uncontrolled time/randomness, global-machine state, and unnecessary network calls.
- Clean up through fixture lifetimes rather than deleting application data.
- Verify persistence by creating a fresh repository/application instance using the same temporary storage, not only by inspecting cached in-memory state.

If a different isolation mechanism becomes necessary, document the reason and update this convention in the same PR. Never run a suspected unsafe test against application data to see whether it writes there.

## Failures and regression tests

For a bug:

1. Reproduce the specific behaviour using safe data.
2. Before changing implementation code, add and run a focused regression test; confirm it fails for the defect where automation is reasonable.
3. Fix the root cause within the issue's scope.
4. Confirm the regression test and applicable existing tests pass.

Test both errors and resulting state. For checkout, cover order persistence failing before cart clearing, and an order write succeeding before a cart update fails. Check preserved cart/order state, historical meaning, and the agreed retry behaviour. Do not assume multiple JSON/CSV writes are transactional.

When a regression cannot reasonably be automated, explain why and provide reproducible manual evidence plus the remaining risk. Manual verification alone is insufficient for behaviour reasonably covered by automated tests.

## Verification before review

Run focused tests during development and broader applicable tests before review. Re-run affected checks after conflict resolution or changes that invalidate earlier evidence. Use actual configured lint, build, and frontend checks when applicable; no such tools are assumed yet.

Record:

- Exact command and working directory/environment context where relevant.
- Actual result, including relevant pass/fail/skip counts when available.
- Behaviour covered and important checks not performed.
- Manual steps and observed outcomes for changed UI/workflows.
- Any environment limitation, pre-existing failure, product failure, and remaining risk.

Never fabricate output, report an unrun command as passing, weaken assertions to hide a defect, or treat API tests as proof that a frontend works. Documentation-only changes need appropriate link/template/content checks, not invented application test results.
