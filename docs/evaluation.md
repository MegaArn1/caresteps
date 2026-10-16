# CareSteps evaluation

The release audit is dated **2026-10-16**. All checks use fictional data.
Software results do not establish clinical accuracy, emergency detection sensitivity,
accessibility conformance or measured improvement in adherence.

## Reproduce

```bash
make setup
make test
make demo-check
```

For a fresh Python environment without `make`:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m scripts.demo_check
```

The tests create temporary databases. The normal demo seed is separate and destructive.
External live model calls are not part of these automated checks.

## Automated software suite

The existing suite passes **171 tests**. It checks:

| File | Tests | Main scope |
|---|---:|---|
| `test_data_integrity.py` | 34 | Input records, timestamps, correction history, content metadata and boundaries |
| `test_degraded_and_output.py` | 45 | Deterministic conversation, extraction and live-output check functions |
| `test_demo_flow.py` | 20 | HTTP workflows, reset and first-request initialization |
| `test_safety.py` | 44 | Known routing patterns, negation and priority conflicts |
| `test_stats_and_summary.py` | 23 | Statistics, missing states, windows and summary facts |
| `test_system_stats_api.py` | 5 | Operational totals, empty DB behavior and period-endpoint compatibility |
| **Total** | **171** | |

The pre-deployment 170-test baseline passed in **40.93 seconds**, with three upstream
warnings concerning FastAPI startup hooks and the TestClient/httpx integration.
Test duration depends on storage and environment; it is not a product metric.
The clean publication-candidate verification is recorded in `submission/release-verification.json`.

`make demo-check` replays **27/27** HTTP routing scenarios against a temporary seeded
database in forced limited mode. This includes known emergencies, denials, medication
boundaries, clarification, urgent advice and priority conflicts. It is a fixture-based
software check, not exhaustive language coverage.

## Submission artifacts

The final video is **441.934 seconds**, H.264/AAC, 1920×1080 at 30 fps. Its file hash
matches the existing verification record. It includes a historical successful live
chat/tool turn; this audit makes no billable external model request and does not verify
the identity behind a gateway's configured model label.

The selected architecture deck has **9 slides**, **10 model-facing contracts** and
**13 SQLite tables**. The exported PDF and previews are checked against the PPTX and
source fingerprints. Clipped text frames and incorrect system-flow arrows found during
release review were corrected and re-exported. The final verifier checks 235 text frames
and 475 native elements, including searchable rendered text inside each frame.

The cover is 1920×1080 and under the form's 1 MB limit. The evidence PDF packages three
existing WorkBuddy screenshots into one upload below 10 MB. Final artifact sizes and
hashes are recorded in `submission/release-verification.json`.

## Scope and limits

- The suite does not exercise an actual remote provider or establish model reliability.
- Safety uses authored patterns and output checks use regex/numeric heuristics. Unknown
  phrasing can be missed or incorrectly matched.
- Some scoped tools write directly. A later provider failure does not roll those writes
  back; the turn is not an atomic transaction.
- The demo shares a fictional profile and lacks production login/authorization.
- No real-patient study, clinical review, clinical validation, assistive-technology
  testing or accessibility conformance audit has been performed.
- The selected public-source corpus is not an exhaustive review of clinical guidance.
- Public access and real live conversation were checked after deployment; see
  [the deployment verification](../submission/web-deployment/verification.json). The free
  service has ephemeral storage, so restart persistence is not claimed.

See [architecture](architecture.md), [content provenance](content-provenance.md),
[development attribution](development.md) and the [submission checklist](../submission/SUBMISSION_CHECKLIST.md).

## Public deployment concurrency regression

The first live Render check returned a source-linked model answer in 8.322 seconds,
but a concurrent `/healthz` request timed out after 5 seconds. Synchronous provider I/O
was running inside an asynchronous route and blocking the event loop.

The chat route now runs as a synchronous FastAPI handler, which dispatches it to the
worker pool. The added regression holds a model turn open while checking that a second
HTTP request can still complete. It fails before the fix. The current suite contains
171 tests; the original video and architecture deck preserve the 170-test snapshot
recorded before this deployment patch.

Final public verification completed the model turn while a concurrent health check
returned HTTP 200 in 0.099 seconds. The deployed commit and check results are recorded
in `submission/web-deployment/verification.json`.
