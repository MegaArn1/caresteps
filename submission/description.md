# CareSteps 乐护同行

**Short blurb:** Everyday support for seniors managing blood pressure

**Track:** The Healthcare Track — NTU LKC Medicine
**Challenge:** Statement 2, AI Healthier Every Day: Intelligent Support for Long-Term Self-Care
**Scenario:** Hypertension management for older adults aged 65+

## Project overview

CareSteps is a web-based companion for older adults in Singapore who already have a
diagnosed hypertension care plan. It helps them record blood pressure, understand
confirmed medicines, explain difficulties with treatment routines, and prepare for an
appointment. Family members can help on the same screen.

Its central idea is simple: a missing record is a question. The app does not turn an
empty entry into a missed dose. It asks what got in the way and preserves the person's
own words, with optional category confirmation and support tailored to that reason.

## Scenario insights

The design draws on the challenge scenario and published Singapore patient-education
material, registered with publisher, URL and review state in the source files. There
have been no patient interviews or field trials. The fictional patient, Mdm Tan, takes
two medicines and has incomplete home-reading history. Her example demonstrates how
forgetfulness, equipment difficulty, uncertainty about a medicine and supply concerns
need different next steps.

The interface uses large text, prominent actions, source labels and a text alternative
to the trend chart. Readings follow enter → preview → confirm. Categories are optional;
the person controls which questions appear in the printed appointment summary.

## Solution design and prompts

The application combines FastAPI, server-rendered templates, local JavaScript and SQLite.
A chat turn first passes deterministic red-flag, medication-boundary and clarification
gates. A matching blocking rule returns authored guidance before a language-model call.
Structured form routes validate separately.

For allowed live turns, a system prompt sets the explanation-only role and directs the
model to named tools and source-linked facts. The server supplies compact profile context
and recent messages, executes up to the configured tool-round budget, and checks live
prose for known unsafe phrases and ungrounded numeric tokens. These checks are limited
heuristics. The model cannot issue arbitrary SQL. Reading and medication-report drafts
need user confirmation; scoped barrier, question and preference tools can write directly.

Ten model-visible tools retrieve the plan, admitted education and recent activity,
compute period statistics, prepare records and assemble a visit summary. All statistics
are calculated in code with windows, counts, denominators and missing days. An optional
chat-completions gateway enables live conversation. Without it, local workflows and a
smaller deterministic conversation remain available.

## Value and evidence

The prototype makes adherence barriers visible alongside records and gives the patient a
printable account for a professional discussion. It does not automatically send a report.
Measurable engineering evidence is **171 passing automated tests**, **27 reproducible
routing scenarios**, **10 model-visible tools**, and a fictional 14-day demo with readings
on 10 days. These demonstrate implementation behavior, not reduced blood pressure,
improved adherence or saved consultation time; those outcomes require future study.

WorkBuddy implemented the system-statistics API and deployment guide, with three saved
conversation screenshots. The recorded development workflow is in
[docs/development.md](../docs/development.md). A narrated 7:22 video covers the core
workflows, a recorded live reply, limited mode and development-tool reflection.

This remains a simulated-data competition prototype. It has no clinical validation,
clinical review, accessibility conformance audit or health-system integration. It uses a
shared fictional profile and has no production login. It does not diagnose, prescribe,
identify an unknown tablet or guarantee detection of emergencies.
