# SkillForge 前端 PRD

## 1. 概述

**问题**：目标用户习惯通过 Web2.0 风格表单填写信息，但不熟悉如何手写高质量 Agent Skill。单靠聊天输入容易导致 Skill 结构不稳定、触发描述模糊、工作流缺失、校验不完整、三端路径适配混乱。

**方案**：建设一个单人使用的 Web 平台。用户主要通过结构化表单填写必要条件，再用一个聊天输入框补充细节；前端展示生成进度、Skill 文件预览、质量校验结果，并在通过校验后提供 zip 下载。

**成功指标**：

- 新用户能在 10 分钟内完成一次 Skill 生成并下载 zip。
- 至少 80% 的必要信息通过表单收集，而不是依赖纯聊天。
- 生成结果页能清晰展示 `SKILL.md`、`references/`、`scripts/`、`assets/` 和安装说明。
- 至少 90% 的生成任务在第一次生成后通过基础结构校验。
- 用户能在设置页完成 Claude 协议或 OpenAI-compatible 协议的大模型配置，并通过连接测试。
- 用户能在页面中看到本地安装、运行、配置 CLI 的 shell 命令说明。
- 页面支持桌面、平板、移动端完成完整流程。

## 2. 产品范围

### 包含

- 单人 Skill 生成流程。
- Web2.0 风格表单向导。
- 聊天补充输入框。
- Skill 文件树预览。
- `SKILL.md` 预览。
- 校验报告和修复建议。
- 生成 zip 下载。
- 单人历史记录。
- LLM Provider 配置界面，支持 Claude 协议和 OpenAI-compatible 协议。
- 本地安装、运行、配置 CLI 的命令说明页面。
- 草稿、生成中、校验中、失败、可下载等状态。

### 不包含

- 多人协作。
- 团队权限。
- 角色管理。
- 公共 marketplace。
- 在线发布社区。
- 计费系统。
- 实时共同编辑。

## 3. 目标用户

**主要用户**：个人开发者、自动化使用者、顾问、PM、运营型用户，了解自己的业务流程和经验规则，但不想直接手写 `SKILL.md`。

**用户诉求**：

- 把个人经验沉淀成可复用的 Agent Skill。
- 用表单降低生成 Skill 的门槛。
- 生成结构正确、流程完整、质量稳定的 Skill 文件夹。
- 支持 Claude Code、Codex、Hermes/OpenClaw 等平台路径。
- 通过校验器减少低质量输出。

## 4. 用户流程

1. 用户进入平台，点击创建新 Skill。
2. 用户填写基础信息、触发条件、工作流、上下文、易错点等表单。
3. 用户在聊天补充框中粘贴额外说明、经验、流程、SOP 或特殊要求。
4. 用户点击生成。
5. 前端展示阶段进度：归一化输入、拆解工作流、生成 Skill IR、渲染文件、校验、打包。
6. 用户查看文件树、`SKILL.md`、校验报告和平台安装说明。
7. 若有问题，用户回到表单修改或触发重新生成。
8. 校验通过后，用户下载 zip。

## 5. 信息架构

### 主导航

- **创建**：核心生成页面。
- **历史**：查看最近生成的 Skill 包。
- **规则**：查看当前启用的质量规则和易错点库。
- **设置**：模型供应商、协议、API Key、默认模型、默认语言、默认平台、存储模式等。
- **本地运行**：展示 `sh` 安装脚本、启动脚本、配置 CLI 和诊断命令。

### 创建页面表单分区

1. **基础信息**
   - Skill 显示名称。
   - Skill 文件夹名称。
   - 输出语言。
   - Skill 类型。
   - 目标平台：Claude Code、Codex、Hermes/OpenClaw、全部。

2. **触发条件**
   - `description` 触发描述生成器。
   - 正向触发场景。
   - 反向触发场景。
   - 用户常见说法。
   - 相关文件类型、工具、业务对象。

3. **工作流**
   - 工作流目标。
   - 步骤列表。
   - 决策分支。
   - 前置条件。
   - 失败处理。
   - 验证检查点。

4. **文件系统上下文**
   - 需要读取的文件或目录。
   - 是否需要 `references/`。
   - 是否需要 `scripts/`。
   - 是否需要 `assets/`。
   - 上下文加载规则。

5. **Agent 未知内容**
   - 行业规则。
   - 内部流程。
   - 个人经验。
   - 易错点。
   - 正例和反例。

6. **输出控制**
   - 自由度：高、中、低。
   - 是否允许硬性限制。
   - 校验严格度。
   - 是否生成安装说明。
   - 是否允许带 warning 下载。

7. **聊天补充**
   - 自由文本输入。
   - 粘贴 SOP、流程描述、业务规则。
   - 让 Agent 帮用户把补充内容归入表单字段。
   - 用户确认后才进入生成。

8. **预览和生成**
   - 信息完整度。
   - 缺失项提醒。
   - 生成进度。
   - 文件树预览。
   - 校验报告。
   - 下载按钮。

### 设置页面表单分区

