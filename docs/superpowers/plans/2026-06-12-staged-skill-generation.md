# Staged Skill Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic SkillIR model call with validated workflow, knowledge, quality, and semantic-trace stages while adding honest long-running progress and cancellation.

**Architecture:** Add focused stage result models and a deterministic assembler in a new backend module. The orchestrator owns stage retries, progress, cancellation checks, and event persistence; PydanticSkillAgents owns the four structured model calls. The existing candidate evaluation, quality repair, revision, rendering, and packaging pipeline remains downstream of the assembled SkillIR.

**Tech Stack:** Python 3.13, Pydantic 2, PydanticAI, FastAPI, SQLite, pytest, React 19, TypeScript, Tailwind CSS 4, Vitest.

---

### Task 1: Stage Contracts And Deterministic Assembly

**Files:**
- Create: `backend/app/staged_generation.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/spec_builder.py`
- Test: `backend/tests/test_staged_generation.py`

- [ ] **Step 1: Write failing stage contract tests**

Add tests that construct `WorkflowGenerationResult`, `KnowledgeGenerationResult`,
`QualityGenerationResult`, and `SemanticTraceResult`, then assert
`assemble_skill_ir()` restores SkillSpec identity, hard restrictions, acceptance
criteria, special cases, knowledge, related Skills, file paths, and complete
deterministic trace entries.

```python
def test_assemble_skill_ir_restores_authoritative_facts_and_traces():
    ir = assemble_skill_ir(brief, spec, workflow, knowledge, quality, semantic)
    assert ir.skill.name == spec.identity.skillName
    assert ir.quality.hardRestrictions == spec.hardRestrictions
    assert {item.specItemId for item in ir.specTrace} >= {
        "identity.name", "special-cases.01", "acceptance.01"
    }
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
/Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q backend/tests/test_staged_generation.py
```

Expected: import failure because `app.staged_generation` does not exist.

- [ ] **Step 3: Implement stage models, validators, assembler, and deterministic trace builder**

Use dedicated Pydantic models with only stage-owned fields. Implement:

```python
def validate_workflow_result(result, spec) -> list[str]: ...
def validate_knowledge_result(result, spec) -> list[str]: ...
def validate_quality_result(result, spec) -> list[str]: ...
def validate_semantic_trace_result(result, spec, ir) -> list[str]: ...
def assemble_skill_ir(brief, spec, workflow, knowledge, quality, semantic) -> SkillIR: ...
```

Deterministic trace ownership must include identity, platforms, knowledge,
supplements, pitfalls, restrictions, special cases, concrete file contracts,
related Skills, acceptance criteria, and rendered package paths. Semantic trace
must be restricted to activation and required workflow-stage IDs.

- [ ] **Step 4: Run focused tests**

Run the Task 1 command and expect all tests to pass.

### Task 2: Four Focused Agent Calls

**Files:**
- Modify: `backend/app/agent.py`
- Modify: `backend/app/prompts.py`
- Modify: `backend/tests/test_pydantic_agents.py`
- Modify: `backend/tests/agent_support.py`

- [ ] **Step 1: Write failing agent tests**

Add tests proving each method requests and returns only its dedicated output:

```python
workflow, metadata = agents.generate_workflow(brief, spec, provider, [])
knowledge, _ = agents.generate_knowledge(brief, spec, workflow, provider, [])
quality, _ = agents.generate_quality(brief, spec, workflow, knowledge, provider, [])
trace, _ = agents.generate_semantic_trace(brief, spec, assembled_ir, provider, [])
```

Assert distinct prompt versions and typed outputs.

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
/Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q backend/tests/test_pydantic_agents.py
```

Expected: missing staged agent methods.

- [ ] **Step 3: Implement the staged agent interface**

Add protocol methods and focused prompts:

```python
generate_workflow(...)
generate_knowledge(...)
generate_quality(...)
generate_semantic_trace(...)
```

Each prompt receives SkillSpec, relevant previously validated stage output, and
retry feedback. Keep the existing `repair()` and judge methods unchanged.

- [ ] **Step 4: Update deterministic test agents**

Make `build_test_agents()` and orchestrator scripted agents return valid stage
results without invoking a real provider.

- [ ] **Step 5: Run focused tests**

Run the Task 2 test command and expect all tests to pass.

### Task 3: Stage Retry Orchestration And Unlimited Application Budget

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/orchestrator.py`
- Modify: `backend/app/state_machine.py`
- Modify: `backend/app/storage.py`
- Modify: `backend/tests/test_quality_orchestrator.py`
- Modify: `backend/tests/test_state_machine.py`

- [ ] **Step 1: Write failing orchestration tests**

Cover:

```python
def test_failed_workflow_stage_retries_only_workflow_three_total_attempts(): ...
def test_completed_stage_is_not_regenerated_when_knowledge_retries(): ...
def test_stage_failure_never_creates_candidate_attempt_or_package(): ...
def test_large_token_usage_does_not_stop_quality_loop(): ...
def test_cancel_request_interrupts_before_next_stage(): ...
```

