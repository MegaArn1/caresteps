# CareSteps 乐护同行

**Everyday support for seniors managing blood pressure**

An AI health companion prototype for older adults (65+) in Singapore who already have a
diagnosed hypertension care plan. It helps them record readings, understand their medicines,
say *why* something was hard to do, and walk into their next appointment prepared.

> Competition entry — **Tencent Cloud AI Singapore Hackathon 2026**
> Track 6: The Healthcare Track (NTU LKC Medicine) — **Challenge Statement 2**
> "AI Healthier Every Day: Intelligent Support for Long-Term Self-Care"
> Scenario: Hypertension Management for Older Adults (Age 65+)

---

## ⚠️ Prototype status — read this first

This is a **competition prototype**. It is not a medical device.

- All patient data in this repository is **fictional** and clearly labelled `is_simulated`.
- The app **does not diagnose**, does not change prescriptions, and **never crosses from
  explanation into medication advice** — a hard requirement of Challenge 2.
- Nothing here has been clinically validated. No clinical review has been completed.
- No hospital, HealthHub, or PTEC system integration exists.
- The app is **not** a monitoring or emergency service.

Health education content is a small, hand-checked set of entries. Every entry carries its
publisher, URL, retrieval date, and review status. Where the knowledge base has no entry,
the app **says so and declines** rather than guessing.

---

## Quick start

```bash
make setup     # create .venv and install 5 dependencies
make seed      # load the fictional demo patient and 14 days of history
make run       # serve at http://127.0.0.1:8000
```

Then open <http://127.0.0.1:8000>.

No API key is required to explore everything. Without a model configured the app runs in
**degraded mode**: recording, viewing, statistics, summaries and the emergency-help path all
still work; the conversational layer falls back to scripted deterministic dialogue and says
plainly that explanation is unavailable.

### With a model

```bash
export LLM_BASE_URL="https://your-endpoint/v1"
export LLM_API_KEY="sk-..."
export LLM_MODEL="your-model"
make run

```

`LLM_BASE_URL` must be an **OpenAI-compatible** `/v1/chat/completions` endpoint that supports
function calling. See [`docs/architecture.md`](docs/architecture.md).

### Reset

```bash
make seed       # wipes caresteps.db and reloads fictional data
```

---

## What it actually does

| Module | Capability |
|---|---|
| M0 Profile & care plan | Shows the existing plan, each item tagged with its **source** and **verification status**. Never invents a personal target. |
| M1 Readings | Two-phase record: draft → confirm. Distinguishes *measured at* from *entered at*. Revision history. Idempotent save. |
| M2 Medicines | Explains what a **confirmed** medicine is for, with the source shown. Four adherence states: `taken` / `not_taken` / `unsure` / `unrecorded`. |
| M3 Barriers | **The differentiator.** A missing record is a question, not a verdict. Asks why, and routes a different reason to a different support. |
| M4 Trends | Statistics computed in code. Shows the denominator, the window, and what is missing. Refuses to compare when data is insufficient. |
| M5 Visit summary | One page for the appointment. Preview → edit/omit → print. **Never auto-sent.** |
| M6 Safety & fallback | Deterministic routing that runs *before* the model. Emergency path is local (Singapore). Degrades gracefully. |

---

## Repository layout

```
caresteps/
  app/
    main.py            FastAPI app, startup, session
    config.py          environment settings
    db.py              SQLite schema and connection
    repository.py      database writes; seed.py also writes directly
    stats.py           deterministic statistics
    summary.py         visit summary fact table
    safety/            deterministic routing: red flags, boundaries, clarification
    llm/               provider adapter, orchestrator, prompts, degraded fallback
    tools/             tool contracts (JSON Schema) + server-side handlers
    routes/            page routes and JSON API
    templates/         Jinja2, mobile-first, large type
    static/            CSS and vanilla JS (no build step)
  content/
    education/         vetted knowledge entries with provenance
    rules/             safety rules with provenance and review status
  demo-data/           README.md explaining the seed (patient/history live in code)
  scripts/             seeding, cover generation, and `demo-check`
  tests/               pytest suite over data behaviour, stats, summary, boundaries
  docs/                plan, architecture, evaluation, decisions
  memory/              working notes kept next to the code, including the open gates
  submission/          competition materials
```

Two of those directories deserve a word, because neither is a build artefact.

`scripts/` holds the entry points the Makefile drives. `make demo-check` runs
`scripts/demo_check.py`, which replays every routing case from the demo guide against a
temporary database and prints a per-case pass or fail.

`memory/` holds the short notes written while building: the invariants a future edit could
silently break, the record of which submission gates are still open, and the research
finding that Singapore publishes no numeric blood-pressure threshold. They are kept in the
repository rather than in someone's head because the second reader of this code should get
the same warnings the first one did. Nothing in them is load-bearing at runtime.

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | Build plan, phases, decisions, risks |
| [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) | **Process log** — every phase, and an honest self-review of each |
| [`docs/architecture.md`](docs/architecture.md) | Architecture, trust boundaries, trade-offs |
| [`docs/evaluation.md`](docs/evaluation.md) | Test conditions, results, failures, limitations |
| [`docs/decisions.md`](docs/decisions.md) | Confirmed scope and change record |
| [`docs/content-provenance.md`](docs/content-provenance.md) | Where every health fact came from |

---

## Proving the AI workflow

Every tool call the model makes is recorded and visible at **`/trace`**: tool name, arguments,
result status, source IDs, and rule version. This is deliberately not a claim to read the
model's internal reasoning — it shows the **auditable** surface: what was called, with what,
and what came back.

---

## Licence and attribution

Original work by the CareSteps team. Third-party health education content is paraphrased and
cited, not reproduced wholesale — see `docs/content-provenance.md` for each source's terms.
