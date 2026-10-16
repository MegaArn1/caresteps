# CareSteps — Deployment Guide

This guide deploys CareSteps as a **single-instance competition demo** on Render or
Railway. The application is a FastAPI service with a local SQLite database and no
frontend build step.

> **Prototype status.** CareSteps is not a medical device, an emergency service, or a
> production authentication system. Deploy only fictional demo data. Do not use this
> configuration for real patient information.

---

## 1. What will be deployed

The service runs one command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The important deployment constraints are:

- Run **one service instance, one replica, and one Uvicorn worker**.
- Store `caresteps.db` on a persistent volume, not the platform's ephemeral filesystem.
- Do not run `make run` in the cloud. It binds to `127.0.0.1`, enables reload, and does
  not use the platform-provided port.
- Do not run the seed command during every build or deploy. It deliberately replaces the
  database.

### Prerequisites

Before starting, you need:

1. A Git repository containing this project.
2. An account on Render or Railway.
3. Python 3.11 for local verification. The pinned dependencies were verified with
   Python 3.11.7.
4. Optional model credentials only if you want the live conversational path. The rest
   of the application works in limited mode without a model.

---

## 2. Environment variables

Configure variables in the platform dashboard. For local development, CareSteps loads
`.env` at startup; platform/exported variables take precedence.

| Variable | Required | Example | Purpose |
|---|---:|---|---|
| `CARESTEPS_DB` | Yes for cloud deployment | `/var/data/caresteps.db` | Absolute path to SQLite on the persistent volume |
| `LLM_BASE_URL` | No | `https://gateway.example/v1` | OpenAI-compatible API root; do not include `/chat/completions` |
| `LLM_API_KEY` | No | Set in the platform's secret manager | Bearer token for the model gateway |
| `LLM_MODEL` | No | `your-model-name` | Model identifier understood by the gateway |
| `LLM_TIMEOUT_S` | No | `30` | Model request timeout in seconds |
| `LLM_MAX_TOOL_ROUNDS` | No | `4` | Maximum tool-calling rounds per turn |
| `LLM_FORCE_DEGRADED` | No | `1` | Forces the no-model path for testing |

Never commit a real API key or paste one into screenshots. If the three main `LLM_*`
settings are absent, CareSteps starts normally in limited mode.

---

## 3. Database initialization

`app.main` calls `init_db()` at startup. On a new persistent volume this creates the
SQLite schema automatically. The first visit to `/app` also loads the knowledge base
and creates the fictional demo patient when no profile exists.

The recommended first-deploy sequence is therefore:

1. Attach the persistent volume.
2. Set `CARESTEPS_DB` to a file under its mount path.
3. Start the service.
4. Open `/healthz` to confirm that the schema is reachable.
5. Open `/app` once to create the fictional demo data.
6. Open `/api/stats` to confirm the database now contains the expected rows.

`/healthz` can show `"profiles": 0` before the first `/app` visit. That is normal for an
empty but healthy database.

### Optional destructive reset

The following command drops the current schema and rebuilds the fictional data:

```bash
python -m scripts.seed --verbose
```

Run it only from a runtime shell with `CARESTEPS_DB` pointing at the mounted volume, and
only when you intend to erase the current demo database. Never use it as a build,
pre-deploy, or automatic start command.

---

## 4. Local production-mode check

Verify the same command the cloud platform will run before deploying.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export CARESTEPS_DB="$(pwd)/var/caresteps.db"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For Git Bash on Windows, activate the environment with:

```bash
source .venv/Scripts/activate
```

In a second terminal:

```bash
curl -f http://127.0.0.1:8000/healthz
curl -f http://127.0.0.1:8000/app > /dev/null
curl -f http://127.0.0.1:8000/api/stats
```

A successful statistics response is a flat JSON object with these keys:

```json
{
  "total_users": 1,
  "total_bp_recordings": 11,
  "total_medications_tracked": 2,
  "active_barriers": 1,
  "database_size_kb": 176
}
```

Counts and database size can differ after the demo is used.

---

## 5. Deploy to Render

A reviewable [render.yaml](../render.yaml) is included. It creates a paid disk-capable
service in limited mode; add optional model secrets in the platform settings and set
`LLM_FORCE_DEGRADED=0` for live calls. No hosting resource is created by this file alone.

