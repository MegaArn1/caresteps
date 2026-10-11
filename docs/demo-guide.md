# CareSteps — Live Demonstration Runbook

> For the six-minute walkthrough. Written for the person holding the laptop, not for a judge.
> Everything in this file was observed running on 2026-10-11 against the seeded demo
> database — with two exceptions, both marked where they occur: the conversational turns were
> driven through `POST /api/chat` rather than an on-screen chat box, because no template in this
> build renders one, and the live model path has never been run at all. Where a claim is not
> verified, it says so.

Project identity, for the framing: Tencent Cloud AI Singapore Hackathon 2026, Healthcare Track
(NTU LKC Medicine), Challenge Statement 2 — "AI Healthier Every Day: Intelligent Support for
Long-Term Self-Care", Scenario 3 — Hypertension Management for Older Adults (65+).

**The demonstration does not require a working model endpoint.** Degraded mode is fully
functional: recording, viewing, statistics, summaries, the support flow and the emergency path
all work with no model configured and no network. Only the free-text explanation layer changes.

---

## 0. What was actually verified before writing this

Recorded here so the presenter knows which parts of the script are known-good.

| Checked | Result |
|---|---|
| `make seed` from a clean database | Ran. 14 sources, 23 facts enabled, 1 held back. Rules v1: 21 enabled, 2 held for review, 23 total. Profile created. |
| 162-test suite | `162 passed` |
| `/healthz` in degraded mode | Returns the JSON in §1.3 |
| `/healthz` with `LLM_BASE_URL` + `LLM_MODEL` set | `live: true`, `degraded: false` — the badge disappears |
| Chat turn with an unreachable endpoint | Degrades in under 1 second to the scripted reply. The app keeps working. |
| Chat turn with an endpoint that accepts the connection and hangs | Degrades at the configured timeout (`LLM_TIMEOUT_S`, default 30s; 5s with `LLM_TIMEOUT_S=5`). Message: "The model did not respond within 5s". |
| Every sentence in §3 | Run through `POST /api/chat`; the routing column is the observed output |
| Reading record → history count | Confirmed: the new row appears, the count changes |
| The unfilled-reason support flow | Confirmed: a reason with no category picked stores `category_confirmed = 0` and the page shows "No reason has been given a name yet" |
| **Live model conversation against a real endpoint** | **NOT verified. Has never been run.** See §6. |

---

## 1. Pre-flight

### 1.1 Commands, in order

From the project root:

```bash
make setup      # creates .venv, installs the runtime + test dependencies
make seed       # wipes the database and loads the fictional demo patient
make run        # serves http://127.0.0.1:8000
```

`make setup` installs `requirements-dev.txt`, which pulls in every pinned runtime package plus
pytest. The runtime list is fastapi, uvicorn, jinja2, httpx, python-multipart and itsdangerous —
six pins, five of them the app's own direct dependencies and itsdangerous pinned separately because
it is a transitive requirement of the session middleware. It is deliberately not needed for the
demonstration to run — only for `make test` — but installing it means a fresh clone can run every
command in this guide.

`make seed` runs with `--verbose` and prints, in this order:

```
knowledge base: 14 source(s), 23 fact(s) enabled, 1 held back
rules: v1, 21 enabled, 2 held for review, 23 total
Seeded profile usr_... (Mdm Tan) with 14 days of history
profile: usr_...
  facts enabled: 23, held back: 1
  clinician-reviewed entries: 0
  user_profile: 1
  care_plan: 3
  medication_item: 2
  bp_reading: 11
  medication_report: 14
  barrier_event: 2
  support_action: 1
  education_source: 14
  education_fact: 24
  consultation_question: 2

database: /.../caresteps.db
run 'make run' and open http://127.0.0.1:8000
```

Watch the counts, because three of them differ on purpose and a judge may spot it.

| Where | On a clean seed | Why |
|---|---|---|
| `make seed` prints `bp_reading: 11` | 11 rows | The table holds every row, including the original that was later corrected. |
| `/app/history` says "Showing 11 records" | 11 rows | Same number. The page states that it "includes older versions that were later corrected, so it may be larger than the number of measurements." |
| `GET /api/stats?days=14` returns `"n": 10` | 10 readings | Only the current value counts. The superseded row is not a measurement any more, and counting it would double-count the day it belongs to. |
| `/app/trends` says "You recorded 10 reading(s)" | 10 readings | Same denominator as `n`. |

The corrected reading is the 2026-10-10 pair: 148/92 was entered first and superseded by 147/91.
Both rows are kept, which is what makes the correction visible. A 2026-10-11 reading entered live
on stage takes `/app/history` to 12 and `n` to 11.

`clinician-reviewed entries: 0` is correct and is not an error. It is the honest number and it is
printed on purpose. Do not skip past it if a judge is watching the terminal — point at it.

Two optional checks before going on stage:

```bash
make test        # 162 passed
make reset && make seed    # back to a known state
```

`make demo-check` is declared in the Makefile but `scripts/demo_check.py` does not exist. Do not
type it on stage.

### 1.2 Two environment configurations

**Configuration A — no model configured (the default, and the one to use on stage).**

Nothing to set. Start with `make run`.

- Every page carries a banner except two: "**Limited mode** — The assistant is not connected, so
  free-text questions are answered by a simpler set of rules. Everything else works: you can still
  record readings, see your numbers, prepare for your appointment, and use the help bar."
  `/summary/print` suppresses the banner deliberately — nothing on that page is interactive, so a
  banner offering a way out of a broken state has nothing to act on — and `/trace` does not render
  it either, because the trace route does not pass the variable `base.html` guards on. If you say
  "every page" and a judge then looks at `/trace`, the one page you call the honest one, the claim
  is checkable and wrong. Say "every page except the printable summary and the trace page".
- The banner also prints the reason in brackets: `(LLM_BASE_URL / LLM_MODEL not set)`.
- Free-text chat falls back to a transparent keyword router that handles: recording a reading with
  numbers, reporting a medication state, viewing trends, building a summary, viewing the plan,
  and raising a difficulty. Everything outside that list gets a plain "I could not tell what you
  were asking." — in full, "I want to help, but I could not tell what you were asking, and the part
  of me that understands free text is not working right now", prefixed with "(No assistant is
  connected)".
- **The safety gates are unaffected by this.** They are deterministic and run before any model
  call. Chest pain still routes to 995 in this mode.

Use Configuration A. It is the configuration to use on stage, and the one whose behaviour has been
exercised end to end here. To be precise about what that means: the 162 tests import the repository,
the content loader, the safety router, the statistics and the summary, and the emergency help
config — and the suite does cover the degraded conversation layer (`app/llm/degraded.py`) and the
orchestrator's output checks, through `tests/test_degraded_and_output.py` (45 of the 162 tests).
What no test reaches is the live provider loop, `_live_turn` in `app/llm/orchestrator.py`; that is
the one path the suite cannot exercise without a model endpoint, and it is covered in §6.

**Configuration B — model configured.**

```bash
export LLM_BASE_URL="https://your-endpoint/v1"
export LLM_API_KEY="sk-..."
export LLM_MODEL="your-model"
make run-live
```

`LLM_BASE_URL` must be an OpenAI-compatible `/v1/chat/completions` endpoint supporting function
calling. With this set, the banner disappears from every page and `/trace` reports
`Attempting live model calls: Yes`.

**One thing Configuration B does not do, and it matters if you demonstrate it.** The app checks
only whether the two variables are set, not whether the endpoint answers. Point the variables at a
dead host and `/healthz` still returns `"live": true`, `"degraded": false`, `"reason": null`, and
the pages render with no banner at all — the app believes it is live. The individual chat turn
still degrades, quickly and correctly, with the reply prefixed `(The assistant is offline)` and
the reason `Could not reach the model service: ConnectError`. So the fallback is visible on the
turn, but not in the banner. This is the difference that makes Configuration A the one to use on
stage.

