# CareSteps design decisions

These decisions describe the release implementation. Detailed historical plans and
agent working notes are retained locally; the Git history retains development authorship.

| Decision | Reason and practical cost |
|---|---|
| Support adults 65+ with an existing hypertension care plan | Keeps the prototype focused; it does not diagnose or create a treatment plan. |
| Treat missing records as unknown | An empty cell cannot prove a missed dose or measurement; ask about barriers instead. |
| Preserve the person's original barrier wording | A category is optional and must remain separate from their words. |
| Use deterministic safety routing before a chat model | Known matches return fixed replies promptly; pattern coverage remains limited. |
| Explain confirmed medicines using an admitted local corpus | Avoid guessing a tablet's identity or changing medication; broader questions may be declined. |
| Compute statistics in Python | Keep denominators, corrections and missing days reproducible; do not delegate arithmetic to prose generation. |
| Confirm readings and medication reports before saving | Allows a final value check; scoped questions, barriers and preferences can write directly. |
| Keep model access optional | Local data workflows remain available; deterministic conversation covers fewer intents. |
| Use FastAPI, templates and SQLite in one process | Simple deployment and testing; requires a single instance and durable disk for persistence. |
| Use a shared fictional profile for the demo | Low setup burden for judges; no claim of production patient isolation. |
| Let the patient control the printed summary | Omission is reversible and no report is automatically sent. |
| State evidence and limits precisely | Software tests and team source checks are not clinical or accessibility validation. |

Development-tool contributions are recorded in [development.md](development.md).
See [architecture](architecture.md) for the corresponding mechanisms and
[evaluation](evaluation.md) for reproducible checks.
