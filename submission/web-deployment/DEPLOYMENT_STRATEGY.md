# Web deployment for the submission

**Project Web Link is mandatory in the supplied actual form.** It must let a reviewer
experience the running project in a browser. A source repository or a local-only note
does not satisfy that field. The handbook's optional-link wording is less strict than
the actual form.

The source repository is [MegaArn1/caresteps](https://github.com/MegaArn1/caresteps).
The free application is live at [CareSteps](https://caresteps-splz.onrender.com/app); see
[the verification record](DEPLOYMENT_INFO.md).

## Selected free-demo configuration

The owner selected Render's **free web service** on October 16, 2026.
[render.yaml](../../render.yaml) uses Python 3.11.7, one instance/worker, `/healthz`,
and `CARESTEPS_DB=/tmp/caresteps.db`, without a disk. No paid service or storage is requested.

The database and entered records are ephemeral. Render can spin the service down after
15 minutes without inbound traffic; the next request can take about a minute to start.
A new instance recreates the fictional seed on the first `/app` visit. This is a
competition demo and does not preserve newly entered records across restarts.

Existing model settings are configured only as service-side environment variables.
`LLM_FORCE_DEGRADED=0` permits live calls when the three `LLM_*` settings are available;
the application falls back when the provider fails. Model-service availability and any
existing gateway usage charges are separate from the free hosting plan.

Automatic deploys are disabled while the demo is being verified. Future application
changes require a manual deploy from the Render dashboard or API.

## Verification before recording the live URL

1. Confirm the Render service reports `plan=free` and has no attached disk.
2. Wait for its first deploy to become live and check the deployed commit.
3. Open `/app` to initialize fictional records, then check `/healthz` and `/api/stats`.
4. Verify CSS, reading preview/confirmation, medicines, trends, chat, `/trace` and summary.
5. Check a real model/tool reply, a known safety boundary and emergency routing.
6. Record the actual public URL and limitations in [DEPLOYMENT_INFO.md](DEPLOYMENT_INFO.md).

Optional paid persistence is documented in [docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md).
It is not part of this free deployment.

## Submission links

- Application URL: https://caresteps-splz.onrender.com/app (verified live).
- Video URL: https://www.youtube.com/watch?v=gTVs-9tpJL8 (YouTube; owner-provided link).
- Source URL: https://github.com/MegaArn1/caresteps.

Do not put placeholder URLs in the submitted form.

Official references: https://render.com/docs/blueprint-spec,
https://render.com/docs/free, https://render.com/docs/disks,
https://docs.railway.com/guides/fastapi. Configuration checked on 2026-10-16.
