> Release annotation (2026-10-16): three conversation screenshots are now present
> and packaged in [CareSteps_WorkBuddy_Evidence.pdf](CareSteps_WorkBuddy_Evidence.pdf).
> The earlier note below about needing two more captures is historical. `/api/status`
> is registered in the current code; the issue recorded below has since been fixed.
> Contribution scope is documented in [development.md](../../docs/development.md).

# WorkBuddy Task 1–2 Completion Summary

Date: 2026-10-15
Tool: WorkBuddy AI

## Task 1 — System statistics API

Implemented and registered `GET /api/stats`.

```bash
curl http://127.0.0.1:18765/api/stats
```

```json
{
  "total_users": 1,
  "total_bp_recordings": 11,
  "total_medications_tracked": 2,
  "active_barriers": 1,
  "database_size_kb": 176
}
```

The original per-user period statistics remain available through the explicit query
`GET /api/stats?days=14`, avoiding a duplicate route while preserving the existing demo
contract.

Validation:

```text
Targeted tests: 5 passed
Full suite: 170 passed, 3 deprecation warnings
```

## Task 2 — Cloud deployment guide

Created `docs/DEPLOYMENT.md` with beginner-oriented instructions for:

- Render deployment with a paid persistent disk
- Railway deployment with a persistent volume
- Environment variables and optional model configuration
- Automatic schema and fictional demo-data initialization
- Single-instance SQLite constraints and consistent backups
- Health checks, post-deploy verification, troubleshooting, and security limitations

The platform-specific details were checked against the current official Render and
Railway documentation on 2026-10-15.

## Files added or updated

- **Added — `app/routes/stats.py`**
  Defines the consolidated `GET /api/stats` route. A request without `days` returns the
  five global operational metrics required by Task 1. An explicit `?days=N` request
  continues to return the existing per-user period statistics, preserving the old demo
  and documentation contract without registering two handlers for the same route.

- **Updated — `app/main.py`**
  Imports the new statistics route module as `stats_routes` and includes its router in
  the FastAPI application. No existing page, medication, barrier, or summary business
  logic was changed for this task.

- **Updated — `app/routes/api.py`**
  Removes the original `/api/stats` handler from the general JSON API module. Its period
  statistics behavior was moved into `app/routes/stats.py`, preventing duplicate
  `GET /api/stats` registrations and keeping all behavior for this path in one place.

- **Updated — `app/repository.py`**
  Adds `system_metrics(conn)`, which queries the actual SQLite tables
  (`user_profile`, `bp_reading`, `medication_item`, and `barrier_event`). It counts open
  barriers as active, counts all stored blood-pressure rows including append-only
  correction history, and calculates database size from SQLite page count and page size.

- **Added — `tests/test_system_stats_api.py`**
  Adds repository and HTTP tests for seeded and empty databases. The tests verify the
  exact five-field JSON response, metric values, database-size calculation, absence of
  implicit demo seeding/session creation, compatibility of `?days=14`, and that only one
  statistics route is declared.

- **Updated — `docs/architecture.md`**
  Clarifies the two intentional forms of the endpoint: bare `/api/stats` provides system
  totals, while `/api/stats?days=14` provides the deterministic period-statistics
  structure used by the trends UI.

- **Added — `docs/DEPLOYMENT.md`**
  Provides a beginner-oriented deployment guide for Render and Railway, including build
  and start commands, environment variables, persistent SQLite storage, initialization,
  health checks, backups, single-instance constraints, verification, troubleshooting,
  and prototype security limitations. Platform details were checked against official
  documentation current on 2026-10-15.

- **Added — `submission/tool-evidence/task1-stats-api-result.json`**
  Stores the verified curl command, returned metrics, and targeted/full test results in a
  compact machine-readable evidence file.

- **Updated — `submission/tool-evidence/README.md`**
  Records Tasks 1 and 2 as completed in WorkBuddy, links the available evidence, updates
  the submission status table, and notes that two more sanitized screenshots or an
  equivalent recording are still required by the handbook.

- **Added and updated — `submission/tool-evidence/task1-2-workbuddy-summary.md`**
  Captures this implementation history, verification output, file-by-file change notes,
  evidence status, and the additional findings below as a process record.

## Important implementation findings

1. **The requested route already existed with a different purpose.**
   Before Task 1, `GET /api/stats?days=14` already returned per-user blood-pressure and
   adherence statistics. Adding another handler at the same method and path would have
   made behavior depend on registration order. The final implementation consolidates both
   contracts in `app/routes/stats.py`: no query returns operational totals, while an
   explicit `days` query preserves period statistics.

2. **The task document used conceptual table names rather than the real schema names.**
   The requested `profiles`, `bp_recordings`, `medications`, and `barriers` tables do not
   exist in the database. The implementation uses the authoritative schema names:
   `user_profile`, `bp_reading`, `medication_item`, and `barrier_event`. An active barrier
   is defined by the existing application rule `status = 'open'`.

3. **An unrelated `/api/status` compatibility issue remains in the working tree.**
   During review, the previous `GET /api/status` route was found to be absent, with its
   former response body appearing as unreachable code after `chat_confirm` returns in
   `app/routes/api.py`. This was not introduced as part of Tasks 1 or 2 and was not changed
   here, but it likely causes `/api/status` to return 404. It should be repaired and given
   a regression test as a separate change.

4. **The passing suite still reports non-blocking deprecation warnings.**
   The application uses FastAPI's deprecated `on_event("startup")` API, and the current
   TestClient stack reports an `httpx`-related deprecation warning. These warnings do not
   affect the Task 1 result, but migrating startup initialization to a lifespan handler
   and updating the test-client dependency path should be tracked as maintenance work.

## Historical evidence note

The existing WorkBuddy screenshot in `submission/tool-evidence/screenshot/` shows the
request and implementation process. Capture at least two additional sanitized screenshots
showing the final response and test/deployment-document results to satisfy the handbook's
minimum of three screenshots or recordings.
