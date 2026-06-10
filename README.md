# NovaFDE

NovaFDE 是一个纯本地运行的专业 Agent Skill 生成平台。用户通过四步 Web 表单提供业务事实、流程、规则、易错点和补充信息，后端使用 PydanticAI 生成结构化 `SkillIR`，再由确定性 renderer 输出 `SKILL.md` 与三端安装说明。

## 核心能力

- Claude Code、Codex、Hermes / OpenClaw 三端适配。
- description 按触发条件生成，而不是功能摘要。
- 使用文件系统进行渐进式上下文组织。
- 只补充 Agent 未知的业务或领域信息。
- 以建议和验证为主，避免无必要的硬性限制。
- 支持多步骤工作流、分支、验证和失败恢复。
- Validation、Activation、Implementation 三类质量评测。
- 初始候选后最多三轮定向修复，始终选择历史最高分安全候选。
- 缺少不可推断的业务事实时暂停原任务并请求用户补充。
- 未达到严格门槛但达到最低可用线时返回明确标识的低分包。
- 生成记录、候选、评分、Trace 和易错点库只保存在本地 SQLite。

## 本地架构

| 层 | 技术 |
|---|---|
| 前端 | React 19、TypeScript、Vite、Tailwind CSS |
| 后端 | FastAPI、PydanticAI、Pydantic |
| 数据库 | 本地 SQLite |
| 产物 | 本地文件系统与 zip |
| 密钥 | 系统钥匙串优先，本地加密密钥库兜底 |

NovaFDE 没有服务器模式、远程数据库、远程任务队列或中央遥测。除用户自行配置的模型 Provider 外，程序不会上传草稿、评分、日志或产物。

## 安装

要求 Python 3.10+、Node.js 18+ 和 npm 9+。

```bash
sh scripts/install.sh
```

配置 Provider 的协议、URL 和模型：

```bash
sh scripts/setup-llm.sh
```

随后启动程序，在 Web 设置页输入 API Key 并执行连接测试。Key 不写入 SQLite 或 `.env`。

```bash
sh scripts/run.sh
```

- 前端：<http://127.0.0.1:5173>
- 后端：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/docs>

## 验证

```bash
.venv/bin/python -m pytest backend/tests -q
cd skill-forge
npm run build
npm run lint
npm test
```

真实模型质量评测应独立运行，不进入普通单元测试。生产生成流程不会在模型失败时生成静态替代作品。

## 目录

```text
backend/          FastAPI、PydanticAI Agent、质量闭环和 SQLite
skill-forge/      React Web 应用
scripts/          本地安装、启动、诊断和 Provider 配置
docs/             产品与技术 PRD
config/           不含明文密钥的本地 Provider 配置
backend/.data/    SQLite、加密密钥库和生成产物
```
