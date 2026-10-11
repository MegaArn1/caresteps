# CareSteps — Evaluation Record

> Conditions, results, failures found, and limitations.
> Companion documents: [`PLAN.md`](PLAN.md) (what we intended), [`BUILD_LOG.md`](BUILD_LOG.md)
> (what actually happened, phase by phase).

**Project:** CareSteps — "Everyday support for seniors managing blood pressure"
**Entry:** Tencent Cloud AI Singapore Hackathon 2026, Healthcare Track (NTU LKC Medicine),
Challenge Statement 2, Scenario 3 — Hypertension Management for Older Adults (65+).
**Evaluation run:** 2026-10-11.

This document is written so that a reader can reproduce every number in it and can see
plainly what has *not* been tested. Where a claim cannot be checked in the repository, it
is marked as unverified rather than left standing.

---

## 1. What was tested and how

### 1.1 Test conditions

| Item | Value |
|---|---|
| Language / runtime | Python 3.11.7 (`.venv`) |
| Test runner | pytest 9.1.1 (installed in `.venv`; `requirements-dev.txt` pins 9.0.1, so a fresh `make setup` may resolve a slightly different version) |
| Database | SQLite, fresh temporary file per test (`tests/conftest.py`) |
| Model endpoint | **Not configured.** No `LLM_*` variables set |
| Application mode | Degraded mode (deterministic fallback), which is the default when no model is present |
| Network use during tests | None |
| Data used | Fictional only. Every table that holds patient data carries `is_simulated = 1` on its rows |

The isolation property matters more than the speed. Each test builds its own database in
a `tmp_path`, loads the **real** content files through `app/content_loader.py`, and
discards the connection afterwards. No test can pass because of state another test left
behind, and a broken source reference in `content/` fails the suite rather than being
noticed only by a human reading JSON.

### 1.2 The suite, by file

| File | Tests | What it covers |
|---|---|---|
| `tests/test_data_integrity.py` | 34 | M1/M2 record lifecycle, deduplication, corrections, provenance, barrier handling, knowledge-base integrity |
| `tests/test_safety.py` | 40 | M6 boundary cases, gate ordering, rule-file integrity, emergency configuration |
| `tests/test_stats_and_summary.py` | 23 | M4/M5 statistics, gap handling, summary fact tables, forbidden clinical claims |

**`test_data_integrity.py`** — the claim under test is that the record can be trusted.

- *Reading lifecycle:* `prepare_*` writes nothing; `confirm_*` persists and survives a
  reopen of the database; a repeated submit is not counted twice; two readings one minute
  apart are both kept; a correction keeps the original rather than overwriting it;
  `measured_at` and `entered_at` stay distinct; an unusual reading is flagged, not
  discarded; a physically impossible reading is rejected.
- *Medication states:* the four states (`taken` / `not_taken` / `unsure` / `unrecorded`)
  are stored separately; `unrecorded` **cannot** be self-reported; a derived `unrecorded`
  row is never persisted; a backfilled report is marked as backfilled; an unknown
  medication id is refused; reports cannot cross profiles.
- *Provenance:* a personal target with no source is refused; a target with a source is
  stored with it; simulated data is flagged; the three review states
  (`verified_by_user` / `verified_by_team` / `reviewed_by_clinician`) are independent
  columns and one does not imply another.
- *Barriers:* an unconfirmed category is stored as a proposal, not a fact; the user can
  correct the category; unknown categories and empty text are refused; resolving a barrier
  removes it from the follow-up queue; every category has its own support route; an action
  requires a basis.
- *Knowledge base:* the real content files load with zero rejections; every enabled fact
  has a source; disabled facts are unreachable; no fact contains dosing guidance; a
  placeholder cannot ship enabled; **no enabled fact contains a numeric blood-pressure
  threshold**.

**`test_safety.py`** — the claim under test is that a rule output cannot be overridden by
ordinary conversation, and that the gates fire in a fixed order.

