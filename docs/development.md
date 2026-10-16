# Development workflow

CareSteps uses a task-based development and verification workflow: define a small
deliverable, inspect the changed files, and run observable checks against fictional data.

## Recorded WorkBuddy tasks

The saved October 15, 2026 conversation documents two completed tasks:

- Implement the consolidated system-statistics API and associated regression tests.
- Write the single-instance cloud deployment guide for Render and Railway.

Supporting records are the [completion summary](../submission/tool-evidence/task1-2-workbuddy-summary.md),
[API result](../submission/tool-evidence/task1-stats-api-result.json),
[three conversation screenshots](../submission/tool-evidence/README.md) and
[combined evidence PDF](../submission/tool-evidence/CareSteps_WorkBuddy_Evidence.pdf).
The evidence PDF packages the existing screenshots rather than a newly executed session.

## Verification

Review the implementation and run `make test` and `make demo-check`. Source-linked
health content retains its review state, and all demonstration patient records are fictional.
Software checks do not establish clinical validation or accessibility conformance.

Development tools are separate from the application's optional runtime model gateway.
The gateway's configured model identifier is not a development-tool record or independent
verification of the backend provider.

Credentials, local environment state and raw media intermediates are excluded from
publication. See [evaluation](evaluation.md) and the [submission checklist](../submission/SUBMISSION_CHECKLIST.md).
