# NovaFDE

> AI Skill 可视化构建工具 — 通过表单向导快速创建、校验和打包 AI Agent Skill

---

## 🚀 快速开始

### 环境要求

- **Python** 3.10+
- **Node.js** 18+（推荐 20+）
- **npm** 9+

### 一键安装

```bash
git clone https://github.com/YOUR_USERNAME/novafde.git
cd novafde
sh scripts/install.sh
```

安装脚本会自动：
- 创建 Python 虚拟环境
- 安装后端（FastAPI）和前端（React + shadcn/ui）依赖
- 初始化本地目录和 `.env` 模板

### 启动项目

```bash
sh scripts/run.sh
```

- 前端：http://localhost:5173
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 🤖 AI Agent 一键安装指南

如果你是 AI Agent（如 Claude、GPT、Cursor 等），请按以下步骤自动完成项目初始化：

```bash
# 1. 进入项目目录
cd novafde

# 2. 环境检查（确认 Python 和 Node 可用）
sh scripts/doctor.sh

# 3. 一键安装依赖
sh scripts/install.sh

# 4. 配置 LLM Provider（交互式，选择 Claude 或 OpenAI 兼容）
sh scripts/setup-llm.sh

# 5. 启动前后端
sh scripts/run.sh
```

**配置文件位置：**
- `.env` — API Key 环境变量（`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`）
- `config/providers.local.json` — Provider 配置（协议、Base URL、模型）

**非交互式配置（环境变量）：**
```bash
export SKILLFORGE_PROVIDER_PROTOCOL=openai-compatible
export SKILLFORGE_PROVIDER_NAME="My Provider"
export SKILLFORGE_PROVIDER_BASE_URL="http://localhost:11434"
export SKILLFORGE_PROVIDER_MODEL="llama3"
export SKILLFORGE_PROVIDER_KEY_ENV="OPENAI_API_KEY"
sh scripts/setup-llm.sh
```

---

## 📦 项目结构

```
novafde/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # API 路由和应用入口
│   │   ├── models.py         # 数据模型（Pydantic）
│   │   ├── service.py        # 业务逻辑
│   │   └── settings.py       # 配置加载
│   ├── tests/                # 后端测试
│   └── requirements.txt
├── skill-forge/              # React 前端
│   ├── src/
│   │   ├── components/       # UI 组件（shadcn/ui + 自定义）
│   │   │   ├── ui/           # shadcn/ui 组件（Button, Card, Input...）
│   │   │   └── steps/        # 7 步创建向导组件
│   │   ├── pages/            # 页面（Create, History, Rules, Settings, LocalRun）
│   │   ├── hooks/            # 自定义 Hooks
│   │   ├── api.ts            # API 客户端
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── data/             # 常量和配置数据
│   │   └── index.css         # Tailwind 主题和基础样式
│   ├── package.json
│   └── vite.config.ts
├── config/                   # 运行时配置
│   └── providers.local.json  # Provider 配置
├── logs/                     # 运行日志
├── scripts/                  # 运维脚本
│   ├── install.sh            # 一键安装
│   ├── run.sh                # 启动前后端
│   ├── doctor.sh             # 环境检查
│   ├── setup-llm.sh          # 配置 LLM Provider
│   └── clean-artifacts.sh    # 清理生成产物
└── README.md
```

---

## 🛠 技术栈

### 前端

| 技术 | 用途 |
|------|------|
| React 19 | UI 框架 |
| TypeScript 6 | 类型安全 |
| Vite 8 | 构建工具 |
| Tailwind CSS 4 | 样式方案 |
| shadcn/ui | 组件库（基于 Radix UI） |
| lucide-react | 图标库 |

### 后端

| 技术 | 用途 |
|------|------|
| FastAPI | Web 框架 |
| Pydantic | 数据校验 |
| SQLite | 本地存储 |
| uvicorn | ASGI 服务器 |

---

## 🎨 模式说明

启动后首次使用需要选择运行模式：

- **本地模式** — 前后端都在本机运行，通过 `localhost` 访问，适合开发和测试
- **服务器模式** — 部署到远程服务器供团队使用，通过域名/IP 访问

模式选择会记住，之后可在设置页切换。

---

## ⚙️ 常用命令

| 命令 | 说明 |
|------|------|
| `sh scripts/install.sh` | 安装所有依赖 |
| `sh scripts/run.sh` | 启动前后端 |
| `sh scripts/doctor.sh` | 检查环境是否就绪 |
| `sh scripts/setup-llm.sh` | 配置 LLM Provider |
| `sh scripts/clean-artifacts.sh --yes` | 清理生成产物和日志 |

### 前端开发

```bash
cd skill-forge
npm run dev          # 启动开发服务器
npm run build        # 构建生产包
npm run lint         # 代码检查
npm run preview      # 预览生产包
```

---

## 📋 支持的 LLM Provider

| 协议 | Provider | 默认模型 |
|------|----------|----------|
| Claude | Anthropic | claude-sonnet-4-20250514 |
| OpenAI Compatible | OpenAI / Ollama / vLLM / 其他 | llama3 |

---

## 🔧 环境变量

`.env` 文件示例：

```env
# Claude
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI 兼容
OPENAI_API_KEY=sk-...

# 自定义（可选）
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

---

## 📄 License

MIT