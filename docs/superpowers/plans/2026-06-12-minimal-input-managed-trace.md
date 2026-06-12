# Minimal Input and Managed Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a standard, downloadable Skill from four required inputs while making Spec Trace entirely deterministic and invisible as a user-facing failure source.

**Architecture:** Normalize missing optional workflow facts into source-tagged SkillSpec defaults, then run focused workflow, knowledge, and quality generation. Assemble authoritative facts on the server and build every trace entry from stable SkillSpec order and canonical IR paths; no model returns `specTrace`.

**Tech Stack:** FastAPI, Pydantic v2, PydanticAI, SQLite, pytest, React 19, TypeScript, Vitest, Tailwind CSS.

---

### Task 1: Preserve Completed Staged Waiting Work

**Files:**
- Modify: `backend/app/orchestrator.py`
- Modify: `backend/tests/test_quality_orchestrator.py`
- Modify: `skill-forge/src/api.ts`
- Modify: `skill-forge/src/components/GenerationLoading.tsx`
- Modify: `skill-forge/src/components/GenerationLoading.test.tsx`
- Modify: `skill-forge/src/components/PipelineProgress.tsx`
- Modify: `skill-forge/src/data/index.ts`
- Modify: `skill-forge/src/pages/CreatePage.tsx`
- Modify: `skill-forge/src/types/index.ts`

- [ ] **Step 1: Run the focused verification**

Run:

```bash
PYTHONPATH=backend /Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q \
  backend/tests/test_quality_orchestrator.py \
  backend/tests/test_api_pipeline.py \
  backend/tests/test_state_machine.py
cd skill-forge && npm test && npm run lint && npm run build
```

Expected: backend tests pass; Vitest, ESLint, and Vite build pass.

- [ ] **Step 2: Commit the verified staged waiting work**

```bash
git add backend/app/orchestrator.py backend/tests/test_quality_orchestrator.py \
  skill-forge/src/api.ts skill-forge/src/components/GenerationLoading.tsx \
  skill-forge/src/components/GenerationLoading.test.tsx \
  skill-forge/src/components/PipelineProgress.tsx skill-forge/src/data/index.ts \
  skill-forge/src/pages/CreatePage.tsx skill-forge/src/types/index.ts
git commit -m "feat: show staged quality-first generation progress"
```

### Task 2: Derive a Complete SkillSpec From Minimal Input

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/normalizer.py`
- Modify: `backend/app/spec_builder.py`
- Test: `backend/tests/test_skill_spec.py`
- Test: `backend/tests/test_api_pipeline.py`

- [ ] **Step 1: Write failing tests for minimal input**

Add tests proving:

```python
def test_minimal_input_derives_workflow_acceptance_and_special_cases():
    # displayName, usage, desiredOutcome, targetPlatforms only
    # PROCESS-001 is a warning, not blocking
    # SkillSpec contains three derived workflow stages
    # acceptance.01 source is derived
    # special-cases.01 source is derived

def test_user_optional_fields_override_derived_defaults():
    # user process/completion/special cases remain exact and source=user
```

Add an API test that generates from a draft with empty `process`,
`completionCriteria`, and `specialCases`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
PYTHONPATH=backend /Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q \
  backend/tests/test_skill_spec.py::test_minimal_input_derives_workflow_acceptance_and_special_cases \
  backend/tests/test_skill_spec.py::test_user_optional_fields_override_derived_defaults \
  backend/tests/test_api_pipeline.py::test_generate_from_minimal_required_input
```

Expected: FAIL because process is blocking and structured special cases/default stages do not exist.

- [ ] **Step 3: Implement source-tagged derived defaults**

Add:

```python
class SpecialCaseSpec(BaseModel):
    id: str
    statement: str
    source: SpecItemSource = "user"
    required: bool = True
```

Add `specialCaseItems` to `SkillSpec`. In `build_skill_spec`, use user process
when present, otherwise derive exactly three safe generic stages. Use the user
special case when present, otherwise derive missing-input, unverifiable-data,
and unsafe-action branches. Keep `specialCases` populated for backward
compatibility.

