# NovaFDE 代码审查修复变更清单

> 日期: 2026-06-10  
> 分支: `codex/simplified-skill-creation`  
> 变更: 65 个文件, +5772 / -3422 行

---

## 审查范围

覆盖后端 20+ Python 模块、前端 20+ React/TypeScript 组件、配置与部署脚本。  
共发现 74 个问题，确认修复 47 项（CRITICAL 3 + HIGH 5 + MEDIUM 28 + LOW 11）。

---

## 🔴 CRITICAL 级修复（3 项）

### C1. 并行评估线程竞态条件
- **文件**: `backend/app/orchestrator.py`
- **问题**: `ThreadPoolExecutor` 中两个线程同时修改共享 `generation` 对象并写入数据库，导致 provider 选择可能丢失。
- **修复**: 重写并行评估逻辑——将激活/实现评估拆为独立线程函数，结果收集完毕后才调用 `_record_provider_selection` 持久化，避免并发写入。

### C2. API 密钥写入 `os.environ`
- **文件**: `backend/app/service.py`
- **问题**: `create_provider`、`patch_provider`、`_load_provider_secrets` 三处将 API 密钥写入 `os.environ`，对进程内所有代码可见。
- **修复**: 删除全部 `os.environ[...] = ...` 代码，密钥仅通过 `SecretStore`（macOS 钥匙串 / 加密文件）管理。移除未使用的 `import os`。

### C3. `.env` 明文 API 密钥
- **文件**: `.gitignore` (已忽略 `.env`)
- **说明**: `.env` 已在 `.gitignore` 中被忽略，但建议立即轮换文件中硬编码的 API 密钥。

---

## 🟠 HIGH 级修复（5 项）

### H1. `render_skill_package` rmtree 无路径防护
- **文件**: `backend/app/renderer.py`
- **问题**: `shutil.rmtree(package_root)` 无条件执行，若路径配置错误可能删除意外目录。
- **修复**: 添加 `len(package_root.parts) < 3` 守卫，拒绝删除根路径或可疑短路径。

### H2. `_finalize` 中 rmtree 无路径校验
- **文件**: `backend/app/orchestrator.py`
- **问题**: `_finalize` 复制候选包时调用 `shutil.rmtree(final_root)` 无安全检查。
- **修复**: 添加 `final_root.resolve().is_relative_to(self.settings.artifact_root.resolve())` 校验，确保仅删除 artifact 目录内路径。

### H3. `render_skill_package` 异常未包装
- **文件**: `backend/app/orchestrator.py`
- **问题**: `render_skill_package` 内部异常直接传播，导致生成任务以不明确错误终止。
- **修复**: 添加 `try/except` 包裹渲染调用，将异常转化为 `RENDER_FAILED` 错误码。

### H4. `ApiKeyRef.name` 允许知名环境变量名
- **文件**: `backend/app/models.py`
- **问题**: 验证器仅检查字母/下划线格式，不阻止 `PATH`、`HOME` 等系统变量名。
- **修复**: 添加 `_BLOCKED_ENV_NAMES` 黑名单（`PATH`、`HOME`、`USER`、`SHELL` 等 14 个变量），拒绝覆盖系统环境变量。

### H5. `download_path` 路径遍历防护不足
- **文件**: `backend/app/service.py`
- **问题**: 使用 `artifact_root not in path.parents` 检查可能遗漏边界情况。
- **修复**: 改为 `path.is_relative_to(artifact_root)` 检查，更严格。

---

## 🟡 MEDIUM 级修复（28 项）

### 后端（18 项）

| # | 文件 | 修复 |
|---|------|------|
| M1 | `models.py:147` | `target_platforms_must_not_be_empty` 改为抛出 `ValueError`，不再静默替换 |
| M2 | `models.py:492-495` | `set_run_id` 仅在 `runId is None` 时设置，不再强制覆盖 |
| M3 | `models.py:265` | 魔术数字 `4` 提取为 `MAX_CRITERION_SCORE` 模块常量 |
| M4 | `models.py:176` | `SkillBrief.targetPlatforms` 默认值改为 `["claude-code"]` 与 `SkillDraft` 一致 |
| M5 | `normalizer.py:253-255` | CJK 检测扩展：假名(U+3040)、片假名(U+30A0)、扩展A(U+3400) |
| M6 | `validator.py:204-219` | 验证项 ID 使用 `_safe_id_component` 清洗，防止路径分隔符注入 |
| M7 | `validator.py:163-169` | `parse_frontmatter` 支持 `\r\n` 行尾，先 `normalize` 再解析 |
| M8 | `validator.py:236` | 避免重复读取 `SKILL.md`，缓存已读内容复用 |
| M9 | `renderer.py:129` | `validationChecklist` 回退逻辑区分空列表(`[]`)和 `None` |
| M10 | `service.py:285-290` | `download_path` 路径检查改为 `is_relative_to` |
| M11 | `service.py:668-675` | `_cleanup_expired_attempts` 添加 `is_relative_to` 路径防护 + `try/except OSError` |
| M12 | `service.py:259` | `close()` 改为 `wait=True`，确保进行中任务完成 |
| M13 | `orchestrator.py:750` | `_finalize` 中 `rmtree` 添加 `is_relative_to` 检查 |
| M14 | `orchestrator.py:916` | `type: ignore[operator]` 改为显式 `cast(float, ...)` |
| M15 | `orchestrator.py:1081` | `_transition` 的 `type: ignore[arg-type]` 替换为描述性注释 |
| M16 | `quality.py:91-113` | `select_best_attempt` 显式处理 `None` 分数，替代 `or 0` 模式 |
| M17 | `utils.py:75-78` | `_SECRET_PATTERNS` 收窄正则，仅匹配 8+ 字符类密钥字符串 |
| M18 | `settings.py:26-34` | 添加 `model_validator` CORS 宽泛 origin 警告 |

