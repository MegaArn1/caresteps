# Tool usage evidence — REQUIRED, and currently NOT satisfied

> **This directory is a placeholder. The requirement it describes is unmet.**
>
> Handbook p.37: "Proof of product usage is mandatory: chat screenshots, API call logs,
> or a written development-process description. **Without proof, the project will not
> proceed to scoring.**"
>
> Nothing here is fabricated, and nothing here should be fabricated later. This file
> exists so the gap is impossible to overlook.

## What the handbook requires

> **CodeBuddy / WorkBuddy Conversation History — Required**
> "Minimum of 3 screenshots/screen recording of your chat logs from CodeBuddy or
> WorkBuddy during the development process"

The project must also be "built on at least one of the products CodeBuddy or
WorkBuddy". Miora is offered as an additional tool but does **not** substitute
(Handbook p.37 is explicit; p.39's looser wording should not be read against it).

## What to do

1. Do real development in **CodeBuddy** or **WorkBuddy** — not a token session. Use it
   for something this repository actually needed, for example:
   - generating the initial SQLite schema in `app/db.py` and iterating on it,
   - writing or debugging the safety rule patterns in `content/rules/`,
   - drafting the four adherence-state logic and having it reviewed,
   - producing the pytest cases in `tests/`,
   - debugging the Starlette `TemplateResponse` signature change.
2. Capture **at least three** screenshots or a screen recording that show the
   *conversation*, including the prompts and the results.
3. Put the files in this directory and replace this README with
   `evidence-index.md`, recording for each item: the date, what was being worked on,
   which files it affected, and what a human then verified.

## How to make the evidence credible

The handbook asks for proof of *usage*, and a judge can check whether the evidence
corresponds to the code. So:

- **Match the evidence to the repository.** If a screenshot shows CodeBuddy producing
  a schema, that schema should be recognisable in `app/db.py`.
- **Report the human correction.** The strongest evidence of genuine use is where a
  tool's output was wrong and a person caught it. The build log records several real
  examples to draw on — the `TemplateResponse` signature break, the missing
  `itsdangerous` dependency, the keyword rule that refused "I forgot my tablet
  yesterday".
- **Do not backfill.** Retrospective sessions invented after the fact are both
  against the rules and easy to spot, because they do not line up with the commit
  history.

## Sanitising

Check every screenshot before submitting:

- [ ] No API keys, tokens, or `.env` contents visible.
- [ ] No personal information (real names, addresses, phone numbers, patient data).
      All patient data in this project is fictional — keep it that way in captures.
- [ ] No other teams' or other people's private material.
- [ ] Any file paths shown do not reveal anything you would not want published
      (account names, unrelated directories).

## Current status

| Item | Status |
|---|---|
| At least 3 CodeBuddy/WorkBuddy conversation captures | **NOT DONE** |
| Project built on CodeBuddy/WorkBuddy | **NOT DONE** — this repository was not developed in either tool |
| Evidence sanitised | N/A |
| `evidence-index.md` written | **NOT DONE** |

Until the first two rows are resolved, this submission does not meet the Handbook's
eligibility condition, regardless of the quality of the prototype.
