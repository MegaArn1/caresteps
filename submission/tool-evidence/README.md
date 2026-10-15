# Tool usage evidence — REQUIRED

> Handbook p.37: "Proof of product usage is mandatory: chat screenshots, API call logs,
> or a written development-process description. **Without proof, the project will not
> proceed to scoring.**"

## Current status

**Tasks 1 and 2 completed in WorkBuddy. Additional screenshot collection is pending.**

This directory contains [`TASKS_FOR_AI_TOOLS.md`](TASKS_FOR_AI_TOOLS.md), the WorkBuddy
conversation screenshot, a machine-readable Task 1 result, and a written completion
summary. Two more sanitized screenshots or a recording are still needed to satisfy the
handbook's minimum of three screenshots or recordings.

## 已完成任务

### 任务 1：系统统计 API

- 工具：WorkBuddy AI
- 时间：2026-10-15
- 证据：`screenshot/Screenshot 2026-10-15 221753.png`, `task1-stats-api-result.json`, `task1-2-workbuddy-summary.md`
- 成果：新增并注册无参数 `GET /api/stats`，返回五项系统指标；显式 `?days=14` 保留原有周期统计结构；定向测试 5 项、完整测试 170 项全部通过

### 任务 2：部署指南

- 工具：WorkBuddy AI
- 时间：2026-10-15
- 证据：`screenshot/Screenshot 2026-10-15 221753.png`, `task1-2-workbuddy-summary.md`
- 成果：新增 `docs/DEPLOYMENT.md`，覆盖 Render 与 Railway 部署、持久卷、数据库初始化、验证、备份和常见故障排查

## What the handbook requires

> **CodeBuddy / WorkBuddy Conversation History — Required**
> "Minimum of 3 screenshots/screen recording of your chat logs from CodeBuddy or
> WorkBuddy during the development process"

The project must also be "built on at least one of the products CodeBuddy or WorkBuddy". Miora is offered as an additional tool but does **not** substitute (Handbook p.37 is explicit; p.39's looser wording should not be read against it).

## Next step

1. Open [`TASKS_FOR_AI_TOOLS.md`](TASKS_FOR_AI_TOOLS.md) and choose 1-2 tasks
2. Complete them in **CodeBuddy** or **WorkBuddy** — not a token session
3. Capture screenshots or screen recordings showing:
   - The conversation (your prompts + AI responses)
   - The verification results (curl output, new files, test output)
4. Save files to this directory with descriptive names (see task doc for naming)
5. Update this README with a completion log (date, tool, evidence files, outcome)

## The three tasks

All tasks are designed to be **low-risk** (won't break existing tests), **independently verifiable** (clear success criteria), and **genuinely useful** to the project:

- **Task 1:** Add `/api/stats` endpoint returning system metrics JSON
- **Task 2:** Write `docs/DEPLOYMENT.md` covering 2+ PaaS platforms (pure documentation, zero code risk)
- **Task 3:** Add `/readings/export.csv` for blood pressure data export

Full requirements in [`TASKS_FOR_AI_TOOLS.md`](TASKS_FOR_AI_TOOLS.md).

## Sanitization checklist

Before submitting, verify every screenshot:

- [ ] No API keys, tokens, or `.env` contents visible
- [ ] No personal information (real names, addresses, phone numbers, patient data). All patient data in this project is fictional — keep it that way in captures.
- [ ] No other teams' or other people's private material
- [ ] No file paths revealing unrelated account names or directories

## Status table

| Item | Status |
|---|---|
| Task definitions written | **DONE** — see `TASKS_FOR_AI_TOOLS.md` |
| At least 1-2 tasks completed in CodeBuddy/WorkBuddy | **DONE** — Tasks 1 and 2 |
| At least 3 conversation screenshots/recordings captured | **IN PROGRESS** — 1 screenshot present |
| Evidence files saved to this directory | **IN PROGRESS** — screenshot, JSON result, and written summary present |
| Evidence sanitized | **IN PROGRESS** — review all final captures before submission |
| This README updated with completion log | **DONE** |

Until at least two more sanitized screenshots or an equivalent recording are added, the
submission does not yet meet the handbook's minimum visual-evidence condition.
