# Agent Instructions

Use this file for agent behaviour. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the team workflow and [docs/TESTING.md](docs/TESTING.md) for testing conventions. Use the issue and PR templates linked from CONTRIBUTING.

## Sources and authority

Use this priority order:

1. Current milestone specification, rubric, Canvas announcement, instructor clarification, or TA clarification.
2. Current COSC 310 food-delivery project specification.
3. Repository-level `AGENTS.md`.
4. Current implementation, configuration, tests, dependency files, and data formats.
5. GitHub issue and GitHub Project Board.
6. Repository documentation.
7. Earlier milestone material not superseded.
8. General engineering knowledge where those sources do not answer the question.

Read applicable nested instructions. Repository instructions remain subject to governing agent instructions and tool permissions. The Project Board governs planning, ownership, and progress; it does not override course sources or prove implementation exists.

Identify conflicting sources and affected behaviour explicitly. Prefer the newest authoritative course source when applicable, recording the resolution. Flag unresolved ambiguity and continue independent work. Never invent requirements, deadlines, grading criteria, stakeholders, business rules, fields, endpoints, acceptance criteria, or existing team policies.

Distinguish **course requirements**, **team/repository conventions**, and **recommendations**. The user has supplied the M0 foundational-gate specification and the AI/provenance policy; see [the M0 checkpoint](docs/milestones/M0.md) and CONTRIBUTING. Other course claims come from the earlier supplied brief; Figma and GitHub planning artifacts remain unverified. At drafting, no application code, dependencies, or tests existed. Reinspect the checkout; do not treat that inventory as permanent.

## Before editing

1. Read the full issue, acceptance criteria, and current milestone sources; never implement from a title alone.
2. Check the Project Board, owner, dependencies, blockers, and overlapping PRs. Do not take over another student's work without coordination.
3. Inspect `git status`, current branch, staged and unstaged diffs, remotes, and applicable instructions. Refresh remote `main` information when possible; disclose stale or unavailable information.
4. Inspect the closest implementation and trace the frontend → route → service → repository → persistence path.
5. Read related models, data files, tests, fixtures, configuration, and documentation.
6. Identify effects on API/shared contracts, persistence format, authentication, authorization, business rules, historical data, test isolation, setup, diagrams, and provenance.
7. Choose the smallest correct scope and a proportionate plan covering design, verification, documentation, and unresolved decisions.

If a source or component is missing, say so. New files/functions/endpoints must follow the authorized task and established requirements, not assumptions that they already exist.

## While working

- Follow CONTRIBUTING's engineering constraints, workflow, and Definition of Done. Preserve unrelated changes; do not silently broaden scope or clean up unrelated code.
- Write and run tests before implementation code for new/changed behaviour and bug fixes; verify the expected failure, implement, then verify passing tests. Follow TESTING's test-first cycle and its guidance for behaviour-preserving refactoring and non-applicable automation.
- Keep business rules authoritative on the backend. Preserve layer boundaries, historical meaning, stable identifiers, and safe checkout ordering.
- Prefer understandable changes students can explain. Comments explain why, constraints, or non-obvious behaviour. Avoid syntax narration, stale comments, commented-out implementations, essay-length generated comments, and unexplained TODOs. Use docstrings to clarify contracts, side effects, or failures.
- Use the project's actual environment and commands. Do not import another project's package manager, branch model, CI, release, or deployment conventions.
- Follow TESTING's isolated-storage approach. Never let automated tests write to committed representative data.
- Never commit or expose secrets, credentials, secret environment values, debugging dumps, virtual environments, or accidental generated files.
- Do not discard changes to obtain a clean tree, rewrite teammates' history casually, or force-push shared branches without explicit team approval and justification. Follow CONTRIBUTING's conflict procedure.
- Keep GitHub writes within user authorization. If posting is unavailable or unauthorized, prepare the content and report it as unposted. Do not invent issues, ownership, comments, reviews, or board updates.
- Do not impersonate a peer reviewer, self-approve on a student's behalf, or certify student understanding without student involvement.

## Verification and provenance

Run applicable checks and inspect the complete final diff, including new files. Give exact commands and actual results. Never claim tests/builds pass, an endpoint works, or an application runs without verification. Separate environment failures, product failures, pre-existing failures, and unperformed checks; explain remaining risk.

Follow [CONTRIBUTING's provenance policy](CONTRIBUTING.md#provenance-and-individual-understanding). Do not invent current-milestone labels or create `docs/PROVENANCE.md` before its required format is available. Until then, retain assistance facts in the PR/handoff and report formal provenance as pending. This supersedes the initial draft's provisional-file instruction.

## Handoff

Provide a concise handoff covering the following; group headings when useful and mark non-applicable items honestly:

- Issue and branch.
- Summary and files changed.
- Behaviour and business rules affected.
- Architecture/design decisions.
- Tests added/changed and exact verification commands/results.
- Documentation and provenance status.
- Risks, limitations, unresolved questions, and follow-up.
- Anything requiring special reviewer attention.

Distinguish verified facts, assumptions, recommendations, and unresolved questions. Separate local edits, commits, pushes, PR creation, review, and integration. Describe work awaiting review or verification accurately; do not call it complete solely because the happy path works.