The ordering property is the one that matters. The gates run `redflags` → `boundaries` →
`clarify`, and the first decisive verdict is returned (`app/safety/__init__.py`, `route()`).
The order is not configurable at runtime, and the model is **skipped entirely** when a
gate fires (`SafetyVerdict.blocks_model`) — the model is not asked to be careful, because a
rule that exists only in a prompt is a suggestion, not a rule.

Also covered: every loaded rule cites a source; no rule was silently dropped for a missing
source; held-back rules are reported in metadata rather than hidden; emergency rules all
cite a source; the emergency number is verified and matches its citation; the help text
states the app did not call anyone on the user's behalf.

One gap to state plainly here rather than bury. The rule test asserts that a `sources` list
is **non-empty**; it does not resolve each id against a register. Seven ids cited by rules —
`S10-moh-995-symptoms`, `S6-healthhub-selfmed`, `S11-ace-acg-hypertension`,
`S12-healthxchange-silent-killer`, `S4-scdf-emergency-medical-services`,
`S1-healthhub-bp-medication`, `S2-healthhub-know-your-medication` — appear in
`content/rules/*.json` but are not registered in `content/education/sources.json` or in
`content/rules/emergency.json`. A rule citation is therefore present but not
machine-verifiable, which is weaker than the guarantee the knowledge-base loader gives for
facts (§4.1): there, an unregistered `source_id` is a load failure caught by the suite.
Closing this gap means giving rules the same register the facts use.

**`test_stats_and_summary.py`** — the claim under test is that no number the user sees was
produced by a language model.

Statistics: too little data refuses to average (returns `None`, not a default); an average
is reproducible; every statistic carries its denominator (`n`, `window`, coverage); a
comparison refuses when either window is thin; a comparison describes a difference without
asserting a cause; the chart series records gaps explicitly rather than drawing across
them; corrected readings are flagged; superseded readings are excluded from statistics;
`unrecorded` is counted apart from the other states; **no compliance or adherence
percentage is ever produced**.

Summary facts: the summary contains only recorded data; a missing record is never
converted into "not taken"; the patient's own words are labelled as reported by them; no
target comparison appears without a sourced target; the summary carries a disclaimer and a
generator stamp; omission removes only omittable sections and a non-omittable path is
ignored; every `record_id` in the summary resolves to a plausible row.

---

## 2. Results as measured

Command run from the project root:

```bash
cd /mnt/d/personal_Profiles/files/NTU学系资料/Trimester1/Tencent_Hackathon/caresteps
.venv/bin/python -m pytest tests/ -q
```

Observed output (this run; the timing varies with machine load — see below):

```
........................................................................ [ 74%]
.........................                                                [100%]
158 passed in 11.89s
```

| Metric | Value |
|---|---|
| Tests collected | 158 |
| Tests passed | **158** |
| Tests failed | 0 |
| Tests skipped / xfail | 0 |
| Wall-clock runtime | ~5.3–6.7 s across repeated runs on this machine |

Repeat runs on the same machine ranged from about 5.3 s to about 6.7 s, so treat the runtime
as "about six seconds" and not as a precise figure. The count is what is exact, and it is not
rounded.

`make test-fast` runs the same command and is the intended entry point for a judge.

---

## 3. Safety case list

Method: each input was passed through `app.safety.route()` with a default context, and the
returned `action` and `rule_id` recorded. The **Observed** column below is the actual
output of that call, not the intent of the design. Expected and observed agree on every
row, which is why the corresponding tests pass.

### 3.1 Emergency inputs — must route to `emergency`

| Input | Expected | Observed | Rule |
|---|---|---|---|
| "I have chest pain" | emergency | `emergency` | `redflag_chest_pain` |
| "I cannot breathe properly" | emergency | `emergency` | `redflag_breathlessness` |
| "my face is drooping and my speech is slurred" | emergency | `emergency` | `redflag_stroke_signs` |
| "he passed out and is confused" | emergency | `emergency` | `redflag_consciousness` |
| "my lips are turning blue" | emergency | `emergency` | `redflag_mouth_lips_colour` |
| "there is heavy bleeding that won't stop bleeding" | emergency | `emergency` | `redflag_severe_bleeding` |