1. **模型协议**
   - 协议类型：Claude 协议、OpenAI-compatible 协议。
   - Provider 名称。
   - Base URL。
   - API Key 或环境变量名称。
   - 默认模型 ID。
   - 生成模型、修复模型、校验辅助模型的选择。

2. **高级参数**
   - temperature。
   - max tokens。
   - timeout。
   - retry 次数。
   - 自定义 headers。
   - 是否启用流式返回。

3. **连接测试**
   - 测试当前 Provider 是否可用。
   - 显示模型列表读取结果或手动模型 ID 校验结果。
   - 显示失败原因：鉴权失败、base URL 错误、模型不存在、网络失败、协议不匹配。

4. **默认策略**
   - 默认用于 Skill 生成的 Provider。
   - 默认用于修复循环的 Provider。
   - 默认用于校验解释的 Provider。
   - 配置缺失时是否阻止生成。

### 本地运行页面分区

1. **一键安装**
   - 展示 `sh scripts/install.sh`。
   - 说明安装内容：前端依赖、后端依赖、数据库初始化、`.env` 模板。

2. **启动项目**
   - 展示 `sh scripts/run.sh`。
   - 显示前端地址、后端地址、日志位置。

3. **配置模型**
   - 展示 `sh scripts/setup-llm.sh`。
   - 说明如何配置 Claude 协议或 OpenAI-compatible 协议。

4. **CLI 命令**
   - 展示 `skillforge doctor`、`skillforge config set`、`skillforge dev`、`skillforge generate`、`skillforge validate`、`skillforge package` 等命令说明。
   - 提供复制按钮。
   - 标明哪些命令会写入本地配置。

## 6. 功能需求

### FR-1 表单向导

- 前端必须用多步骤表单引导用户填写 Skill 必要信息。
- 每个步骤必须显示当前完成度。
- 用户修改字段后必须自动保存草稿。
- 必填字段必须在生成前完成。
- 表单控件包括输入框、下拉框、多选 chip、开关、重复列表、长文本框。

### FR-2 触发条件构建器

- 前端必须帮助用户写出“触发条件式 description”，而不是摘要式 description。
- 触发条件必须拆成：
  - 用户意图；
  - 任务类型；
  - 输入对象；
  - 适用场景；
  - 不适用场景；
  - 用户常见说法。
- 当前端检测到 description 太空泛时，必须提醒用户。

### FR-3 工作流编辑器

- 用户可以新增、删除、复制、排序工作流步骤。
- 每个步骤至少包含：
  - 目的；
  - Agent 要做什么；
  - 需要什么输入；
  - 产出什么；
  - 如何验证；
  - 失败后怎么办。
- 用户可以添加条件分支，不需要写代码。

### FR-4 聊天补充框

- 聊天补充框不能替代表单。
- 用户补充的信息必须回填或关联到具体字段。
- 前端要展示“由聊天补充推断出的字段变化”。
- 用户可以接受、忽略或编辑这些推断。

### FR-5 生成进度

- 前端必须展示生成阶段：
  - 输入归一化；
  - 注入规则；
  - 工作流拆解；
  - 生成 Skill IR；
  - 渲染文件；
  - 质量校验；
  - zip 打包。
- 失败时必须显示失败阶段和可恢复动作。

### FR-6 Skill 预览

- 前端必须展示生成后的文件树。
- 前端必须展示 `SKILL.md` 预览。
- 如果生成了 `references/`、`scripts/`、`assets/`，必须显示其文件列表。
- 校验 warning 应尽量定位到对应字段或文件。

### FR-7 校验报告

- 校验项必须分为通过、警告、阻塞失败。
- 每个问题必须包含：
  - 规则 ID；
  - 问题描述；
  - 为什么重要；
  - 建议修复方式；
  - 是否阻止下载。
- 阻塞失败默认不能下载。

### FR-8 zip 下载

- 校验通过后，前端显示下载按钮。
- 下载卡片必须显示：
  - 包名；
  - 版本；
  - 生成时间；
  - 支持平台；
  - 文件数量；
  - 包大小。

### FR-9 单人历史记录

- 用户可以查看最近生成记录。
- 用户可以基于历史记录复制一个新草稿。
- MVP 可先使用本地浏览器缓存或单人后端存储。

### FR-10 LLM Provider 配置

- 用户必须能在设置页新增、编辑、删除 LLM Provider。
- Provider 必须支持两类协议：
  - Claude 协议；
  - OpenAI-compatible 协议。
- 每个 Provider 至少包含：
  - provider 名称；
  - protocol；
  - base URL；
  - API Key 来源；
  - 默认模型 ID；
  - timeout；
  - retry；
  - 是否启用。
- API Key 字段必须默认隐藏。
- 前端不得在普通列表中明文展示 API Key。
- 用户必须能将某个 Provider 设置为默认生成模型。
- 用户必须能为生成、修复、校验解释分别选择模型，未选择时使用默认模型。

### FR-11 Provider 连接测试

