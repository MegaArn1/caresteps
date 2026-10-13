# Content provenance

Where every health fact in CareSteps came from, and what we decided not to use.

This document exists because of one question a judge is entitled to ask: when this app tells
an older adult something about their blood pressure, who says so, and how do we know they say
it? Every enabled statement in the app traces to a registered source, and this file is the
record of that trace.

It is evidence for the **Responsible AI** judging dimension. It is written to be checkable
against the repository: the source register is `content/education/sources.json`, the knowledge
base is `content/education/facts.json`, and the audit that rewrote the statements is the
`_audit` block inside that same file.

Two things this document is not. It is not a claim that the content has been clinically
reviewed — it has not (see [Review status](#6-review-status)). And it is not a claim that the
live model endpoint has been exercised — it has not; the evidence here is about content, not
about runtime.

---

## 1. The process

Content did not arrive in one step. It arrived in three passes, and the second and third
passes did most of the work.

### Pass 1 — retrieval of Singapore first-hand sources

Retrieval was scoped before it was run. The population is older adults in Singapore with a
diagnosed hypertension care plan, so the question was not "what does the medical literature
say about blood pressure" but "what do Singapore's own health bodies publish for this
audience".

Sources were restricted to Singapore first-hand publishers:

- Ministry of Health (MOH)
- HealthHub (MOH's public health portal, with articles contributed by the polyclinics and
  the National Heart Centre Singapore)
- SingHealth and SingHealth Polyclinics
- Singapore Heart Foundation
- Singapore Civil Defence Force (for emergency numbers)

This is a deliberate narrowing. An American or European guideline is often better evidenced,
but it is written for a different health system, a different drug formulary, a different
referral route and a different set of emergency numbers. For an app whose entire safety story
ends in "call 995" or "see your GP", a source that does not know what a GP is cannot be the
foundation.

**63 candidate sources were gathered. 32 were rejected.**

The rejections were not about format. They were substantive. The build log records the
category of defect, and it does so for the five highlighted below rather than for all
32 (`docs/BUILD_LOG.md`, phase P7):

| Rejected candidate | Defect |
|---|---|
| `S8-healthhub-amlodipine` | Contains "may be taken with or without food" — administration instruction, not explanation |
| `S2-moh-hbp`, `S4-sgh-gpfirst-hbp` | Contain "continue taking **your usual medicines**" — a medication directive |
| `S4-sgh-gpfirst-hbp` | Claimed to carry a not-medical-advice disclaimer that does not exist on the page (the verifier grepped the HTML and got zero matches) |
| `S6-shf-elderly-bp` | "Quit smoking" is stronger than the page's "Limit the Use of Cigarettes"; and the page's 130/85 figure conflicts with mainstream guidance |
| `S2-healthhub-know-your-medication` | "You may need several medicines" steers toward combination therapy |

A source that is excellent for one purpose and dangerous for another is a normal outcome, not
a reason to discard the publisher. What mattered was recording which purpose we were using it
for.

### Pass 2 — adversarial verification of what we were actually going to ship

The rejected entries above are whole source records. But what ships to a user is not a source
record — it is a sentence. So a second pass ran against the **23 statements we intended to
enable**, one sentence at a time, with the explicit job of finding where the sentence claims
more than its page does.

Four questions were asked of every statement:

1. Does every claim in the sentence actually appear on the cited page?
2. Has a cause, a benefit or a prevalence link been added that the page does not state?
3. Does the sentence contain any instruction to take, continue, stop, skip or double a
   medicine, any administration detail, any steer toward combining medicines, or any numeric
   blood-pressure threshold presented as a judgement?
4. Has anything been imported from an out-of-scope part of the page — dosing, missed doses, or
   a target belonging to a different patient group?

**Result: 10 of the 23 enabled statements were defective and had to be reworded.** Every
defect was the same species of error — we had written a causal link, a frequency or a benefit
into a fact presented as coming from an authority. Four further statements were rewritten for
wording consistency alongside the corrected ones, so **14 statements were rewritten in total**.
**No statement had to be re-sourced, and none had to be removed**; the page behind each one
already supported the corrected sentence.

Each rewrite is recorded in `facts.json` → `_audit.detail`. The cases:

| Statement | What was wrong | What it became |
|---|---|---|
| `edu_class_diuretic_purpose` | Claimed the alias "water tablets", a term the page never uses | The page's own wording, "some common groups of high blood pressure medicines" |
| `edu_class_ccb_purpose`, `edu_class_arb_purpose`, `edu_class_ace_purpose`, `edu_class_betablocker_purpose` | "one of the main groups" — the page says "some common groups" | Wording aligned to the page |
| `edu_multiple_medicines_common` | Asserted prevalence ("it is common to need more than one") and inferred that differing mechanisms are *why* medicines are combined — which also nudged the reader toward combining | States that a person may need more than one type, that the groups work differently, and that the choice is the doctor's |
| `edu_measure_same_time_same_arm` | Added a benefit ("makes a record easier to compare") the page does not give | The page's measurement instruction alone |
| `edu_measure_cuff_size` | Added a mechanism (too small / too large causes inaccurate readings) the page does not state | The page's own instruction to use the correct cuff size |
| `edu_measure_readings_vary` | Added "a series of readings tells your doctor more than any single one", plus the causal link built on it | The page's variation note, plus its own advice to measure at home regularly and record readings for appointments |
| `edu_advice_follow_instruction` | "Blood pressure medicines should be taken..." was an unconditional **take** directive | The decision is attributed to the reader's own doctor or pharmacist; the app offers only the question to ask |
| `edu_advice_ask_pharmacist` | "Bringing your medicines with you" is not on the page | The page's actual claim: keep a written record of your medicines and show it to your doctor |
| `edu_help_often_no_symptoms` | "usually causes no symptoms at all" asserted near-universal absence the page does not claim | The page's "does not often produce symptoms" |
| `edu_help_see_gp_if_persistently_above_usual` | Tied giddiness and headache to a high reading, inventing a coupling that could tell a giddy reader with usual readings not to seek care | Giddiness and headache as standalone reasons to see a GP, plus the page's own severity split routing severe cases to the Emergency Department |
| `edu_help_emergency_signs` | Our broader "sudden change in alertness or consciousness" | The page's own wording, "sudden confusion or disorientation" |

Two notes on the substance of these fixes rather than the bookkeeping.

The `edu_help_see_gp_if_persistently_above_usual` rewrite **closed a safety-routing gap**.
Splitting severe giddiness and severe headache out to the Emergency Department means no other
fact in the knowledge base was left covering those presentations.

The `edu_advice_follow_instruction` rewrite **removed a directive**. The original sentence told
the reader that a blood pressure medicine should be taken in a particular way. That is
medication advice, and Challenge Statement 2 forbids the app from crossing from explanation
into it. The rewritten sentence says the decision belongs to the reader's own doctor or
pharmacist and that this app does not make it.

Honest assessment: had the second pass not run, **10 sentences that read as authoritative and
in fact contained our own inference would have shipped**. A judge who opened one cited URL
would have found the discrepancy.

### Pass 3 — keeping the exclusions visible

Statements that were disabled were not deleted. `edu_numeric_bands_disabled` is retained in
`facts.json` with `enabled:false` and a statement that begins "PLACEHOLDER - NOT SHOWN". The
reason is stated in `_about`: entries that are switched off are kept *so the boundary of what
is covered is visible rather than hidden*. A knowledge base that shows only its successes
cannot show where its edges are.

---

## 2. Registered sources

14 sources are registered in `content/education/sources.json`. All 14 have a publisher, a
title, a URL, a retrieval date, a reuse note and a review state. The loader rejects any source
without a resolvable-looking URL and a retrieval date (`app/content_loader.py`,
`validate_source`), and rejects any fact whose `source_id` is not in this register
(`validate_fact`) — a fact without provenance cannot load.

All 14 were retrieved on **2026-10-11**.

| id | Publisher | Title | URL | Retrieved | Review state |
|---|---|---|---|---|---|
| `S1-healthhub-hf-bp-monitoring` | HealthHub (MOH, Singapore), contributed by NHCS | Monitoring Weight and Blood Pressure | https://www.healthhub.sg/health-conditions/heart-failure-monitoring-weight-and-blood-pressure | 2026-10-11 | team_checked |
| `S1-scdf-ems` | Singapore Civil Defence Force | Emergency Medical Services | https://www.scdf.gov.sg/home/about-scdf/emergency-medical-services | 2026-10-11 | team_checked |
| `S2-healthhub-bp-medication` | HealthHub, MOH Singapore (article contributed by NHG Polyclinics) | High Blood Pressure: Medication | https://www.healthhub.sg/health-conditions/high-blood-pressure-medicines | 2026-10-11 | team_checked |
| `S2-moh-hbp` | Ministry of Health, Singapore | High blood pressure | https://www.moh.gov.sg/seeking-healthcare/getting-medical-help/conditions/high-blood-pressure/ | 2026-10-11 | team_checked |
| `S2b-healthhub-know-your-medication` | HealthHub, MOH Singapore | Understand Your Medication for Chronic Illness | https://www.healthhub.sg/well-being-and-lifestyle/personal-care/know-your-medication | 2026-10-11 | team_checked |
| `S2b-singhealth-polyclinics-telemonitoring` | SingHealth Polyclinics | Manage Your Blood Pressure Through Telemonitoring | https://www.singhealth.com.sg/news/shp-pop/we-advance-take-charge-of-your-blood-pressure-through-telemonitoring | 2026-10-11 | team_checked |
| `S3-healthhub-hypertension-hub` | HealthHub, MOH Singapore | Hypertension | https://www.healthhub.sg/health-conditions/hypertension | 2026-10-11 | team_checked |
| `S3-moh-ed` | Ministry of Health, Singapore | When to visit the hospital for emergencies | https://www.moh.gov.sg/seeking-healthcare/getting-medical-help/visiting-the-hospital-for-emergencies/ | 2026-10-11 | team_checked |
| `S4-healthhub-5-ways-lower-bp` | HealthHub (MOH Singapore), contributed by the National Heart Centre Singapore | 5 Ways to Lower Your High Blood Pressure Without the Help of Medicine | https://www.healthhub.sg/health-conditions/5-ways-to-lower-your-high-blood-pressure-without-the-help-of-medicine | 2026-10-11 | team_checked |
| `S4-sgh-gpfirst-hbp` | SingHealth, GPFirst programme | Hypertension - What is GPFirst? | https://www.singhealth.com.sg/community-care/find-resources-in-your-community/what-is-gpfirst/conditions-your-gp-can-treat/hypertension | 2026-10-11 | team_checked |
| `S4a-healthhub-amlodipine` | HealthHub (MOH, Singapore) | Amlodipine (patient information leaflet) | https://www.healthhub.sg/medication-devices-and-treatment/medications/amlodipine | 2026-10-11 | team_checked |
| `S4b-healthhub-losartan` | HealthHub (MOH, Singapore) | Losartan (patient information leaflet) | https://www.healthhub.sg/medication-devices-and-treatment/medications/losartan | 2026-10-11 | team_checked |
| `S5-singhealth-hypertension-management` | SingHealth (Singapore Health Services) | High Blood Pressure (Hypertension) Management | https://www.singhealth.com.sg/symptoms-treatments/high-blood-pressure-hypertension-management | 2026-10-11 | team_checked |
| `S6-shf-elderly-bp` | Singapore Heart Foundation | Normal Blood Pressure: Guidelines for the Elderly | https://www.myheart.org.sg/heart-news/blood-pressure-for-elderly/ | 2026-10-11 | team_checked |

Three of these carry scope limits recorded in their `reuse_note`, and the limits are part of the
provenance rather than a footnote:

- **`S2b-healthhub-know-your-medication` is not independent corroboration of
  `S2-healthhub-bp-medication`.** Both are HealthHub / MOH publications with near-identical
  drug-class content. This source is never counted as second corroboration of anything the
  other says; it is cited only for what it says in its own right.
- **`S6-shf-elderly-bp` must never be cited for smoking claims.** Its only smoking content is
  the treatment step "Limit the Use of Cigarettes". It does not state that quitting lowers
  blood pressure.
- **`S1-healthhub-hf-bp-monitoring` carries a 130/80 target belonging to a heart-failure
  population.** That number is not imported anywhere.

Three registered sources are not cited by any enabled fact: `S1-scdf-ems` (the 995 emergency
number, which is consumed by the emergency configuration rather than by an education fact),
`S3-healthhub-hypertension-hub` (registered, but cited by no fact at all — not even a disabled
one), and `S5-singhealth-hypertension-management` (cited only by the disabled numeric-bands
entry). They are listed here because the register is the register.

### Attribution corrections

On 2026-10-11 an attribution audit corrected two publisher credits in the register. The earlier
version credited `S2-healthhub-bp-medication` to the Health Promotion Board; the page's own
footer reads "(c) 2026 Ministry of Health Singapore" and the article is contributed by NHG
Polyclinics. The same audit reviewed `S3-healthhub-hypertension-hub`, whose reuse note still
carries an unreconciled "MOH/HPB" credit — that one has not yet been checked against the page
footer and should be before submission. A wrong publisher in a provenance file is exactly the
kind of error this file exists to prevent, so it is recorded rather than quietly tidied.

---

## 3. The enabled facts

23 of the 24 entries in `content/education/facts.json` are enabled. Each carries an `id`, a
`topic`, a `statement`, an `applies_to` scope, a `review_state` and the `source_id` it came
from. Seven also carry a `subject`, which is the drug class or drug the statement is about;
the measurement and routing facts leave it empty.

The statement column below is the shipped text, copied from the file.

| fact id | Topic | Statement | Source id |
|---|---|---|---|
| `edu_amlodipine_purpose` | medication_purpose | Amlodipine is a blood pressure medicine. It works by relaxing and widening your blood vessels, which brings your blood pressure down. | `S4a-healthhub-amlodipine` |
| `edu_losartan_purpose` | medication_purpose | Losartan is a blood pressure medicine. It blocks the action of a substance called angiotensin II, which normally makes your blood vessels narrower. Blocking it lets the vessels widen and your blood pressure come down. | `S4b-healthhub-losartan` |
| `edu_class_ccb_purpose` | medication_purpose | Calcium channel blockers are one of the common groups of blood pressure medicines. They stop calcium from entering the muscle cells of the heart and blood vessels, so the vessels relax and widen. | `S2-healthhub-bp-medication` |
| `edu_class_arb_purpose` | medication_purpose | ARBs, or angiotensin II receptor blockers, are one of the common groups of blood pressure medicines. They block angiotensin II at the blood vessel wall so the vessels do not narrow. | `S2-healthhub-bp-medication` |
| `edu_class_ace_purpose` | medication_purpose | ACE inhibitors are one of the common groups of blood pressure medicines. They stop the body from making angiotensin II, a substance that normally makes blood vessels narrow. | `S2-healthhub-bp-medication` |
| `edu_class_diuretic_purpose` | medication_purpose | Diuretics are one of the common groups of blood pressure medicines. They help your body get rid of excess water and salt. | `S2-healthhub-bp-medication` |
| `edu_class_betablocker_purpose` | medication_purpose | Beta blockers are one of the common groups of blood pressure medicines. They slow your heart rate and reduce how much blood your heart pumps out. | `S2-healthhub-bp-medication` |
| `edu_multiple_medicines_common` | medication_purpose | There are many types of medicine that help to lower blood pressure, and you may need more than one type to keep your condition under control. The different groups work in different ways. Which medicines you take is decided by your doctor. | `S2-healthhub-bp-medication` |
| `edu_measure_same_time_same_arm` | how_to_measure | Measure your blood pressure at about the same time every day, using the same arm. | `S1-healthhub-hf-bp-monitoring` |
| `edu_measure_cuff_size` | how_to_measure | Use the correct cuff size for accurate readings. | `S1-healthhub-hf-bp-monitoring` |
| `edu_measure_before_coffee` | how_to_measure | Avoid coffee, cigarettes and hard exercise for 30 minutes before you measure. | `S1-healthhub-hf-bp-monitoring` |
| `edu_measure_sitting_position` | how_to_measure | Sit upright with your back supported and both feet flat on the ground. Rest your forearm on a table with the palm facing up, and keep the cuff level with your heart. | `S1-healthhub-hf-bp-monitoring` |
| `edu_measure_high_reading_repeat` | how_to_measure | If a reading seems high, rest for five minutes and measure again. If it is still high after repeating it three times, contact your nurse, doctor or case manager. | `S1-healthhub-hf-bp-monitoring` |
| `edu_measure_which_number_is_which` | how_to_measure | The top number, the systolic, is the pressure when your heart contracts. The bottom number, the diastolic, is the pressure when your heart relaxes between beats. | `S1-healthhub-hf-bp-monitoring` |
| `edu_measure_readings_vary` | how_to_measure | A blood pressure reading varies with what you are doing — your body position, breathing, emotional state, exercise and sleep. That is normal. It is worth measuring your blood pressure at home regularly and recording the readings for your doctor's appointments. | `S6-shf-elderly-bp` |
| `edu_advice_follow_instruction` | adherence_support | How a blood pressure medicine is taken is decided by your own doctor or pharmacist, not by this app. Where anything about your medicine is unclear to you, that is a good thing to ask them about. | `S2-healthhub-bp-medication` |
| `edu_advice_ask_pharmacist` | adherence_support | It is reasonable to ask your pharmacist or doctor anything you are unsure about, including what a medicine is for and why you are taking it. Keeping a written record of your medicines can help you tell your doctor what you are taking. | `S2b-healthhub-know-your-medication` |
| `edu_advice_lifestyle_general` | adherence_support | General measures that support blood pressure management include reducing salt, staying active, keeping a healthy weight, not smoking, and managing stress. For most people treatment is long-term. | `S4-healthhub-5-ways-lower-bp` |
| `edu_help_often_no_symptoms` | when_to_seek_help | High blood pressure often causes no noticeable symptoms, which is why it is sometimes called a silent condition. Feeling fine is not evidence that your blood pressure is fine, and this is exactly why keeping a record matters. | `S2b-singhealth-polyclinics-telemonitoring` |
| `edu_help_see_gp_if_persistently_above_usual` | when_to_seek_help | See your GP if your blood pressure readings are consistently higher than your usual. See your GP also if you have giddiness or a headache — but severe giddiness or a severe headache needs the Emergency Department instead. | `S4-sgh-gpfirst-hbp` |
| `edu_help_ed_symptoms` | when_to_seek_help | Go to the Emergency Department if you develop weakness or numbness, difficulty seeing, difficulty speaking or difficulty walking. These need to be checked urgently. | `S2-moh-hbp` |
| `edu_help_emergency_signs` | when_to_seek_help | Signs of a medical emergency include sudden or severe pain, including chest pain, difficulty breathing or shortness of breath, uncontrolled bleeding, and sudden confusion or disorientation. | `S3-moh-ed` |
| `edu_help_annual_review` | when_to_seek_help | High blood pressure should be reviewed by a doctor at least once a year, and more often for some people. | `S4-healthhub-5-ways-lower-bp` |

Distribution by topic: 8 medication_purpose, 7 how_to_measure, 5 when_to_seek_help,
3 adherence_support.

One entry is **disabled** and is not shown anywhere in the interface:
`edu_numeric_bands_disabled`, on the SingHealth grading table. See §5.

---

## 4. How this differs from a scraper

The distinction matters because the two approaches can produce a file that looks identical
from the outside.

**What we did not do:** we did not crawl the pages, extract their text, and put it into a
retrieval index or a knowledge base. No part of CareSteps reproduces the body text of any
cited page.

**What we did instead:** each of the 23 enabled entries is **our own short paraphrase of a
specific section** of one page. The `_why_paraphrase` note in `facts.json` states the rule in
one line: *citing a source is not the same as being allowed to reproduce it.* The section we
used is recorded in the source's `reuse_note` rather than as a per-fact field — an entry points
at a whole source, not at a page anchor, and the reuse note is what narrows it.

The practical differences:

| | Scraper | What this project does |
|---|---|---|
| Unit | The page | A specific section of a page |
| Text | Copied, then possibly truncated | Rewritten by us, then checked against the page |
| Source visibility | Implicit in the index | The URL is shown to the user beside the statement |
| Failure mode | Copies out-of-scope content silently | Out-of-scope sections are named and excluded |
| Copyright position | Reproduction with attribution | Paraphrase with attribution |

Two points follow from this.

**The URL is shown to the user beside the statement.** This is not decoration. It means a
reader — or a judge — can go and read the original and decide for themselves whether our
paraphrase is fair. Attribution that the reader cannot inspect is a claim, not evidence.

**A publicly readable page is not a page we may copy.** That a page loads in a browser without
a paywall says nothing about the terms it is published under. HealthHub, MOH and SingHealth
pages are published under Crown/publisher copyright, and they are written to be read — not
republished as another product's content layer. We paraphrase, we credit the publisher by name,
we link to the original, and we do not present any of it as our own work or as medical advice.

The same logic applies at a finer grain. It is not enough that the *source* is appropriate; the
*sentence* has to be appropriate. That is why pass 2 in §1 examined 23 sentences individually
rather than trusting 14 source records.

---

## 5. Things deliberately NOT included, and why

This is the most important section in the document. What a health app refuses to say is a
stronger signal about its judgement than what it does say, and an app that will answer anything
is not a careful app — it is an unguarded one.

### 5.1 Any numeric blood-pressure threshold

**MOH and HealthHub publish no numeric blood-pressure threshold for calling an ambulance.** We
searched for one and did not find one. Other jurisdictions do publish such a figure; the
Singapore sources this app is built on do not.

Therefore the app states no threshold, anywhere. No rule in `content/rules/` keys on a
blood-pressure number, and no enabled fact states a cut-off. (The rules directory does contain
numbers — 995 and the other emergency contacts, and version years. The claim here is about
numeric *blood-pressure* thresholds, and there is none.) Inventing 180/120 because other
sources use it would be a fabrication with real consequences for a real reader.

This is enforced by tests rather than by good intentions:

| Test | What it enforces |
|---|---|
| `tests/test_safety.py::TestRuleIntegrity::test_no_numeric_threshold_is_used_as_a_trigger` | No rule pattern may match an `NNN/NN` form. A rule keyed to a number cannot be added. |
| `tests/test_safety.py::TestEmergencyConfig::test_no_blood_pressure_threshold_in_emergency_config` | Walks the whole emergency config tree, including nested strings, so a threshold cannot be added anywhere without the test noticing. |
| `tests/test_data_integrity.py::TestKnowledgeBase::test_no_numeric_threshold_in_enabled_content` | Scans the `when_to_seek_help` and `how_to_measure` statements. If our own content has no threshold, the app cannot leak one by retrieval. |

The consequence is stated plainly in `content/rules/redflags.json`: *a very high reading with no
symptoms does not trigger this gate; the app reports the number and its source without
interpreting it.* The app is designed to not classify a reading as good or bad.

### 5.2 Dosing, missed-dose, switching, stopping, storage and administration

All of these appear on the very pages we cite. HealthHub publishes patient information leaflets
that include dosing, missed-dose and side-effect sections; we paraphrase the "what is this
medication for" section and leave the rest on the page.

The clearest example is `S4a-healthhub-amlodipine`. Its reuse note reads: *the dosing,
missed-dose and side-effect sections of the same page are deliberately NOT used.*

The general principle is this: **a page can be a fine source for a mechanism and a terrible
source for advice.** "This medicine relaxes your blood vessels" is an explanation of how a
drug works. "Take it at the same time each day, and if you forget a dose take it as soon as you
remember unless it is nearly time for the next one" is a clinical instruction that depends on
which drug, which dose, what else the person takes, and how their kidneys are doing. The first
belongs to a patient-education explanation. The second does not belong to an app with no
clinician behind it.

This exclusion is implemented in two places, and neither is the content file:

- **The content layer** carries no dosing statement, because none was written.
- **The safety layer** refuses them at runtime. `content/rules/boundaries.json` contains
  enabled boundary rules including `boundary_change_dose`, `boundary_stop_medication`,
  `boundary_start_new`, `boundary_missed_dose`, `boundary_pill_identification`,
  `boundary_diagnosis_request`, `boundary_side_effect_causation` and
  `boundary_share_without_consent`. Each carries a `reason`. The missed-dose rule reads: *catch-up
  dosing is medicine-specific and time-specific; giving generic advice here is how apps cause
  harm.*

The two layers are deliberate. Content absence means we never chose to say it. Boundary rules
mean that when a user *asks*, the app routes the question to a professional rather than
declining with a shrug.

The boundary rules are also subject to the no-citation-no-rule rule: `app/safety/rules.py`
drops any rule that declares no source and records a load problem, so *there is no way to ship
an uncited threshold.*

### 5.3 Side-effect rates and percentages

No side-effect percentage appears in the app. Cards like "about 1 in 10 people experience..."
are common in consumer health products and none of them is here.

The reason is sourcing, not squeamishness. **No Singapore source in our register was verified to
state side-effect rates** for the drugs we explain. A rate is a number a reader will act on, and
we could not point at a Singapore page carrying it. Without one, the honest options were to omit
the number or to import a figure from elsewhere — and importing it would have been a second
context error on top of a sourcing one.

A reader who asks about side effects is routed by `boundary_side_effect_causation`, whose stated
reason is that establishing causation between a drug and a symptom is a clinical assessment.

### 5.4 The 130/85 "normal" figure

`S6-shf-elderly-bp` carries a 130/85 figure (and a 120/80 figure for people with diabetes or
kidney disease). Its reuse note records: *none of that is imported into any fact.*

The decision not to surface it is a judgement about classification rather than about the source.
**Guideline bodies disagree about where "normal" begins**, and the disagreement is widest around
older adults — which is precisely this app's population. Surfacing one body's figure as a
universal cutoff would tell a large number of people with readings above 130/85 that they are
outside "normal" on the authority of a number that another guideline body would dispute.

The failure mode is asymmetric. An older adult who sees "normal is below 130/85" beside their
own 138/86 may become anxious about a reading no clinician has assessed; or the opposite, they
may treat a single number as a diagnosis. Either way the app has made a clinical statement. It
does not.

This is the same reasoning that disables the SingHealth grading table. That entry,
`edu_numeric_bands_disabled`, records the position directly: *a prototype that tells an older
adult their reading is "grade 1 hypertension" is making a clinical statement, and an untrained
user reading a grade against a single home measurement is likely to misunderstand it.* The bands
exist in the file only as a reference for builders, are marked "PLACEHOLDER - NOT SHOWN", and
are disabled. A test asserts no enabled fact contains placeholder text
(`test_placeholder_cannot_ship_enabled`), so this entry cannot be switched on by accident.

### 5.5 MIMIC-III and similar clinical datasets

No MIMIC-III or comparable de-identified clinical dataset is used anywhere in this project. The
only mentions of one in the repository are the discussions of why it was not used (`decisions.md`,
and this section); no code, content file or test reads one, and none is a dependency. This is a
category exclusion rather than a record of a rejected candidate, and it is stated here so the
absence is visible rather than assumed.

The reasons are three, and any one of them is sufficient:

1. **Different population.** MIMIC-type data comes from intensive-care and hospital admissions.
   The people this app is for are community-dwelling older adults managing a diagnosed
   condition at home. A distribution learned from one population does not transfer to the
   other, and blood-pressure behaviour in particular does not.
2. **Different task.** These datasets are built for clinical research and model development, not
   for generating patient-facing explanation text. Using one to produce sentences a 72-year-old
   reads at home would be a use the data was not collected for.
3. **Governance.** Such datasets are de-identified but still real patients' records, released
   under data use agreements that govern what may be derived from them and how it may be
   presented. A competition prototype has no basis for that use.

All patient data in this repository is **fictional**. The demo patient, Mdm Tan, is a
constructed character, and the seed data is labelled `is_simulated` on every table that holds
patient records, so that synthetic records cannot be mistaken for real ones. The three tables
that do not carry the flag — `education_fact`, `conversation_message` and `audit_event` — hold
no patient data: they are the knowledge base, the transcript, and the audit trail.

### 5.6 Drug-class taxonomy presented as exhaustive

`S2-healthhub-bp-medication` says "some common groups of high blood pressure medicines". Our
original wording said "one of the main groups" for the five class statements.

That is a small edit with a real reason. "Main groups" implies a closed and ranked set with a
defined membership; "some common groups" is what the page actually claims. For a reader trying
to place their own medicine in a taxonomy, the difference is whether the app has told them their
medicine is one of the important ones, or has described a subset. The first is a claim about
their treatment. The second is a description of a page.

The five class statements — calcium channel blocker, ARB, ACE inhibitor, diuretic, beta blocker
— were rewritten together so the wording matches across all of them.

### 5.7 Two further things that did not make it

- **The "water tablets" alias for diuretics.** The cited page never uses the term. Our statement
  did, which made a colloquialism look sourced. Removed.
- **The "not smoking" claim on `S6-shf-elderly-bp`.** The lifestyle statement in the enabled
  facts is cited to `S4-healthhub-5-ways-lower-bp`, not to the Singapore Heart Foundation page,
  because that page does not state that quitting smoking lowers blood pressure. The attribution
  audit checked this specifically and found no enabled statement credits the SHF page with
  quit-smoking language.

---

## 6. Review status

**Every source record and every fact in this app has a `review_state` of `team_checked`. No
clinician has reviewed any content.**

That is the whole of it, and it should be read as narrowly as it is written.

**What `team_checked` means.** A member of the CareSteps team read the page, paraphrased a
specific section of it in their own words, recorded the publisher, URL and retrieval date, and
re-checked the shipped sentence against the page in the adversarial pass described in §1. It is
a statement about **provenance and wording** — that a sentence says what a located page says,
and does not say more.

**What `team_checked` does not mean.** It does not mean the content is medically correct,
complete, appropriate for any individual, or current. The team has no clinical training. Nobody
qualified has checked whether these are the right things to tell an older adult with
hypertension, whether the omissions are safe, or whether the routing thresholds in
`edu_measure_high_reading_repeat` — rest five minutes, repeat, contact a professional after
three still-high readings — are sensible.

Note that `edu_measure_high_reading_repeat` is a case in point. It is sourced, but the number
"three" is an instruction carried across from the page, not a clinical judgement we are
qualified to have made. We cite it; we do not defend it.

The same applies to the safety rules. The build log records it as a known limitation: every
*enabled* rule's `review_state` is `team_checked` and **none has been reviewed by a
clinician**. (Two rules are disabled and carry `pending_review` rather than `team_checked`:
`boundary_emergency_contact_change` and `redflag_fever_with_confusion`.) This is stated in
three places in the product — `/trace`, the README, and seed output — rather than left for a
reader to discover.

Related limitations, all of which are load-bearing for how much this provenance file is worth:

| Limitation | Status |
|---|---|
| Clinical review | None. Not done at any stage. |
| Real-patient testing | None. The demo patient is fictional. |
| User walkthrough with older adults | Not done. The plan suggested 3–5 participants; no resources this round. |
| Live model endpoint exercised | Not done. The endpoint probe was blocked; degraded mode is tested, the live path is statically reviewed only. |
| Accessibility certification | None. The interface was designed for large type, 48px touch targets and WCAG AA contrast, but no independent conformance audit has been performed. |
| Clinical validation of any kind | None. There is no clinical validation, no clinical review, and no real-patient testing behind any statement in this app. |
| HealthHub / hospital / PTEC integration | None exists. |
| CodeBuddy / WorkBuddy evidence | **OUTSTANDING.** This is a hard submission gate (Handbook p.37) and is not yet satisfied. Evidence of at least three screenshots or recordings is required and has not been prepared. |

A `review_state` vocabulary exists in the schema that distinguishes `verified_by_user`,
`verified_by_team` and `reviewed_by_clinician` as three separate columns — the three statuses
are structurally incapable of being merged or blurred in the database. The third column being
empty everywhere is the honest state of this project.

---

## 7. Reuse and attribution

Content in this app is derived from pages published by:

| Publisher | Content used here |
|---|---|
| Ministry of Health, Singapore | High blood pressure; emergency visiting guidance |
| HealthHub (MOH) | Medication and condition articles; amlodipine and losartan patient information leaflet "what is this medication for" sections |
| SingHealth / SingHealth Polyclinics | Hypertension management; GPFirst hypertension; telemonitoring |
| Singapore Heart Foundation | Blood-pressure variation note; home measurement advice |
| Singapore Civil Defence Force | Emergency medical services number |

**All of this content is published under the respective publishers' copyright.** The reuse
notes in `sources.json` record this per source; the HealthHub footer text, for example, reads
"(c) 2026 Ministry of Health Singapore".

What we do with it:

- **We paraphrase.** Each enabled statement is a short summary, in our own words, of a
  specific section of a specific page. We do not reproduce page text, whole or in part.
- **We attribute.** The publisher and the URL are shown to the user alongside the statement.
- **We link.** A reader can open the original rather than trust our summary.
- **We do not present it as advice.** No fact is framed as advice for the reader. The app states
  what a source says and who says it.
- **We do not silently drop a source's own warnings.** Where a source carries a
  not-medical-advice disclaimer — as `S5-singhealth-hypertension-management` does — that is
  recorded in its `reuse_note`. The app's own disclaimers are its own words rather than the
  publisher's: the visit summary prints a fixed CareSteps disclaimer, not the wording of any
  cited page.
- **Emergency numbers** are quoted as facts with attribution to SCDF.

Original work in this repository — the application code, the safety architecture, the
deterministic statistics and summary layers, the provenance and audit process — is the CareSteps
team's own. The README's licence section states the same split.

If any publisher considers a paraphrase here to misrepresent their page, the fix is a wording
change or a removal, and this file is the record of which statement to change and which page to
check it against.

---

## 8. How to check this document

Nothing above should be taken on trust. The artefacts are in the repository.

| Claim | Where to check it |
|---|---|
| 14 sources, with publishers, URLs, dates and review states | `content/education/sources.json` |
| 23 enabled facts and their source ids | `content/education/facts.json` |
| The audit, the 14 rewrites and the reason for each | `facts.json` → `_audit` |
| The 63 candidates and the 32 rejections, with the defect named for six of them | `docs/BUILD_LOG.md`, phase P7 |
| No numeric threshold in any rule or config | `tests/test_safety.py`; run `make test` |
| No numeric threshold in enabled content | `tests/test_data_integrity.py` |
| Uncited rules cannot load | `app/safety/rules.py`; `content/rules/boundaries.json` |
| Uncited facts cannot load | `app/content_loader.py`, `validate_fact` / `validate_source` |
| The disabled grading-table entry | `facts.json` → `edu_numeric_bands_disabled` |
| No clinical review anywhere | `review_state` fields in `content/education/*.json` and `content/rules/*.json`; every enabled entry reads `team_checked` |

The automated test suite is 165 tests, covering data integrity, safety boundaries, statistics
and summary behaviour, the degraded conversation layer, and the demo flows. All 165 pass. That figure and the ones in this document come from
`docs/BUILD_LOG.md` and from test output; no other numbers about this project's coverage or
performance are asserted anywhere.

---

*All patient data referenced in this document and in the application is fictional and labelled
`is_simulated`. CareSteps is a competition prototype, not a medical device, and has not been
clinically reviewed or clinically validated.*