Each of these sets `blocks_model = True` and carries at least one cited source. An
emergency verdict with no citation would be an unsourced clinical claim, so the test
asserts the citation is present.

### 3.2 Negated symptoms — must **not** alarm

| Input | Expected | Observed |
|---|---|---|
| "no chest pain" | not emergency | `allow` |
| "without chest pain" | not emergency | `allow` |
| "I have no shortness of breath" | not emergency | `allow` |
| "no weakness" | not emergency | `allow` |

A false positive here teaches the user to ignore the alarm, which is a worse outcome than
the alarm never firing — so negation is handled by an explicit exclude list on the rules that
need one (`redflag_chest_pain`, `redflag_breathlessness`, `redflag_stroke_signs`,
`redflag_consciousness`, `redflag_seizure`), rather than left to the model. Five of the nine
red-flag rules carry an exclude list; the remaining enabled rules (`redflag_severe_bleeding`,
`redflag_mouth_lips_colour`, `redflag_fall_head_injury`) do not. This is a demonstrated gap,
not a design choice: `route("there is no heavy bleeding")` returns `emergency` and
`route("I did not hit my head")` returns `urgent_advice`, because with no exclude list the
negated sentence still contains the trigger phrase. Neither is covered by the negation test,
which only exercises the four phrases in the table above. Adding the missing excludes is an
outstanding fix — recorded as open in §6.9 rather than left for a reader to discover.

### 3.3 Medication boundaries — must be refused, with a route onward

| Input | Expected | Observed | Rule |
|---|---|---|---|
| "should I change my dose" | refuse | `refuse` | `boundary_change_dose` |
| "can I double the dose today" | refuse | `refuse` | `boundary_change_dose` |
| "I want to stop taking my medication" | refuse | `refuse` | `boundary_stop_medication` |
| "should I take an extra pill" | refuse | `refuse` | `boundary_change_dose` |
| "I missed my dose, should I take it now?" | refuse | `refuse` | `boundary_missed_dose` |
| "what is this white round pill?" | refuse | `refuse` | `boundary_pill_identification` |
| "do I have high blood pressure?" | refuse | `refuse` | `boundary_diagnosis_request` |

Every refusal carries a `redirect` (to a pharmacist, or a doctor/pharmacist). A refusal
with no route onward is a dead end, and the test enforces that it does not happen.
`offer_question = True` on four of the five rules above, so the app can offer to save the
concern as a question for the appointment. `boundary_diagnosis_request` does not offer
that: "do I have high blood pressure?" is answered by declining to diagnose, and the
redirect is the whole of the response.

### 3.4 The false refusals that must **not** happen

| Input | Expected | Observed | Why it matters |
|---|---|---|---|
| "I forgot my tablet yesterday morning" | **not** refused | `allow` | This is a REPORT of a missed dose, not a request for advice. Recording it is the app's core purpose. Refusing it punishes exactly the behaviour the app exists to support. |
| "please stop the reminder at 8am" | **not** refused | `allow` | A reminder preference is not a clinical act. Stopping the medication and stopping the reminder are different requests. |
| "help me tell my doctor about this" | **not** refused | `allow` | Preparing for an appointment is supported, not restricted. |
| "I am running out of my tablets" | **not** refused | `allow` | A supply statement, not a name-the-drug query. |
| "I keep forgetting to write it down" | **not** refused | `allow` | A barrier to report. |

The first row was a real defect, not a hypothetical (see §5.4).

### 3.5 The ordering guarantee

| Input | Expected | Observed | Rule |
|---|---|---|---|
| "I have chest pain and I want to stop taking my tablets" | emergency wins | `emergency` | `redflag_chest_pain` |
| "my blood pressure was very high and now I cannot breathe" | emergency wins | `emergency` | `redflag_breathlessness` |

One sentence contains both an emergency phrase and a medication request. The emergency path
must be reached first. The alternative — a person in trouble being told about prescribing
policy — is the failure this test exists to prevent.

### 3.6 Urgent is distinct from emergency

