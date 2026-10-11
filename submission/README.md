# submission/

Competition submission materials for the Tencent Cloud AI Singapore Hackathon 2026.

## Contents

| File | Item | Handbook status | State |
|---|---|---|---|
| [`description.md`](description.md) | Project title, short blurb, full description | Required | Written |
| `cover_16x9_1920x1080.png` | Cover image, true 16:9 | Required | Generated |
| `cover_380x216.png` | Cover image at the exact size the handbook names | Required | Generated |
| `cover_16x9_1280x720.png` | Cover image, mid size | — | Generated |
| [`tool-evidence/`](tool-evidence/README.md) | CodeBuddy/WorkBuddy conversation history | **Required — blocks scoring** | **NOT DONE** |
| Demo video, 5–8 minutes | Project overview, core features, build reflection | Optional (recommended) | **NOT DONE** |
| Online project link | Live demo URL; optional but earns bonus points | Optional | **NOT DONE** |
| Source code | Complete source via GitHub | Required | In this repository |

## Regenerating the cover

```bash
.venv/bin/python scripts/make_cover.py
```

No design tool or external asset is used — the cover is drawn in code with Pillow, and
the palette is taken from `app/static/css/app.css` so the cover and the product match.

Note that the handbook recommends **380×216 px** and calls it 16:9. Those are not the
same ratio (380/216 = 1.759; 16/9 = 1.778), so both are produced: a true 16:9 image for
displays that care about the ratio, and the exact stated pixel size in case the
submission form enforces dimensions.

## Before submitting

- [ ] Confirm the exact deadline time and timezone — the handbook gives 2026-10-16 with
      no time, and no published timezone. Do not assume a late-evening cutoff.
- [ ] CodeBuddy/WorkBuddy evidence collected and sanitised (see `tool-evidence/`).
- [ ] Screenshots and video contain no credentials and no real personal data.
- [ ] Every claim in the description matches what the prototype actually does.
- [ ] The GitHub repository is accessible to reviewers, and a fresh clone runs with
      `make setup && make seed && make run`.
- [ ] Re-read `docs/demo-guide.md` section "Things not to claim on stage".
- [ ] Keep the receipt.