A third setting exists for demonstration purposes:

```bash
export LLM_FORCE_DEGRADED=1
```

This forces the fallback path while `LLM_BASE_URL` and `LLM_MODEL` remain set. `/trace` then
reports the reason as `forced off by LLM_FORCE_DEGRADED`. Useful if a judge asks to see the
fallback without unplugging anything.

### 1.3 What "healthy" looks like

```bash
curl -s http://127.0.0.1:8000/healthz
```

Configuration A:

```json
{
    "ok": true,
    "db": "/.../caresteps.db",
    "profiles": 1,
    "llm": {
        "configured": false,
        "live": false,
        "degraded": true,
        "model": null,
        "base_url_host": null,
        "api_key_present": false,
        "reason": "LLM_BASE_URL / LLM_MODEL not set"
    },
    "rules_version": "1"
}
```

Configuration B differs only in the `llm` block: `"configured": true, "live": true,
"degraded": false`, the model name and the endpoint host filled in, `"reason": null`.

Read what matters: `"ok": true`, `"profiles": 1` (the fictional patient exists),
`"rules_version": "1"`, and an `llm.reason` that matches what you configured. **The key itself is
never returned by this endpoint** — only whether one is present.

The database is `/.../caresteps.db` in the project root, unless `CARESTEPS_DB` overrides it.
Every string in it is fictional.

### 1.4 Have the video as the backup

Record the six-minute walkthrough in advance. If the laptop, the projector, the wifi or the
database misbehaves, play the video and narrate over it. This is not a fallback of last resort;
it is a planned contingency that costs ten minutes to prepare.

---

## 2. The timed runbook

Total six minutes. The timings are targets, not requirements. If a segment overruns, drop
0:40–1:30 (the record-a-reading walkthrough) before dropping 5:20–6:00 (`/trace`).

Two standing rules for the whole six minutes:

1. Say "this is simulated" out loud at least twice. In the UI, the seeded rows carry
   `is_simulated = 1`, every page bears base.html's "Prototype — not a medical service" banner
   saying the records are fictional, and the summary and printable summary carry the additional
   line "All of this is simulated demo data". Say it yourself anyway; the banner is small and a
   judge may be looking at your screen rather than the page.
2. Never describe what the model is thinking. `/trace` shows tool calls and rule decisions. The
   app deliberately does not claim to read the model's internal reasoning, and neither should the
   presenter.

---

### 0:00–0:40 — Frame

Say the challenge, then the problem, then stop.

- Challenge Statement 2, Scenario 3: hypertension management for adults 65 and over.
- The product is not a blood-pressure tracker. It is an execution-support tool for someone who
  already has a diagnosed condition and a plan.
- The specific problem to name, in about one sentence: **a missing record is not information about
  why it is missing.**

A gap in a log has many causes. The person forgot. The cuff was hard to use. They do not know what
the medicine is for. They are worried it is causing something. They are running out. They would
rather not say. A reminder app reads the gap as a failure and escalates the reminder. That answer
is wrong for five of those six cases, and it punishes the person for the behaviour the product
exists to support.

Land the sentence: the app asks why, and a different answer leads somewhere different. That is the
whole differentiator and the rest of the run is evidence for it.

Optional, if there is a screen free: open `http://127.0.0.1:8000/app` (keep this as a second tab;
do not navigate away from the flow).

---

### 0:40–1:30 — Record a reading live

Click path:

1. On `/app`, click the tile **Record blood pressure** → `/readings/new`.
2. Type into the two number boxes. Use a reading that is not in the seed, so the count visibly
   changes — for example top `152`, bottom `94`, pulse `76`.
3. Change the time if it is convenient; otherwise leave it. It defaults to now.
4. Click the submit button. The page becomes **"Check this before saving"**.

Expected text on the confirmation page, verbatim:

> Check this before saving
> This is what will be stored. Nothing has been saved yet.

> Written as 152 over 94.
> The units a home monitor uses are millimetres of mercury, usually shown as mmHg.

> No checks were raised
> These are checks to catch a typing mistake. Nothing was raised here. That says nothing about
> what the numbers mean.

> **Yes, save this reading** / **No, go back**
> Going back saves nothing. Nothing you entered has been stored, and the entry form will open
> again.

> Saving does not tell anyone else, does not contact a clinic, and does not alert a doctor. It
> only adds this reading to your own list.

**The point to make here, in one sentence:** the confirmation step exists so a draft is never
silently saved. The prepare step writes nothing. The confirm step is a separate request that the
person makes by clicking a button. There is no code path from a typed number to a stored row that
does not pass through this screen.

5. Click **Yes, save this reading**. You land on `/app/history?saved=1`.
6. Point at the count. On a clean seed the history page says:

   > Showing 11 records from the last 60 days, newest first. This count includes older versions
   > that were later corrected, so it may be larger than the number of measurements.

   After the save it should read **12** — 11 rows from the seed plus the one just entered. If you
   want a cleaner number, run
   `curl -s "http://127.0.0.1:8000/api/stats?days=14" | python3 -m json.tool` and read
   `readings.n`: it goes from **10** to **11**. `n` counts the measurements in the 14-day window
   using the corrected values, and it is the honest denominator. The two counts differ by one
   because the seed contains a correction, which keeps two rows for one day — see §1.1.

7. Point at one row that has a **corrected** marker. The seed contains one deliberately corrected
   reading, and both the original and its replacement are kept, chained by `corrects` /
   `superseded_by`. Corrections supersede; they do not overwrite.

Do not describe the new reading as "a good number" or "a bit high". The page does not interpret
it and neither should the presentation.

---

### 1:30–2:40 — The differentiator: the gap question

This is the strongest ninety seconds in the demonstration. Do not rush it.

1. Go to `/app`. Under **There is no record for some days** the page says, on a clean seed:

   > There is no record for the last 2 day(s). Would you like to add anything? You can also skip
   > this.

   and lists the two dates. Point out the words: it asks a question. It does not say "you missed
   two days", and it does not call the days missed doses.

2. Click **Say what was hard** → `/support/ask`.

   Expected text:

   > What has been difficult?
   > You do not have to explain. If you would like to, tell me what got in the way. You can also
   > skip this page entirely. Skipping costs nothing here, it is not recorded as a difficulty,
   > and the app will not bring it up again unless you do.

   > If it helps, which of these is closest?
   > Pick one, or pick none.

   Note out loud what is missing from this page: any suggestion of what the reason might be. The
   options come only after the person has had the chance to say it themselves.

3. Type a reason in the person's own words. Use something the seed does not contain, for example:

   > The cuff is hard to get on by myself in the morning.

4. **Deliberately pick no category.** Click **Save this** with the free text and no radio button
   chosen.

5. The page that follows is the important one. Expected text:

   > One thing that was difficult
   > In your words: The cuff is hard to get on by myself in the morning.

   > **No reason has been given a name yet.**
   > That is a complete answer on its own. The app has not picked one for you. If you want to say
   > more, you can choose below, and the help offered here will change to match.

   > Something that might help
   > Confirm what kind of difficulty this was

   Make the structural point: the reason is stored with `category_confirmed = 0` and
   `proposed_by` not set to the user. The app has recorded the person's words and has **not**
   labelled them. Nothing in the record claims the user said "it is hard to do" when the user did
   not.

6. Now pick **It is hard for me to do it** and click **Save my answer**. The page reloads and
   changes. Expected text:

   > You told us: It is hard for me to do it
   > You picked this one yourself, so the app treats it as answered. **You can still change it
   > below if your answer has changed.**

   > Something that might help
   > Use the shorter entry form
   > Have someone help with the app

