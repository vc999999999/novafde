# Simplified Skill Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy seven-step Skill form with the approved four-step input model across frontend, backend, SQLite persistence, normalization, generation, validation, and documentation.

**Architecture:** `SkillDraft` stores only user-owned business facts. The normalizer converts it into a richer `SkillBrief`, while the project Skill Creator provider derives trigger wording, detailed workflow steps, output standards, and package structure. SQLite keeps JSON payloads and migrates legacy draft payloads when they are read.

**Tech Stack:** React 19, TypeScript, Vite, FastAPI, Pydantic v2, SQLite, pytest.

---

### Task 1: Lock the new backend contract

**Files:**
- Modify: `backend/tests/test_api_pipeline.py`
- Modify: `backend/app/models.py`

- [x] Add failing API tests for the four draft sections: basic information, purpose/process, knowledge/rules/dependencies, and free-form supplement.
- [x] Verify old task type, anti-trigger, file context, output control, and chat-message fields are absent from API responses.
- [x] Add the new Pydantic draft and brief models and run the focused tests until they pass.

### Task 2: Preserve existing SQLite drafts

**Files:**
- Modify: `backend/tests/test_api_pipeline.py`
- Modify: `backend/app/storage.py`

- [x] Add a failing test that inserts a legacy JSON draft directly into SQLite.
- [x] Add a deterministic legacy payload migration that maps intent, objective, workflow actions, knowledge, pitfalls, related tools, and chat text into the new model.
- [x] Verify migrated drafts are returned through the API and resaved in the new shape.

### Task 3: Update normalization and Skill Creator generation

**Files:**
- Modify: `backend/app/normalizer.py`
- Modify: `backend/app/agent.py`
- Modify: `backend/app/repair.py`
- Modify: `backend/app/rules.py`

- [x] Add failing tests for required fields and supplement precedence.
- [x] Normalize user inputs without letting supplement content override mandatory rules.
- [x] Make the Skill Creator provider derive detailed workflow steps, trigger descriptions, quality standards, and references/scripts/assets decisions.
- [x] Update repair and validation messages to the new field paths and rules.

### Task 4: Replace the frontend wizard

**Files:**
- Modify: `skill-forge/src/types/index.ts`
- Modify: `skill-forge/src/data/index.ts`
- Modify: `skill-forge/src/hooks/useDraft.ts`
- Modify: `skill-forge/src/pages/CreatePage.tsx`
- Modify: `skill-forge/src/components/steps/*.tsx`

- [x] Replace seven step keys with `basic`, `purpose`, `knowledge`, and `supplement`.
- [x] Keep only Skill name and target platforms in basic information.
- [x] Build the combined purpose/process form with usage, desired outcome, rough process, completion criteria, and optional special cases.
- [x] Build the knowledge form with professional information, mandatory rules, user-supplied pitfalls/counterexamples, and related Skills.
- [x] Replace chat and paste templates with one optional free-form supplement textarea.
- [x] Keep confirmation, provider status, autosave, generation progress, preview, validation, and download behavior.

### Task 5: Synchronize docs and verify the full project

**Files:**
- Modify: `docs/frontend-prd.md`
- Modify: `docs/backend-architecture-prd.md`

- [x] Replace legacy field lists and flows with the approved four-step model and explicit precedence rules.
- [x] Search for legacy product-field references and remove executable references.
- [x] Run backend pytest and Ruff.
- [x] Run frontend ESLint and production build.
- [x] Audit the final API shape, SQLite migration, generated package, and static references against every approved requirement.
