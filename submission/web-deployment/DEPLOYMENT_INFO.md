# Deployment status

**Live and verified on October 16, 2026.**

| Field | Verified value |
|---|---|
| Application URL | https://caresteps-splz.onrender.com/app |
| Health-check URL | https://caresteps-splz.onrender.com/healthz |
| Trace URL | https://caresteps-splz.onrender.com/trace |
| GitHub repository | https://github.com/MegaArn1/caresteps |
| Hosted demo video | https://www.youtube.com/watch?v=gTVs-9tpJL8 |
| Platform / region | Render / Singapore |
| Plan / instances | Free / 1 instance, 1 worker |
| Persistent disk | None; SQLite is `/tmp/caresteps.db` |
| Deployed application commit | `e7319fcd7d38908daf30cc1f7adc827666e92313` |
| Deployment status | `live` |
| Verification time (UTC) | 2026-10-16T14:31:34.403918+00:00 |

## Verified behavior

Anonymous HTTPS access, 13 page/API/static paths, reading preview without persistence
followed by explicit confirmation/save, trends, medicines, summary/print, trace and
browser chat all passed. A real model turn returned `mode=live`, called the care-plan
and local education tools, and returned source IDs. Medication-boundary and configured
emergency test inputs returned authored safety replies before model access.

A concurrent health request completed in 0.099 seconds during an
8.882-second model turn. The concurrency regression was fixed before this
final verification. The current software suite has 171 passing tests and the demo
routing check has 27/27 passing scenarios. The mobile page has no horizontal overflow
at 390 px, and its Send control works.

## Free-demo limits

Render can spin down the service after 15 minutes without inbound traffic; the next
visit can take about a minute to start. Entered records are ephemeral and reset on a
new instance. The first `/app` visit restores the fictional dataset. Hosting is free;
existing model-gateway usage is separate. All demonstration patient information is fictional.

Automatic deployments are disabled. Later application changes need a manual deployment;
documentation-only GitHub updates do not change the running application commit above.

[Machine-readable verification](verification.json) · [Deployment strategy](DEPLOYMENT_STRATEGY.md)
