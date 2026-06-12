# Minimal Input and System-Managed Spec Trace Design

## Goal

Allow a user to generate a useful, standard Skill from a small set of real
business facts without exposing internal Spec Trace failures or requiring the
user to design the full workflow.

The system must treat user facts as authoritative, let agents infer reasonable
implementation details, and deterministically own all trace bookkeeping.

## Product Principles

1. Ask the user only for facts the system cannot responsibly invent.
2. Let agents elaborate execution details, examples, checks, and supporting
   knowledge.
3. Never delegate deterministic identifiers, IR paths, rendered paths, or
   package bookkeeping to a language model.
4. Do not fail a user task because internal trace metadata is missing or stale
   when the underlying content can be repaired deterministically.
5. Block delivery only for unsafe output, invalid package structure, missing
   required user facts, or content below the minimum usable quality line.

## Input Model

### Required

- Display name
- Usage scenario: when the Skill should be used
- Desired outcome: what successful completion should produce
- At least one target platform

The technical Skill name remains derived from the display name and can be
edited in advanced settings if the current product supports it.

### Optional Enhancements

- Rough process
- Completion criteria
- Special cases
- Professional information
- Mandatory rules
- Pitfalls and examples
- Related Skills
- Supplemental context

Optional fields improve specificity but must not be prerequisites for starting
generation.

## Derived SkillSpec

Before model generation, the server creates an immutable SkillSpec revision.
Every field records whether it came from the user, the system, or a derived
default.

When optional fields are absent:

- Rough process becomes three derived stages: clarify inputs and success,
  execute the requested work, and validate the deliverable against the desired
  outcome.
- Completion criteria becomes a derived acceptance statement tied to the
  desired outcome.
- Special cases become standard operational branches such as missing inputs,
  unverifiable information, and unsafe actions.
- Baseline restrictions are always supplied by the system.
- File requirements are derived conservatively from the requested work.

Derived content is a starting contract, not a claim about unknown business
facts. It must use generic operational language and must not invent company
names, policies, thresholds, credentials, or domain evidence.

Workflow stages, acceptance criteria, restrictions, and special cases are
stored as structured SkillSpec items with stable IDs and a `source` value of
`user`, `system`, or `derived`. The existing plain `specialCases` field remains
readable for historical revisions, while new revisions use structured special
case items as the authoritative representation.

## Generation Architecture

### Stage 1: Requirement Planner

Inputs:

- Required user facts
- Optional enhancements
- Immutable SkillSpec

Outputs:

- Workflow outline
- Assumptions that are safe to infer
- Missing facts that would materially affect correctness

If a missing fact is essential and cannot be handled with a safe fallback, the
system asks one concise user question. Questions are grouped so the user is not
interrupted repeatedly.

### Stage 2: Workflow Generator

Produces executable steps containing:

- Purpose
- Action
- Inputs
- Outputs
- Validation
- Failure handling

It may elaborate the derived process, but it cannot remove or contradict user
facts and mandatory rules.

### Stage 3: Knowledge and Quality Generator

Produces:

- Incremental knowledge
- Reference or script needs
- Pitfalls and counterexamples
- Freedom level
- Validation checklist
- Soft guidance

The server injects authoritative restrictions and acceptance criteria after
the model response.

### Stage 4: Deterministic Assembly

The server assembles the final SkillIR from stage outputs and restores all
authoritative facts:

- Identity and platforms
- User statements
- Derived SkillSpec statements
- Mandatory restrictions
- Acceptance criteria
- Special-case branches

The language model does not output `specTrace`.

### Stage 5: System-Managed Trace

The server builds the complete trace from the assembled IR and SkillSpec:

- Stable spec item IDs
- Canonical IR paths
- Final rendered file paths
- Distinct workflow step ownership

`special-cases.01`, acceptance criteria, restrictions, knowledge, file
contracts, and identity mappings are always deterministic.

Activation paths are fixed. Required workflow stages are bound by stable
SkillSpec order to the corresponding generated workflow steps. The workflow
validator checks that each step implements its bound stage before assembly.
Failure to implement a stage causes a focused workflow retry; it never becomes
a missing Trace entry.