Assert stage events include attempt number, errors, provider metadata, duration,
and result status.

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
/Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q backend/tests/test_quality_orchestrator.py backend/tests/test_state_machine.py
```

Expected: staged fields and methods are missing.

- [ ] **Step 3: Add generation progress metadata**

Add backward-compatible defaults to `GenerationResult`:

```python
stageAttempt: int = 0
stageMaxAttempts: int = 3
completedStages: list[str] = Field(default_factory=list)
stageMessage: str = ""
cancelRequested: bool = False
stageAttempts: list[GenerationStageAttempt] = Field(default_factory=list)
```

- [ ] **Step 4: Implement stage execution**

Implement an orchestrator helper that:

- Sets the current stage and milestone.
- Tries the stage at most three total times.
- Sends validation errors into the next call.
- Saves a `GenerationStageAttempt` and run event after every attempt.
- Checks persisted cancellation before and after every provider call.
- Fails with a stage-specific code after the third failed attempt.

- [ ] **Step 5: Remove aggregate budget termination**

Delete calls to `_budget_limit_reason()` and remove the helper. Keep token, cost,
and duration metadata for diagnostics. Keep provider request timeouts and model
output limits.

- [ ] **Step 6: Run focused tests**

Run the Task 3 command and expect all tests to pass.

### Task 4: Cancellation API

**Files:**
- Modify: `backend/app/service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api_pipeline.py`

- [ ] **Step 1: Write failing API tests**

Add tests for:

```http
POST /api/generations/{generation_id}/cancel
```

Assert a queued or active run returns `cancelRequested=true`, becomes
`interrupted` at a safe boundary, and never exposes a download.

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
/Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q backend/tests/test_api_pipeline.py
```

Expected: HTTP 404 for the cancel route.

- [ ] **Step 3: Implement cancellation**

Add `SkillForgeService.cancel_generation()` and the API route. Terminal runs
remain unchanged. Waiting or queued runs interrupt immediately; active runs set
the persisted flag and stop after the current provider call.

- [ ] **Step 4: Run focused tests**

Run the Task 4 command and expect all tests to pass.

### Task 5: Staged Waiting UI

**Files:**
- Modify: `skill-forge/src/types/index.ts`
- Modify: `skill-forge/src/data/index.ts`
- Modify: `skill-forge/src/api.ts`
- Modify: `skill-forge/src/components/GenerationLoading.tsx`
- Modify: `skill-forge/src/components/PipelineProgress.tsx`
- Modify: `skill-forge/src/components/GenerationLoading.test.tsx`
- Modify: `skill-forge/src/pages/CreatePage.tsx`

- [ ] **Step 1: Write failing component tests**

Test stage labels, retry copy, quality-first waiting copy, completed stages,
legacy payload fallback, and cancel button callback:

```tsx
expect(screen.getByText('正在构建工作流骨架')).toBeInTheDocument();
expect(screen.getByText('第 2/3 次尝试')).toBeInTheDocument();
await user.click(screen.getByRole('button', { name: '停止生成' }));
expect(onCancel).toHaveBeenCalled();
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
cd skill-forge && npm test -- GenerationLoading.test.tsx
```

Expected: missing staged props and cancel control.

- [ ] **Step 3: Implement typed API and UI**

Add staged fields to `GenerationResult`, `cancelGeneration()`, stage milestone
definitions, an animated current-stage treatment, completed-stage states,
retry copy, quality-first explanation, and a cancel button. Use transform and
opacity animations and preserve reduced-motion behavior.

- [ ] **Step 4: Wire CreatePage**

Pass all stage metadata to `GenerationLoading`. Disable repeated cancellation,
show “正在停止” after the request, and continue polling until the backend
reports `interrupted`.

- [ ] **Step 5: Run frontend tests and build**

```bash
cd skill-forge && npm test
cd skill-forge && npm run build
```

Expected: all tests pass and Vite build exits 0.

### Task 6: Full Regression And Visual Verification

**Files:**
- Modify only files required by failures discovered in this task.

- [ ] **Step 1: Run the full backend suite**

```bash
/Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q backend/tests
```

Expected: all tests pass.

- [ ] **Step 2: Run static checks**

```bash
/Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m compileall -q backend/app backend/tests
git diff --check
```

Expected: exit 0.

- [ ] **Step 3: Run the app and inspect the generation screen**

Start the local backend and frontend, open the generation flow in the in-app
browser, and verify desktop and narrow layouts. Confirm stage progression,
retry rendering, waiting animation, cancel control, and no overlap with the
SkillSpec panel.

- [ ] **Step 4: Review scope and final diff**

Confirm the immutable SkillSpec, revision history, three quality repair rounds,
official validation, final selection, and package format remain unchanged.