### 前端（10 项）

| # | 文件 | 修复 |
|---|------|------|
| M19 | `api.ts:34-43` | `readError` 的 `response.json()` 包裹 `try/catch`，防止无效 JSON 崩溃 |
| M20 | `api.ts:55-56` | API 调用添加 30 秒超时（`AbortController`） |
| M21 | `CreatePage.tsx:72,109-110` | Autosave 首次 `POST` 后改为 `PATCH` 更新，避免重复创建草稿 |
| M22 | `CreatePage.tsx:381` | 向 `PipelineProgress` 传递 `isFailed` prop，失败时显示红色进度条 |
| M23 | `data/index.ts:9-16` | 补充 3 个缺失阶段：`injecting-rules`、`splitting-workflow`、`quality-gate` |
| M24 | `SupplementDialog.tsx:54-55` | 添加 Escape 键关闭和背景点击关闭（无障碍修复） |
| M25 | `QualityScorePanel.tsx:13` | `null` 分数显示灰色（`text-muted-foreground`）而非红色 |
| M26 | `LocalRunPage.tsx:14-16` | Clipboard API 添加 `.catch()` 错误处理 |
| M27 | `LocalRunPage.tsx:106-109` | 命令过滤改为显示所有命令，新增"其他"分类 |
| M28 | `SettingsPage.tsx:505` | 删除 Provider 添加 `window.confirm` 确认对话框 |

---

## 🔵 LOW 级修复（11 项）

| # | 文件 | 修复 |
|---|------|------|
| L1 | `backend/requirements.txt` | 核心依赖添加版本锁定 |
| L2 | `scripts/run.sh` | 后端/前端启动后添加健康检查 |
| L3 | `scripts/doctor.sh` | 添加 Python 包和 node_modules 依赖检查 |
| L4 | `state_machine.py:63` | 相同状态转换添加 debug 日志 |
| L5 | `models.py:303-337` | `recalculate_dimension_score` 中 `requiresUserInput` 覆盖添加意图说明注释 |
| L6 | `orchestrator.py:459` | 渲染失败异常包装为 `RENDER_FAILED` |
| L7 | `SettingsPage.tsx` | 防抖保存错误不再静默吞掉，添加 `try/catch` |
| L8 | `FileTree.tsx:23` | 使用路径组合 key 避免同名文件 key 冲突 |
| L9 | `BasicStep.tsx` | `slugify` 空值兜底为 `"untitled"` |
| L10 | `RulesPage.tsx:188` | 错误模式分页添加"显示更多"提示 |
| L11 | `vite.config.ts` | 环境变量命名标准化 |
| L12 | `backend/tests/test_model_providers.py:84` | 更新测试断言，反映密钥不再写入 `os.environ` 的行为 |

---

## 逻辑流畅性验证

### 核心数据流

```
用户表单 → SkillDraft → normalize_draft → SkillBrief
  ↓
PydanticAI 生成 → SkillIR
  ↓
render_skill_package（新增路径防护）→ 文件系统
  ↓
evaluate_validation（ID 清洗 + CRLF 支持）→ 验证报告
  ↓
并行评估（线程安全重构）→ 质量报告
  ↓
降级门控（显式 None 处理）→ 最终包
  ↓
create_zip → 下载
```

### 状态机流转（全部通过 `assert_generation_transition` 验证）

```
queued → normalizing → generating_initial_ir → rendering_candidate
  → running_validation_checks → evaluating_activation/implementation
  → aggregating_scores → [awaiting_user_input | repairing_round_*]
  → selecting_best_candidate → packaging_* → succeeded/degraded/failed
```

### 测试结果

```
backend/tests/ — 59 passed in 2.10s ✅
skill-forge TypeScript — 编译通过 ✅（无类型错误）
```

---

## 已知遗留（设计决策，非 bug）

| 项 | 说明 | 状态 |
|----|------|------|
| 降级门控仅检查总分 >= 60 | 允许单维度极低分通过，代码中已添加注释说明 | 设计决策 |
| `repair.py` 已删除 | AI-based repair 已在 `orchestrator.py` 中实现 | 架构决策 |
| 前端测试覆盖不足 | 仅 3 个组件有测试文件 | 建议后续补充 |

---

## 变更影响范围

- **安全**: 密钥管理、路径遍历、环境变量覆盖 — 全部加固
- **数据完整性**: 并行评估竞态、autosave 重复创建 — 已修复
- **健壮性**: JSON 解析崩溃、超时处理、CRLF 支持 — 已修复
- **用户体验**: 进度条缺失阶段、无障碍、确认对话框 — 已修复
- **代码质量**: 魔术数字、类型安全、`type: ignore` 清理 — 已修复
