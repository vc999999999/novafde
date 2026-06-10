# SkillForge 后端与技术架构 PRD

## 1. 架构目标

后端把用户明确提供的业务事实保存为 `SkillDraft`，归一化为 `SkillBrief`，再调用项目封装的 Skill Creator Agent 生成标准 `SkillIR`。程序负责校验、渲染、路径安全、平台说明和 zip 打包。

核心原则：

- 用户决定业务事实，Agent 决定 Skill 标准。
- 强制规则优先级最高。
- 补充说明只作为低优先级上下文。
- Agent 输出结构化 IR，不直接写 zip。
- 文件渲染、校验和打包必须确定性执行。
- 旧 SQLite 草稿必须兼容迁移。

```mermaid
flowchart LR
  UI["四步用户输入"] --> API["Draft API"]
  API --> DB["SQLite JSON Payload"]
  DB --> Normalizer["Brief Normalizer"]
  Normalizer --> Brief["SkillBrief"]
  Brief --> Creator["Wrapped Skill Creator Agent"]
  Creator --> IR["SkillIR"]
  IR --> Validator["IR Validator"]
  Validator --> Repair["Repair Loop"]
  Repair --> IR
  Validator --> Renderer["Deterministic Renderer"]
  Renderer --> PackageValidator["Package Validator"]
  PackageValidator --> Adapter["Platform Adapter"]
  Adapter --> Zip["Zip Packager"]
```

## 2. SkillDraft

`SkillDraft` 只保存用户输入，不保存 Agent 派生结果。

```json
{
  "id": "draft_123",
  "status": "draft",
  "name": "product-research",
  "displayName": "Product Research",
  "targetPlatforms": ["claude-code", "codex", "hermes-openclaw"],
  "purpose": {
    "usage": "当产品团队需要系统化完成竞品调研时使用",
    "desiredOutcome": "形成可验证的产品研究结论",
    "process": [
      "明确研究范围",
      "整理证据",
      "形成结论"
    ],
    "completionCriteria": "每个结论都有来源",
    "specialCases": "来源不足时输出缺口清单"
  },
  "knowledge": {
    "professionalInformation": ["区分事实、推断和假设"],
    "mandatoryRules": ["不得把供应商自述直接当作第三方事实"],
    "pitfalls": [
      {
        "id": "pit_1",
        "description": "把营销话术当成事实",
        "goodExample": "明确标记信息来源",
        "badExample": "直接写成市场结论"
      }
    ],
    "relatedSkills": ["web-research"]
  },
  "supplement": {
    "content": "报告表达尽量简洁。"
  },
  "createdAt": 1780915200000,
  "updatedAt": 1780915200000
}
```

必填字段：

- `displayName`
- `targetPlatforms`
- `purpose.usage`
- `purpose.desiredOutcome`
- `purpose.process`
- `purpose.completionCriteria`
- `knowledge.professionalInformation`
- `knowledge.mandatoryRules`
- `knowledge.pitfalls`

可选字段：

- `purpose.specialCases`
- `knowledge.relatedSkills`
- `supplement.content`

## 3. SkillBrief

`Brief Normalizer` 清理空白、推断语言和文件需求，并保持来源优先级。

```json
{
  "skillName": "product-research",
  "displayName": "Product Research",
  "usage": "当产品团队需要系统化完成竞品调研时使用",
  "desiredOutcome": "形成可验证的产品研究结论",
  "roughProcess": ["明确研究范围", "整理证据", "形成结论"],
  "completionCriteria": "每个结论都有来源",
  "specialCases": "来源不足时输出缺口清单",
  "professionalInformation": ["区分事实、推断和假设"],
  "mandatoryRules": ["不得把供应商自述直接当作第三方事实"],
  "pitfalls": [],
  "relatedSkills": ["web-research"],
  "supplementalContext": "报告表达尽量简洁。",
  "targetPlatforms": ["claude-code", "codex"],
  "outputLanguage": "zh-CN",
  "workflowSteps": [],
  "needsReferences": true,
  "needsScripts": false,
  "needsAssets": false
}
```

派生规则：

- `skillName` 由显示名称或用户提交名称生成安全 slug。
- `outputLanguage` 根据主要内容语言推断。
- `workflowSteps` 由 Skill Creator Agent 从 `roughProcess` 扩展。
- 存在专业信息、强制规则、常见错误、协同 Skill 或补充说明时生成 `references/`。
- 只有稳定、重复的自动化需求才生成 `scripts/`。
- 只有明确需要模板、样例文件或素材时才生成 `assets/`。

## 4. 输入优先级

固定优先级：

1. `mandatoryRules`
2. 用途、结果、流程、完成标准、专业信息、常见错误和协同 Skill
3. `supplementalContext`
4. Agent 的结构和表达决策

约束：

- Skill Creator、解析修复和 Repair Loop 都必须原样保留 `mandatoryRules`。
- 补充说明可以丰富普通信息，但不能覆盖、弱化或删除强制规则。
- 常见错误必须来自用户输入，不允许用模型猜测的内容替代。
- 补充说明为空时不得产生 warning 或 blocking。

## 5. Skill Creator Agent

Skill Creator 负责：