Render can deploy the repository as a native Python web service. A persistent disk is
required because the normal service filesystem is ephemeral. Render persistent disks are
available only on paid services, so a free web service cannot provide durable SQLite
storage for this deployment.

### Step 1 — Create the web service

1. Push the project to GitHub, GitLab, or Bitbucket.
2. In the Render dashboard, select **New > Web Service**.
3. Connect the repository and choose the branch to deploy.
4. Select the Python runtime.
5. Use these commands:

   **Build Command**

   ```bash
   python -m pip install -r requirements.txt
   ```

   **Start Command**

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

6. Set the health-check path to:

   ```text
   /healthz
   ```

### Step 2 — Pin the Python version

Add this environment variable because the project was verified on Python 3.11.7:

```text
PYTHON_VERSION=3.11.7
```

Render requires a fully qualified version when `PYTHON_VERSION` is used.

### Step 3 — Attach persistent storage

1. Open the service's **Advanced** settings during creation, or its **Disk** page later.
2. Add a persistent disk.
3. Use the mount path:

   ```text
   /var/data
   ```

4. Add this environment variable:

   ```text
   CARESTEPS_DB=/var/data/caresteps.db
   ```

Only files below `/var/data` survive restarts and deploys. Render disks are available at
runtime, not during build or pre-deploy commands, so database initialization belongs to
application startup.

### Step 4 — Configure optional model access

Add `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` as environment variables. Mark the API
key as secret. Skip this step to run in limited mode.

### Step 5 — Deploy and verify

Start the deployment, then replace `<service>` with the assigned service name:

```bash
curl -f https://<service>.onrender.com/healthz
curl -f https://<service>.onrender.com/app > /dev/null
curl -f https://<service>.onrender.com/api/stats
```

The first `/app` request initializes the fictional demo dataset if the volume is empty.

### Render-specific limits

A Render persistent disk is attached to one service instance and prevents horizontal
scaling. Disk-backed deploys have brief downtime because the old instance is stopped
before the new one mounts the disk. Both constraints match this prototype's required
single-instance SQLite design.

---

## 6. Deploy to Railway

Railway can deploy from GitHub or from its CLI. The service is private until you generate
a public domain.

### Step 1 — Create the project

From a terminal with the Railway CLI installed:

```bash
railway login
railway init
railway up
```

`railway init` creates or links a Railway project. `railway up` scans and uploads the
current application directory.

Alternatively, choose **New Project > Deploy from GitHub repo** in the Railway dashboard
and select this repository.

### Step 2 — Set the start command

In the service settings, set the start command to:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway's non-Docker build runs this command through a shell, so `$PORT` is expanded. If
you later switch to a Docker image and override its start command, wrap the command in
`/bin/sh -c` so environment variables expand.

### Step 3 — Attach a volume

1. Create a Railway volume and attach it to the CareSteps service.
2. Set the mount path to:

   ```text
   /data
   ```

3. Add the service variable:

   ```text
   CARESTEPS_DB=/data/caresteps.db
   ```

Railway mounts volumes only when the service container starts. They are not available
during build or pre-deploy steps, so do not seed the database in either phase.

### Step 4 — Add variables and health check

Add optional `LLM_*` variables under **Variables**. Under service settings, configure the
health-check path as:

```text
/healthz
```

Keep the service at one replica because Railway volumes do not support replicas.

### Step 5 — Generate a public domain

1. Open the service's **Settings** tab.
2. Go to **Networking**.
3. Select **Generate Domain**.

Then verify the deployment:

```bash
curl -f https://<generated-domain>/healthz
curl -f https://<generated-domain>/app > /dev/null
curl -f https://<generated-domain>/api/stats
```

Railway also has brief downtime when redeploying a service with a volume attached. This
prevents two deployments from writing to the same volume at once.

---

## 7. SQLite persistence and backups

SQLite is suitable for this low-traffic, single-process demo, but it changes the way the
service must be operated.

### Required operating rules

- Keep exactly one application instance and one Uvicorn worker.
- Keep `CARESTEPS_DB` under the persistent volume's mount path.
- Preserve the main `.db` file and its `-wal` and `-shm` sidecars while the service is
  running.
