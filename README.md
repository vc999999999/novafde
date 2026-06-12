# NovaFDE

**AI Skill 可视化构建工具 — 通过四步表单向导快速创建、校验和打包 AI Agent Skill**

*Build, validate, and package AI Agent Skills through an intuitive 4-step visual wizard with PydanticAI quality loop.*

[![GitHub Stars](https://img.shields.io/github/stars/vc999999999/novafde?style=for-the-badge&logo=github&logoColor=white)](https://github.com/vc999999999/novafde)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](https://opensource.org/license/mit/)
[![React](https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS_4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![shadcn/ui](https://img.shields.io/badge/shadcn%2Fui-000000?style=for-the-badge&logo=shadcnui&logoColor=white)](https://ui.shadcn.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PydanticAI](https://img.shields.io/badge/PydanticAI-000000?style=for-the-badge&logo=python&logoColor=white)](https://ai.pydantic.dev/)
[![Quick Start](https://img.shields.io/badge/Quick_Start-Ready_To_Go-yellow?style=for-the-badge&logo=rocket)](#-quick-start--快速开始)

---

## 中文

### 这是什么？

NovaFDE 是一个**纯本地运行的 AI Skill 生成平台**，帮助开发者通过四步 Web 表单向导快速创建符合规范的 `SKILL.md` 文件。

后端先把 `SkillBrief` 确定性构建为不可变、带 SHA256 修订记录的 `SkillSpec`，再使用版本化的官方 Skill Creator 方法论生成 `SkillIR 1.1`。最终由确定性 renderer 输出 `SKILL.md` 与三端安装说明，并通过固定版本 `skills-ref==0.1.1` 校验。

### 核心功能

| 功能 | 说明 |
|------|------|
| **四步可视化向导** | 基本信息 → 用途描述 → 知识库 → 补充信息 |
| **PydanticAI 质量循环** | 初始候选后最多三轮定向修复，始终选择历史最高分安全候选 |
| **SDD 规格驱动生成** | 每次生成绑定只读 SkillSpec 修订、SHA256 和逐项 Spec Trace |
| **官方 Skill Creator** | 使用仓库内版本化、可审计的官方方法论快照设计 SkillIR |
| **官方规范校验** | 每个候选和最终包都由本地 `skills-ref` 校验，不依赖运行时网络 |
| **三类质量评测** | Validation、Activation、Implementation 评分 |
| **智能补充** | 缺少不可推断的业务事实时暂停并请求用户补充 |
| **三端适配** | Claude Code / Codex / Hermes-OpenClaw |
| **实时评分** | 侧边栏显示每个步骤和总体完成百分比 |
| **校验报告** | 自动生成质量校验，标记阻塞项和警告 |
| **历史记录** | 查看、重新生成、下载过往 Skill 包 |
| **纯本地运行** | 所有数据保存在本地 SQLite，无远程服务 |
| **密钥安全** | 系统钥匙串优先，本地加密密钥库兜底 |

### 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | React 19 + TypeScript 6 |
| 构建工具 | Vite 8 |
| 样式方案 | Tailwind CSS 4 + shadcn/ui |
| 图标库 | Lucide React |
| 后端框架 | FastAPI + PydanticAI |
| 数据存储 | 本地 SQLite |
| 产物管理 | 本地文件系统与 zip |

### 项目结构

```
novafde/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # API 路由和应用入口
│   │   ├── models.py         # 数据模型（Pydantic）
│   │   ├── service.py        # 业务逻辑
│   │   ├── orchestrator.py   # PydanticAI 质量循环编排器
│   │   ├── spec_builder.py   # 确定性 SkillSpec 与稳定追踪 ID
│   │   ├── creator_skill.py  # 版本化 Skill Creator 快照加载
│   │   ├── validator.py      # Spec Trace 与官方 Agent Skills 校验
│   │   ├── quality.py        # 质量评分引擎
│   │   └── settings.py       # 配置加载
│   ├── tests/                # 后端测试（包含质量循环测试）
│   └── requirements.txt
├── skill-forge/              # React 前端
│   ├── src/
│   │   ├── components/       # UI 组件（shadcn/ui + 自定义）
│   │   │   ├── ui/           # shadcn/ui 组件（Button, Card, Input...）
│   │   │   └── steps/        # 4 步创建向导组件
│   │   ├── pages/            # 页面（Create, History, Rules, Settings, LocalRun）
│   │   ├── hooks/            # 自定义 Hooks
│   │   ├── api.ts            # API 客户端
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── data/             # 常量和配置数据
│   │   └── index.css         # Tailwind 主题和基础样式
│   ├── package.json
│   └── vite.config.ts
├── config/                   # 运行时配置
│   └── providers.local.json  # Provider 配置（不含明文密钥）
├── logs/                     # 运行日志
├── scripts/                  # 运维脚本
│   ├── install.sh            # 一键安装
│   ├── run.sh                # 启动前后端
│   ├── doctor.sh             # 环境检查
│   └── setup-llm.sh          # 配置 LLM Provider
└── README.md
```

---

## English

### What is NovaFDE?

NovaFDE is a **pure local AI Skill generation platform** that helps developers quickly create `SKILL.md` files through a 4-step web form wizard.

The backend deterministically builds an immutable, SHA256-versioned `SkillSpec` before using a versioned official Skill Creator methodology to generate `SkillIR 1.1`. A deterministic renderer writes the package, and pinned `skills-ref==0.1.1` validates every candidate and final artifact.

### Core Features

| Feature | Description |
|---------|-------------|
| **4-Step Visual Wizard** | Basic Info → Purpose → Knowledge Base → Supplement |
| **PydanticAI Quality Loop** | Up to 3 rounds of targeted fixes after initial candidates, always selects highest-scoring safe candidate |
| **Specification-Driven Generation** | Every attempt is bound to an immutable SkillSpec revision, SHA256, and item-level Spec Trace |
| **Versioned Skill Creator** | Uses an audited local snapshot of the official methodology |
| **Official Validation** | Validates every candidate and final package locally with pinned `skills-ref` |
| **Three Quality Evaluations** | Validation, Activation, and Implementation scoring |
| **Smart Supplements** | Pauses and requests user input when business facts cannot be inferred |
| **Multi-Platform Support** | Claude Code / Codex / Hermes-OpenClaw |
| **Real-time Scoring** | Sidebar displays completion percentage for each step |
| **Validation Reports** | Auto-generates quality checks with blocking items and warnings |
| **History** | View, regenerate, download past Skill packages |
| **Pure Local** | All data saved in local SQLite, no remote services |
| **Secure Keys** | System keychain preferred, local encrypted keystore fallback |

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend Framework | React 19 + TypeScript 6 |
| Build Tool | Vite 8 |
| Styling | Tailwind CSS 4 + shadcn/ui |
| Icons | Lucide React |
| Backend Framework | FastAPI + PydanticAI |
| Data Storage | Local SQLite |
| Artifacts | Local filesystem and zip |

### Project Structure

```
novafde/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── main.py           # API routes and app entry
│   │   ├── models.py         # Data models (Pydantic)
│   │   ├── service.py        # Business logic
│   │   ├── orchestrator.py   # PydanticAI quality loop orchestrator
│   │   ├── spec_builder.py   # Deterministic SkillSpec and stable trace IDs
│   │   ├── creator_skill.py  # Versioned Skill Creator snapshot loader
│   │   ├── validator.py      # Spec Trace and official Agent Skills validation
│   │   ├── quality.py        # Quality scoring engine
│   │   └── settings.py       # Configuration loading
│   ├── tests/                # Backend tests (including quality loop tests)
│   └── requirements.txt
├── skill-forge/              # React frontend
│   ├── src/
│   │   ├── components/       # UI components (shadcn/ui + custom)
│   │   │   ├── ui/           # shadcn/ui components (Button, Card, Input...)
│   │   │   └── steps/        # 4-step creation wizard components
│   │   ├── pages/            # Pages (Create, History, Rules, Settings, LocalRun)
│   │   ├── hooks/            # Custom Hooks
│   │   ├── api.ts            # API client
│   │   ├── types/            # TypeScript type definitions
│   │   ├── data/             # Constants and configuration data
│   │   └── index.css         # Tailwind theme and base styles
│   ├── package.json
│   └── vite.config.ts
├── config/                   # Runtime configuration
│   └── providers.local.json  # Provider config (no plaintext keys)
├── logs/                     # Runtime logs
├── scripts/                  # Operations scripts
│   ├── install.sh            # One-click install
│   ├── run.sh                # Start frontend and backend
│   ├── doctor.sh             # Environment check
│   └── setup-llm.sh          # Configure LLM Provider
└── README.md
```

---

## 🚀 Quick Start / 快速开始

### 环境要求 / Prerequisites

- **Python** 3.10+
- **Node.js** 18+（推荐 20+）
- **npm** 9+

### 一键安装 / One-Click Install

```bash
git clone https://github.com/vc999999999/novafde.git
cd novafde
sh scripts/install.sh
```

安装脚本会自动：/ The install script automatically:
- 创建 Python 虚拟环境 / Creates Python virtual environment
- 安装后端（FastAPI）和前端（React + shadcn/ui）依赖 / Installs backend and frontend dependencies
- 初始化本地目录和 `.env` 模板 / Initializes local directories and `.env` template

### 配置 LLM Provider / Configure LLM Provider

```bash
sh scripts/setup-llm.sh
```

支持的 Provider：/ Supported providers:

| 协议 / Protocol | Provider | 默认模型 / Default Model |
|-----------------|----------|--------------------------|
| Claude | Anthropic | claude-sonnet-4-20250514 |
| OpenAI Compatible | OpenAI / Ollama / vLLM / 其他 | llama3 |

随后在 Web 设置页输入 API Key 并执行连接测试。Key 不写入 SQLite 或 `.env`。

Then enter API Key in web settings page and run connection test. Keys are not stored in SQLite or `.env`.

### 启动项目 / Start Project

```bash
sh scripts/run.sh
```

- 前端 / Frontend：http://localhost:5173
- 后端 / Backend：http://localhost:8000
- API 文档 / API Docs：http://localhost:8000/docs

---

## 🤖 AI Agent 一键安装指南 / AI Agent Quick Setup

如果你是 AI Agent（如 Claude、GPT、Cursor 等），请按以下步骤自动完成项目初始化：

If you are an AI Agent (Claude, GPT, Cursor, etc.), follow these steps to automatically initialize the project:

```bash
# 1. 进入项目目录 / Enter project directory
cd novafde

# 2. 环境检查（确认 Python 和 Node 可用）/ Environment check
sh scripts/doctor.sh

# 3. 一键安装依赖 / One-click install dependencies
sh scripts/install.sh

# 4. 配置 LLM Provider（交互式）/ Configure LLM Provider (interactive)
sh scripts/setup-llm.sh

# 5. 启动前后端 / Start frontend and backend
sh scripts/run.sh
```

**配置文件位置 / Config file locations：**
- `.env` — API Key 环境变量 / API Key environment variables
- `config/providers.local.json` — Provider 配置（协议、Base URL、模型）/ Provider config

**非交互式配置（环境变量）/ Non-interactive configuration (environment variables)：**
```bash
export SKILLFORGE_PROVIDER_PROTOCOL=openai-compatible
export SKILLFORGE_PROVIDER_NAME="My Provider"
export SKILLFORGE_PROVIDER_BASE_URL="http://localhost:11434"
export SKILLFORGE_PROVIDER_MODEL="llama3"
export SKILLFORGE_PROVIDER_KEY_ENV="OPENAI_API_KEY"
sh scripts/setup-llm.sh
```

---

## ⚙️ 常用命令 / Common Commands

| 命令 / Command | 说明 / Description |
|----------------|-------------------|
| `sh scripts/install.sh` | 安装所有依赖 / Install all dependencies |
| `sh scripts/run.sh` | 启动前后端 / Start frontend and backend |
| `sh scripts/doctor.sh` | 检查环境是否就绪 / Check environment readiness |
| `sh scripts/setup-llm.sh` | 配置 LLM Provider / Configure LLM Provider |
| `sh scripts/clean-artifacts.sh --yes` | 清理生成产物和日志 / Clean artifacts and logs |

### 前端开发 / Frontend Development

```bash
cd skill-forge
npm run dev          # 启动开发服务器 / Start dev server
npm run build        # 构建生产包 / Build production
npm run lint         # 代码检查 / Lint code
npm test             # 运行测试 / Run tests
npm run preview      # 预览生产包 / Preview production
```

### 后端验证 / Backend Verification

```bash
.venv/bin/python -m pytest backend/tests -q
```

真实模型质量评测应独立运行，不进入普通单元测试。/ Real model quality evaluations should run separately, not in regular unit tests.

---

## 🔧 环境变量 / Environment Variables

`.env` 文件示例 / `.env` file example：

```env
# Claude
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI 兼容 / OpenAI compatible
OPENAI_API_KEY=sk-...

# 自定义（可选）/ Custom (optional)
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

---

## 📄 License

MIT