Change `PROCESS-001` to a warning and describe that the workflow will be
derived.

- [ ] **Step 4: Run tests and verify GREEN**

Run the three tests from Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/normalizer.py backend/app/spec_builder.py \
  backend/tests/test_skill_spec.py backend/tests/test_api_pipeline.py
git commit -m "feat: derive skill spec from minimal input"
```

### Task 3: Replace Semantic Trace Generation With Deterministic Trace Assembly

**Files:**
- Modify: `backend/app/staged_generation.py`
- Modify: `backend/app/spec_builder.py`
- Test: `backend/tests/test_staged_generation.py`
- Test: `backend/tests/test_validator.py`

- [ ] **Step 1: Write failing deterministic trace tests**

Replace semantic trace tests with tests proving:

```python
ir = assemble_skill_ir(brief, spec, workflow, knowledge, quality)
trace = {item.specItemId: item for item in ir.specTrace}

assert trace["activation.usage"].irPaths == ["skill.description"]
assert trace["activation.outcome"].irPaths == ["workflow.objective"]
assert trace["workflow.stage.01"].irPaths == ["workflow.steps[0]"]
assert trace["special-cases.01"].irPaths[0].startswith("workflow.decisionPoints[")
assert missing_trace_ids(ir, spec) == []
```

Add a validator test that removes or corrupts trace metadata, calls
`enforce_spec_contract`, renders the package, and verifies no
`SPEC-TRACE-001/002` blocker remains.

- [ ] **Step 2: Run tests and verify RED**

Expected: FAIL because assembly still requires `SemanticTraceResult` and only
repairs a subset of deterministic traces.

- [ ] **Step 3: Implement complete deterministic trace builder**

Delete `SemanticTraceItem`, `SemanticTraceResult`, and semantic validation.
Change `assemble_skill_ir` to accept only workflow, knowledge, and quality
results. Build identity, activation, ordered workflow, special case,
knowledge, pitfall, restriction, file, related-skill, and acceptance traces
from canonical paths.

Extend `enforce_spec_contract` so every deterministic requirement is rebuilt,
not only special cases and acceptance criteria. Duplicate deterministic IDs
are collapsed to one canonical entry.

- [ ] **Step 4: Run staged generation and validator tests**

```bash
PYTHONPATH=backend /Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q \
  backend/tests/test_staged_generation.py backend/tests/test_validator.py \
  backend/tests/test_skill_spec.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/staged_generation.py backend/app/spec_builder.py \
  backend/tests/test_staged_generation.py backend/tests/test_validator.py
git commit -m "feat: build spec trace deterministically"
```

### Task 4: Remove the Trace Agent From the Runtime

**Files:**
- Modify: `backend/app/prompts.py`
- Modify: `backend/app/agent.py`
- Modify: `backend/app/orchestrator.py`
- Modify: `backend/app/models.py`
- Modify: `backend/tests/agent_support.py`
- Modify: `backend/tests/test_pydantic_agents.py`
- Modify: `backend/tests/test_quality_orchestrator.py`

- [ ] **Step 1: Write failing runtime tests**

Update tests to require:

```python
assert agents.workflow_calls == 1
assert agents.knowledge_calls == 1
assert agents.quality_calls == 1
assert not hasattr(agents, "generate_semantic_trace")
assert generation.completedStages == ["workflow", "knowledge", "quality"]
```

The previous missing semantic trace failure test becomes a success test proving
the package is still complete without model trace output.

- [ ] **Step 2: Run tests and verify RED**

Expected: FAIL because protocol, prompts, orchestrator, and fixtures still call
the semantic trace stage.

- [ ] **Step 3: Remove semantic trace runtime code**

Delete the semantic trace prompt/version, Agent protocol method, Pydantic agent,
orchestrator call, and `generating-trace` stage. Set the prompt bundle to the
workflow, knowledge, and quality versions only. Assemble the SkillIR directly
after quality generation.

- [ ] **Step 4: Run runtime tests**

```bash
PYTHONPATH=backend /Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q \
  backend/tests/test_pydantic_agents.py backend/tests/test_quality_orchestrator.py \
  backend/tests/test_api_pipeline.py backend/tests/test_state_machine.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts.py backend/app/agent.py backend/app/orchestrator.py \
  backend/app/models.py backend/tests/agent_support.py \
  backend/tests/test_pydantic_agents.py backend/tests/test_quality_orchestrator.py