7. Now the payoff. Go to `/app/support`. The page lists the whole reason→support map. It reads:

   > How the same situation leads to different help
   > Two people can both have a day with no record. If one says the day was too busy and the other
   > says the medicine was hard to open, the useful next step is not the same thing.
   > Below is the whole set of routes this app has on record: **7 categories of 7**. Each one is a
   > different question with a different answer.

   The seven, with their distinct supports:

   | Reason | What the app offers |
   |---|---|
   | I forgot to record / take it | Fill in the days you remember; choose a better reminder time |
   | It is hard for me to do it | Use the shorter entry form; have someone help with the app |
   | I do not know what this medicine is for | Read what this medicine is for (from a recorded source); add a question for the pharmacist |
   | I am worried it is causing a problem | Write down what you noticed and when; add a question for the doctor |
   | I am running out of it | Note how many are left; ask about your next repeat prescription |
   | I would rather not say | Leave this for now |
   | Something else | Say more in your own words |

   **The sentence to say:** the same missing record, seven different next steps, and the app chose
   none of them. The user did. And if the user picked wrong, the answer is changeable in one tap
   from the same page.

8. Optional, if there is time: open the seeded difficulty **"I am not sure what the second tablet
   is actually for."** (the open one, raised 2026-10-05). Because its category is
   `unclear_purpose`, the page does not merely describe that an explanation exists — it renders
   the actual Amlodipine explanation inline, with its HealthHub source underneath. Follow through
   from reason to support to source in one page.

Do not claim this is a validated taxonomy. It is a seven-entry routing table written by the team,
it is stored as data, and every entry is visible at `/app/support` and `/trace`.

---

### 2:40–3:30 — Medicine explanation and the boundary cases

**Part one: the explanation, with its source.**

Go to `/app/medicines`. Click path: `/app` → tile **Confirm my medicine** → `/app/medicines`.

Expected content for Amlodipine — statement, then source, then the caveat:

> Amlodipine is a blood pressure medicine. It works by relaxing and widening your blood vessels,
> which brings your blood pressure down.

> Where this came from
> HealthHub (Ministry of Health, Singapore)
> Amlodipine (patient information leaflet)
> Retrieved 2026-10-11.
> **Checked by the team, not by a clinician**
> "Checked by the team" means a team member read the source. It does not mean a doctor checked it.

The source is a live link: `https://www.healthhub.sg/medication-devices-and-treatment/medications/amlodipine`.
Losartan has the same shape with a different page.

**Say three things about that block:**

1. The statement is the app's own paraphrase, not a scraped paragraph. Fourteen of these
   statements were rewritten in an adversarial pass whose job was to find where a sentence claimed
   more than its source did. Ten of the fourteen had defects — added causes, added benefits, added
   frequency, an instruction to take a medicine. All fourteen were rewritten and the changes are
   logged in `content/education/facts.json` under `_audit`. The audit is in the repository and can
   be opened on request.
2. `Retrieved 2026-10-11` is real. The date is stored per source.
3. The review state is `team_checked` for every entry, and the page says so unprompted. No
   clinician has reviewed any of this. The page states that rather than leaving it to be
   discovered.

Then point at the bottom of the page and read:

> A medicine that is not on this list, or not on your plan, is not guessed at. The app says it
> could not match the name, offers no explanation, and offers to help you ask a pharmacist
> instead. A wrong answer is worse than no answer.
> **I will not guess.**

**Part two: the boundary cases, through `POST /api/chat`.**

Open the chat. **Note before the run:** the conversational panel is wired in
`app/static/js/app.js` (it posts to `/api/chat` and renders the reply), but no template in this
build contains its markup — there is no `chat-log` / `chat-form` element on `/app`, `/app/support`
or anywhere else, so the panel does not appear on screen. Drive these turns through `POST /api/chat`
instead: `curl -s -X POST http://127.0.0.1:8000/api/chat -d 'message=I have chest pain'`, which
prints the same JSON the panel would have rendered, or use the Try-it-out form at
`http://127.0.0.1:8000/api/docs` (the automatic API docs, enabled by `docs_url="/api/docs"`). Say
this plainly if a judge asks why there is no chat box — the endpoint and the browser code are both
built, the markup was not.

Type the first sentence. Read the reply aloud.

Type: `should I double the dose today`

Expected reply, verbatim:

> I cannot decide or suggest a dose change for you - that is a decision only your doctor or
> pharmacist can make. What I can do is write this down so it is not forgotten. Would you like me
> to add "should my dose change?" to the questions you take to your next appointment?

Routing: `refuse`, rule `boundary_change_dose`, source `S1-healthhub-bp-medication`.
Note the two halves: the refusal, and the route onward. A refusal with no destination is a dead
end, so every boundary rule carries a `redirect` and, where it fits, offers to add the question to
the appointment list.

Type: `what is this white round pill`

> I cannot identify a medicine from how it looks - two different medicines can look identical, and
> guessing would be worse than not answering. Your pharmacist can identify it safely. Would you
> like to add that to your questions?

Routing: `refuse`, rule `boundary_pill_identification`, source `S2-healthhub-know-your-medication`.

**The claim to make, and its limit.** Say: this refusal does not depend on the model behaving. It
is a phrase match on a rule file with a citation attached. The rule loader refuses to load a rule
loaded from `content/rules/` that declares no source, so an uncited loaded rule cannot run. What
this does **not** mean is that the rule set is complete — it is 21 live rules covering the cases
the team thought of, and a phrasing nobody wrote down will not be caught. Say the limitation out
loud; do not let a judge find it.

One narrower limitation, in case a judge reads the JSON: the loader enforces that a rule *names*
at least one source, and it does not check that the named source is one of the fourteen registered
in `content/education/sources.json`. Seven identifiers cited by the rules — including
`S1-healthhub-bp-medication` on `boundary_change_dose` — are declared only inside the rule files
and have no register entry, so `/trace` shows an identifier that does not resolve to a publisher
and URL the way the emergency number's sources do. Nothing *loaded from a rule file* runs uncited;
the citation chain is just thinner than it looks for those rules. The one thing outside the rule
files is `boundary_unknown_medication` in §3 Group C, which runs with an empty `sources` list — see
the note under that table.

---

### 3:30–4:30 — Numbers, then the summary

**Part one: `/app/trends`.**

Click path: `/app` → **See my numbers over time**, or the nav item **My numbers**.

Expected header, on a clean seed (before the reading added at 0:40 — the numbers below are the
seed values; if you recorded a reading first, `n` is 11 and the averages shift slightly):

> This page describes 14 day(s): from 2026-09-28 to 2026-10-11.
> You recorded 10 reading(s) in that time.
> Figures put together on 2026-10-11 from what is stored in your record.

Point at each of the four things in turn. Do not paraphrase them; they are the argument.

1. **A denominator on every figure.**

   > Top number, average (systolic) — 141.9 mmHg
   > Range of the top number across those 10 reading(s): 136 to 147 mmHg.
   > Bottom number, average (diastolic) — 88.0 mmHg
   > Range of the bottom number across those 10 reading(s): 84 to 91 mmHg.

   An average with no `n` is an assertion. `141.9 mmHg, from 10 readings, range 136–147` is a fact
   about a record.

2. **The broken line at the gap.**

   > The line stops on days with no reading rather than carrying across them.
   > 10 of 14 days have a reading.
   > The dashed lines mark days with no reading.

   The chart is drawn from per-day points, and a day with no reading has `has_data: false`. The
   renderer draws separate paths for runs of consecutive days with data, which is why the line is
   **broken** rather than straight across the gap. This is not a styling choice. A line drawn
   across three missing days is a fabricated reading, and it is the most common way a health chart
   lies. The same numbers are listed below the chart, so the chart is never the only copy.

   Check it in the API if a judge wants it: `GET /api/stats?days=14` returns a `series` object
   whose `points` array has one entry per day — `series.points`, not `series` itself. The object
   also carries `from`, `to`, `days_with_data` and `days_without_data`. Each point is shaped
   `{"date": ..., "has_data": false, "n": 0}` on a gap day: `"has_data": false` with no values.

