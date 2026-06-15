---
name: skill-creator
description: Use when designing or improving an Agent Skill that needs clear activation, an executable workflow, and progressive disclosure through files.
---

# Skill Creator Methodology

This is NovaFDE's audited, versioned local snapshot of the Skill Creator
methodology used by the Generation Agent. It is reference material only. The
Generation Agent returns structured SkillIR and never writes final files.

## Core Principles

### Discovery Inputs

- Derive the Skill from concrete user intents, not from a generic category.
- Use the brief to identify purpose, scope, trigger scenarios, required
  outcome, completion criteria, domain knowledge, mandatory rules, pitfalls,
  output formats, and related Skills.
- Ask for user input only when a user-specific business fact is missing and
  cannot be inferred. Do not ask the user to design Skill internals such as
  references, scripts, assets, trigger syntax, or validation strictness.
- Treat optional brief fields as quality signals, not as padding
  requirements. If they are empty, omit the corresponding generated content
  unless it can be safely derived from purpose and outcome.

### Activation

- The frontmatter description is the primary triggering mechanism. It must
  state both what the Skill does AND the specific contexts for when to use it.
- Write the "when" as enumerated concrete user intents and trigger keywords,
  not as an introduction or marketing summary. Pattern:
  `<what it does>. Use when users ask to <action 1>, <action 2>, <action 3>,
  or mention <keyword, keyword, keyword>.`
- Enumerate the words users will actually type, in the language they will
  type them: product names, brand names, domain nouns, action verbs, and
  common aliases or synonyms.
- Agents tend to under-trigger Skills. Make the description deliberately
  "pushy": cover adjacent intents and add coverage for cases where the user
  means this task without naming it explicitly.
- All "when to use" information goes in the description, never only in the
  body. Do not use the description as a summary of the body.

### Workflow Design

- Turn the user's rough process into an ordered, coordinated workflow.
- Every step needs a purpose, action, input, output, verification, and recovery.
- Add decision points only where the execution genuinely branches.
- Define completion in observable terms.
- Describe collaboration with related Skills as explicit handoffs.

### Progressive disclosure

- Skills load in three levels: metadata (name + description, always in
  context), SKILL.md body (loaded when the Skill triggers), and bundled
  resources (loaded only when needed).
- Keep SKILL.md focused on the instructions needed to execute the workflow,
  well under 500 lines.
- Put detailed domain knowledge, policies, schemas, examples, and pitfalls in
  references that the Agent loads only when needed, and point to each
  reference from SKILL.md with guidance on when to read it.
- Put stable repeatable automation in scripts.
- Put templates and reusable materials in assets.
- Every referenced resource needs a concrete purpose and a one-level path
  directly under references/, scripts/, or assets/. Do not emit bare folders,
  nested navigation chains, placeholder files, or unused optional directories.
- Do not move generic knowledge into references merely to hide unnecessary
  content. Omit knowledge a capable Agent already has.

### Degrees of Freedom

- Use high freedom when multiple approaches can succeed, judgment matters, and
  the Skill should provide principles or checklists.
- Use medium freedom when a preferred pattern exists but parameters or context
  vary; provide templates, pseudocode, or ordered defaults with escape hatches.
- Use low freedom when operations are fragile, safety-sensitive, repetitive, or
  need deterministic behavior; prefer explicit commands or scripts.
- Hard restrictions must come from authoritative user or system requirements.

### Resource Selection

- Choose references/ when detailed knowledge is needed sometimes: schemas,
  policies, domain facts, examples, pitfalls, or API details.
- Choose scripts/ when the same operation would otherwise be regenerated, when
  consistency matters, or when failure handling should be deterministic.
- Choose assets/ when the Skill must reuse templates, sample files, images,
  fonts, or other output materials.
- Use one strong default tool or approach per task. Mention alternatives only
  when a specific branch requires them, such as OCR for scanned PDFs.

### Validation

- Check that the Skill can be activated from its description alone.
- Check every workflow step for executability and verifiability.
- Check that every referenced file exists and has a clear loading purpose.
- Check that the final package follows the Agent Skills specification.
- Check for anti-patterns: vague names, summary-only descriptions, too many
  equal tool options, inconsistent terminology, time-sensitive instructions
  without a stable fallback, generic knowledge, unused resources, and deep or
  unsafe paths.

## NovaFDE Boundary

The Skill Creator methodology may decide structure, wording, workflow detail,
file placement, and derived Skill handoffs. It may not:

- change the read-only SkillSpec;
- invent user-specific business facts;
- add hard restrictions;
- write the final package directly;
- bypass deterministic validation, rendering, or packaging.