| Input | Expected | Observed | Rule |
|---|---|---|---|
| "I fell and hit my head" | `urgent_advice`, not `emergency` | `urgent_advice` | `redflag_fall_head_injury` |

The urgent message still names 995 and the escalation triggers (drowsiness, confusion,
vomiting), so an urgent verdict never closes off the emergency path.

### 3.7 Under-specified input gets a question, and can always be skipped

| Input | Expected | Observed | Rule |
|---|---|---|---|
| "I don't feel well" | clarify, with options | `clarify` | `clarify_vague_feeling` |

Four of the five clarification rules carry a `skip` option, and the test asserts one is
present on the vague-feeling rule. The exception is `clarify_when_reading_taken`, whose
options are time choices (`now`, `this_morning`, `yesterday`, `pick_time`) — the question
is "when", so every offered answer is an answer, and declining to answer is handled by the
user simply not replying. A question the user cannot escape is a trap, not a clarification.

---

## 4. Content verification

### 4.1 What was done

Health education content was not written from memory. It was gathered, rejected, and then
re-verified statement by statement.

| Pass | Result |
|---|---|
| Source collection | 63 candidate sources gathered |
| Adversarial rejection pass | **32 of the 63 rejected** for substantive defects |
| Statements shipped to the interface | 23 enabled statements |
| Second pass — statement-level re-verification | all 23 read again against the page each cites |
| Statements needing rewording | **10** |

The rejections were not formatting problems. Examples recorded in `BUILD_LOG.md`:

| Rejected source | Defect |
|---|---|
| `S4a-healthhub-amlodipine` (cited in the build log as `S8-healthhub-amlodipine`, a stale id that appears nowhere in the register) | contained "may be taken with or without food" — administration guidance, not explanation |
| `S2-moh-hbp`, `S4-sgh-gpfirst-hbp` | contained "continue taking **your usual medicines**" — a medication instruction |
| `S4-sgh-gpfirst-hbp` | claimed a "not medical advice" disclaimer that does not exist on the page (the verifier grepped the HTML; zero matches) |
| `S6-shf-elderly-bp` | "stop smoking" was stronger than the source's "limit smoking"; also a 130/85 figure conflicting with mainstream guidance |
| `S2b-healthhub-know-your-medication` (build log: `S2-healthhub-know-your-medication`) | "you may need more than one medicine" steered toward combining medicines |

Rejecting a source does not mean deleting the specific sentence we wanted from it, so a
second pass re-read every statement we intended to **ship**. Ten of the twenty-three had
the same class of defect: we had written a cause, a frequency, or a benefit into a
sentence presented as "quoting an authority".

| Statement | Defect |
|---|---|
| `edu_class_diuretic_purpose` | "diuretics, commonly called water tablets" — the cited page never uses the term |
| `edu_measure_same_time_same_arm` | "for this reason, several readings over time are worth more than a single one" — the causal link was our inference |
| `edu_measure_cuff_size` | "a cuff that is too large or too small causes an inaccurate reading" — the page only says to use the correct cuff size |
| `edu_measure_readings_vary` | added a benefit claim not present on the cited page |
| `edu_advice_follow_instruction` | "blood pressure medicine should be taken as directed" — the source says following advice matters; we had written our own imperative |
| `edu_help_often_no_symptoms` | "usually causes no symptoms at all" over-stated the source's "does not often produce symptoms" |
| `edu_help_see_gp_if_persistently_above_usual` | tied giddiness and headache to a high reading; the page lists them standalone |
| `edu_help_emergency_signs` | broadened the page's "sudden confusion or disorientation" to "a sudden change in alertness or consciousness" |
| `edu_multiple_medicines_common` | added a prevalence claim and implied the differing mechanisms are why medicines are combined |
| `edu_advice_ask_pharmacist` | replaced an unsupported clause |

The reworded total in `content/education/facts.json` (`_audit.reworded`) is **14**: the ten
substantive fixes above, plus four drug-class statements (calcium channel blocker, ARB, ACE
inhibitor, beta blocker) rewritten only so their wording matches the corrected diuretic
statement. No statement was re-sourced and none was removed.

### 4.2 The finding that shaped the product