git commit -m "refactor: remove model-generated spec trace"
```

### Task 5: Present Minimal Required Inputs and Product-Level Stages

**Files:**
- Modify: `skill-forge/src/components/steps/PurposeStep.tsx`
- Modify: `skill-forge/src/components/GenerationLoading.tsx`
- Modify: `skill-forge/src/components/PipelineProgress.tsx`
- Modify: `skill-forge/src/data/index.ts`
- Modify: `skill-forge/src/types/index.ts`
- Test: `skill-forge/src/components/GenerationLoading.test.tsx`
- Create: `skill-forge/src/components/steps/PurposeStep.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Tests must prove:

```tsx
expect(screen.getByText('可选质量增强')).toBeInTheDocument()
expect(screen.getByText('大致执行流程（可选）')).toBeInTheDocument()
expect(screen.getByText('特殊情况（可选）')).toBeInTheDocument()
expect(screen.queryByText('规格映射')).not.toBeInTheDocument()
expect(screen.getByText('检查与打包')).toBeInTheDocument()
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd skill-forge && npm test -- --run \
  src/components/steps/PurposeStep.test.tsx \
  src/components/GenerationLoading.test.tsx
```

Expected: FAIL because process still appears required and trace is still a
visible generation stage.

- [ ] **Step 3: Implement the minimal-input form and four product stages**

Keep usage and desired outcome prominent. Move process, completion criteria,
and special cases into a collapsed "可选质量增强" section. Replace technical
generation stages with:

- 理解需求
- 构建工作流
- 补全知识与质量
- 检查与打包

Do not display validator codes in the normal generation/result surface.

- [ ] **Step 4: Run UI tests, lint, and build**

```bash
cd skill-forge && npm test && npm run lint && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill-forge/src/components/steps/PurposeStep.tsx \
  skill-forge/src/components/steps/PurposeStep.test.tsx \
  skill-forge/src/components/GenerationLoading.tsx \
  skill-forge/src/components/GenerationLoading.test.tsx \
  skill-forge/src/components/PipelineProgress.tsx skill-forge/src/data/index.ts \
  skill-forge/src/types/index.ts
git commit -m "feat: simplify skill generation inputs"
```

### Task 6: Full Verification and Safe Integration

**Files:**
- Verify: entire repository
- Integrate: `/Users/vcbb/Documents/opc项目/novafde`

- [ ] **Step 1: Run the complete backend suite**

```bash
PYTHONPATH=backend /Users/vcbb/Documents/opc项目/novafde/.venv/bin/python -m pytest -q backend/tests
```

Expected: all tests pass.

- [ ] **Step 2: Run the complete frontend verification**

```bash
cd skill-forge && npm test && npm run lint && npm run build
```

Expected: all commands pass.

- [ ] **Step 3: Browser verification**

Verify desktop and 390px mobile layouts, minimal input generation, staged
waiting animation, cancellation, and absence of internal Spec Trace errors.

- [ ] **Step 4: Inspect the main worktree before integration**

The main worktree currently has an uncommitted
`skill-forge/src/pages/CreatePage.tsx`. Save its patch, compare it to the
feature branch, and reapply only nonconflicting user changes after integrating.
Do not overwrite or discard it.

- [ ] **Step 5: Integrate and push**

After tests pass, use the finishing-development-branch workflow. Merge the
feature branch into `main`, preserve the user's local change, rerun focused
verification in the main worktree, then push `main` to GitHub.
