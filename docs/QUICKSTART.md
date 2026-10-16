# CareSteps quick start

Use fictional information throughout. The seeded patient is **Mdm Tan**, age band 65–74,
with two medicines: amlodipine and losartan. There are 11 stored blood-pressure rows
(including correction history), with current readings on 10 days in the initial 14-day window.

## Linux, macOS or WSL

From the repository root, with Python 3.11 installed:

```bash
make setup
make seed
make run
```

Open http://127.0.0.1:8000/app. Setup installs runtime and test dependencies.
`make seed` is destructive: use it to restore fictional fixtures, never to initialize
an existing deployed database on each restart.

## Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m scripts.seed --verbose
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Optional live model

Copy `.env.example` to `.env` and set your own configuration:

```dotenv
LLM_BASE_URL=https://gateway.example/v1
LLM_API_KEY=YOUR_MODEL_API_KEY
LLM_MODEL=your-tool-capable-model
LLM_FORCE_DEGRADED=0
```

The application reads `.env` at startup; platform/exported variables take precedence.
Restart after changing it. The endpoint must implement chat completions with function
calling. Never commit `.env` or print the key in troubleshooting output.

`live: true` in `/healthz` means the configuration permits calls. Check an actual
`POST /api/chat` result and its trace to establish that a particular call succeeded.
The recorded video contains a historical successful live turn; this release audit
runs without making billable external model requests.

## Five-minute walkthrough

1. Open `/app`, inspect the fictional care-plan label and mode badge.
2. Choose **Record blood pressure**. Enter fictional values `145` and `88`, preview,
   then confirm. Open the history to see the saved row.
3. Open **My numbers**. Check the time window, coverage, and the expandable data table.
   Gaps mean missing records, not missed measurements or missed medicine.
4. Open medicines. Inspect the two source-linked entries and report a fictional status.
5. Choose **Something is difficult**. Describe a cuff difficulty; category confirmation
   and support selection remain separate from the person's original words.
6. In the home-page chat, try `What is amlodipine for?`. In limited mode the response
   follows deterministic routing; with an available configured model it can use tools.
7. Try the demo-guide inputs `should I double the dose today` and `I have chest pain`.
   The first is refused; the second returns the configured local emergency panel before
   model access. These are software routing examples, not a clinical assessment.
8. Open `/trace`, then the appointment summary. Omit a question and inspect `/summary/print`.

## Verify or reset

```bash
make test
make demo-check
make seed
```

Expected automated results: **171 tests** and **27/27 routing cases**. The HTTP test
suite creates temporary databases. `make seed` instead resets the configured demo DB.

```bash
curl -f http://127.0.0.1:8000/healthz
curl -f http://127.0.0.1:8000/api/stats
curl -f 'http://127.0.0.1:8000/api/stats?days=14'
```

`/healthz` returns `ok`, `db`, `profiles`, `llm` and `rules_version`. Bare `/api/stats`
returns operational totals; the explicit `days` query returns per-user period statistics.

If port 8000 is occupied, run `make run PORT=8001`. To deliberately check limited mode,
start with `LLM_FORCE_DEGRADED=1 make run`. Do not stop an unrelated running server.

See [deployment](DEPLOYMENT.md), [architecture](architecture.md),
[evaluation](evaluation.md) and the [demo guide](demo-guide.md).
