# NovaFDE Frontend

React 19 + TypeScript + Vite frontend for the NovaFDE Skill builder.

The creation flow contains four user-input steps:

1. Basic information
2. Purpose and process
3. Knowledge, mandatory rules, pitfalls, and related Skills
4. Optional free-form supplement

Detailed trigger wording, workflow fields, file structure, and output standards are derived by the backend Skill Creator Agent.

## Commands

```bash
npm install
npm run dev
npm run lint
npm run build
npm test
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`.
