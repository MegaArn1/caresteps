# Web deployment for the submission

**Project Web Link is mandatory in the supplied actual form.** It must let a reviewer
experience the running project in a browser. A source repository or a local-only note
does not satisfy that field. The handbook's optional-link wording is less strict than
the actual form.

The source repository is [MegaArn1/caresteps](https://github.com/MegaArn1/caresteps).
Public application hosting has not yet been provisioned.

## Selected configuration

[render.yaml](../../render.yaml) defines a native Python service, one instance, a
persistent SQLite disk, health check `/healthz` and a start command binding `$PORT`.
The selected disk-capable service is paid; this is configuration for review, not an
already purchased or provisioned service. A Render free service has ephemeral storage
and cannot attach a persistent disk.

The blueprint initially uses limited mode without model credentials. After deploying,
set `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` through the hosting secret settings and
set `LLM_FORCE_DEGRADED=0` if live conversation is wanted. Do not copy credentials into
this file. Configure one worker and one replica. Do not seed during each deploy.

The application reads a local `.env` for development; exported/platform variables take
precedence. GitHub does not receive `.env`. Shared fictional demo data is suitable for
judging; this configuration has no production patient authentication.

## Deploy from GitHub

1. Use the reviewed `main` branch in the GitHub repository.
2. Connect that repository to Render and review the blueprint before deploying.
3. Confirm the disk mount and `CARESTEPS_DB=/var/data/caresteps.db`.
4. Open `/app` once to initialize the fictional profile on a new volume.
5. Verify `/healthz`, `/api/stats`, reading preview/confirm, chat, `/trace` and summary.
6. Add optional model configuration and check an actual live result if required.
7. Record the actual public URL in [DEPLOYMENT_INFO.md](DEPLOYMENT_INFO.md), then test
   access without a signed-in hosting account.

Railway with a volume is an alternative in [docs/DEPLOYMENT.md](../../docs/DEPLOYMENT.md).
No current free-credit or pricing promise is made.

## Remaining submission links

- Application URL: pending deployment.
- Video URL: pending hosting of the selected 7:22 MP4, with public/unlisted playback.
- Source URL: https://github.com/MegaArn1/caresteps.

Do not put placeholder URLs in the submitted form.

Official references: https://render.com/docs/blueprint-spec,
https://render.com/docs/free, https://render.com/docs/disks,
https://docs.railway.com/guides/fastapi. Configuration checked on 2026-10-16.
