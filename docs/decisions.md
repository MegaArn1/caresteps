# Decision record

**CareSteps — Tencent Cloud AI Singapore Hackathon 2026**
Healthcare Track (NTU LKC Medicine), Challenge Statement 2, Scenario 3:
Hypertension Management for Older Adults (65+).

This is the record of the decisions that shaped the prototype, and of the ones we expect to be
argued with.

Every entry below uses the same six fields:

| Field | What it contains |
|---|---|
| **Date** | When the decision was taken. All entries in this round are 2026-10-11. |
| **Decision** | The choice, stated so that the opposite choice is also visible. |
| **Reason** | Why, in the terms that actually drove it. |
| **Evidence** | Where to check the decision in the repository. If a claim here cannot be checked in the code, the claim is wrong. |
| **Cost** | What we gave up, stated plainly. A decision with no cost was not a decision. |
| **What would change our mind** | The evidence or event that would reverse it. |

The build ran from 2026-10-11 to a submission deadline of 2026-10-16. That is five days,
including the submission rehearsal. It is not a background fact. It is the reason several
decisions below are smaller than they would otherwise be.

---

## How this record relates to the plan

The build plan (`docs/PLAN.md`, section 5) recorded six decisions under the identifiers D1–D6.
This document is the fuller record. It keeps those identifiers where they already exist and
cross-references where a plan entry is split or extended here.

| Plan ID | Plan wording | Here |
|---|---|---|
| D2 | No frontend build step | D2 |
| D3 | Bare SQL, not an ORM | D3 |
| D4 | Model forced to use tools and a fact table | Split into **D4** (single orchestrator, restricted tools) and **D5** (all numbers computed in code) |
| D5 | Degraded mode as a first-class citizen | D7 |
| D1 | English-first for this round | D11 |
| D6 | Mdm Tan as the single main character | D12 |

D1, D6, D8, D9 and D10 in **this** document are new here and did not appear in the plan's
table. D1 in this document is the challenge selection, which the plan treated as a given
rather than as a decision worth recording. It is recorded here because it is the decision every
later one depends on.

---

## D1 — Challenge 2, Scenario 3: hypertension in adults 65 and over

**Date:** 2026-10-11