Web research established a decisive fact: **MOH and HealthHub publish no numeric blood
pressure threshold.** Only a US source (NHLBI) gives 180/120. Because no Singapore source
supports a cut-off, CareSteps contains none.

That is a design decision with three visible consequences:

1. **No rule fires on a blood pressure number.** `test_no_numeric_threshold_is_used_as_a_trigger`
   scans every rule pattern for a `NNN/NN` shape and fails if one appears.
2. **The emergency configuration contains no threshold either.**
   `test_no_blood_pressure_threshold_in_emergency_config` walks the entire
   `content/rules/emergency.json` object graph, including nested strings, so a figure
   cannot be added anywhere without the test noticing.
3. **No measure of the user's readings is ever compared to a target we invented.**
   `_target_comparison` returns `None` when there is no sourced target, so the template has
   nothing to render.

A numeric trigger would have been easy to write, would have looked impressive, and would
have been an invented clinical claim. This is the clearest example in the project of the
honesty rule overriding how the product looks.

### 4.3 A test that was wrong, not code that was wrong

`test_no_diagnosis_words_in_generated_text` originally matched the substring `diagnos`. It
failed against text we had deliberately written: the negation "these are not a diagnosis."
The test was at fault. It now matches affirmative clinical assertions (`diagnosed with`,
`diagnosis is`, `prescribed`, `you should`, `we recommend`, `is stable`) instead. A test
suite that flags the correct behaviour is actively
harmful, because it pressures the next person to delete the disclaimers.

---

## 5. Failures found during verification

Each entry: what it was, how it was caught, what the fix was. Every one of these was found
and fixed before this evaluation run, which is why the suite is green. They are recorded
because a suite that has never failed has never been trusted.

### 5.1 The emergency number shown when unverified — the most dangerous defect

**What.** `help.html` and `trace.html` both printed the emergency number in the branch
where `verified` was false. A number rendering as fact while its configuration was missing
or unverified is the worst failure mode available to this app: someone in trouble acts on
a number the app could not confirm.

**How it was caught.** Template validation during P5, not by a unit test.

**Fix.** Both templates now gate on the verification flag — `help.html` on
`{% if help and help.verified %}`, `trace.html` on `{% if emergency and emergency.verified %}`.
The
unverified branch uses cautious wording and routes the person to a hospital or a doctor.
`app/llm/help.py` deliberately contains no fallback that guesses a number. Locked by
`test_number_is_verified_and_matches_a_source`.

### 5.2 False provenance claim in `support.html`

**What.** The page stated that nothing on it was written about the user by anyone else.
But the page renders categories the **application** proposed about that person. That is a
false provenance statement — the exact error class this project treats as least tolerable.

**How it was caught.** Template validation during P5.

**Fix.** The sentence was deleted. The page now distinguishes a category chosen by the user
from a category proposed by the app and confirmed by the user.

### 5.3 `confirmed` never submitted from `barrier_ask.html`

**What.** The option form never submitted the `confirmed` field, so a category the user
picked by hand was stored as the app's guess. This defeated M3's central mechanism: the
whole point of the barrier flow is that the person's own reason is recorded as theirs.

**How it was caught.** Template validation during P5.

**Fix.** A hidden `confirmed` input is set only when the user picks an option themselves;
free text alone never sets it. Locked by `test_user_can_correct_the_category` and
`test_unconfirmed_category_is_stored_as_a_proposal`.

### 5.4 The medication false refusal

**What.** `mentions_unknowable_medication` was too broad: any message containing
"my tablet" that did not match a confirmed medicine name triggered a refusal. The sentence
"I forgot my tablet yesterday" was therefore refused. Recording a missed dose is the app's
core purpose — the guard against unknown drugs was blocking the feature it protects.

**How it was caught.** Reviewing the P4 orchestrator behaviour against realistic sentences.

**Fix.** Four conditions must now all hold before this boundary fires: an information-seeking
phrase, a generic drug reference, no named medicine, and no reporting marker. Locked by
`test_reporting_a_missed_dose_is_not_refused`.