- Do not copy only the main database file during active writes.
- On Railway, configure a manual or automated volume backup before destructive resets.
- On Render, do not assume a disk snapshot is a consistent SQLite backup. Create an
  online backup with SQLite's backup API from the runtime shell, then transfer the backup
  file off the service:

  ```bash
  python -c "import os, sqlite3; src=sqlite3.connect(os.environ['CARESTEPS_DB']); dst=sqlite3.connect('/var/data/caresteps-backup.db'); src.backup(dst); dst.close(); src.close()"
  ```

- Test restoration in a separate environment instead of assuming a backup is usable.

For a production system, migrate to a managed database such as PostgreSQL and add a real
migration process. `init_db()` creates missing tables but is not a schema-migration tool.

---

## 8. Verification checklist

After every deployment:

- [ ] `GET /healthz` returns HTTP 200 and an `"ok": true` field.
- [ ] `GET /app` renders and initializes the fictional dataset on a new volume.
- [ ] `GET /api/stats` returns the five system-metric fields.
- [ ] `/api/docs` opens the generated FastAPI documentation.
- [ ] Restarting or redeploying the service does not reset `total_users` to zero.
- [ ] The service has one instance, one replica, and one worker.
- [ ] No credential appears in logs, source code, or screenshots.

---

## 9. Troubleshooting

### The service starts but data disappears after redeploy

**Cause:** `CARESTEPS_DB` points outside the persistent volume, or no volume is attached.

**Fix:** Confirm the exact mount path and set the database path to a file below it:

```text
Render:  CARESTEPS_DB=/var/data/caresteps.db
Railway: CARESTEPS_DB=/data/caresteps.db
```

### The platform reports that no port is open

**Cause:** The service is bound to `127.0.0.1`, or the start command ignores `$PORT`.

**Fix:** Use exactly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### `/healthz` works but shows zero profiles

**Cause:** The empty schema exists, but no page requiring a user has initialized the demo
patient.

**Fix:** Visit `/app` once, then check `/api/stats` again.

### `sqlite3.OperationalError: database is locked`

**Cause:** More than one process is writing to SQLite, a second deployment still has the
volume, or a long-running shell command holds a transaction.

**Fix:** Return to one instance and one worker, stop extra processes, and retry. Do not add
multiple Uvicorn workers.

### The model path stays in limited mode

Check that:

- `LLM_BASE_URL` is an OpenAI-compatible API root such as `https://host/v1`.
- The URL does not already end in `/chat/completions`.
- `LLM_MODEL` is set.
- `LLM_FORCE_DEGRADED` is unset or false.
- The gateway accepts `Authorization: Bearer` and supports function calling.

The application remains usable without model access.

### A deployment wiped the demo data

**Cause:** The destructive seed command ran automatically.

**Fix:** Remove `python -m scripts.seed --verbose` from build, pre-deploy, and start
commands. Restore the volume backup, or run the command once only if intentionally
rebuilding fictional data.

---

## 10. Security limitations

The current application deliberately favors a reproducible hackathon demo over production
security:

- The session-signing key is generated again on every boot, so restarts sign users out.
- The session cookie is configured for local HTTP rather than production-only HTTPS.
- There is no account login or production authorization layer.
- The demo-reset endpoint is destructive and is not protected as an administrative action.
- System metrics are public.

Do not deploy real health information. Before any real-world pilot, add authentication,
stable secret management, authorization, CSRF review, secure-cookie settings, protected
administrative routes, encrypted managed storage, backups, monitoring, and clinical/privacy
review.

---

## Official platform references

- [Render: Deploy a FastAPI app](https://render.com/docs/deploy-fastapi)
- [Render: Persistent disks](https://render.com/docs/disks)
- [Render: Set the Python version](https://render.com/docs/python-version)
- [Railway: Deploy a FastAPI app](https://docs.railway.com/guides/fastapi)
- [Railway: Using volumes](https://docs.railway.com/volumes)
- [Railway: Volume limits](https://docs.railway.com/reference/volumes)
- [Railway: Start commands](https://docs.railway.com/guides/start-command)
