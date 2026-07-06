# NovaFDE

A local-first Skill factory for agents.

[![License](https://img.shields.io/badge/license-MIT-0e7c73.svg)](https://opensource.org/license/mit/)
[![React](https://img.shields.io/badge/React-19-18181b.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-local-18181b.svg)](https://fastapi.tiangolo.com/)
[![PydanticAI](https://img.shields.io/badge/PydanticAI-quality_loop-18181b.svg)](https://ai.pydantic.dev/)

NovaFDE turns a rough workflow description into an installable Agent Skill package. You describe what the skill is for, when it should trigger, what domain knowledge matters, and what must never be violated. NovaFDE builds a versioned SkillSpec, generates a structured SkillIR, renders `SKILL.md` plus resources, validates the package, scores it, repairs it when needed, and gives you a zip you can install into Claude Code, Codex, or Hermes/OpenClaw.

Everything runs on your machine. Drafts, history, artifacts, provider config, logs, and generated packages stay local.

## Why

Writing a good Agent Skill is less about producing Markdown and more about preserving constraints.

A useful skill needs a trigger description that actually activates, a workflow an agent can execute, domain knowledge that is loaded only when needed, and validation strong enough to catch vague or fragile output. In practice, hand-written skills often drift: the description becomes a summary, business rules get softened, references become clutter, and a regeneration fixes one issue while breaking another.

NovaFDE makes skill creation repeatable:

- users provide business facts, not file-structure decisions;
- the backend turns those facts into an immutable `SkillSpec` with SHA256 history;
- generation is split into workflow, knowledge, and quality stages;
- every candidate is rendered deterministically before evaluation;
- validation, activation, and implementation scores drive up to three repair rounds;
- the highest-scoring safe candidate is selected instead of blindly trusting the last model response.

## See It

NovaFDE has five working surfaces:

| Surface | What it is for |
|---|---|
| Create | Four-step wizard for building a skill from business intent |
| History | Reopen, inspect, regenerate, and download previous packages |
| Rules | Review the local quality rules used during generation |
| Settings | Configure and test Claude or OpenAI-compatible providers |
| Local Run | Copyable install, setup, run, doctor, and cleanup commands |

The normal path is intentionally short:

```text
Basic info -> Purpose and workflow -> Knowledge and rules -> Supplement -> Generate
```

If the model or validator finds that a user-specific business fact is missing, generation pauses and asks for a targeted supplement. Otherwise there is no chat loop.

## How It Works

A successful generation is usually one user input pass plus five AI calls:

```text
User draft
  -> normalize draft
  -> build SkillSpec
  -> AI: workflow stage
  -> AI: knowledge/files stage
  -> AI: quality controls stage
  -> render package
  -> deterministic validation
  -> AI: activation judge
  -> AI: implementation judge
  -> aggregate score
  -> package zip
```

If quality gates fail, NovaFDE can run up to three repair rounds. Each round uses a focused repair call, then re-renders and re-evaluates the candidate. The default maximum is therefore roughly:

```text
initial 5 AI calls + 3 repair rounds * 3 AI calls = 14 AI calls
```

Deterministic steps such as normalization, spec building, rendering, path safety, zip creation, and `skills-ref` validation do not call a model.

## Install

Requirements:

- Python 3.10+
- Node.js 18+ recommended
- npm 9+

```bash
git clone https://github.com/vc999999999/novafde.git
cd novafde
sh scripts/install.sh
```

The installer creates `.venv`, installs backend dependencies from `backend/requirements.txt`, installs frontend dependencies in `skill-forge/`, and initializes local data directories.

## AI Copy: One-Pass Local Setup

Copy this command when you want an AI coding agent or terminal helper to install dependencies, write the default local model config, and run diagnostics from the project root:

```bash
sh scripts/install.sh && sh scripts/setup-llm.sh && sh scripts/doctor.sh
```

Or copy this prompt into Codex, Claude Code, or another local coding agent:

```text
You are in the NovaFDE repository root.

Set up the project locally:
1. Confirm the current directory contains README.md, backend/, skill-forge/, and scripts/.
2. Run: sh scripts/install.sh
3. Run: sh scripts/setup-llm.sh
4. Run: sh scripts/doctor.sh
5. If diagnostics pass, tell me to add and test the API key in the Settings page, or export the configured key environment variable before running the app.

Safety rules:
- Do not ask me to paste a plaintext API key into chat.
- Do not print any API key value.
- If a command fails, stop and report the failed command, the error output, and any relevant files under logs/.

After setup, start NovaFDE with:
sh scripts/run.sh
```

For an OpenAI-compatible provider, replace step 3 with:

```bash
export SKILLFORGE_PROVIDER_PROTOCOL=openai-compatible
export SKILLFORGE_PROVIDER_NAME="local-ollama"
export SKILLFORGE_PROVIDER_BASE_URL="http://localhost:11434"
export SKILLFORGE_PROVIDER_MODEL="llama3"
export SKILLFORGE_PROVIDER_KEY_ENV="OPENAI_API_KEY"
sh scripts/setup-llm.sh
```

## Configure a Model

Create a local provider config:

```bash
sh scripts/setup-llm.sh
```

By default this writes `config/providers.local.json` for Anthropic-compatible Claude settings. You can also configure an OpenAI-compatible provider non-interactively:

```bash
export SKILLFORGE_PROVIDER_PROTOCOL=openai-compatible
export SKILLFORGE_PROVIDER_NAME="local-ollama"
export SKILLFORGE_PROVIDER_BASE_URL="http://localhost:11434"
export SKILLFORGE_PROVIDER_MODEL="llama3"
export SKILLFORGE_PROVIDER_KEY_ENV="OPENAI_API_KEY"
sh scripts/setup-llm.sh
```

API keys are not stored in plain SQLite records. Use the Settings page to add and test the key through the local keychain/encrypted secret flow, or provide the configured environment variable yourself.

## Run

```bash
sh scripts/run.sh
```

Then open:

- Frontend: <http://127.0.0.1:5173>
- Backend: <http://127.0.0.1:8000>
- API docs: <http://127.0.0.1:8000/docs>

Logs are written to `logs/backend.log` and `logs/frontend.log`.

## Commands

| Command | Purpose |
|---|---|
| `sh scripts/install.sh` | Install Python and frontend dependencies |
| `sh scripts/setup-llm.sh` | Write local model provider config |
| `sh scripts/run.sh` | Start FastAPI and Vite together |
| `sh scripts/doctor.sh` | Check imports, directories, frontend metadata, and provider config |
| `sh scripts/clean-artifacts.sh --yes` | Remove generated artifacts and logs |

Frontend development:

```bash
cd skill-forge
npm run dev
npm run build
npm run preview
```

## Architecture

```text
novafde/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI routes
│   │   ├── service.py          # app-level orchestration
│   │   ├── orchestrator.py     # staged generation and quality loop
│   │   ├── spec_builder.py     # immutable SkillSpec and trace IDs
│   │   ├── renderer.py         # deterministic SKILL.md/package rendering
│   │   ├── validator.py        # validation, spec compliance, skills-ref checks
│   │   ├── quality.py          # score aggregation and candidate selection
│   │   ├── storage.py          # local drafts, history, and generated artifacts
│   │   └── resources/          # audited Skill Creator methodology snapshots
├── skill-forge/
│   ├── src/components/         # wizard, reports, controls, page chrome
│   ├── src/pages/              # Create, History, Rules, Settings, Local Run
│   └── src/index.css           # light minimal teal theme
├── scripts/                    # install, run, doctor, setup, cleanup
├── config/                     # local provider config, created at runtime
└── logs/                       # runtime logs, created at runtime
```

The backend never asks the model to write arbitrary files or zip archives directly. Models return typed structures; NovaFDE renders, validates, and packages them through local code.

## Quality Model

NovaFDE evaluates each candidate across three dimensions:

| Dimension | What it checks |
|---|---|
| Validation | structure, paths, frontmatter, package shape, SkillSpec trace, official `skills-ref` compatibility |
| Activation | whether `description` will trigger in the right situations and avoid neighboring intents |
| Implementation | whether the rendered skill is concise, actionable, clear, and uses progressive disclosure well |

Default strict gates require no blockers, high validation score, sufficient activation/implementation scores, preserved hard rules, safe paths, and traceable required spec items. If strict delivery fails but a safe candidate exists, NovaFDE can return a clearly marked degraded package with the full quality report.

## Design

The app is deliberately calm: light canvas, neutral surfaces, teal as the only strong accent, compact cards, predictable navigation, and dense but readable operational screens. It is a tool for repeated work, not a landing page.

The README style is inspired by the concise product storytelling and direct Usage/Design sections in [tw93/Kami](https://github.com/tw93/Kami), while keeping NovaFDE's local architecture and validation details explicit.

## Current Boundaries

NovaFDE is local-first and single-user. It does not include team workspaces, hosted sync, billing, marketplace publishing, or automatic installation into every agent runtime. Generated skills are packaged for export; you choose where to install them.

Model quality depends on the provider you configure. The deterministic validator catches structure and safety issues, while activation and implementation judges provide quality scoring rather than absolute proof that every future agent run will behave perfectly.

## License

MIT

> Last maintained: 2026-07-06