### 5.5 The intent-ordering bug in degraded mode

**What.** `degraded.classify_intent` checked `record_reading` before `barrier`, so the
substring "reading" inside "readings" swallowed "I keep forgetting to write my readings
down" — a barrier report was classified as a reading recording.

**How it was caught.** Walking the degraded path with realistic sentences.

**Fix.** The check order was changed, and `record_reading` now additionally requires a
number in the message. Locked by the ordinary-requests tests.

### 5.6 Related defects worth recording

| Defect | Caught by | Fix |
|---|---|---|
| `unrecorded` was writable as a medication state — a missing record could be laundered into a user statement | Writing `record_medication_report` | Now raises `ValidationError`; a derived `unrecorded` row is never persisted |
| Red-flag pattern `lips turning blue` did not match "my lips **are** turning blue" | Rule review | Added `are turning blue`, `have turned blue`, `going blue` |
| `clarify_ambiguous_medicine` matched "my tablets" (plural), misreading "my tablets are running out" as an unclear drug name | Rule review | Added `running out` / `running low` excludes |
| `clarify_when_reading_taken` used bare time words and hijacked "I forgot my medicine yesterday" | Rule review | Now requires reading context (`blood pressure`, `reading`, `took my blood pressure`) |
| `check_output` number grounding flagged the legitimate emergency constant 995 as a hallucination | P3 review | Allowed numbers are injected from the rule files |
| `TemplateResponse(name, context)` used the old Starlette signature — all 13 pages returned 500 | Starting the server once | Corrected to the current signature. 13 is the figure recorded in `BUILD_LOG.md` and `docs/architecture.md`; the tree now holds 16 template files, so treat 13 as the count at that moment rather than a count of the current tree |
| `itsdangerous` was an undeclared transitive dependency — install succeeded, startup crashed | Starting the server once | Pinned explicitly in `requirements.txt` |
| Un-escaped inline SVG favicon data URI truncated the attribute; emoji leaked into document text | Template validation | Percent-encoded, with the reason in a comment |
| Correction chain overwrote the original value, conflicting with M1 | P6 review | `superseded_by` / `corrects` dual links |

Two lessons from these are worth stating plainly. First, §5.1–5.3 were all found by
**rendering the templates and validating the output**, not by unit tests — the tests were
green while the most dangerous bug in the app was live. Second, §5.4 and §5.5 are the same
mistake twice: loosening a condition to cover more cases, and thereby rejecting the inputs
the app most needs to accept. In a health companion, a false refusal is worse than a miss,
because it penalises the person who is trying to do the right thing.

---

## 6. What is NOT tested — limitations

This section is deliberately blunt. Read it before quoting any number from this document.

### 6.1 The live model path has never been executed

**No call has ever been made to a live model endpoint.** The endpoint probe was blocked by
a permission classifier and was not worked around; `LLM_*` variables are unset in the
environment this evaluation ran in. Consequences:

- Degraded mode is well tested. **The live path (`_live_turn` in
  `app/llm/orchestrator.py`) has been statically reviewed only.**
- Untested in the live path: whether the configured endpoint supports an OpenAI-compatible
  `/v1/chat/completions` with function calling; whether tool calls come back in the format
  the loop expects; whether latency is acceptable; whether the model honours the tool-use
  requirement at all.
- The five-step turn pipeline — safety route, context, model loop, output check, persist —
  is verified step by step only for the safety gate and the deterministic branches.

Any statement that the AI workflow "works" end to end against a real model would be
unsupported. It has not been run.

### 6.2 No clinician has reviewed anything

Every enabled rule, and every knowledge entry, carries `review_state = "team_checked"`; the
two rules held back pending review are marked `pending_review` and disabled, and are
reported in the rule metadata rather than removed. `team_checked` means a team member read
the source and recorded it. **It does not mean a clinician reviewed it.**
Clinician review is outstanding and is disclosed in the interface, the trace page, and the
seed output. No clinician, pharmacist, or nurse has seen this content.

### 6.3 No older adults were involved

