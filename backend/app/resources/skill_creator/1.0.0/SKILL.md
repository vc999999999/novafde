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

- The frontmatter description states what the Skill does and when to use it.
- Include concrete user intents and trigger language.
- Do not use the description as a summary of the body.

### Workflow Design

- Turn the user's rough process into an ordered, coordinated workflow.
- Every step needs a purpose, action, input, output, verification, and recovery.
- Add decision points only where the execution genuinely branches.
- Define completion in observable terms.
- Describe collaboration with related Skills as explicit handoffs.

### Progressive disclosure

- Keep SKILL.md focused on the instructions needed to execute the workflow.
- Put detailed domain knowledge, policies, schemas, examples, and pitfalls in
  references that the Agent loads only when needed.
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
