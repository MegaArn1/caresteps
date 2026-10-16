# WorkBuddy conversation evidence

The actual form requires chat history and **at least three screenshots**, uploaded as
**one file no larger than 10 MB**. Use
[CareSteps_WorkBuddy_Evidence.pdf](CareSteps_WorkBuddy_Evidence.pdf): a scope/contents
page followed by all three existing October 15 conversation screenshots.

| Screenshot | What it shows |
|---|---|
| [22:17:53](screenshot/Screenshot%202026-10-15%20221753.png) | WorkBuddy interface, task request and project inspection |
| [22:37:51](screenshot/Screenshot%202026-10-15%20223751.png) | Statistics route/tests, deployment guide and validation work |
| [22:52:18](screenshot/Screenshot%202026-10-15%20225218.png) | Completion response, API result and deployment-guide preview |

The three captures are from one real task session, not three separate sessions. The
form asks for three screenshots and does not require three separate conversations.
Private local-path prefixes and an account display name were redacted. Prompts, replies,
tool identity and result content remain. [evidence-manifest.json](evidence-manifest.json)
records image hashes and redaction boxes; originals remain in the local archive.
`python3 submission/tool-evidence/build_evidence.py` recreates the PDF from these
sanitized images (optional dependencies are in `submission/requirements-assets.txt`).

[Task result JSON](task1-stats-api-result.json) and the
[completion record](task1-2-workbuddy-summary.md) provide supporting written evidence.
The completion record describes historical findings; it is not a current bug checklist.

The recorded tasks produced the system-statistics API, tests and deployment guide.
See [the development workflow](../../docs/development.md) for the observable checks.
