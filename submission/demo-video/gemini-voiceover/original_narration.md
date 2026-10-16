# CareSteps demo narration

English narration and subtitles accompany the real browser recording. All patients shown are fictional. The live model turn and limited-mode fallback are recorded from separate local demo databases.

## CareSteps

CareSteps is a competition prototype for older adults managing an existing blood pressure care plan in Singapore. This is a fictional patient, Mdm Tan. The app is not a medical service.

## Everyday support

The home screen keeps the daily actions close: record a reading, check medicines, or explain what made self care difficult. The red help bar stays available across pages.

## Record a reading

I will record a blood pressure reading. Only the two numbers are required; the measurement time defaults to now. The page states that nothing has been saved yet.

## Enter 145 over 88

Here I enter one hundred forty five over eighty eight from the fictional home monitor. Optional fields can record a pulse or the patient's own words.

## Check before saving

The first action prepares a draft and shows both numbers again. It has not written a reading. This explicit check helps catch a typing mistake before the record changes.

## Saved to history

Now I confirm the draft. The reading appears in history with its measurement time. Earlier corrected rows remain visible, while statistics count only current readings.

## Numbers with context

My numbers shows a fourteen day window and the exact number of current readings used for each average. It does not classify any single measurement as safe or dangerous.

## Gaps stay visible

The chart stops at gaps instead of drawing a reassuring line across missing days. A gap means there is no record; it cannot tell us whether a measurement was missed.

## Accessible data list

I can expand the list to inspect each day, including those with no reading. The text table carries the same values as the chart for people who do not use graphics.

## Ask what got in the way

The distinctive feature begins here. Rather than calling a missing record noncompliance, CareSteps asks what was difficult. The person may describe it, select a category, or skip the question.

## No forced category

I write that the cuff is difficult to use and leave every category unselected. The next page explicitly says no reason has been given a name yet. The patient's words remain intact.

## Confirm the reason

Only after I choose a category does the app treat that reason as confirmed. A suggestion from a model would remain a suggestion until the person confirms or changes it.

## Matching support

This page offers a different next step for a difficulty using equipment than it would for forgetting or running out of medicine. A support choice never changes a prescription.

## Medicine information

The medicine page lists the two fictional prescribed items. Each explanation is linked to a recorded source, and this prototype cannot decide a dose or change what a clinician prescribed.

## Source and review state

Notice the publisher, source link, and review status. These entries were checked by the team and have not received clinical review. That distinction appears where the explanation is displayed.

## Assistant in the app

The live assistant is available directly on the home page. I will ask one ordinary medicine question, then test a question it must refuse and a symptom that needs emergency routing.

## Ask about amlodipine

I ask what amlodipine is for. The app sends the question to its configured model and makes source retrieval available as a tool. We will inspect the actual reply.

## Model answer

The model explains the medicine using a recorded Singapore health source, and the chat labels the answer as coming from the assistant. The trace page will show the underlying tool calls and their results.

## Medication boundary

Now I ask whether to double a dose. The deterministic safety boundary refuses to make that medication decision. It offers a way to raise the question with a doctor instead.

## Chest pain: safety first

The words I have chest pain trigger the safety rules before any model request. The red answer points to the Singapore emergency ambulance number, nine nine five. The app has not called anyone.

## Help is explicit

The dedicated help page repeats the verified contact route and states what the app has not done. This is guidance to seek help, not a diagnosis or a monitoring service.

## Inspect the system

The trace page reports the current configuration: whether live model calls are attempted, which model is named, and a fingerprint for the prompts. It never displays an API key.

## Rules before model

Safety and boundary rules run before the language model. The rule set shows twenty one enabled rules and two held for review. That is a limited, inspectable set, not clinical validation.

## Auditable tool calls

The session log records routing decisions and tool call outcomes, including an unsuccessful call if one occurred. It is evidence of system actions, not a view into private model reasoning.

## Limited mode

Here is the same app deliberately running without model access. The visible banner says limited mode. Recording, trends, visit preparation and the fixed emergency path remain available.

## Honest fallback

The fallback answers through a small deterministic router. Where it cannot explain a free text question, it says so. The safety gate still works even with no language model.

## Appointment preparation

Back in the live instance, the appointment page assembles a fourteen day summary from stored facts. Nothing here books a visit, contacts a clinic, or sends a document.

## Context for every number

The summary includes coverage and blood pressure counts with the period they describe. A corrected entry is tracked without double counting. Missing days remain visible rather than becoming an invented zero.

## Medication records

The medication section distinguishes four states, including no record at all. That last state cannot be called a missed dose. These are descriptions of what was recorded, not treatment advice.

## Questions for the visit

The patient can bring questions and reported difficulties into the appointment. The summary separates their words from the app's calculated facts, keeping the provenance of each claim clear.

## Patient controls the page

I can leave questions out of the printed document. The control changes to put back in the summary, so this choice is reversible. It does not delete the underlying patient record.

## Print-ready result

This is the print view the user can save as a PDF or carry into the visit. It keeps the time window and caveats. It has never been automatically shared.

## WorkBuddy build evidence

For the build workflow, we used WorkBuddy on bounded tasks. The saved development conversation shows its implementation of a system statistics endpoint and a single instance deployment guide, alongside a sample API result.

## What we learned

A practical tool tip is to give the agent a small deliverable and an observable check, then inspect the changed files and run tests. An AI tool response alone is not verification.

## Limits and next steps

CareSteps remains a prototype with simulated records. The health content has not been clinically reviewed, the app has no hospital integration or real authentication, and the rules cannot guarantee detection of every emergency.
