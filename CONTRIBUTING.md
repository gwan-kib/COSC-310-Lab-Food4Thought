# Contributing

## Purpose and authority

This is the human team workflow for Food4Thought, the four-student, 12-week UBC Okanagan COSC 310 food-delivery project. Engineering work includes requirements, design, code, tests, documentation, review, integration, provenance, and contribution evidence.

Unless labelled otherwise, this document establishes **team/repository conventions**, not grading requirements. **Course/project constraints reported in the supplied brief** are identified below and must be checked against current authoritative course material. Recommendations are labelled explicitly. See [AGENTS.md](AGENTS.md#sources-and-authority) for source priority and conflict handling.

At drafting, the checkout has no application implementation, dependency file, test suite, or verified setup commands. No frontend framework, Python version, endpoint schema, CI, or merge strategy is selected by these documents.

The supplied M0 specification is summarized in [the M0 checkpoint](docs/milestones/M0.md), including scope, required evidence, submission, and unresolved source questions. Use that checkpoint for M0; the full-project workflows below are not all M0 deliverables.

## Start with an issue

```text
Issue → Assign yourself → Update main → Feature branch → Write failing tests
      → Implement → Pass tests → Refactor → Documentation → Commit → Push → PR → Peer review
      → Address comments → Merge → Pull main
```

The GitHub Project Board is the primary record of planning, ownership, and progress. Read the full issue, acceptance criteria, current milestone, dependencies, blockers, and related PRs before starting. Verify actual code; board status alone is not evidence of implementation.

Search for overlapping work before creating an issue. Use:

- [User story](.github/ISSUE_TEMPLATE/user-story.md) for functional requirements.
- [Technical task](.github/ISSUE_TEMPLATE/technical-task.md) for refactoring, tooling, configuration, test infrastructure, or documentation.
- [Bug report](.github/ISSUE_TEMPLATE/bug.md) for reproducible defects.

Assign yourself only after checking ownership and coordinating overlap. Use actual board fields and milestones; none are assumed here. Keep one focused issue per branch where reasonable. Acceptance criteria must be observable and grounded in a requirement or an agreed technical objective. Do not invent stakeholder needs or business rules to fill a template.

Record source references and preserve the chain:

```text
Course requirement → Requirement ID (when assigned) → Issue/acceptance criteria
                  → Design → Branch/code → Tests/docs → PR/review → Evidence
```

Use actual references, paths, and test names. Do not fabricate requirement IDs, issue numbers, or completed evidence. If discoveries materially change scope, update the issue and dependencies, record why, and seek clarification where necessary. Record unrelated technical debt separately instead of adding it to the task.

## Branches and safe integration

**Course workflow reported in the brief:** no implementation commits directly to `main`; implementation enters through PRs. Use focused, short-lived branches.

**Team naming convention:** use `feature/<issue>-<short-description>`, `fix/<issue>-<short-description>`, or `chore/<issue>-<short-description>` as appropriate. For example, `feature/23-cart-total`. This is a team convention, not an exact course-mandated rule. If no issue number exists yet, omit it and record the pending issue link.

Inspect before changing branches:

```sh
git status
git branch --show-current
git remote -v
git diff
git diff --cached
```

After verifying the working tree, branch names, remote, and upstream, a new feature may start with:

```sh
git checkout main
git pull --ff-only
git checkout -b feature/23-cart-total
```

Replace the example with the actual issue. Continue on an appropriate existing task branch instead of restarting. If a fast-forward pull fails, inspect divergence; do not reset away commits. Report when remote information cannot be refreshed.

Preserve unrelated working-tree changes. Do not automatically stash, relocate, or commit another person's work. Use an isolated worktree when appropriate, or coordinate a safe separation if changes conflict. Never use destructive restore/reset/clean commands merely to obtain a clean tree.

### Merge conflicts

1. Inspect status and diffs; identify local changes and conflicting commits before integration.
2. Coordinate shared ownership and understand intended behaviour on both sides.
3. Resolve from requirements and layer contracts, not by blindly choosing “ours” or “theirs.”
4. Inspect the entire resulting diff, including non-conflicting changes and documentation.
5. Re-run affected tests and applicable broader checks; record results in the PR.

Do not casually rewrite teammates' commits. Force-pushing a shared branch requires explicit team approval and justification. No merge strategy or approval count is assumed beyond the review rules below.

## Engineering constraints

**Course/project constraints reported in the brief:** use Python, FastAPI, Pydantic, pytest, and JSON and/or CSV persistence. Do not introduce a database unless later authoritative course material changes that constraint. Use a Python virtual environment. M0 permits `requirements.txt` or `pyproject.toml`; this repository's convention is to maintain `requirements.txt` once dependencies are selected.

Required workflows are Discover a Restaurant, Build a Cart, Place an Order, Manage an Order and Delivery, and Manage the Platform. Functional areas include authentication/roles, restaurant discovery, menu management, customer accounts, carts, checkout/orders, order management, delivery management, and reporting. The instructor's Figma mockup is a specification and starting point, not a completed frontend.

Real payment providers/transactions, GPS, external delivery services, and production-scale infrastructure are outside normal core scope. Optional filtering, favourites, reviews, promotions, notifications, or delivery enhancements require explicit selection after the required system is complete and stable.

### Layer boundaries

```text
Frontend → FastAPI routes → Services → Repositories → JSON / CSV
```

| Layer | Responsibility |
| --- | --- |
| Frontend | Present workflows, collect input, call the API, and display loading, validation, success, and failure states. |
| Routes | HTTP paths, parameters, request parsing/models, responses, and status codes. Delegate substantial business logic. |
| Services | Business rules, calculations, state-dependent validation, transitions, and orchestration. |
| Repositories | Storage operations and serialization; hide JSON/CSV details from routes and services. |
| Persistence | Survive restarts with stable IDs, valid relationships, and preserved historical meaning. |

Routes and services must not directly open persistence files. Pydantic structural validation does not replace state-dependent service checks. This is the required boundary model, not a claim that corresponding modules already exist.

### Backend authority and reliability

The backend enforces permissions, resource ownership, and current-state rules even when the frontend blocks an action. Relevant roles include customers, restaurant users, and system administrators; derive exact permissions from current requirements. Never trust client-supplied roles, ownership, prices, totals, or stale resource state as authoritative.

Validate relevant restaurants, menus, accounts, carts, orders, and deliveries against current state. Derive lifecycle transitions from the specification. Preserve historical transaction information when current menu prices or restaurant details change; do not invent snapshot fields before the data design supports them.

Checkout must validate current data, recalculate required values, create the required snapshot, successfully persist the order, and only then close/clear the cart when required. Consider both an order-write failure and a successful order write followed by a failed cart update. Define resulting state and retry behaviour; ordering alone does not make multiple file writes atomic.

Do not swallow meaningful exceptions, return success after persistence failure, expose unnecessary internal errors, or silently treat corrupt data as empty. Preserve stable identifiers and relationships. Test failure consequences, not just exception handling.

**Recommended practices:** use safe file replacement and write coordination when the execution model warrants them; document actual guarantees. Use established password-hashing/authentication libraries and never store plaintext passwords or invent cryptography. Keep solutions proportionate to this project's needs.

## Implementation, tests, and documentation

Inspect nearby code and trace the request/data path before changing it. Prefer small, explainable changes. Refactoring preserves external behaviour unless the issue requires otherwise. Do not mix unrelated formatting, fixes, refactors, or documentation cleanup into a feature.

**Team convention: write tests before implementation code.** For new or changed behaviour and bug fixes, write the relevant automated tests first and run them to confirm they fail for the expected missing behaviour or defect. Then write the smallest implementation that makes them pass, and refactor while keeping tests passing. For behaviour-preserving refactoring, confirm existing coverage passes and add any missing characterization tests before changing the implementation.

Follow [TESTING.md](docs/TESTING.md) for the test-first cycle, coverage, isolation, regression tests, commands, and evidence, including changes where automated tests are not applicable. Run narrow checks while developing and broader applicable checks before review. Never claim verification that was not performed.

Keep comments focused on why, business constraints, edge cases, and unusual ordering. Remove stale comments in changed code and avoid unexplained TODOs or commented-out implementations. Docstrings should clarify meaningful contracts and side effects.

Update affected documentation in the same PR as code. Keep README concise and useful for setup, running, testing, and navigation. Do not document secrets or commands that do not exist. Keep dependency information reproducible; never generate requirements from an unrelated global environment or assume global packages.

Create the following documents when real content warrants them, rather than filling speculative files now:

| Future document | Trigger and content |
| --- | --- |
| `docs/DEVELOPMENT.md` | Verified clone/setup instructions, Python version, virtual environments, dependencies, startup commands, environment variables, troubleshooting, and structure. |
| `docs/ARCHITECTURE.md` | Actual components, responsibilities, interfaces, dependencies, and data flow; update diagrams with implementation. |
| `docs/REQUIREMENTS.md` | Source-grounded requirements index with IDs when adopted, issue/PR links, implementation/tests, and status. Avoid duplicating the entire specification. |
| `docs/DATA_MODEL.md` | Agreed fields, identifiers, relationships, mutable data, historical snapshots, formats, and compatibility/migration considerations. |
| `docs/API.md` | Implemented API semantics, rules, errors, and cross-layer contracts. Prefer generated OpenAPI for raw schemas once available. |
| `docs/CODE_REVIEW.md` | Extract the review guidance below if it grows enough to warrant a separate handbook. |
| `docs/DECISIONS.md` | Significant decisions: date, problem/source, decision/status, rationale, alternatives, trade-offs, and consequences. Avoid a large empty ADR system. |
| `docs/milestones/M1.md` through `M3.md` | Create each when its actual specification arrives: source/version, deliverables, acceptance checklist, issues, dependencies, risks, ownership, required evidence, and contribution notes. M0 is recorded in the linked checkpoint above. |

**Milestone orientation from the brief, not a substitute for specifications:** M0 establishes foundations and layer connections; M1 delivers a complete vertical slice; M2 integrates major workflows and business rules; M3 stabilizes, tests, refactors, documents, and prepares release. Do not infer deadlines or rubric details.

When contracts or behaviour change, update requirement/acceptance-criteria links when officially clarified, examples, tests, designs, and documentation. Consider existing stored data and backward compatibility. Do not leave diagrams or docs contradicting implementation.

## Commits and pull requests

Before committing, run `git status`, `git diff`, and `git diff --cached`; inspect new files too. Prefer explicit file staging over `git add .`, and re-read the exact staged diff. Use `git diff --check` for whitespace problems. Stage the entire tree only when every change intentionally belongs to the commit.

Keep commits small and focused on one logical change. Examples of useful subjects:

```text
Add quantity validation to cart service
Reject checkout when cart is empty
Add tests for unavailable menu items
Document order persistence format
Update setup instructions for new dependency
```

These illustrate wording, not additional business requirements. Avoid `fix`, `stuff`, `changes`, `final`, `final2`, `working`, and `misc`. Do not commit secrets, debugging output, `.venv`, generated caches, machine-specific paths, or accidental IDE files.

Push the intended feature branch and open a PR using the [PR template](.github/PULL_REQUEST_TEMPLATE.md) for every PR. Complete relevant sections and explain non-applicable checks. Link the actual issue; use a closing keyword only when the PR fully resolves it. Include design decisions, actual test evidence, documentation/provenance status, and reviewer attention points.

Before requesting review, inspect the complete diff against the verified base, check acceptance criteria, run applicable checks, and remove unrelated changes from the PR without losing them. Draft/incomplete work must be identified as such.

### Peer review and comments

**Course review rules reported in the brief:** students may not approve their own PRs; significant changes require review by another team member. Reviewing your own diff is preparation, not peer approval.

Review for:

- Correctness, acceptance criteria, edge cases, and unintended scope.
- Thin routes, service-owned rules, repository-owned persistence, and shared contracts.
- Backend authentication/authorization, ownership, and current-state checks.
- Stable IDs, valid relationships, historical integrity, order/delivery lifecycles, partial writes, and retries.
- Meaningful tests and assertions, failure coverage, and isolation from committed data.
- Readability, names, duplication, complexity, documentation, and provenance.

Ask: **If this behaviour were broken, would the test actually fail?** Do not approve only because CI is green, code compiles, the happy path works, or the diff is small.

Make comments useful engineering evidence. Record decisions, clarifications, scope changes, test evidence, and blockers. A blocker comment states what is blocked, why, what was tried, evidence, and the needed action. Review comments identify exact code/behaviour, impact, risk, and a suggested direction. For example, where such a method exists:

> `CartService.checkout()` clears the cart before the order write succeeds. A write failure loses the customer's cart without creating an order. Persist the order before clearing the cart, and cover the failure path.

Distinguish blocking defects from optional suggestions. Do not post activity-only comments or resolve substantive feedback without fixing it or explaining why no change is needed.

Before merging, verify required review, actual checks, resolved feedback, and the final diff. Follow repository settings without inventing approval counts. Verify the merge and then update issue/board status; pull `main` safely for subsequent work. “Ready for review” and “merged” are different states.

## Provenance and individual understanding

**Course policy:** the user-supplied **Generative AI Use and Provenance Guide**, read on 2026-09-22, requires one shared [docs/PROVENANCE.md](docs/PROVENANCE.md). Students remain responsible for understanding, validating, testing, correcting, and explaining all submitted work.

Record AI use when it produces or influences a project artifact: code, tests, documentation, diagrams, API specifications, or adopted design decisions. Record each relevant contribution separately when contributors or AI roles differ, even for the same artifact. Interactions that do not affect project artifacts, such as learning a concept, need no entry; minor autocomplete that does not meaningfully affect work normally needs none. When in doubt, record the contribution. Labels on every Git commit are not required.

Use one label per entry, based on the role AI played:

| Label | Use when |
| --- | --- |
| `AI-GENERATED` | AI produced content or a substantial part that was used or adapted, even if the output was later edited. |
| `AI-ASSISTED` | AI provided ideas, explanations, alternatives, or guidance, but the student created the final content. |
| `AI-REVISED` | The student created the original work and AI later substantially changed, refactored, or rewrote it. |
| `NO-AI` | No generative AI produced or influenced the work described in the entry. |

For each recorded contribution, include **student(s), artifact, provenance label, AI tool, purpose, influence, validation, and the relevant PR or commit when practical**. Use the [entry template](docs/PROVENANCE.md#entry-template). Do not fabricate identities, tool details, checks, or approval; distinguish historical reported validation from checks performed now.

**Team workflow:** update the shared file with the affected work, link its entries in the PR, and add the PR/commit reference when available. Keep responsible-student confirmation and review status explicit; agent checks do not certify student understanding. Earlier documentation and scaffold assistance disclosures are now recorded in [the historical entries](docs/PROVENANCE.md#recorded-contributions). Recheck newer authoritative course guidance before submission.

The use of generative AI does not automatically reduce a student's grade. **However, submitting work that a student cannot explain, validate, test, or take responsibility for may result in the student failing the individual component.** Do not promise grading outcomes. The earlier brief prohibits generative AI during midterms and other explicitly prohibited activities; consult current rules without extending those restrictions by assumption.

Every student should be able to set up/run the app, run and interpret tests, demonstrate workflows, trace requests, explain rules and associated tests, discuss architecture/trade-offs/limitations, and explain work contributed to or reviewed. Leave a short walkthrough after significant changes. Avoid hidden design shifts or generated changes the team cannot explain.

## Contribution evidence and Definition of Done

**Assessment context reported in the brief:** each milestone requires a contribution statement; development artifacts may serve as evidence. Commit count and lines of code are not direct measures of contribution. Record meaningful work through issues, commits, PRs, substantive reviews, tests, documentation, decisions, and discussions. Do not manufacture commits, fake work, or shallow reviews to inflate metrics.

Before calling an issue complete, confirm where relevant:

- [ ] Source-grounded acceptance criteria are satisfied.
- [ ] Architecture, backend rules, authorization, and current-state validation are correct.
- [ ] Historical data, stable IDs, relationships, and persistence remain valid.
- [ ] Failure/retry behaviour is understood and verified appropriately.
- [ ] Tests were written and observed failing for the expected reason before implementing new/changed behaviour or a bug fix; non-applicable cases are explained.
- [ ] Meaningful tests pass and do not alter committed representative data.
- [ ] Applicable manual checks and broader checks are complete; remaining gaps are explicit.
- [ ] Affected setup, API/data, design, requirements, and other documentation is updated.
- [ ] Required provenance is complete in the current format; student review is accurately recorded.
- [ ] The complete diff contains no secrets, accidental artifacts, or unrelated work.
- [ ] The PR contains real evidence; significant work received peer review and no self-approval.
- [ ] Substantive feedback and applicable integration requirements are satisfied.
- [ ] Merge and issue/board completion state are verified.
- [ ] The responsible student can explain the change and contribution evidence is truthful.

Explain non-applicable items. Work awaiting source clarification, provenance format, testing, human review, or integration must retain that pending status. A working happy path alone is insufficient.