There is no semantic Trace Agent and no model-generated `specTrace`.

### Stage 6: Validation and Repair

Validation is split into two categories.

Internal contract repair:

- Missing trace entry
- Stale IR path
- Wrong rendered path
- Duplicate deterministic trace ID
- Missing authoritative statement in its canonical IR section

These issues trigger deterministic repair and revalidation. They are not
shown to the user and do not consume an Agent repair round.

Content repair:

- Incomplete workflow
- Weak activation description
- Unusable instructions
- Unsafe behavior
- Contradiction with user facts

These issues use focused Agent repair with a maximum of three attempts per
affected stage.

## Delivery Policy

### Deliver Normally

- Strict quality gate passed.
- Package and security validation passed.
- All system-managed trace checks passed after automatic repair.

### Deliver With Suggestions

- Package is safe and usable.
- Strict quality target was not fully reached.
- Remaining issues are improvements, not correctness blockers.

The UI labels this result as "可用，建议优化" and provides actionable
suggestions. It must not present internal validator codes.

### Ask the User

Only when an unknown fact changes the meaning or safety of the Skill and no
generic fallback is responsible. Examples include:

- The exact system or data source the workflow must operate on
- A required approval boundary
- A business-specific definition of completion when the desired outcome is
  too ambiguous to derive one

### Fail

Only when:

- Required input remains invalid after normalization
- No safe package can be produced
- Generated files cannot be rendered or packaged
- Security validation blocks delivery
- Model/provider execution cannot complete after configured retries

Spec Trace metadata alone is never a terminal user-facing failure.

## User Experience

### Form

The form is divided into:

- Necessary information
- Optional quality enhancements

Necessary information contains the four required inputs. Optional enhancement
sections are collapsed by default and explain how each field improves output.

### Waiting State

The user sees product-level stages:

1. Understanding the requirement
2. Building the workflow
3. Adding knowledge and quality controls
4. Checking and packaging

The UI shows retries as quality refinement, supports cancellation, and states
that quality is prioritized over a fixed task duration.

### Errors

User-facing messages describe an action or missing fact. Codes such as
`SPEC-TRACE-001` and `SPEC-TRACE-002` remain available only in diagnostics and
run events.

## Persistence and Diagnostics

Persist:

- SkillSpec revisions and source classification
- Stage attempts and validation feedback
- Deterministic trace repair events
- User questions and answers
- Final delivery classification

Diagnostics may retain validator codes for developers, but API fields intended
for the primary UI return normalized user messages.

## Migration

Existing drafts remain valid. Empty optional fields no longer generate blocking
brief validation issues.

Existing generations and packages remain readable. New generations use a new
prompt bundle and trace-builder version. No historical SkillSpec revision is
rewritten.

## Testing Strategy

### Contract Tests

- A draft containing only required fields produces a complete SkillSpec.
- Derived process, acceptance, and special cases are marked as derived.
- User-provided optional fields override derived defaults.

### Trace Tests

- Empty model trace output is irrelevant because models no longer own trace.
- The generation Agent contract contains no `specTrace` output.
- `special-cases.01` is always generated when special cases exist.
- Acceptance, restriction, knowledge, file, identity, and platform traces use
  canonical paths.
- Invalid or missing trace metadata is rebuilt before validation.
- Trace repair does not consume Agent repair rounds.

### Pipeline Tests

- Minimal input can produce a downloadable Skill.
- Missing essential business facts result in one grouped user question.
- Nonessential quality issues produce a usable result with suggestions.
- Security and package failures remain blocking.

### UI Tests

- Only four fields are visibly required.
- Optional enhancements are clearly separated.
- Internal validator codes never appear in the normal result flow.
- Waiting state, cancellation, and usable-with-suggestions states render
  correctly on desktop and mobile.

## Success Criteria

- A user can start generation using only the four required inputs.
- A valid special case can never fail solely because
  `special-cases.01` is absent.
- Spec Trace coverage is deterministic and independent of model compliance.
- Internal trace repair happens before candidate quality scoring.
- Safe, usable Skills are delivered even when optional enhancements were not
  supplied.
- The primary UI never instructs the user to ask Skill Creator or Repair Agent
  to repair trace metadata.
