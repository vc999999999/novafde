# Staged Skill Generation Design

## Goal

Improve generated `SKILL.md` quality and stability by replacing the single
large SkillIR generation call with a staged backend pipeline. Keep the user
workflow, immutable SkillSpec revisions, quality gates, and package format
unchanged.

Quality takes priority over fixed completion time. The application will not
stop a run because of an aggregate token, cost, or elapsed-time budget.
Provider-level context windows, output limits, request timeouts, and retry
behavior still apply.

## User Experience

The visible workflow remains:

1. Fill in the creation form.
2. Start generation.
3. Wait while the staged pipeline runs.
4. Supply missing user-specific facts when requested.
5. Download a validated package.

The generation screen will show an animated stage timeline instead of a generic
single progress sequence. It will display:

- Current stage and a short explanation.
- Completed stages.
- Current stage attempt, including retry 1 or retry 2.
- Determinate progress based on completed pipeline stages, not estimated model
  duration.
- A patient-waiting message that explains quality-first processing.
- A user-controlled cancel action.

Animation must respect `prefers-reduced-motion`. Cancellation must preserve
completed attempts and mark the generation interrupted without packaging an
incomplete candidate.

## Pipeline

The backend pipeline is:

1. **Normalize and build SkillSpec**
   - Preserve the existing deterministic normalization, immutable revision, and
     SHA256 behavior.
2. **Generate workflow foundation**
   - Produce identity-dependent activation content, overview, objective,
     executable workflow steps, decisions, failure handling, verification, and
     Skill handoffs.
   - Validate workflow completeness and required workflow-stage coverage before
     continuing.
3. **Generate knowledge and files**
   - Produce incremental knowledge, pitfalls, examples, related Skills,
     progressive-loading references, scripts, assets, and authored reference
     files.
   - Validate required knowledge and file contracts before continuing.
4. **Generate quality controls**
   - Produce freedom level, soft guidance, and validation checklist.
   - Restore immutable hard restrictions deterministically.
   - Validate acceptance criteria and restrictions before continuing.
5. **Assemble SkillIR**
   - Merge the three stage outputs into one `SkillIR 1.1`.
   - Restore authoritative identity and user facts.
6. **Build and validate Spec Trace**
   - Programmatically build mappings whose IR paths are unambiguous.
   - Request semantic mappings only for workflow stages and activation content
     that cannot be proven by exact values alone.
   - Require complete, unique, valid IR paths and real rendered paths.
7. **Render and evaluate**
   - Render the package deterministically.
   - Run structural, security, official Agent Skills, activation, and
     implementation checks.
8. **Targeted repair**
   - Repair only failed stages or failed semantic mappings.
   - Preserve the existing maximum of three quality repair rounds after initial
     staged generation.
9. **Select and package**
   - Preserve best-candidate selection, degraded-package rules, revision-bound
     final validation, manifest generation, and zip creation.

## Stage Contracts

Each model stage gets a dedicated Pydantic output model rather than the full
SkillIR schema:

- `WorkflowGenerationResult`
- `KnowledgeGenerationResult`
- `QualityGenerationResult`
- `SemanticTraceResult`

Each result contains only fields owned by that stage. No stage may overwrite
fields owned by another stage or modify SkillSpec.

The assembler is deterministic. It creates the complete SkillIR from validated
stage results and authoritative SkillSpec facts. This reduces output size,
prevents unrelated rewrites, and gives failures a precise ownership boundary.

## Trace Ownership

The program owns trace entries that can be derived without semantic judgment:

- Identity and target platforms.
- Incremental knowledge and user supplements.
- Pitfalls that retain stable IDs or exact source content.
- Hard restrictions.
- Special cases restored verbatim.
- Required file contracts with concrete file paths.
- Related Skills.
- Acceptance criteria.
- Rendered paths after rendering.

The semantic trace stage owns:

- Mapping each required workflow stage to the step that implements it.
- Mapping activation usage to the generated trigger description.
- Mapping activation outcome to the workflow objective when semantic expansion
  prevents exact comparison.

The validator remains authoritative. A generated mapping cannot pass merely
because its path exists; the mapped content must implement the corresponding
spec item.

## Retry And Failure Handling

Each generation stage gets an initial attempt and at most two retries.

- Retry only the failed stage.
- Feed validation errors from that stage into its retry prompt.
- Do not regenerate stages that already passed.
- Do not assemble or package partial stage output.
- After the second retry fails, mark the generation failed with a stage-specific
  failure code and actionable message.

Provider fallback remains available within each stage. Provider request
timeouts remain configurable because an unbounded network call is not a useful
quality feature.

Quality repair rounds remain separate from stage retries:

- Stage retries establish a structurally complete initial candidate.
- Quality repair rounds improve a complete candidate after judges evaluate it.

## State And Persistence

Persist stage results and stage attempts so interrupted runs are inspectable.
Automatic resume after a backend process restart is outside this implementation
scope: the active generation is marked interrupted, validated stage results are
retained for inspection, and no partial model response is reused.

Add stage metadata to run events:

- Stage key.
- Attempt number.
- Provider and model.
- Input and output token usage for observability only.
- Duration.
- Validation result.
- Failure category.

Token, cost, and elapsed totals remain visible metadata but no longer stop a
run. Remove aggregate budget checks from candidate processing and remove the
fixed application run-duration cutoff. Do not remove per-request provider
timeouts or model output limits.

## Frontend Progress Model

Expose sufficient generation state through the existing generation response:

- `currentStage`
- `stageAttempt`
- `stageMaxAttempts`
- `completedStages`
- `stageMessage`
- `cancelRequested`

Progress is mapped to durable milestones:

- Spec ready: 10%
- Workflow ready: 28%
- Knowledge and files ready: 46%
- Quality controls ready: 58%
- Trace ready: 68%
- Initial render and validation ready: 76%
- Judge evaluation ready: 86%
- Repair or selection: 92%
- Packaging complete: 100%

Retries do not move progress backward. The UI animates activity within the
current milestone rather than showing fake percentage movement.

## Compatibility

- Existing drafts and historical generations remain readable.
- Existing generations without staged metadata use the current fallback
  progress display.
- API consumers continue receiving a complete final SkillIR and the same
  downloadable package format.
- SkillSpec schema version, revision semantics, and SHA256 calculation remain
  unchanged.
- Existing quality policies and maximum three post-generation repair rounds
  remain unchanged.

## Testing

Backend tests must cover:

- Every stage output schema.
- Stage-only retry and the two-retry limit.
- No regeneration of completed stages.
- Failure without partial packaging.
- Deterministic assembly.
- Deterministic and semantic trace ownership.
- Full trace coverage and invalid semantic mapping rejection.
- Provider fallback per stage.
- Removal of aggregate token, cost, and duration termination.
- Cancellation.
- Existing supplement revision and best-candidate behavior.
- Full API pipeline and final package validation.

Frontend tests must cover:

- Stage labels and progress milestones.
- Retry state.
- Backward compatibility for old generation payloads.
- Cancel action.
- Reduced-motion behavior where practical.

## Acceptance Criteria

- Large SkillIR generation is split into the four model-owned outputs described
  above.
- A stage failure retries only that stage and never more than twice.
- The application does not terminate a run because of aggregate token, cost, or
  elapsed-time budgets.
- The UI gives continuous, honest feedback throughout long runs.
- Spec Trace reaches complete valid coverage before judge evaluation.
- Incomplete stage output can never be packaged.
- All existing backend and frontend tests pass, with new staged-generation
  regression coverage added.