3. **The four adherence states, with `unrecorded` shown apart.**

   > You reported taking it — 13
   > You reported not taking it — 0
   > You were not sure — 1
   > **No record either way — 2**
   > The last line is kept apart from the others on purpose. It counts days with no record either
   > way, which is not the same as a day you reported not taking it.

   Then the two caveats the page prints without being asked:

   > This counts what was reported. It is not a measure of how well the medicine worked, and it is
   > not a measure of true adherence.

   **Say the structural point:** there is no adherence percentage anywhere in this app. The
   adherence result in `app/stats.py` returns four integer counts — `taken`, `not_taken`, `unsure`,
   `unrecorded` — and no ratio of any kind over them; the file's own comment calls the compliance
   rate "an explicitly refused statistic". (The module does compute one ratio elsewhere,
   `coverage_ratio` in `coverage()`, which is the share of days that have *any* record. That is a
   statement about how complete the record is, not about whether the medicine was taken, and it is
   the only ratio in the file.) An adherence percentage would silently convert "no record" into
   "not taken", and that conversion is the exact error the product is built against. `unrecorded`
   is derived from an absent event; the database refuses to store it as something a patient
   reported.

4. **The comparison that refuses to happen.**

   > These two periods are not compared
   > There is not enough recorded in one or both periods to compare them. This period has 10
   > reading(s); the period before has 0.
   > No difference between the periods is shown, because a difference worked out from this few
   > readings would not mean anything.

   The seed patient has no history before 2026-09-28, so the earlier window has nothing in it and
   the app declines. This is the app choosing to show nothing over showing something computable
   but meaningless. If a judge asks whether the app always refuses: no, it compares when both
   windows meet the threshold. The two thresholds are `MIN_READINGS_FOR_MEAN = 2` and
   `MIN_READINGS_PER_WINDOW_FOR_COMPARISON = 3` in `app/stats.py`, and `docs/evaluation.md` §6.10
   ("Statistical threshold provenance") calls them engineering judgements rather than
   literature-derived values. Point a judge at §6.10, not §6.9 — §6.9 is the negation defect.

**Part two: `/summary`.**

Click path: nav item **Appointment**, or `/summary`.

1. Open the preview. Read the top block, which is not boilerplate:

   > **What this page is**
   > This page was assembled by a prototype from the user's own records. It is not a medical
   > report. Numbers are as recorded and may be incomplete. Anything under 'reported by the
   > patient' is what the patient said, not a clinical finding. No part of this was written or
   > checked by a doctor.

   > **All of this is simulated demo data**

2. Scroll to **Reported by the patient** and click **Remove from summary** on one section — for
   example the reading notes, or how the patient said they felt.

   **The section does not disappear from this preview. Do not point at it expecting that.** What
   changes on this page is the button label, which flips to **Put back in the summary**; the
   section's content stays on screen in full. The omission is real, but it is applied only by
   `/summary/print` — the print route runs the omissions, the preview route does not. So show the
   effect where it actually happens: click **Print or save as PDF** (step 3) and point at the
   missing section on the printed page, or open `/summary/print` in a second tab. Say it the way
   the page itself explains it:

   > Removing a section takes it out of the printed version only. It does not delete anything from
   > your record, and it does not change what is stored.

   That sentence is accurate and is the whole design: the section leaves the paper, not the
   record, and not this preview.

   What is omittable is a fixed list: feelings, reading notes, difficulties, chosen actions, and
   questions. What is **not** omittable is the completion block and the readings. The reason is in
   the code — a summary with the numbers stripped out and the caveats left in would mislead in the
   other direction.

3. Click **Print or save as PDF**. The printable page has no buttons and no forms at all. It does
   still render the standard header navigation — the print stylesheet hides `nav.main`, the help
   bar and anything marked `.no-print`, so the navigation is on screen but does not reach the
   paper. If you are showing the page rather than printing it, say that, because the nav is
   visible for the second or two before the print dialog.

   > Nothing on this page was sent to anyone. The patient printed it or showed it, on their own
   > decision.

   **Say the sentence that matters most here:** there is no code path in this application that
   sends the summary anywhere. Not to a doctor, not to a clinic, not to a family member. Ask the
   app through `POST /api/chat` to send it to a doctor and it refuses —
   `boundary_share_without_consent`, the sixth row of Group C in §3 — and offers a page you can
   hand over yourself instead. The absence of a send function is the control.

---

### 4:30–5:20 — The emergency branch, and the help page

**Part one: type a red flag.**

Through `POST /api/chat` (see the note at §2, 2:40 — there is no on-screen chat box in this build),
send: `I have chest pain`. The same verdict is reachable without the endpoint at all, from the red
bar and `/app/help`, so if the network or the tooling is awkward on stage, fall back to the help
page rather than fighting it.

Expected reply, verbatim:

> Chest pain needs to be checked right away. Please call 995 now, or ask someone near you to call
> for them. Do not wait to see if it passes, and do not drive yourself.

Alongside it, in the same `/api/chat` response, the emergency block carries `payload.help`:

> Emergency ambulance (SCDF) — **995**
> **This app has not contacted anyone and cannot do so. You need to make the call yourself, or ask
> someone nearby to call for you.**

Two of those three lines are in the JSON — `help.label` with `help.number`, and `help.app_does_not`
verbatim. The third line the runbook used to quote here, "Call this number only for something
life-threatening", is **not** in the chat payload; it is a sentence on `/app/help` and belongs to
the Part-two block below, where it renders in full as "Call this number only for something
life-threatening. For anything else, the other routes further down this page are the usual ones."
Do not read it off the JSON.

**Three things to say about this, in this order:**

1. **The verdict is not the model's.** This text comes from `content/rules/redflags.json`, matched
   on the phrase, before any model call is made. In the trace for this turn, the recorded decision
   is `action=emergency rule=redflag_chest_pain`, and the model is never invoked. A rule that
   exists only inside a prompt is a suggestion; this one is a gate. The same reply appears in
   Configuration A with no model configured at all.
2. **The number is configured, not coded.** `/app/help` says: "This number was copied from a
   published source on 2026-10-11 and has been checked by the project team. It has not been
   confirmed by a clinician, and the app has no way of knowing if it has changed since." The
   number comes from `content/rules/emergency.json` with four named sources, and if the source
   list is missing the app refuses to print a number at all rather than printing a plausible one.
   That refusal path exists because an unverified emergency number appearing on screen was the
   most dangerous defect found during the build.
3. **The app has not called anyone.** Point at that sentence and read it. An app that shows 995
   in a red panel can easily be read as an app that has summoned help. It has not, it cannot, and
   it says so on the panel itself and again on `/app/help` under "What this app is not".

**Part two: `/app/help`.**

Click path: the red bar at the bottom of every page, or nav to `/app/help`.

Read the section headed **What this app is not**:

> A prototype. It was built for a competition and for demonstration. It is not a finished service.
> Not able to judge how serious something is. It cannot tell a small problem from a dangerous one,
> and it never tries to.
> Not a monitoring service. **Nobody is watching these records.** No one is alerted if a number
> changes, and no one will contact you.
> Not a replacement for a doctor. It does not diagnose, does not change a prescription, and does
> not tell you what to take.
> Not connected to anyone. It has no link to a hospital, a clinic, an ambulance service, or a
> family member.

Above that section, the emergency panel itself renders here, and this is where the line about
scope belongs:

> Emergency ambulance (SCDF) — **995**
> Call this number only for something life-threatening. For anything else, the other routes
> further down this page are the usual ones.
> This app has not contacted anyone and cannot do so. You need to make the call yourself, or ask
> someone nearby to call for you.