- 设置页必须提供“测试连接”按钮。
- 测试成功时显示协议、模型 ID、响应耗时。
- 测试失败时显示可操作的错误分类：
  - 缺少 API Key；
  - 鉴权失败；
  - base URL 无法访问；
  - 模型 ID 不存在；
  - 协议选择错误；
  - 网络超时。
- 未通过连接测试的 Provider 可以保存，但默认不应设为启用状态。

### FR-12 本地安装运行与 CLI 指引

- 前端必须提供本地运行页面，展示项目支持的 shell 脚本和 CLI 命令。
- 每条命令必须包含：
  - 命令文本；
  - 用途；
  - 是否安全可重复执行；
  - 会读取或写入哪些文件；
  - 常见失败原因。
- 命令必须支持复制。
- 页面必须展示推荐顺序：
  1. `sh scripts/install.sh`
  2. `sh scripts/setup-llm.sh`
  3. `sh scripts/run.sh`
  4. `skillforge doctor`
  5. `skillforge generate`

## 7. 体验要求

### 布局

- 桌面端：左侧表单，右侧指导、预览、校验状态。
- 平板端：上下堆叠，保留固定生成状态栏。
- 移动端：单列向导，校验结果折叠展示。

### 视觉风格

- 像专业工具，不像营销落地页。
- 信息密度适中，方便反复使用。
- 控件清晰，帮助文本短。
- 不做大面积装饰、过度动画和营销式 hero。

### 表单行为

- 有限选项用下拉框。
- 多平台、标签、易错点用 chip。
- 工作流步骤用可排序列表。
- 二元选项用开关。
- 长流程、领域知识、SOP 用长文本框。

### 可访问性

- 所有控件必须有文本 label。
- 错误不能只依赖颜色表达。
- 支持键盘完成主流程。
- 移动端不能出现横向滚动。

## 8. 验收标准

- 用户可以从空状态创建 Skill 草稿。
- 用户可以不使用聊天，仅靠表单完成生成。
- 用户可以用聊天补充上下文，并确认回填结果。
- 用户可以看到生成阶段进度。
- 用户可以查看 `SKILL.md` 和文件树。
- 用户可以查看校验失败和修复建议。
- 用户可以在校验通过后下载 zip。
- 用户可以在设置页配置 Claude 协议 Provider。
- 用户可以在设置页配置 OpenAI-compatible 协议 Provider。
- 用户可以测试 Provider 连接并看到明确结果。
- 用户可以查看安装、启动、模型配置和 CLI 命令说明。
- 页面不存在多人协作入口。

## 9. 前端数据契约

### SkillDraft

```json
{
  "id": "draft_123",
  "name": "product-research",
  "displayName": "Product Research",
  "language": "zh-CN",
  "targetPlatforms": ["claude-code", "codex", "hermes-openclaw"],
  "trigger": {
    "intent": "",
    "taskType": "",
    "positiveExamples": [],
    "negativeExamples": []
  },
  "workflow": {
    "objective": "",
    "steps": []
  },
  "context": {
    "references": [],
    "scripts": [],
    "assets": []
  },
  "knowledge": {
    "unknownToAgent": [],
    "pitfalls": []
  },
  "supplement": {
    "messages": []
  }
}
```

### GenerationStatus

```json
{
  "generationId": "gen_123",
  "status": "validating",
  "stage": "quality-gate",
  "progress": 72,
  "blockingIssues": 0,
  "warnings": 3
}
```

### ModelProviderConfig

```json
{
  "id": "provider_123",
  "name": "local-openai-compatible",
  "protocol": "openai-compatible",
  "baseUrl": "http://localhost:11434/v1",
  "apiKeySource": {
    "type": "env",
    "name": "OPENAI_API_KEY"
  },
  "defaultModel": "gpt-4.1",
  "timeoutMs": 120000,
  "retries": 2,
  "streaming": true,
  "enabled": true
}
```

### CliCommandHelp

```json
{
  "command": "sh scripts/setup-llm.sh",
  "purpose": "配置 Claude 协议或 OpenAI-compatible 协议的大模型 Provider。",
  "repeatable": true,
  "writes": [".env", "config/providers.local.json"],
  "commonFailures": ["missing shell permission", "invalid api key", "network timeout"]
}
```

## 10. 指标

- 表单完成率。
- 生成成功率。
- 平均生成到下载耗时。
- 第一次校验通过率。
- 工作流步骤非空比例。
- 高质量触发描述比例。
- Provider 连接测试成功率。
- 用户完成本地安装脚本步骤的比例。
- CLI 命令复制次数和失败反馈次数。
- 用户覆盖阻塞校验的次数。

## 11. 待确认问题

- MVP 历史记录只放浏览器，还是后端也存？
- 是否允许用户在下载前手动编辑生成的 `SKILL.md`？
- 规则页展示完整规则，还是只展示用户友好的说明？
- 是否默认生成三端安装说明？
- 是否允许一个生成任务同时使用不同 Provider 分别负责生成、修复和校验解释？
- 本地 CLI 名称使用 `skillforge` 还是更短的 `sf`？
