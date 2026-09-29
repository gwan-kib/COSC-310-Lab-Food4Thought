---
name: Epic
about: Organize a major capability made up of multiple user stories
title: "[EPIC] "
labels: ""
assignees: ""
---

<!--
Use an epic for a major capability or coherent project area that spans multiple user stories.
Implementation work should remain in child user-story issues with their own acceptance criteria.
Do not use an epic as a substitute for a course milestone or as a catch-all task list.
-->

## Goal

What major capability should this epic deliver, and why does it matter?

## Source / Requirements

<!--
Link the current course/project source, requirement IDs if they exist, and the relevant workflow.
Do not invent stakeholder needs or requirements.
-->

Relevant source(s):

Relevant workflow / requirement(s):

## Delivery Target

Milestone:

Target release / tag:

## Scope

Included:

- 

Not included:

- 

## Child User Stories

<!-- Link only actual child issues. Add stories as the epic is refined. -->

- [ ] #
- [ ] #

## Dependencies / Blockers

Depends on:

Blocked by:

Related epics / issues / PRs:

## Engineering Requirements

<!-- Check only what applies to this epic. Detailed feature acceptance criteria belong in child user stories. -->

- [ ] Route → Service → Repository boundaries are respected where applicable
- [ ] Pydantic request/response models are used where applicable
- [ ] JSON/CSV persistence is handled through repositories where applicable
- [ ] Error and failure scenarios are handled
- [ ] Automated tests cover implemented behaviour
- [ ] Test data is isolated from committed application data
- [ ] API documentation matches the implementation
- [ ] Frontend communicates with the REST API where applicable
- [ ] CI passes
- [ ] Relevant documentation and provenance are updated

## Design / Engineering Decisions

<!-- Link significant design decisions or Decision Receipts. Keep detailed rationale in the appropriate project document. -->

- 

## Definition of Done

- [ ] All required child user stories are complete
- [ ] Child-story acceptance criteria are verified
- [ ] The capability works end-to-end at the intended milestone scope
- [ ] Relevant automated tests pass
- [ ] Relevant documentation is accurate
- [ ] Required implementation PRs received peer review
- [ ] Required provenance is complete
- [ ] Remaining limitations or deferred work are documented

## Notes / Open Questions

<!-- Separate confirmed requirements, assumptions, proposed decisions, and unresolved questions. -->