Also on this page, the other routes with their own sources: non-emergency ambulance 1777 (with the
SCDF note that this hotline ceases from 1 January 2027), emergency SMS 70995, and the NurseFirst
helpline 6262 6262. Each carries the source it came from and the date it was read.

One honest note if a judge asks about scale: this rule set covers eight enabled red-flag
presentations (a ninth, fever with confusion, is held back — see `5:20`). It is not a triage
system, it does not rank severity, and a no-match result means only that no configured phrase was
found.

On the wording of that last point, be accurate rather than generous: `/app/help` does say "It
cannot tell a small problem from a dangerous one, and it never tries to", and that is the denial a
judge will see. The stronger sentence written for this purpose — "This check only looks for a short
list of phrases. It does not rule anything out." — lives in `app/safety/redflags.py` as
`no_match_disclaimer` and is **not currently rendered on any page**; no template or script reads
it. Say the limitation in your own words rather than telling a judge to read it on the screen.

---

### 5:20–6:00 — `/trace`

Click path: `/trace`, directly in the URL bar. (There is also `/app/trace`, which redirects here.)

This is the evidence page and it is generated from the running system, not written by hand. Four
things to show, quickly:

1. **Model status, honestly reported.**

   > Is a model connected — Not connected
   > Provider configured — No
   > Attempting live model calls — No
   > Model name — Not set
   > Endpoint host — Not set
   > **API key present — no**
   > Why it is not connected — LLM_BASE_URL / LLM_MODEL not set

   Say it plainly: the key itself is never read onto this page. The app reports only whether one is
   present. And if the model is not connected, this page says so rather than displaying a
   reassuring badge.

2. **The tool contracts.** Ten named functions, each with its inputs and which are mandatory.
   Read the naming convention out loud, because it carries the safety argument:

   - `get_*` — read-only. Never mutates.
   - `prepare_*` — validates and returns a draft. Never persists.
   - `confirm_*` — persists, and only from a draft the matching `prepare_*` produced.
   - `record_*` — persists a small fact the user has directly stated.

   The ten functions on the page are `get_care_plan`, `get_period_stats`, `get_recent_activity`,
   `prepare_reading`, `prepare_medication_report`, `retrieve_education`, `record_barrier`,
   `set_reminder_preference`, `build_visit_summary` and `add_question`.

   Then say what is absent: **there is no tool that changes a dose, stops a medicine, sends a
   message, or contacts anyone.** The absence is the control. The model cannot request what was
   never offered to it.

   If a judge wants the count: ten tools are shown on `/trace`. In degraded mode nothing calls
   them, and the page still lists them — the list is the contract, not the log.

3. **The rule set with sources and the held-back rules.**

   > Rule set version 1. It holds 23 rule(s) in total: 21 switched on, and 2 present but switched
   > off. Held-back rules are listed too, on purpose.

   **Say "21 rules are switched on; 23 exist, and the two that are off are shown here with the
   reason."** Saying "23 rules" on its own overstates the live enforcement set by one seventh —
   only 21 can fire — and this page prints the breakdown a line above, so a judge reading the
   screen while hearing 23 sees the mismatch. The 21 is the stronger answer anyway: the held-back
   pair is the evidence of judgement.

   The two switched off are listed **first**, so they are hard to miss:

   - `boundary_emergency_contact_change` — `pending_review`. Would handle a user asking to change
     the emergency number. Left disabled because an incorrect emergency number is the single most
     harmful content error this app could ship.
   - `redflag_fever_with_confusion` — `pending_review`. Would cover fever with confusion in an
     older adult. Left disabled because the fever threshold and the definition of confusion both
     need clinical input.

   **The point:** a rule that is not present and a rule that is present but held back are
   different facts. This page shows the second kind, with the reason attached, rather than
   deleting the gap and pretending it does not exist. Every rule loaded from the content files,
   including the disabled ones, carries at least one named source — the loader drops any rule that
   does not, so an uncited rule cannot be quietly switched on later. The 21 switched on is the
   number to say out loud; 23 is the total including the two held back, and a judge reading this
   screen will see both.

   The footer is the sentence to read:

   > "Team checked" means a member of the team read the source and wrote it down. It does not mean
   > a clinician has reviewed it. **Clinician review is outstanding.**

4. **The live audit log.** At the bottom:

   > What it did while you were using it

   If you have been running the sentences in §3 during this session, the log now holds real
   entries. Two examples recorded during preparation of this guide:

   | kind | tool | status | detail |
   |---|---|---|---|
   | `safety_route` | `safety.route` | `refused` | `action=emergency rule=redflag_chest_pain` |
   | `safety_route` | `safety.route` | `refused` | `action=refuse rule=boundary_change_dose` |

   And the honest note the app prints when the log is empty, which is worth showing if a judge
   sees zero lines on a fresh browser:

   > Nothing has been logged in this session yet — No tool call and no rule decision has been
   > recorded for this browser session, so there is nothing to show. **This is an empty log, not a
   > zero.**

   Say what the log is and is not:

   > These lines are tool calls and rule decisions. They are not a claim to read the model's
   > internal reasoning. The app records what it was asked to do and what came back, and nothing
   > more.

**Close on the honest note.** The last thing said on stage should be a limitation, not a claim:
the live model path has not been run, no clinician has reviewed the content, and the CodeBuddy /
WorkBuddy evidence required by Handbook p.37 is outstanding. Say those three, then stop.

---

## 3. Exact sentences to type, and the expected routing

Run each before going on stage with a clean `make seed`, through `POST /api/chat`. The routing
column is the observed output, not the intent. Every row below was executed on 2026-10-11.

### Group A — must alarm (emergency)

| Type this | Observed | Rule |
|---|---|---|
| `I have chest pain` | `emergency` | `redflag_chest_pain` |
| `I cannot breathe properly` | `emergency` | `redflag_breathlessness` |
| `my face is drooping and my speech is slurred` | `emergency` | `redflag_stroke_signs` |
| `he passed out and is confused` | `emergency` | `redflag_consciousness` |
| `my lips are turning blue` | `emergency` | `redflag_mouth_lips_colour` |
| `there is heavy bleeding that won't stop bleeding` | `emergency` | `redflag_severe_bleeding` |

### Group B — must NOT alarm (the negated case)

| Type this | Observed | Rule |
|---|---|---|
| **`no chest pain today`** | **no alarm.** No emergency panel, no number displayed, no 995, and no rule fires. What comes back is the ordinary degraded reply, which in Configuration A begins "(No assistant is connected) " and then reads: "I want to help, but I could not tell what you were asking, and the part of me that understands free text is not working right now." It is a worse answer than a person would want and an honest sign that nothing alarming was detected. | none |

This is the single most important sentence in this table to rehearse. A false alarm is worse than
no alarm: it teaches the person to ignore the red panel, which is exactly the behaviour that kills
someone. **Most** rules carry an explicit `exclude_patterns` list rather than leaving it to the
model to notice the negation — but three enabled red-flag rules do not, so a negated sentence
naming those still fires. See the risk note below; do not offer to demonstrate negation on those
three on stage.

Also verified not to alarm: `without chest pain`, `I have no shortness of breath`, `no weakness`,
`my lips are not blue`.

**Three risks in group B that must be stated, not discovered.**

*First, the three rules with no exclusion list at all.* `redflag_severe_bleeding`,
`redflag_mouth_lips_colour` and `redflag_fall_head_injury` carry an empty `exclude_patterns` list.
Plain negation therefore fires them — verified live:

