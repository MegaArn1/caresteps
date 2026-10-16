# CareSteps Architecture - Speaker Notes

## 01. CARESteps  /  ARCHITECTURE

CareSteps architecture submission. Healthcare Challenge Statement 2: AI Healthier Every Day. The deck is a source-checked prototype overview using simulated data.

## 02. CARESteps  /  ARCHITECTURE

Solid arrows represent local flow. Dashed arrows cross the optional model or content boundary. The three chat safety gates run before the orchestrator; SQLite is local to the application host.

## 03. CARESteps  /  ARCHITECTURE

Four zones separate user device, trusted application, local storage and external inputs. The model has no database credential, arbitrary SQL tool or confirm_draft contract. The signed cookie provides integrity, not production authentication.

## 04. CARESteps  /  ARCHITECTURE

route() evaluates red flags, boundaries and clarification in order. emergency, urgent_advice, refuse and clarify all block model access. Detection uses authored patterns and context; it is not a clinical diagnostic system.

## 05. CARESteps  /  ARCHITECTURE

The read example uses the real get_period_stats tool with days=7. user_id comes from ToolContext. Readings and medication reports stage a draft, then a user action confirms the write. record_barrier, add_question and set_reminder_preference are scoped direct-write exceptions.

## 06. CARESteps  /  ARCHITECTURE

Missing configuration or forced degraded mode uses _degraded_turn. A provider failure before tools also degrades. If tools already ran, the fallback text can still return mode live and is checked. Completed writes are not rolled back.

## 07. CARESteps  /  ARCHITECTURE

The table count is checked by executing SCHEMA in memory. This is a responsibility map, not a complete ER diagram. Corrections preserve history through superseded_by; missing reports remain unknown rather than compliant/non-compliant.

## 08. CARESteps  /  ARCHITECTURE

The system prompt is caresteps.system.v3. Context includes profile orientation and the latest 12 messages; tool results are appended. check_output uses heuristic numeric and phrase checks. /trace exposes contracts, rule metadata, provider status, source IDs and audit events.

## 09. CARESteps  /  ARCHITECTURE

Automated validation recorded 170 passed tests on 16 October 2026. Tests do not establish clinical safety, accessibility conformance or live model performance. Known limits include no production login, no encryption at rest, no atomic whole-turn transaction and no health-system integration.