**Decision.** Enter Challenge Statement 2 ("AI Healthier Every Day: Intelligent Support for
Long-Term Self-Care"), Scenario 3 (Hypertension Management for Older Adults, 65+). Do not build
a general health assistant. Do not cover several conditions.

**Reason.** Two things narrow the field, and both point the same way.

The first is scope. One person, five days, and a judged demonstration. A horizontal health app
covers many conditions badly and cannot be defended in detail at any point. A single scenario
can be described end to end, including its edges, which is what a judge actually tests.

The second is that the safety story only works if the app knows where its users are. Every
safety path in this app ends in one of a small set of local routes: call 995, see your GP, ask
your polyclinic pharmacist, go to the Emergency Department. An app that does not know what a
polyclinic is cannot give that advice. Choosing the scenario is what makes the routing concrete
rather than generic.

The scenario also fits what we can honestly build. Older adults managing an existing diagnosed
plan need execution support — recording, understanding, explaining why something was hard,
preparing for an appointment. None of that requires a diagnosis, which is the one thing we
cannot and must not do.

**Evidence.** `content/rules/emergency.json` is a Singapore-specific configuration with SCDF and
MOH sources. `content/education/sources.json` registers 14 sources, every one of them a
Singapore publisher (MOH, HealthHub, SingHealth, Singapore Heart Foundation, SCDF).
`app/demo/seed.py` builds Mdm Tan at age band `65-74`. `app/config.py` carries the challenge
label.

**Cost.** Nothing generalises. We cannot claim this works for a different condition, a different
health system, or a different age group, and we do not. The source restriction also costs us the
better-evidenced American and European guidance (NHLBI's numeric threshold, AHA cuff-size
guidance), because those documents do not know the local referral route or the local emergency
number.

**What would change our mind.** A clinician on the team, or a second week. With a clinical
co-investigator the review gap would close and the vertical scope could widen to one adjacent
scenario. With no clinical input, widening the scope would widen the part of the app that has
not been checked by anyone qualified to check it.

---

## D2 — Mobile-first web prototype with no frontend build step

**Date:** 2026-10-11

**Decision.** Jinja2 templates, hand-written CSS, and one vanilla JavaScript file. No bundler, no
npm, no transpiler, no CSS framework, no web fonts, no CDN, no external request of any kind.

**Reason.** The demonstration is the deliverable. A build step is a step that can fail on the
demonstration machine, in the room, in front of the judges, five minutes before the walkthrough.
A missing `node_modules`, a registry that cannot be reached from conference wifi, or a version
mismatch between a global tool and a lockfile are all failures that have nothing to do with the
product and everything to do with whether anyone sees it.

There is a second reason that is not about failure. The target user is on a phone. A
server-rendered page that works on a phone, in a large font, with 48px tap targets, is what the
design requires. The framework we would add is not what makes that work; the CSS is.

**Evidence.** `requirements.txt` lists five direct dependencies plus `itsdangerous`, pinned to
the versions verified working. `app/templates/base.html` links one local stylesheet, one local
script, and an inline percent-encoded SVG favicon — no external host appears anywhere in it.
`app/static/css/app.css` declares a 19px base font, a `--target: 48px` tap size, no `@import`,
and no `url()` pointing outside the app. `grep -rn "http" app/static/js/app.js` returns one hit:
the SVG namespace string.

**Cost.** Everything the DOM does is hand-written. There is no component model, no reactivity,
no type checking in templates. Renaming a field means finding it in Python and in Jinja by
hand. The chart code in `app/static/js/app.js` builds SVG elements directly, which is more code
than a chart library would need. A richer interface would get expensive to maintain this way.

**What would change our mind.** A second engineer or a second week, and a component layer would
start paying for itself. It would not change before the submission deadline, because that is
precisely the period in which a build step is most likely to break.

---

## D3 — Bare SQL and a hand-written schema, not an ORM

**Date:** 2026-10-11

**Decision.** SQLite through the standard library `sqlite3`, with the schema written out as SQL
in `app/db.py`. No ORM, no migration framework, no query builder.

**Reason.** The schema is the specification of this application, and it has to be explainable
live. Several of the strongest claims in the project are claims about the *shape* of the data,
and an ORM would put a translation layer between the claim and the evidence.

The clearest example is the pair of timestamps on a reading. `bp_reading` carries `measured_at`
when the cuff was on the arm and `entered_at` when the row was created. These are different
questions, and a schema that stores one column loses the ability to answer the other. That is
visible in a `CREATE TABLE` statement and it is a comment in a model class.

**Evidence.** `app/db.py` defines ten tables with column-level comments stating what each column
answers. The claims that are structural, not stylistic:

| Claim | Where it is enforced |
|---|---|
| Three separate verification questions | `verified_by_user`, `verified_by_team`, `reviewed_by_clinician` are three independent columns on `care_plan` and on `education_fact` |
| Simulated data can never be mistaken for real | `is_simulated` on every table, defaulting to 1 |
| When it was measured is not when it was entered | `measured_at` and `entered_at`, never merged |
| A correction keeps its predecessor | `superseded_by` and `corrects` on `bp_reading` |
| A repeated submit does not double-count | `dedupe_key TEXT UNIQUE` |
| Unrecorded is derived, not reported | `is_self_report` on `medication_report`, `0` for derived rows; `app/repository.py` raises `ValidationError` if a caller tries to submit `status="unrecorded"` |

**Cost.** No migrations. The prototype resets by deleting the file (`make seed`), which is
acceptable now and is debt the moment there is data worth keeping. Queries are written by hand,
so a column rename is a search across Python rather than a change in one place.

**What would change our mind.** Any real data that must survive a schema change. At that point
the cost of the migration tool is smaller than the cost of not having one. It would also change
if someone joined who had to work on this without reading SQL, though the schema comments are an
attempt to make that a smaller problem than it normally is.

---

## D4 — One conversational orchestrator with restricted tools, not a multi-agent system

**Date:** 2026-10-11

**Decision.** A single agent, a fixed five-step turn pipeline, and ten tool contracts. No planner
agent, no specialist sub-agents, no agent-to-agent messages.

**Reason.** Three arguments, in the order they weighed.

The Handbook does not require a multi-agent design. Building one would be adding a graded
integration surface that is not being graded.

A demonstration cannot afford the integration risk. Multi-agent failure modes are not additive;
they compound. Agent A produces a plan that agent B interprets differently, and the result is
both non-deterministic and harder to explain in the room than a single call chain. With five
days, the variance is the enemy.

The safety architecture is simpler and stronger with one agent. Safety routing runs once, before
anything else, and its verdict is final. With several agents there are several entry points to
guard, and each is a place where the rule could be reached later or not at all.

**Evidence.** `app/llm/orchestrator.py` documents the order and implements it with no step
skippable: safety route, then context, then the model loop, then output checking, then persist.
`app/tools/contracts.py` declares exactly ten tools. `app/tools/handlers.py` `dispatch()` returns
an error for an unknown tool name rather than raising, so a hallucinated tool name cannot become
an exception.

Two structural points carry most of the weight:

- **Safety can return without ever calling the model.** `SafetyVerdict.blocks_model` is true for
  `emergency`, `urgent_advice`, `refuse` and `clarify`, and `run_turn` returns immediately in
  those cases. An emergency message cannot be delayed, reworded, or softened by a language
  model, because no language model is involved.
- **The model cannot write to the database.** Every health record is written in two phases:
  `prepare_*` validates and returns a draft without persisting, and a separate `confirm_*` step
  persists it after the user confirms. No tool handler executes SQL; `app/repository.py` is the
  only module that writes, and it uses parameterised statements. The model has no path to a
  direct write, which makes "the model cannot save anything by itself" a structural fact rather
  than a prompt instruction.

**Cost.** A single agent has one context window and one tool budget. If a future version needed
genuinely different reasoning for a benefits question and a records question, a single agent
would have to hold both. We have accepted a ceiling on complexity in exchange for a floor on
reliability.

**What would change our mind.** A measured failure that a second agent demonstrably fixes, in a
scenario where the turn no longer has a single deterministic safety decision to make. Not a
general argument that multi-agent systems are better; a specific failure in this app that a
specific second agent resolves.

---

## D5 — Every number is computed in code; the model may only rephrase

**Date:** 2026-10-11

**Decision.** All arithmetic, all counting, all windowing and all comparison happens in
`app/stats.py` and `app/summary.py`. The model receives the results and may put them into
sentences. It may not add, average, subtract, count or compare.

**Reason.** The largest class of hallucination in a health application is a plausible number.
"Your average this week was about 140" is exactly the kind of sentence a language model produces
fluently and incorrectly, and it is exactly the kind of sentence a patient will act on.

This decision has a second benefit that mattered as much as the first. A number produced by
code is a number a reviewer can re-derive. If the judgement is "this mean is wrong", the bug is
in one Python function, not in a prompt.

**Evidence.** `app/stats.py` carries the commitment in its module docstring and implements the
consequences: every result includes the denominator (`n`), the window, the date range, and a
`sufficient` flag; a mean is `None` when there is not enough data rather than a default; and
`compare_windows` reports that two windows differ without reporting a cause. `series_for_chart`
emits a per-day entry with `has_data: False` on a gap day, so the chart is drawn with a break
rather than a line across the missing days.

The enforcement is in `check_output` in `app/llm/orchestrator.py`. Every two- and three-digit
number in the model's prose must appear in what the tools actually returned. A turn that fails
the check is **replaced**, not amended — a model that has drifted once is likely to drift again
while being repaired, so the app substitutes a sentence built from the tool results instead.
Latitude for legitimate constants (the emergency number, configured times) is drawn from
`content/rules/*.json` rather than hard-coded, so the number in the prose and the number on the
help page cannot diverge.

`app/summary.py` applies the same rule to the appointment page: it produces a structured fact
table where every item names the `record_ids` it came from, and prose is generated from that
structure and never the other way round.

**Cost.** The model cannot do anything clever with numbers, including things it would get right.
A question that a capable model could answer approximately is now answered only if a tool
returns the figure. The orchestrator is more complex than a plain chat loop, and the two-phase
write pattern means more code and more tool calls per turn.

**What would change our mind.** This is the decision we would change last. It would take a
demonstration that the numeric check produces more wrong refusals than it prevents wrong
figures. `check_output` has already produced one false positive in development — it once
flagged the legitimate emergency constant 995 as ungrounded — and the fix was to widen the
allow-list from the rules, not to weaken the check.

---

## D6 — Deterministic safety gates that run before the model and cannot be overridden

**Date:** 2026-10-11

**Decision.** Three ordered gates — red flags, then boundaries, then clarification — implemented
as ordinary code over rule data, evaluated before the model on every turn. A gate that returns a
decisive verdict ends the turn. The model is not consulted, and no later step can revisit the
verdict. The order is fixed and not configurable at runtime.

**Reason.** A rule that exists only in a system prompt is not a rule. It is a suggestion that
competes with everything else in the prompt, including a user who is trying hard to get a
different answer. If the app must never advise a dose change, then no arrangement of words in a
user message may reach the model with a request to advise a dose change.

Running the gate first also removes latency from the path that can least afford it. An emergency
message does not wait for a model call, does not depend on the network being up, and does not
degrade when the model is unavailable.

**Evidence.** `app/safety/__init__.py` defines the ordered `route()` function and the
`blocks_model` property. Rules live as data in `content/rules/*.json` so that a reviewer can read
every trigger and its citation without reading Python. `app/safety/rules.py` enforces two things
at load time: a rule with no source is dropped and recorded as a load problem, and a disabled
rule is retained but inert, so the demo can show a rule that exists and is deliberately held
back rather than pretending it does not exist.

The current state of the rule set, readable from the files:

| File | Rules | Enabled | Held back |
|---|---|---|---|
| `content/rules/redflags.json` | 9 | 8 | `redflag_fever_with_confusion`, `pending_review` |
| `content/rules/boundaries.json` | 9 | 8 | `boundary_emergency_contact_change`, `pending_review` |
| `content/rules/clarify.json` | 5 | 5 | — |

The two held-back rules are shown on the trace page with their review state rather than hidden.
`tests/test_safety.py` covers the ordering directly: an emergency phrase beats a medication
request, and an emergency phrase beats a clarification request.

**Cost.** Keyword rules over natural language misfire, and this cost was paid three times in
development, all recorded in `docs/BUILD_LOG.md` phase P2: `lips turning blue` did not match
"my lips are turning blue"; `my tablet` matched "my tablets are running out" and misread a
supply problem as a drug-identification problem; and bare time words hijacked "I forgot
yesterday". Every fix was a longer pattern list or an exclusion list, which is more rule data to
maintain. The general lesson recorded at the time: a keyword rule matching natural language will
be triggered by compound sentences, so every rule needs exclusions and must be tested against
real sentences rather than sentences the designer imagined.

**What would change our mind.** A clinically reviewed rule set with a defensible severity
model. That would still not move the gates after the model — it would improve what the gates
decide, not when they decide it.

---

## D7 — Degraded mode as a first-class path, not a fallback stub

**Date:** 2026-10-11

**Decision.** Build the no-model path as a complete working layer with its own tested behaviour,
not as an error page. It is the default state of the app and the state the judges will most
likely see.

**Reason.** The model endpoint may not be reachable in the demonstration room, and it certainly
cannot be relied on if it is being called for the first time. Choosing the degraded path as the
default also forces the honest question early: if the assistant is unavailable, what can this
app still do? The answer defines the real product.

The answer we settled on: recording, viewing history, statistics, the appointment summary, the
barrier flow and the emergency-help path never needed a model. They are computed and rendered
from data. Only the conversational explanation layer is lost.

**Evidence.** `app/llm/degraded.py` states the commitment and implements it. It carries an
explicit `MODEL_FREE_INTENTS` set (`record_reading`, `record_medication`, `view_trends`,
`build_summary`, `view_plan`, `help_emergency`, `barrier`, `unknown`), a deliberately crude
keyword intent classifier, and `UNAVAILABLE_MESSAGE`, which declines to explain a medicine and
says where to ask instead. The file states the reason directly: explaining a drug badly is worse
than declining to explain it.

`app/config.py` exposes `LLM_FORCE_DEGRADED`, so the fallback path can be demonstrated and tested
without unplugging anything, and `LLMSettings.describe()` reports why the app is in the state it
is in without ever printing the key. `README.md` states that no API key is required to explore
everything, and `make run` works with no model configured.

The honest limit belongs in this entry. **The live model path has never been exercised.** The
endpoint probe was blocked during the build and was not worked around. Degraded mode is
thoroughly tested; `_live_turn` is statically reviewed only. This is recorded in
`docs/BUILD_LOG.md` and it is the first item on the outstanding list.

**Cost.** Two conversation paths to maintain, and they can disagree. The degraded path is
cruder, so what the app can do is visibly smaller than what it claims to be capable of. That
asymmetry is the price of never being blocked by a network.

**What would change our mind.** A completed live run would not remove this decision; it would
downgrade degraded mode from default to insurance. The decision would reverse only if a real
model were guaranteed present and reliable at every point of use, which is not the situation
here.

---

## D8 — Eight hand-checked medication-purpose entries instead of a drug database

**Date:** 2026-10-11

**Decision.** Ship a small set of medication-purpose entries, each traced to a named page and
each read against that page. Do not integrate a drug database, a formulary, or a
medication-information API. Do not extend the knowledge base by retrieval at runtime.

**Reason.** The requirement in Challenge 2 is to explain, not to advise. A drug database is
built for a different job: dosing, interactions, contraindications, administration. Most of what
it contains is content this app must never surface, and the parts we would want are buried
inside text we would have to filter. Importing it would mean filtering it, and filtering a
medical database with a regex is not a safety strategy.

A hand-checked set inverts the problem. We choose the sentences, and then we have to show where
each one came from. Breadth is traded for correctness, and the trade is visible to the user.

**Evidence.** `content/education/facts.json` contains 24 entries, 23 enabled and 1 deliberately
disabled. Of those, eight are `medication_purpose` entries:

| Entry | Subject | Source |
|---|---|---|
| `edu_amlodipine_purpose` | amlodipine | `S4a-healthhub-amlodipine` |
| `edu_losartan_purpose` | losartan | `S4b-healthhub-losartan` |
| `edu_class_ccb_purpose` | calcium channel blocker | `S2-healthhub-bp-medication` |
| `edu_class_arb_purpose` | angiotensin receptor blocker | `S2-healthhub-bp-medication` |
| `edu_class_ace_purpose` | ACE inhibitor | `S2-healthhub-bp-medication` |
| `edu_class_diuretic_purpose` | diuretic | `S2-healthhub-bp-medication` |
| `edu_class_betablocker_purpose` | beta blocker | `S2-healthhub-bp-medication` |
| `edu_multiple_medicines_common` | (medicines in general) | `S2-healthhub-bp-medication` |

Two are named drugs and five are drug classes, which is the shape of the sources rather than a
claim that seven drugs is a formulary. The demo patient is on two medicines, both named here.

The set is enforced, not merely described. `app/content_loader.py` rejects a fact whose source is
not registered, and reports the rejection rather than skipping it quietly.
`app/repository.py::search_facts` returns `enabled = 1` rows only, so a held-back entry is
unreachable from the model by construction. `app/tools/handlers.py::h_retrieve_education` returns
the empty result as a first-class outcome, with an instruction not to fill the gap from general
knowledge. The medicines page shows the same boundary to the user: a medicine that is not on the
list is not guessed at, the app says it could not match the name, and it offers to help ask a
pharmacist.

**Cost.** This is a small set. Most antihypertensives a real patient might be taking are not
covered, and the app must decline to explain them. A declined explanation is a worse user
experience than a correct one, and it will happen often outside the demo.

The content also required an adversarial second pass beyond the source screening. 63 candidate
sources were gathered and 32 rejected in the first pass. What actually ships is sentences, not
source records, so a second pass re-checked the 23 statements intended for release one at a
time. Ten had to be rewritten; four more were rewritten for consistency with them. The defects
were all one kind: a cause, a frequency or a benefit that the cited page does not state, written
into a sentence presented as coming from that page. The full list is recorded in the `_audit`
block of `content/education/facts.json`.

**What would change our mind.** A licensed, maintained source register whose purpose matches
explanation-only use, plus the review capacity to keep it checked. The failure mode that would
reverse this is not "the app declines too often"; it is "the app answered a question it had no
source for". Wider coverage purchased by looser sourcing is the exact trade this project exists
to refuse.

---

## D9 — Four adherence states, with `unrecorded` derived and never reported

**Date:** 2026-10-11

**Decision.** Medication status has exactly four values: `taken`, `not_taken`, `unsure` and
`unrecorded`. A patient may report the first three. `unrecorded` is computed from the absence of
a report and is never accepted as a submission. A day with no record is counted separately from
a day the patient said they skipped.

**Reason.** This is the single most important self-correction in the build, and it is recorded
as such in `docs/BUILD_LOG.md` phase P1.

The first version of the schema listed `unrecorded` as one of the values a user could report.
Writing the `record_medication_report` handler made the consequence obvious: if a user can
report "unrecorded", then a missing record can be laundered into a statement the user made.
At that point the app's silence becomes the patient's omission, and a downstream reader — a
doctor, or the summary page — sees a missed dose where the truth is that nobody knows.

For an older adult with a diagnosed condition, "you did not take your medicine" is a serious
claim to make on their behalf from nothing. The app must not be able to make it.

**Evidence.** `app/repository.py` defines `ADHERENCE_STATUSES` with all four values, and raises
`ValidationError` when a caller submits `status="unrecorded"`, with the message that it is
derived from a missing entry and cannot be reported. `derive_unrecorded` returns synthetic rows
with `is_self_report = 0`, so the distinction survives into the database.
`app/db.py` documents the same rule on the `medication_report` table.

`app/stats.py::adherence_summary` counts the four states into four separate keys and states the
interpretation explicitly: a day with no record does not mean a dose was missed. The same
function carries an explicit refusal — there is no percentage in the returned structure, and the
`note` field says why: counting reported status is not a measure of true adherence, and a rate
would require treating missing records as misses.

The same distinction is visible in the demo data. The seed deliberately stops medication reports
two days before the end of the window and includes one backfilled report, so both the derived
state and the "you told us later" state appear in the walkthrough rather than being theoretical.

**Cost.** The app reports a less satisfying number. A user who wants to know "how am I doing"
gets four counts and a statement about how many days have no record, not a percentage. The
barrier flow — asking why a record is missing — exists partly because the app refuses to answer
that question itself.

**What would change our mind.** Nothing we can currently construct. A change would require a
data source that records doses independently of the patient, which this app does not have and
deliberately does not integrate with.

---

## D10 — No numeric blood-pressure threshold anywhere in the app

**Date:** 2026-10-11

**Decision.** No rule, no content entry, and no configuration file contains a numeric
blood-pressure threshold — not for an emergency, not for "high", not for a target. The app
reports a reading and where the number came from. It does not judge it.

**Reason.** This came from a research finding, not from a design preference. Retrieval for this
prototype found that **MOH and HealthHub do not publish a numeric blood-pressure cut-off**. Only
an American source states 180/120. If the app triggered help at 180/120, it would be asserting a
clinical threshold that the health system its users actually live in does not publish, in a
country whose referral routes and emergency number we are otherwise careful to get right.

The finding produced a rule, which is the part worth stating: **where we have no basis, we do
not write one.** A fabricated threshold has real consequences in both directions — it can send
someone to an emergency department unnecessarily, and it can imply that a reading below it is
fine.

**Evidence.** `content/rules/redflags.json` carries a `_deliberate_omissions` block stating that
no numeric threshold appears in the file and why: a very high reading with no symptoms therefore
does not trigger the emergency gate, and the app reports the number and its source without
interpreting it. `content/rules/emergency.json` states the same for the emergency configuration.
`edu_numeric_bands_disabled` in `content/education/facts.json` is the SingHealth grading table
recorded as a disabled placeholder, marked "NOT SHOWN", with the reasoning that an untrained
user reading a grade against a single home measurement is likely to misunderstand it.

Three tests enforce the decision across different surfaces:
`test_no_numeric_threshold_is_used_as_a_trigger` (no rule pattern may match an `NNN/NN` form),
`test_no_blood_pressure_threshold_in_emergency_config` (walks the whole emergency configuration
tree, including nested strings), and `test_no_numeric_threshold_in_enabled_content` (scans the
enabled `when_to_seek_help` and `how_to_measure` statements). Together they mean a threshold
cannot be added to the rules, the configuration, or the content without a test failing.

**Cost.** The app is less helpful than it looks like it could be. A 65-year-old can record a
reading of 158/94 and the app will not say whether that is high. It will say what was recorded,
how many readings there are, and from what period — and it will offer to write a question down.
Some users will read that as the app not working.

A second, sharper cost belongs here. **The emergency gate does not fire on a number.** Someone
with no symptoms and a very high reading gets no emergency routing, because the sources do not
support one. We judge that the honest failure is preferable to a fabricated threshold, but it is
a real gap and it is stated rather than hidden.

**What would change our mind.** A numeric threshold published by MOH or HealthHub for home
readings. That is the specific, checkable event. An American guideline alone would not settle it,
for the reason in D1: the threshold would arrive with a referral route that does not exist here.

---

## D11 — English only for this round

**Date:** 2026-10-11

**Decision.** Ship the interface in English. Do not offer a second language. Do not present a
language switcher that is not wired to anything.

**Reason.** A half-translated interface in a health app is worse than an English one, and a
translation that is not reviewed is a second set of unverified health statements. The interface
strings are not the hard part; the reviewed content and the safety messages are. Translating
them without review would put unreviewed wording on the emergency path.

The plan lists a second language as P1 and it was not reached in five days. That is a scope
outcome, not an oversight, and it is stated as one.

**Evidence.** `app/config.py` records the challenge context. `user_profile.language` exists in
the schema and defaults to `'en'` (`app/db.py`). `app/demo/seed.py` sets the demo patient's
language to `en`. There is no locale mechanism, no message catalogue and no translation file
anywhere in `app/`. `docs/BUILD_LOG.md` phase P5 records the limitation explicitly: the interface
is English only, the plan put a second language at P1, and this round did not do it, so it must
not be claimed.

**Cost.** Singapore is a multilingual country and a large part of the target population is more
comfortable in Mandarin, Malay or Tamil. An English-only app excludes people it is built for.
This is the decision on this list with the clearest social cost and the weakest technical
justification — it is a time constraint, not a design conclusion.

**What would change our mind.** Reviewed translations of the safety messages and the knowledge
entries, by someone competent in the target language and able to check the clinical claims.
Translating the interface alone would change nothing that matters here.

---

## D12 — One fictional persona rather than several

**Date:** 2026-10-11

**Decision.** One demo patient: Mdm Tan, age band `65-74`, diagnosed hypertension, with a care
plan, two medicines and a two-week history. Additional personas were allowed by the plan and
were not built.

**Reason.** A demonstration is a narrative, and a narrative with several protagonists has none.
More importantly, one persona is what makes the interesting states visible. A clean two weeks
would leave the app's central feature — asking why a record is missing — impossible to
demonstrate at all. So the history was designed around the states the app exists to handle:
a three-day gap with no readings, two days with no medication report, one backfilled report, one
corrected reading, one open difficulty and one resolved difficulty.

The gaps had to be designed before the interface, because the interface has to have something to
respond to.

**Evidence.** `app/demo/seed.py` documents the character and the reasoning in its module
docstring, and implements the pattern in `READING_PATTERN` with explicit `None` days commented
as gaps. Plan items carry `source_type = 'demo_fictional'`, so the plan text is labelled as
written by us and carrying no clinical authority. Every seeded row sets `is_simulated`, and the
schema sets that column on every table so no simulated history can be mistaken for a real
observation.

**Cost.** No breadth. The app cannot be shown with a patient on four medicines, or a patient who
raises a difficulty in a language other than English, or a patient whose plan came from a
clinician rather than from us. `docs/BUILD_LOG.md` phase P6 records this as not done.

**What would change our mind.** A reviewer or an early tester asking a question that the single
persona cannot answer. Adding a second persona is cheap; doing it before knowing what it needs to
show would add a second set of fictional records without adding an answer.

---

## Decisions we expect to be challenged on

These are the questions a judge or a technical reviewer is most likely to ask, with the answer we
would give. Where the answer is a limitation, it says so.

### Why not use a real clinical dataset, such as MIMIC-III?

Because it is the wrong data for this task, in three independent ways, and any one of them would
be sufficient.

**Population.** MIMIC-type datasets come from intensive care and hospital admissions. The users
of this app are community-dwelling older adults managing a diagnosed condition at home. Blood
pressure behaviour in an ICU is not blood pressure behaviour in a flat in Toa Payoh, and a
distribution learned from one does not transfer to the other.

**Task shape.** These datasets exist for clinical research and model development. This app does
not predict anything; it supports execution — recording a reading, understanding a medicine,
explaining why something was hard, preparing for an appointment. There is nothing in an ICU
dataset that improves a flow about a patient forgetting to log a reading.

**Governance.** These are de-identified but still real patients' records, released under data use
agreements that govern what may be derived from them and how it may be presented. A competition
prototype has no basis for that use, and the app's own emergency path depends on it being plainly
not a clinical service.

There is also a fourth reason, and it is the one that decides it. Using a real dataset would not
make this app better at the thing it does. It would make it look more serious while changing
nothing about whether a 72-year-old can record a reading. The dataset question and the product
question are different questions, and only the second one is being asked here.

This is written up in `docs/content-provenance.md` section 5.5, and no file in this repository
references such a dataset.

### Is eight medication-purpose entries enough?

No. It is nowhere near enough, and the app says so rather than working around it.

Eight entries cover two named drugs and five drug classes, from two HealthHub pages. A real
hypertension patient may be on any of several dozen medicines, and most of them are not here. The
app's behaviour when it has no entry is deliberate: `h_retrieve_education` returns an empty
result flagged `nothing_found: True` with an instruction not to answer from general knowledge,
and the medicines page tells the user directly that a medicine not on the list is not guessed
at.

The relevant comparison is not "eight versus a database". It is what the app does with the gap.
A system with a database that is wrong about a drug is worse than a system that declines, because
the wrong answer arrives with the same fluency as the right one.

What would change this: a licensed source register whose purpose matches explanation-only use,
plus review capacity to keep it checked. Not a scraper, and not a larger model.

### Why is there no Bluetooth or device sync?

It is a deliberate cut, recorded as P1 in `docs/PLAN.md` and as out of scope for this round.

The demonstration is a five-minute walkthrough of the main flow. Manual entry keeps that flow
visible end to end: the user types two numbers, sees a draft, confirms it, and the record appears.
With a device in the middle, the same flow depends on a pairing state, a manufacturer's
protocol, and a device that has to be present and charged. That is added risk in the one part of
the demo that cannot fail.

The decision is also honest about what it is not. A blood-pressure monitor with Bluetooth is the
normal way an older adult in Singapore would record a reading, and manual entry is a step
backward from what the hardware already does. The right version of this app reads the cuff. It
just is not the version that can be demonstrated reliably in five days by one person.

### Why is the whole thing in one process with one user session?

It is a prototype, and the session model is cookie-level, not production authentication. There
is no multi-tenancy, no user management, and no claim that the isolation would hold against an
adversary. This is stated in `docs/architecture.md` and in `docs/BUILD_LOG.md` under technical
debt rather than being left for a reviewer to discover.

### Has any of this been tested with real patients, or reviewed by a clinician?

No, on both counts, and neither is claimed anywhere.

No clinician has reviewed the safety rules or the knowledge entries. Every rule and every fact
carries `review_state: team_checked`, which means a team member read the source and recorded it.
It does not mean a clinician reviewed it. This appears in the interface in three places, on the
trace page, and in the seed output, and it is listed as outstanding in
`docs/content-provenance.md` section 6.

No user walkthrough with older adults was run. No clinical validation, real-patient testing, or
hospital, HealthHub or PTEC integration exists. There is no accessibility certification: the
interface was designed against a 19px base font, 48px tap targets and WCAG AA contrast, and it
was not independently audited.

### Has the live model path been run?

No, and this is the most important limitation in the project.

The model endpoint was never exercised. The probe was blocked during the build and was not worked
around. Degraded mode is what the 97 tests cover and what the demonstration will most likely
show. `_live_turn` in `app/llm/orchestrator.py` has been statically reviewed and not run.

This means the following are unverified: whether a configured endpoint supports the
OpenAI-compatible `/v1/chat/completions` format with function calling, whether latency is
acceptable for a conversational turn, and whether tool calls are returned in the shape the
orchestrator expects. It is recorded as the first item on the outstanding list in
`docs/BUILD_LOG.md`.

### Is the CodeBuddy / WorkBuddy evidence requirement satisfied?

No. It is **OUTSTANDING**, and it is a hard submission gate (Handbook p.37). Evidence of at least
three screenshots or recordings showing genuine development in CodeBuddy or WorkBuddy, matching
what the code actually contains, has not been prepared. This is not something the code can
satisfy, and it is recorded in `docs/content-provenance.md` section 6 and in
`docs/BUILD_LOG.md` rather than being left out of the documentation.

---

## Smaller decisions, recorded for completeness

| Decision | Reason | Evidence |
|---|---|---|
| A single OpenAI-compatible wire format for the model | One format the adapter is small enough to audit, and it decouples the app from a vendor | `app/llm/provider.py` |
| A failed model call returns `ok=False` rather than raising | A dead endpoint degrades the app; it does not break it | `LLMResult` in `app/llm/provider.py`; the failure branch in `_live_turn` |
| Statistics thresholds set at 2 readings for a mean and 3 per window for a comparison | An engineering judgement to avoid describing a period from a single reading | `MIN_READINGS_FOR_MEAN`, `MIN_READINGS_PER_WINDOW_FOR_COMPARISON` in `app/stats.py`, marked in the comments as an engineering judgement and not a literature finding |
| Local emergency numbers are shown only when the entry is verified | The most dangerous bug found in the whole build was two templates printing the emergency number when the verification flag was false | Fixed and recorded in `docs/BUILD_LOG.md` phase P5 |
| The user's own words are stored verbatim in barrier records and reproduced on the summary | A concern rewritten into clinical language is no longer the patient's concern | `app/stats.py`, `app/summary.py`; the `reported by the patient` labelling in the summary |
| The visit summary is preview, edit, omit, then print — never sent | The app cannot send anything, and must not appear to | `app/summary.py::apply_omissions`; `docs/PLAN.md` M5 |
| Two held-back safety rules ship disabled rather than deleted | The demo can show a rule that exists and is held back pending confirmation instead of pretending the gap is not there | `redflag_fever_with_confusion`, `boundary_emergency_contact_change` |
| The demo database resets by deleting the file | No migration tooling is needed for fictional data, and a clean demonstration is worth more than persisted state | `make seed`, `make reset`, and `app/db.py::reset_db` |

---

## What all of this costs, in one place

A summary of the deliberate sacrifices, so they are not scattered across the entries above.

| We chose | We gave up |
|---|---|
| One scenario, one population, one health system | Any claim of generality |
| No build step | A component model and template type checking |
| Bare SQL | Migrations and persistence across schema changes |
| One agent | Depth per topic, and any multi-agent story |
| All numbers computed in code | The model's ability to reason about figures flexibly |
| Safety gates before the model | Nuance in edge cases a model would handle better |
| Degraded mode as default | The app looks smaller than the plan describes |
| Eight hand-checked medication-purpose entries (2 named drugs, 5 classes, 1 general) | Coverage of most real antihypertensives |
| Four adherence states, `unrecorded` derived | Any single convenient adherence figure |
| No numeric threshold anywhere | The app cannot tell a user whether a reading is high |
| English only | A large part of the Singapore target population |
| One persona | Breadth of demonstrated cases |

Two of these are time constraints rather than design conclusions, and they should be read that
way: **English only** (D11) and **one persona** (D12). Neither has a technical argument behind it
that would survive a second week. The rest we would defend.

---

## Review status of this document

Written 2026-10-11. Every claim above is checkable in the repository at the paths given. Where a
claim depends on something that has not been verified — the live model endpoint, clinical review,
the CodeBuddy/WorkBuddy evidence requirement, user testing — it is stated as outstanding rather
than omitted.

No decision in this record has been reviewed by a clinician. None of it is clinical advice, and
all patient data referenced here is fictional and labelled `is_simulated`.