| Avoid on stage | What actually happens |
|---|---|
| `there is no heavy bleeding` | `emergency`, `redflag_severe_bleeding` |
| `I did not hit my head` | `urgent_advice`, `redflag_fall_head_injury` |
| `no head injury` | `urgent_advice`, `redflag_fall_head_injury` |
| `no blue lips` | `emergency`, `redflag_mouth_lips_colour` |

This is recorded as an open defect in `docs/evaluation.md` §6.9. The suite does not catch it
because `test_negated_symptoms_do_not_trigger` covers only four phrases, none of them on these
rules. If a judge asks about false alarms, say it plainly: negation is handled by a substring
exclusion on some rules, not all, three enabled rules have no exclusion list, and that is the same
class of error this app argues is the most dangerous. The fix is structural — a negation-aware
pre-pass rather than a longer phrase list — and it is outstanding.

*Second, one enabled rule whose exclusion list is too narrow.* `redflag_seizure` does carry an
`exclude_patterns` list, but it holds only `no seizure` and `not a seizure` as literal substrings.
The phrase a person would actually use does not match either, so `I am not having a seizure`
returns `emergency` / `redflag_seizure`. The exclusion exists; it just does not cover the wording.
Do not type that sentence on stage.

*Third, the mixed sentence.* The exclusion is a substring match, so in a sentence containing both
a negation and a genuine symptom — `I have chest pain today, but no chest pain yesterday` — the
exclusion fires and the emergency rule does **not** trigger. Verified. Do not type a mixed
sentence like that expecting the alarm, and if a judge asks, say the exclusion list is a substring
match that can be defeated by a sentence negating one symptom while naming another; the model
layer was never given authority over this gate, and the fix is a structural rule rather than a
longer list.

### Group C — refused, with a route onward

| Type this | Observed | Rule |
|---|---|---|
| `should I double the dose today` | `refuse` | `boundary_change_dose` |
| `I want to stop taking my tablets` | `refuse` | `boundary_stop_medication` |
| `I missed my dose, should I take it now?` | `refuse` | `boundary_missed_dose` |
| `what is this white round pill` | `refuse` | `boundary_pill_identification` |
| `do I have high blood pressure?` | `refuse` | `boundary_diagnosis_request` |
| `send this to my doctor` | `refuse` | `boundary_share_without_consent` |
| `what is this medicine for` | `refuse` | `boundary_unknown_medication` — the medicine was not named, so the app declines rather than guessing which one. **Read the note below before demonstrating this row.** |

Every refusal carries a redirect and, where it fits, an offer to add the question to the
appointment list.

**The one exception, and it is the row a judge is most likely to check.** `boundary_unknown_medication`
is not loaded from `content/rules/` and is not one of the 23 rules on `/trace`. It is synthesised in
`app/safety/boundaries.py` from the `mentions_unknowable_medication` context flag, so it carries no
source identifier — its `sources` list in the JSON response is empty, unlike the other boundary
rules. It still refuses, and its redirect to a pharmacist is real. But do not use it as an example
of "every rule has a citation", and do not go looking for it in the `/trace` table; it is not there.
The other six rows in this table are loaded rules and do carry sources.

### Group D — must NOT be refused (the false refusals)

| Type this | Observed | Why it matters |
|---|---|---|
| `I forgot my tablet yesterday` | not refused — routed to the difficulty flow | This is a **report**, not a request for advice. Refusing it would punish the exact behaviour the app exists to support. This was a real defect, fixed. |
| `I am running out of my tablets` | not refused — routed to the difficulty flow | A supply statement, not a name-the-drug query. |
| `I keep forgetting to write it down` | not refused — routed to the difficulty flow | A barrier to report. The intent router checks for a difficulty **before** it checks for a reading, because "readings" contains "reading". |
| `help me tell my doctor` | not refused — routed to the appointment flow | Preparing for an appointment is the product's purpose and must never be blocked. |

### Group E — asked a question, and can always skip

| Type this | Observed | Rule |
|---|---|---|
| `I don't feel well` | `clarify`, with six options, including "Rather not say" | `clarify_vague_feeling` |
| `my blood pressure was 146 over 90 just now` | `clarify` — asks for the two numbers, because the reading gate runs before the recording gate | `clarify_missing_reading_fields` |

Every clarification carries a skip option. A question the user cannot escape is a trap.

### Group F — urgent, distinct from emergency

| Type this | Observed | Rule |
|---|---|---|
| `I fell and hit my head` | `urgent_advice`, **not** `emergency` | `redflag_fall_head_injury` |

The urgent message still names 995 and the escalation triggers (drowsiness, confusion, vomiting),
so an urgent verdict never closes off the emergency path.

### Group G — the ordering guarantee

| Type this | Observed | Rule |
|---|---|---|
| `I have chest pain and I want to stop taking my tablets` | `emergency` — the emergency wins | `redflag_chest_pain` |

One sentence contains both an emergency phrase and a medication request. The emergency path is
reached first. The alternative — a person in trouble being told about prescribing policy — is the
failure this test exists to prevent.

**Before going on stage, run Groups A, B and G once each.** They are the three that must not
surprise you: one must alarm, one must not, and one must pick the right priority when both are
present.

---

## 4. Failure recovery

### The model is configured and hangs

**Do nothing.** Wait for the turn to finish. The app degrades by itself.

- It times out at `LLM_TIMEOUT_S` (default 30 seconds) and returns the scripted reply with the
  prefix "(The assistant is offline)". (The prefix differs by cause: a configured endpoint that
  failed or timed out gives "(The assistant is offline)", while no endpoint configured at all gives
  "(No assistant is connected)".)
- The prefix is deliberately plain. The technical reason goes to the audit log, not to a
  70-year-old on a phone.
- Everything else keeps working on the same screen. Recording, history, numbers, the summary and
  the help bar do not touch the model at all.

Observed behaviours, both verified:

| Failure | Result | Time |
|---|---|---|
| Endpoint unreachable (connection refused) | Degraded reply, `Could not reach the model service: ConnectError` | under 1 second |
| Endpoint accepts and never answers | Degraded reply, `The model did not respond within 5s` (with `LLM_TIMEOUT_S=5`) | 5.4 seconds |

**Do not retry blindly.** Retrying a hanging endpoint spends the six minutes on a spinner. Say out
loud, "the assistant is offline, so this part is answered by the simpler rule set, and everything
else still works" — that sentence is true, and it is more convincing than a retry.

Where to point while saying it depends on which configuration you are running. In Configuration A
there is no model configured, so the banner is on screen and you point at it. In Configuration B
with a dead endpoint, **there is no banner** — the app believes it is live and renders no warning —
so say the sentence yourself and point at the reply's `(The assistant is offline)` prefix instead,
which is on the turn in front of the judge. Do not reach for a banner that is not there.

If you want to convert the situation into a deliberate demonstration, restart with
`LLM_FORCE_DEGRADED=1` and tell the audience you are choosing the fallback path. That is honest
and it looks intentional rather than broken.

### A judge clicks "Confirm my medicine" and expects a status button

The home tile labelled **Confirm my medicine** goes to `/app/medicines`, which is an explanation
page. It has no buttons for reporting "I took it" / "I did not take it" / "I am not sure". The
four states are real in the database and counted on `/app/trends`, but no page in this build
writes them, and the endpoint that was meant to write them is not wired up: `app/routes/readings.py`
defines a `med_router` with `POST /medication/report` on it, and `app/main.py` never registers that
router, so the path answers **404**. The writing code exists and the counts are real; the route to
it does not.

**Do not go looking for that button on stage.** If a judge asks, or if someone clicks the tile and
says "where do I say I took it?", the honest answer is: the medication states in the demo come from
the seeded history, there is no screen that lets you add one by tapping, and the endpoint that was
built for it is not reachable in this build. That is a gap in the interface and a gap in the
wiring, not in the data model, and it is better said than worked around. Do not claim the endpoint
works — it answers 404.

### The database is in an odd state

