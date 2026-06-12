---
name: skill-creator
description: Use when designing or improving an Agent Skill that needs clear activation, an executable workflow, and progressive disclosure through files.
---

# Skill Creator Methodology

This is NovaFDE's audited, versioned local snapshot of the Skill Creator
methodology used by the Generation Agent. It is reference material only. The
Generation Agent returns structured SkillIR and never writes final files.

## Core Principles

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
- Do not move generic knowledge into references merely to hide unnecessary
  content. Omit knowledge a capable Agent already has.

### Degrees of Freedom

- Use precise instructions when the task is fragile or safety-sensitive.
- Use guidance rather than rigid rules when multiple approaches can succeed.
- Hard restrictions must come from authoritative user or system requirements.

### Validation

- Check that the Skill can be activated from its description alone.
- Check every workflow step for executability and verifiability.
- Check that every referenced file exists and has a clear loading purpose.
- Check that the final package follows the Agent Skills specification.

## NovaFDE Boundary

The Skill Creator methodology may decide structure, wording, workflow detail,
file placement, and derived Skill handoffs. It may not:

- change the read-only SkillSpec;
- invent user-specific business facts;
- add hard restrictions;
- write the final package directly;
- bypass deterministic validation, rendering, or packaging.