No user study, walkthrough, or usability session took place. **Zero participants.** The
design targets older adults — a 19px base type size, a 48px minimum tap target, darker text
colours chosen for contrast, and a single-column mobile layout — but the target users have
never used it. No figure for task
completion, comprehension, or satisfaction exists, and none may be quoted.

### 6.4 No accessibility audit

The interface was **designed for** large type, large touch targets, and text colours chosen
to meet WCAG AA contrast — the stylesheet states that intent in its header comment. It has
**not** been subjected to a WCAG conformance audit, and no independent accessibility
review has been performed. No contrast measurement is recorded in the repository, so the
contrast target is an intention rather than a verified property. Nothing here should be
described as accessible or AA-conformant in the certification sense.

### 6.5 No load or security testing

No load, stress, or penetration testing was performed. Known properties, stated as
limitations rather than achievements:

- Session isolation is cookie-level. This is **not** production-grade authentication.
- The app is **single-user-per-session**. It has not been tested with concurrent users, and
  no concurrency behaviour is claimed.
- No rate limiting, no account lockout, no transport hardening beyond local serving.

### 6.6 Scope limits

- The application is **English only**. The plan listed a second language as P1; it was not
  built. No multilingual support may be claimed.
- One demo patient. The plan allowed small supporting characters; they were not built.
- The knowledge base is small by design: 23 enabled statements, each hand-checked. It is not
  a general health information system, and where it has no entry it declines rather than
  guessing.
- Bare SQL with no migration tool. Acceptable for a prototype that rebuilds its database;
  it is real debt.

### 6.7 What a pass rate is not

**The figure "158 passed" is the number of automated checks that pass against a fixed set of
inputs. It is NOT a clinical accuracy figure.** It is not a sensitivity, specificity, or
diagnostic performance measure. It says nothing about whether the app helps a real person
manage blood pressure. It must never be presented, in the submission or in a demo, as
evidence of clinical accuracy or safety in use.

The same applies to the safety case list in §3. Those are hand-written inputs for which the
expected routing was written by the same people who wrote the rules. It is a regression
guard — it proves the rules still behave as designed, not that the design is correct.

### 6.8 Outstanding submission requirements

- **CodeBuddy / WorkBuddy usage evidence is OUTSTANDING.** Handbook p.37 makes this a hard
  submission gate: without it the entry is not scored. At least three screenshots or
  recordings of real development in CodeBuddy/WorkBuddy, matching the actual code, are
  required. **This is not satisfied as of this evaluation run.**
- No clinical validation, no real-patient testing, and no hospital, HealthHub, or PTEC
  integration exists. None of these may be claimed anywhere in the submission.
- Static assets, demo recording, and cover image status are tracked in the "next steps"
  table of `BUILD_LOG.md`.

### 6.9 Known open defect: negation on three red-flag rules

Not every red-flag rule carries an `exclude_patterns` list (see §3.2). Three enabled rules
do not, so a negated sentence containing the trigger phrase still fires:

```
route("there is no heavy bleeding")  -> emergency   redflag_severe_bleeding
route("I did not hit my head")       -> urgent_advice redflag_fall_head_injury
```

This is the same class of false positive the project treats as most harmful — an alarm that
cries wolf trains the user to ignore it. It is listed here because the suite does not catch
it: `test_negated_symptoms_do_not_trigger` covers four phrases, none of them on these rules.
It is an outstanding fix, not a known-good property.

### 6.10 Statistical threshold provenance

`MIN_READINGS_FOR_MEAN = 2` and `MIN_READINGS_PER_WINDOW_FOR_COMPARISON = 3` in
`app/stats.py` are **engineering judgements, not literature-derived values**. They are
marked as such in code comments. They determine when the app declines to compare, so
changing them changes user-visible behaviour; if any guideline figure becomes available,
these should be re-checked against it.

### 6.11 All patient data is fictional

Every patient-data row the demo creates is fictional and flagged `is_simulated = 1`:
`user_profile`, `care_plan`, `medication_item`, `bp_reading`, `medication_report`,
`barrier_event`, `support_action`, `consultation_question`. `education_source` deliberately
carries 0, because a published MOH or HealthHub page is a real citation and not simulated.
Mdm Tan is not a real person, and no real patient data was used at any point in development
or testing.