```bash
make reset && make seed
```

`make reset` deletes `caresteps.db`, and `make seed` rebuilds it from the fixtures. There is no
migration to run and no state to preserve — the whole value of a demo you can trust is that it
always starts from the same place. This takes a few seconds.

What "odd" looks like: the home page says there are readings from 60 days but the trends page
shows none; a barrier appears with an id that does not resolve; the record count is larger than
expected. All three are symptoms of a database that has been written to during a rehearsal.

**`POST /api/demo/reset` is broken in this build. Do not call it on stage.** It answers HTTP 500,
not the "Demo data rebuilt. All of it is simulated." it was written to return, and it is
destructive rather than merely unusable: the handler drops every table first and then dies before
re-seeding them, so the app is left with zero profiles, zero readings and zero barriers. The
route is not repairable with a URL change; the fault is in `app/routes/api.py`, which calls
`db_session()` as a plain function when `app/db.py` defines `session()` as a `@contextmanager` —
so `seed_demo` fails at its first `execute` and the `finally: conn.close()` fails too. The lazy
re-seed in `app/routes/deps.py` will rebuild the patient on the next page view, but it never calls
`load_knowledge`, so the education tables stay empty and `/app/medicines` silently loses the
Amlodipine explanation and says it could not match the name instead. If you have already called
it, recover with the command at the top of this section.

### A page errors

Play the video. A 500 does not mean anything about the claims being made, and the six minutes are
better spent on the recorded run than on a live debugging session.

If there is time and the error is on a page whose route is known, note the path — the build log
records that all 13 pages once returned 500 simultaneously because of a framework signature
change, and the lesson recorded there is that locking versions is not enough; the server has to be
started. Do not attempt a fix on stage.

### The whole laptop fails

Play the video. This is what it is for. It is listed in §1.4 as a planned contingency, not as a
last resort, so using it costs no credibility.

### There is no network at all

Nothing here needs one, in Configuration A. `make setup` needs PyPI once; after that, `make run`
and the whole demonstration are local. Verify before arriving that `.venv` exists and the app
starts from a cold boot, because a fresh clone without a network cannot install the pinned
dependencies — the five direct runtime packages plus itsdangerous, and pytest for `make test`.

---

## 5. Questions to expect, and the honest answers

Answer each one in two or three sentences, and say the limitation before the judge has to ask a
second time.

**"How is this different from the blood-pressure apps already on the phone?"**

Most of them solve recording. A reminder fires, the person taps a number in, a chart appears, and
if the tap does not happen, the app treats the gap as non-compliance and escalates. This one treats
the gap as a question. The same missing record leads to seven different next steps depending on
why it is missing, and the reason is stored in the person's own words with a flag saying whether
they confirmed it. Recording is a solved problem; the reason it does not happen is not.

**"Why is AI needed here at all? You could hard-code this."**

Because the parts that matter are not the parts that need a model. The safety gates, the
statistics, the adherence states and the emergency number are all deterministic, and they were
deliberately kept that way. What the model adds is the one thing a phrase list is bad at: letting
someone say what got in the way in their own words, and turning that into a short sentence drawn
from facts the tools returned. It has no medical knowledge of its own to apply — explanations come
from a hand-checked set of entries with sources, and every number in a reply has to match a
computed fact table or the reply is replaced. If the model is unavailable, the app loses the
understanding layer and keeps everything else, and it says so rather than substituting a guess.
The honest version of the answer is that this prototype is mostly deterministic code with a
language layer on top, on purpose, and the language layer is the least load-bearing part.

**"How do you know it works long-term?"**

We do not, and we are not claiming it. There is no longitudinal evidence: the demo history is
fourteen fictional days written by us, and no real patient has used the app at any point. What has
been tested is the behaviour under specific inputs — 162 automated tests over data integrity,
safety boundaries, statistics and the summary; 45 of them cover the degraded conversation layer
and the model-output checks. What has not been done is a user study with older
adults — zero participants. The handbook's solution section (方案 9.4) recommends a walkthrough
with three to five older adults, and we did not have the resources in this round; it is recorded
as an outstanding item rather than quietly dropped. We would describe the
fourteen-day history as a fixture designed to contain the states the app must handle, not as a
trial.

**"Would it ever advise changing medication?"**

No, and the line is enforced rather than promised. Requests to change a dose, stop a medicine,
start a new one, or handle a missed dose are intercepted by a deterministic rule that runs before
the model, and the model is not called at all for those turns — that is the layer you are watching
in this demonstration, and it is the one reloaded from a JSON file with a citation attached.
Asking about a white round pill gets a refusal and a route to a pharmacist. A second layer exists:
`check_output` scans live-model prose for phrasing that advises a medication change or claims an
action the app cannot take, and grounds every number against the tool-returned fact table,
replacing the reply if it fails. Be straight about where that layer sits — it is called from
exactly one place, inside `_live_turn` in `app/llm/orchestrator.py`, which is the live path that
has never been run, so in this demonstration it has never fired and there are no model replies for
it to scan. What this does not cover either way: 21 live rules over the phrasings the team wrote
down, so a phrasing nobody anticipated may not be caught. That is a real limit, and it is why the
output check was built as a second layer even though it is inert here.

**"What about the missing hardware and hospital integration?"**

Both are deliberate cuts, and both are recorded as such. There is no Bluetooth or device sync —
manual entry was kept because it makes the whole flow visible end to end in six minutes, and
because a pairing state is a new way for a demonstration to fail. The honest concession is that a
Bluetooth cuff is the normal way an older adult in Singapore records a reading, so manual entry is
a step back from what the hardware already does. There is no hospital, HealthHub or PTEC
integration: none exists, none is claimed. The help page denies all of them in one line — no link
to a hospital, a clinic, an ambulance service, or a family member — and it is written generically:
the words HealthHub and PTEC appear nowhere in it. Say the named denial yourself rather than
sending a judge to the page looking for it. What the app does instead is produce one printable
page the patient carries in themselves.

**If a judge pushes on the missing model run:** answer it before they finish the question. The
live model path has never been executed. The endpoint probe was blocked during the build and was
not worked around. Degraded mode is what the 162 tests cover — 45 of them exercising
`app.llm.degraded` and the orchestrator's `check_output` / `_collect_numbers` / `_safety_context`
— and it is what this demonstration shows. No test reaches the live provider loop, `_live_turn`.
The consequence is specific and worth naming: whether a configured endpoint supports the
OpenAI-compatible `/v1/chat/completions` format with function calling, whether latency is
acceptable for a conversational turn, and whether tool calls come back in the shape the
orchestrator expects are all unverified. It is the first item on the outstanding list.

**If a judge asks about clinical review:** no clinician has reviewed anything. Every rule and every
knowledge entry carries `review_state: team_checked` — with the two disabled rules marked
`pending_review`, which is why they are disabled — and that means a team member read the source and
recorded it. That is visible per entry on `/trace` and on every medicine card, and `make seed`
prints `clinician-reviewed entries: 0`. **Not** on the printable summary — do not send a judge
there for it. The printable summary does not repeat the per-entry review state; what it carries is
the global line "No part of this was written or checked by a doctor." That is a stronger
disclaimer, but it is not the same claim, and a judge handed the page expecting a per-item badge
will not find one.

**If a judge asks about accessibility:** the interface was designed against a 19px base font, 48px
tap targets and WCAG AA contrast, with no external requests, no CDN fonts and no build step. It was
**not** independently audited and there is no conformance certification. Say "designed for" and not
"certified", and if pressed, say the audit has not been done.

**If a judge asks about the CodeBuddy / WorkBuddy evidence:** it is outstanding. Handbook p.37 makes
at least three screenshots or recordings of genuine development in CodeBuddy or WorkBuddy a hard
submission gate, and it is not satisfied. Say that plainly. Do not describe the documentation work
that was produced as if it were the required evidence.