- 把使用时机转换为触发条件式 `description`。
- 把每个大致流程阶段扩展为包含 purpose、action、input、output、validation、failureHandling 的完整步骤。
- 根据完成标准生成验证检查点。
- 根据特殊情况生成恢复策略和分支。
- 判断信息放入 `SKILL.md`、`references/`、`scripts/` 或 `assets/`。
- 保留专业信息、强制规则、常见错误和协同 Skill。
- 输出符合 Pydantic schema 的 `SkillIR` JSON。

模型失败时不得生成静态替代作品。已有安全候选时选择历史最佳候选；没有可评估候选时返回结构化技术失败。

## 6. SkillIR

```json
{
  "schemaVersion": "1.0",
  "skill": {
    "name": "product-research",
    "description": "Use when the user needs this workflow: ...",
    "language": "zh-CN"
  },
  "workflow": {
    "objective": "形成可验证的产品研究结论",
    "steps": [],
    "decisionPoints": [],
    "failureHandling": [],
    "verification": []
  },
  "contextEngineering": {
    "filesystemAssumptions": [],
    "references": ["references/domain-knowledge.md"],
    "scripts": [],
    "assets": []
  },
  "agentKnowledge": {
    "unknownKnowledge": [],
    "pitfalls": [],
    "examples": [],
    "counterExamples": [],
    "relatedSkills": [],
    "supplementalContext": ""
  },
  "quality": {
    "freedomLevel": "medium",
    "hardRestrictions": [],
    "softGuidance": [],
    "validationChecklist": []
  },
  "platforms": {
    "targets": ["claude-code", "codex"]
  }
}
```

`quality.hardRestrictions` 必须与 Brief 的 `mandatoryRules` 一致。

## 7. 校验规则

Brief 阻塞规则：

- `NAME-001`：缺少 Skill 名称。
- `PURPOSE-001`：缺少使用时机。
- `PURPOSE-002`：缺少目标结果。
- `PROCESS-001`：缺少大致执行流程。
- `PROCESS-002`：缺少完成标准。
- `KNOW-001`：缺少专业信息。
- `RULE-001`：缺少强制规则。
- `KNOW-002`：缺少用户提供的常见错误或反例。

IR 阻塞规则：

- `IR-001`：核心结构缺失。
- `TRIG-001`：description 不是触发条件。
- `WF-001`：工作流为空或步骤字段不完整。
- `RULE-001`：强制规则在生成过程中丢失。

包阻塞规则：

- 缺少合法 `SKILL.md`。
- frontmatter 无法解析或名称不一致。
- 引用文件不存在。
- 文件路径不安全或 zip 存在路径穿越。

## 8. SQLite 与兼容迁移

SQLite 表：

- `drafts`
- `generations`
- `model_providers`
- `app_settings`

Draft 和 Generation 使用 JSON payload 保存。

读取旧 Draft 时执行一次确定性迁移：

- `trigger.intent` -> `purpose.usage`
- `workflow.objective` -> `purpose.desiredOutcome`
- 旧工作流的 purpose/action -> `purpose.process`
- 旧 validation -> `purpose.completionCriteria`
- 旧 failureHandling -> `purpose.specialCases`
- industryRules/internalProcesses/personalExperience -> `professionalInformation`
- industryRules -> `mandatoryRules`
- relatedTools -> `relatedSkills`
- 用户 chat messages -> `supplement.content`

迁移成功后立即以新结构重新保存，后续读取不再重复迁移。

## 9. API

```text
POST   /api/drafts
GET    /api/drafts
GET    /api/drafts/:id
PATCH  /api/drafts/:id
POST   /api/drafts/:id/generate
GET    /api/generations/:id
GET    /api/generations/:id/preview
GET    /api/generations/:id/validation
GET    /api/generations/:id/download
POST   /api/generations/:id/regenerate
GET    /api/history
GET    /api/rules
GET    /api/model-providers
POST   /api/model-providers
PATCH  /api/model-providers/:id
DELETE /api/model-providers/:id
POST   /api/model-providers/:id/test
GET    /api/settings
PUT    /api/settings
GET    /api/cli/commands
```

## 10. Provider 与安全

- 支持 `claude` 和 `openai-compatible` 协议。
- API Key 只写入环境变量或本地秘密配置，响应中不得返回明文。
- 自定义 header 不得覆盖鉴权 header。
- generation Provider 缺失时阻塞生成。
- 每次生成记录 provider ID、协议和连接风险状态。
- 路径必须通过安全相对路径校验。
- zip 不允许绝对路径或 `..`。

## 11. 渲染和打包

canonical package：

```text
skill-name/
  SKILL.md
  references/
  scripts/
  assets/
install/
  claude-code.md
  codex.md
  hermes-openclaw.md
validation-report.json
package-manifest.json
```

渲染要求：

- `SKILL.md` 明确展示 Mandatory Rules。
- 专业信息、强制规则、常见错误、协同 Skill 和补充说明可进入 references。
- 补充说明章节必须标注其优先级低于强制规则。
- 仅为选中的平台生成安装说明。

## 12. 验收标准

- 最新 Draft API 只返回四步模型字段。
- 旧 Draft 可读取、迁移并重新保存。
- 八类业务必填输入均有字段级阻塞校验，目标平台为空时自动回退 Claude Code。
- 生成结果完整保留强制规则和用户常见错误。
- 与强制规则冲突的补充说明不能改变硬性约束。
- Skill Creator 能从大致流程生成完整步骤。
- 前后端契约一致。
- 全部 pytest、Ruff、ESLint 和生产构建通过。