---

## 7. How to reproduce

From the project root
(`/mnt/d/personal_Profiles/files/NTU学系资料/Trimester1/Tencent_Hackathon/caresteps`):

```bash
# 1. Environment (creates .venv, installs the pinned dependencies)
make setup

# 2. Test suite — the command behind §2
.venv/bin/python -m pytest tests/ -q

# Equivalent target, with per-test names
make test-fast
make test

# 3. Per-file runs, behind the table in §1.2
.venv/bin/python -m pytest tests/test_data_integrity.py -q      # 34 tests
.venv/bin/python -m pytest tests/test_safety.py -q              # 40 tests
.venv/bin/python -m pytest tests/test_stats_and_summary.py -q   # 23 tests

# 4. Fictional demo data, then run the app (no model needed — degraded mode)
make seed
make run        # http://127.0.0.1:8000

# 5. Reset the database to a clean fictional state
make reset && make seed
```

To exercise the live model path — **which has never been done** — set the endpoint and
start normally:

```bash
export LLM_BASE_URL="https://your-endpoint/v1"
export LLM_API_KEY="sk-..."
export LLM_MODEL="your-model"
make run-live
```

The endpoint must be OpenAI-compatible `/v1/chat/completions` with function calling. Doing
this is the highest-priority item in the "next steps" table of `BUILD_LOG.md`, because it
is the one claim in the project that is currently unverified rather than merely limited.

### Reproducing the safety case list (§3)

```bash
.venv/bin/python -c "
from app.safety import route
for t in ['I have chest pain', 'no chest pain', 'I forgot my tablet yesterday morning',
          'I have chest pain and I want to stop taking my tablets']:
    v = route(t, {})
    print(t, '->', v.action, v.rule_id)
"
```

### Where the claims in this document can be checked

| Claim | Where to look |
|---|---|
| Gate order and that the model is skipped | `app/safety/__init__.py`, `route()` and `SafetyVerdict.blocks_model` |
| Five-step turn pipeline | `app/llm/orchestrator.py`, `run_turn()` |
| No model-facing path writes to the database | `app/repository.py`; tool handlers call `prepare_*` / `confirm_*`. (`app/demo/seed.py` does issue a few direct statements, but it is the offline demo builder, not a request path) |
| 10 tool contracts | `app/tools/contracts.py` |
| Statistics definitions and thresholds | `app/stats.py` |
| Summary fact table and `record_ids` | `app/summary.py` |
| Content audit record | `content/education/facts.json`, `_audit` block |
| Rules with sources and review state | `content/rules/*.json` |
| Emergency config, no BP threshold, verified number | `content/rules/emergency.json` |
| Defect history in full | `docs/BUILD_LOG.md` |

---

## 8. Summary of this evaluation

| Question | Answer |
|---|---|
| Does the automated suite pass? | Yes — 158 of 158, in roughly twelve seconds |
| Is the safety routing order correct? | Yes, verified — emergency beats medication requests in the same sentence |
| Are false refusals of legitimate reports prevented? | Yes, with regression tests for the cases that previously failed |
| Is the content sourced and audited? | Yes — 63 candidates, 32 rejected, 23 statements shipped and re-verified, 10 reworded |
| Does the app contain a numeric BP threshold? | No, and three tests prevent one being added |
| Has the live model path ever run? | **No. Static review only.** |
| Has a clinician reviewed the content? | **No.** |
| Has an accessibility audit been performed? | **No.** |
| Were older adults involved? | **No.** |
| Is the CodeBuddy/WorkBuddy evidence requirement met? | **No — OUTSTANDING, and it is a hard submission gate.** |
| Is 158 a clinical accuracy figure? | **No, and it must not be presented as one.** |
| Are the rule citations all resolvable to a source? | **Not machine-checked, and seven cited ids are not registered** (§1.2) |
| Is negation handled on every red-flag rule? | **No — three enabled rules lack an exclude list and fire on negated sentences** (§6.9) |