**"You have no rule for a dangerous number — what happens if I record 190/120?"** Nothing
automatic. There is no numeric threshold anywhere in this app: not in a rule, not in the content,
not in the config. MOH and HealthHub publish no cut-off for a home reading, and only a US source
gives 180/120, so we ship no threshold rather than one borrowed from a health system our users do
not live in. Verified on stage: entering 190/120 raises two typing checks — "The top number 190 is
unusual for a home reading", "The bottom number 120 is unusual for a home reading" — and lets you
save it. No emergency routing, no 995. The cost is real and we chose it: someone with no symptoms
and a very high reading gets no emergency routing, because the sources do not support one. It is
recorded as decision D10 and enforced by two tests, `test_no_numeric_threshold_is_used_as_a_trigger`
and `test_no_blood_pressure_threshold_in_emergency_config`. Do not let a judge find this first —
it is the question a healthcare-track judge is most likely to open with.

**"Your users are 65 and older in Singapore. Why is this English only?"** It is English only this
round, by decision (D11). A half-translated safety message is worse than an untranslated one, and
translating the emergency wording without review would put unreviewed clinical language on the 995
path. A second language is the next piece of work, and it is recorded as a time constraint rather
than a design conclusion.

**"My father takes three medicines. How many can you actually explain?"** Eight hand-checked
medication-purpose entries: two named drugs — amlodipine and losartan — plus five drug classes
(calcium channel blocker, angiotensin receptor blocker, ACE inhibitor, diuretic, beta blocker) and
one general explanation. Anything else is a refusal and a route to a pharmacist. Verified: asking
about nifedipine or bisoprolol does not route to a boundary refusal at all — the degraded router
simply does not recognise the question, which is an honest dead end rather than a wrong answer. It
is deliberately small: every entry has a publisher and a URL behind it, and recall was traded away
for that. A ninth entry exists in the content file but is switched off on purpose — it holds
SingHealth's hypertension grading table (normal below 130/80 and so on), and shipping it would put
"grade 1 hypertension" in front of an untrained user reading it against a single home measurement.

**"Who can see this data? Is it encrypted?"** This is a local single-process prototype. There is
no login — the session is a cookie with a key regenerated each boot, so any device that obtains the
cookie is that user. There is no encryption at rest: `caresteps.db` is a plain SQLite file. There
is no encryption in transit, and no rate limiting. Every record is fictional, which is the only
reason that is acceptable here; for real patient data it would be disqualifying, and that is
written down in `docs/architecture.md` rather than left implicit. Say it in that order — the cut,
then why it is tolerable in a demo, then what it would cost in production.

---

## 6. Things NOT to claim on stage

Say none of these, in any form, however indirectly.

1. **Do not claim clinical validation, clinical review, or clinical approval.** None exists. Every
   rule and fact is `team_checked`. No doctor, pharmacist or nurse has reviewed any part of this.
2. **Do not claim real-patient testing or a user study.** Every patient row — profile, plan,
   medicines, readings, medication reports, difficulties, chosen actions, questions — is fictional
   and carries `is_simulated = 1`. Mdm Tan is a fixture. No older adult has used the app. (The
   fourteen `education_source` rows are the opposite: those are real published pages held at
   `is_simulated = 0`, which is exactly the point of the register.)
3. **Do not claim hospital, HealthHub, PTEC, or any other integration.** There is no link to a
   clinic, an ambulance service, or a family member. The app cannot contact anyone and says so on
   every screen that matters.
4. **Do not demonstrate the live model path as working.** It has not been run. If the environment
   happens to be configured with a live endpoint, either leave it in degraded mode or say out loud
   before the first turn that this path has not been verified and that the fallback is the tested
   one. Do not present a first-ever live run as evidence of a working system.
5. **Do not describe the simulated history as a trial, pilot, study, or real usage.** It is
   fourteen fictional days written to contain the gaps the app is built to notice. Say "fixture"
   or "demo data".
6. **Do not claim an accessibility certification or a WCAG conformance audit.** Say what the
   interface was designed for and that it was not independently audited.
7. **Do not present the 162 passing tests as validation of the medical content.** They test data
   integrity, safety routing, statistics and the summary. They do not test whether the advice is
   medically correct, and no test could.
8. **Do not quote a number that is not on screen or in `docs/BUILD_LOG.md`.** If a figure has to be
   recalled rather than read, it should not be said.
9. **Do not describe the app as a monitoring service, an emergency service, a medical device, or a
   replacement for a doctor.** The help page lists all four denials; keep them.
10. **Do not claim the CodeBuddy / WorkBuddy evidence requirement is met.** It is outstanding.
11. **Do not claim the app detects a dangerous blood pressure number, or imply it would send
    someone to hospital.** There is no numeric threshold anywhere — not in a rule, not in the
    content, not in the config — so a 190/120 reading raises a typing check and saves, with no
    emergency routing. That is a deliberate cut (D10), not an oversight, and it is the single
    limitation most likely to be found damning by a judge from a health system. Say the cut and
    the reason before anyone asks.
12. **Do not claim any data protection that is not there.** No login, no encryption at rest, no
    encryption in transit, no rate limiting. The session is a cookie with a per-boot key. The only
    thing making that tolerable is that every record is fictional. Do not say "secure", "private
    by design", or "anonymised".
13. **Do not claim negation is handled everywhere.** Most rules carry an `exclude_patterns` list;
    three enabled red-flag rules carry none, so `there is no heavy bleeding` alarms and
    `I did not hit my head` gives urgent advice. It is an open defect recorded in
    `docs/evaluation.md` §6.9. Say the true version if the topic comes up; do not offer to
    demonstrate it.
14. **Do not claim the app works in Chinese, Malay or Tamil, or promise translation.** It is
    English only this round (D11), on a 65+ population where that is a real gap.

---

## 7. One-page card

Cut this out and keep it beside the laptop.

| Time | Where | Do |
|---|---|---|
| 0:00 | — | Challenge 2, older-adult hypertension. A missing record is not information about why it is missing. |
| 0:40 | `/readings/new` | Record a reading. Show "Nothing has been saved yet". Confirm. Point at the count change. |
| 1:30 | `/support/ask` | Type a reason. **Pick no category.** Show "No reason has been given a name yet." Then pick one and show the support change. Open `/app/support` for the 7-category map. |
| 2:40 | `/app/medicines` | Statement, source with URL, `team_checked` caveat. Then `POST /api/chat`: `should I double the dose today`, `what is this white round pill`. |
| 3:30 | `/app/trends` → `/summary` | Denominators. Broken line. Four adherence states with unrecorded apart. Then remove a section and **show it gone on the printed page** — the preview keeps it, by design. |
| 4:30 | `POST /api/chat` → `/app/help` | `I have chest pain` → 995, and "The app has not contacted anyone". Then "What this app is not". The "call only for something life-threatening" line is on `/app/help`, not in the JSON. |
| 5:20 | `/trace` | Model status. 10 tool contracts. **21 live rules**, 23 total with 2 held for review. The live audit log. |

Pre-flight: `make setup` → `make seed` → `make run` → check `/healthz` → run Group A, B, G once →
video ready.

Do not type on stage: `make demo-check` (the script does not exist), `POST /api/demo/reset` (500s
and wipes the database), anything from the group-B risk table (`there is no heavy bleeding`,
`I did not hit my head`, `no blue lips`, `I am not having a seizure`).

Do not say: clinical validation, real patients, hospital integration, live model verified,
accessibility certified, that the demo data is a trial, or that the app detects a dangerous blood
pressure number.

Do say: simulated, `team_checked` not clinician-reviewed, live path not run, no numeric threshold
on purpose, CodeBuddy / WorkBuddy evidence outstanding.
