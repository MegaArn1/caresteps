# Tool usage evidence — REQUIRED

> Handbook p.37: "Proof of product usage is mandatory: chat screenshots, API call logs,
> or a written development-process description. **Without proof, the project will not
> proceed to scoring.**"

## Current status

**Task definitions ready. Evidence collection pending.**

This directory now contains [`TASKS_FOR_AI_TOOLS.md`](TASKS_FOR_AI_TOOLS.md) — three concrete, low-risk tasks designed for CodeBuddy or WorkBuddy completion. Complete 1-2 of them and save screenshots or recordings here to satisfy the Handbook requirement.

## What the handbook requires

> **CodeBuddy / WorkBuddy Conversation History — Required**
> "Minimum of 3 screenshots/screen recording of your chat logs from CodeBuddy or
> WorkBuddy during the development process"

The project must also be "built on at least one of the products CodeBuddy or WorkBuddy". Miora is offered as an additional tool but does **not** substitute (Handbook p.37 is explicit; p.39's looser wording should not be read against it).

## Next step

1. Open [`TASKS_FOR_AI_TOOLS.md`](TASKS_FOR_AI_TOOLS.md) and choose 1-2 tasks
2. Complete them in **CodeBuddy** or **WorkBuddy** — not a token session
3. Capture screenshots or screen recordings showing:
   - The conversation (your prompts + AI responses)
   - The verification results (curl output, new files, test output)
4. Save files to this directory with descriptive names (see task doc for naming)
5. Update this README with a completion log (date, tool, evidence files, outcome)

## The three tasks

All tasks are designed to be **low-risk** (won't break existing tests), **independently verifiable** (clear success criteria), and **genuinely useful** to the project:

- **Task 1:** Add `/api/stats` endpoint returning system metrics JSON
- **Task 2:** Write `docs/DEPLOYMENT.md` covering 2+ PaaS platforms (pure documentation, zero code risk)
- **Task 3:** Add `/readings/export.csv` for blood pressure data export

Full requirements in [`TASKS_FOR_AI_TOOLS.md`](TASKS_FOR_AI_TOOLS.md).

## Sanitization checklist

Before submitting, verify every screenshot:

- [ ] No API keys, tokens, or `.env` contents visible
- [ ] No personal information (real names, addresses, phone numbers, patient data). All patient data in this project is fictional — keep it that way in captures.
- [ ] No other teams' or other people's private material
- [ ] No file paths revealing unrelated account names or directories

## Status table

| Item | Status |
|---|---|
| Task definitions written | **DONE** — see `TASKS_FOR_AI_TOOLS.md` |
| At least 1-2 tasks completed in CodeBuddy/WorkBuddy | **NOT DONE** |
| At least 3 conversation screenshots/recordings captured | **NOT DONE** |
| Evidence files saved to this directory | **NOT DONE** |
| Evidence sanitized | N/A |
| This README updated with completion log | **NOT DONE** |

Until rows 2-3 are complete, this submission does not meet the Handbook's eligibility condition, regardless of the quality of the prototype.
