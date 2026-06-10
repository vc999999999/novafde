# PydanticAI Skill Quality Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full local-only SkillForge quality-loop PRD with real configured model calls, deterministic rendering and validation, user supplementation, three repair rounds, degraded delivery, and complete frontend states.

**Architecture:** Keep FastAPI, SQLite, SkillIR, renderer, and packager. Replace the fallback generator with PydanticAI role agents behind a provider adapter, then add a persisted `QualityOrchestrator` that creates candidate attempts, evaluates them, pauses for user facts when required, repairs up to three times, and packages the best safe candidate. The React application polls persisted generation state and exposes one global model connection indicator, loading stages, supplementation, quality results, and downloads.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, PydanticAI, SQLite, PyYAML, pytest, React 19, TypeScript, Vite, ESLint.

---

### Task 1: Establish testable local-only configuration

**Files:**
- Modify: `backend/app/settings.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/storage.py`
- Test: `backend/tests/test_local_runtime.py`

- [ ] Write failing tests proving SQLite is the only production database and local API metadata reports loopback-only operation.
- [ ] Run the focused tests and verify they fail because local runtime contracts are absent.
- [ ] Add explicit local runtime settings, SQLite pragmas, schema versioning, and interrupted-run recovery.
- [ ] Run focused and existing backend tests.

### Task 2: Define persisted quality-loop contracts

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/storage.py`
- Test: `backend/tests/test_quality_models.py`
- Test: `backend/tests/test_storage_quality.py`

- [ ] Write failing tests for attempts, quality reports, issues, supplementation, connection status, and new generation states.
- [ ] Add strict Pydantic models and SQLite tables for attempts, reports, supplements, and error patterns.
- [ ] Verify serialization, migrations, and history compatibility.

### Task 3: Replace fallback generation with PydanticAI agents

**Files:**
- Modify: `backend/requirements.txt`
- Rewrite: `backend/app/agent.py`
- Modify: `backend/app/provider_runtime.py`
- Create: `backend/app/prompts.py`
- Test: `backend/tests/test_pydantic_agents.py`

- [ ] Write failing agent contract tests using PydanticAI test models and the real SkillIR schema.
- [ ] Implement generation, repair, activation judge, and implementation judge agents.
- [ ] Remove production deterministic fallback and ad hoc JSON extraction.
- [ ] Preserve authoritative user facts after every model result.
- [ ] Verify configured Claude and OpenAI-compatible providers are translated into PydanticAI models.

### Task 4: Implement deterministic validation and scoring

**Files:**
- Modify: `backend/app/validator.py`
- Create: `backend/app/quality.py`
- Modify: `backend/app/rules.py`
- Test: `backend/tests/test_quality_engine.py`

- [ ] Write failing tests for severity levels, frontmatter rules, mandatory-rule preservation, score weighting, strict gate, degraded gate, and user-input classification.
- [ ] Implement validation score calculation and Tessl-aligned activation and implementation rubrics.
- [ ] Ensure security and structure blockers override scores.

### Task 5: Implement the persisted orchestrator

**Files:**
- Rewrite: `backend/app/service.py`
- Rewrite: `backend/app/repair.py`
- Modify: `backend/app/renderer.py`
- Modify: `backend/app/packager.py`
- Create: `backend/app/orchestrator.py`
- Test: `backend/tests/test_quality_orchestrator.py`

- [ ] Write failing tests for initial generation, three repairs, early stop, score regression, best-candidate selection, user-input pause, skip, resume, interruption, and degraded delivery.
- [ ] Implement candidate isolation and immutable attempt persistence.
- [ ] Run deterministic checks before judges and run independent judges only for safe candidates.
- [ ] Enforce three repair calls maximum and select the highest-scoring safe candidate.
- [ ] Generate high-quality or low-score package names and quality reports.

### Task 6: Expose complete local APIs

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_quality_api.py`

- [ ] Write failing API tests for generation creation, polling, quality reports, attempts, supplementation, provider connection status, and download behavior.
- [ ] Implement the local loopback API endpoints and structured error responses.
- [ ] Keep old draft generation route as a compatibility alias where it does not conflict with the PRD.

### Task 7: Remove server mode and add global connection state

**Files:**
- Modify: `skill-forge/src/App.tsx`
- Modify: `skill-forge/src/types/index.ts`
- Modify: `skill-forge/src/api.ts`
- Modify: `skill-forge/src/pages/SettingsPage.tsx`
- Create: `skill-forge/src/components/ModelConnectionStatus.tsx`

- [ ] Add frontend test tooling and write failing component tests for a single global connection indicator.
- [ ] Remove `AppMode`, server mode dialog, and server settings.
- [ ] Poll the backend connection status and link failures to Provider settings.

### Task 8: Implement asynchronous generation UX

**Files:**
- Rewrite: `skill-forge/src/pages/CreatePage.tsx`
- Modify: `skill-forge/src/components/PipelineProgress.tsx`
- Create: `skill-forge/src/components/GenerationLoading.tsx`
- Create: `skill-forge/src/components/SupplementDialog.tsx`
- Create: `skill-forge/src/components/QualityScorePanel.tsx`
- Modify: `skill-forge/src/components/DownloadCard.tsx`

- [ ] Write failing frontend tests for immediate loading, stage polling, supplementation, resume, skip, degraded status, and quality scores.
- [ ] Create the draft and generation run, then poll until terminal or user-input state.
- [ ] Stop animation while waiting for user input and resume after submission.
- [ ] Display strict, degraded, interrupted, and failed outcomes accurately.

### Task 9: Remove production mock and stale branches

**Files:**
- Modify: `skill-forge/src/data/index.ts`
- Modify: `skill-forge/src/pages/HistoryPage.tsx`
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `skill-forge/README.md`
- Modify: `scripts/install.sh`
- Modify: `scripts/run.sh`
- Modify: `scripts/doctor.sh`

- [ ] Remove mock/static runtime data and deterministic production fallbacks.
- [ ] Update scripts to use `.venv`, loopback hosts, SQLite, and PydanticAI dependencies.
- [ ] Remove server-mode and remote-database documentation.

### Task 10: Full verification and PRD audit

**Files:**
- Modify as needed based on findings.

- [ ] Run all backend tests.
- [ ] Run Python compile/static checks.
- [ ] Run frontend tests, ESLint, and production build.
- [ ] Start the local backend and frontend and exercise health, provider status, draft, generation state, supplementation, quality, history, and download routes.
- [ ] Search production sources for mock data, fallback generation, server mode, and remote database branches.
- [ ] Audit every PRD requirement against code and verification evidence; fix every uncovered gap before completion.
