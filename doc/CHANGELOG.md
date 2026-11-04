# 设计变更日志（Design Changelog）

本文件记录 **LLMTestAgent 架构与产品设计** 的变更历史，面向 ADR、流程图、数据模型、API 契约等产品/技术设计文档。

> 代码与依赖发布变更见项目根目录 [`CHANGELOG.md`](../CHANGELOG.md)。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
设计状态标签：`Proposed`（提议中）· `Accepted`（已采纳）· `Implemented`（已实现）· `Superseded`（已取代）

---

## [2.0.0] - 2026-11-04 · 文档体系重整（`Implemented`）

以当前代码为准做了一次文档审计：先判定哪些文档仍有存在价值，再逐篇对齐实现。
判定标准是「这份文档是否还在描述当前系统」以及「它是否与其他文档重复」。

### Removed

- **`design/Refactor-Design.md`** —— v1.0 重构的目标态设计。重构已完成，其结论已并入
  [Architecture.md](./design/Architecture.md)，保留会与实现文档形成第二套「应该是什么样」的说法。
- **`design/Refactor-Plan.md`** —— P0–P5 实施计划。任务全部完成或已失效，引用的文件多数已删除。
- **`design/Mode-System-Gap-Analysis.md`** —— v0.1 破损状态的差距扫描，文档自身已标注「已归档」，
  四项缺失全部落地。
- **`doc/images/`** —— 三份 `.puml` 源与三份 `.svg` 导出。这些图描述的是已删除的 `test_run` 等表，
  环境内也没有可用的 PlantUML 渲染器，无法随文档一起更新。图改为在 Markdown 内嵌 Mermaid，
  与正文同一次修改，不会再出现「图是旧的、文字是新的」。

三份被删除的设计文档可在 `git log` 中查到原文（最后一次出现在提交 `2616de3` 之前）。

### Changed

- **Architecture.md v2.0** —— 五段式流水线（新增执行记录阶段）；模式步数上限 12/8 → 100/80；
  工具与路由清单按代码重建；新增执行记录、成本账本、截断三档、已知限制六条；表数量 15 → 12。
- **DatabaseDesign.md v2.0** —— 全量重写。删除 `test_run` / `test_case` / `test_result` /
  `test_summary` / `report` 五章（已由 v3 / v4 迁移删除），新增 `agent_run` / `agent_tool_call`；
  补「`space.base_url` 已移除」的说明；`llm_log` 补 `run_id` 与 `idx_llm_log_run`。
- **ER.md v2.0** —— 按 12 张表重绘；新增「逻辑引用为什么不建外键」与四域拓扑；
  补「一次对话会写入哪些表」的写入顺序表。
- **SystemFlowchart.md v2.0** —— 补时序图、失败与中断对照表；`start` 事件载荷更正为
  `skills` + `run_id`。
- **Mode-System-Design.md v2.0** —— 改为实现优先的写法，删除与实际端点不符的示例代码；
  补三项行为差异与四项缺口。
- **Testing-Agent-Roadmap.md v2.0** —— 由「从零设计」改为「现状 + 缺口 + 阶段」，
  逐层标注实现状态；原文档假设的 `engine/` 目标结构与五层计划与当前方向不符，已重写。
- **UI-Design-Guidelines.md v2.0** —— 补测试报告、报告详情、执行详情三个页面骨架；
  空间页签「测试运行」更正为「执行记录」。

---

## [1.0.2] - 2026-10-20 · LLM 成本账本闭环（`Implemented`）

修复「对话链路不产生 token 统计」：runner 走 `get_model()` 拿到裸 `BaseChatModel` 自行 `bind_tools().astream()`，
绕过了 `LLMService` 的埋点；同时 `llm_log` 没有任何归因列，即使有数据也算不出「哪个空间/会话花了多少」。

### Added

- **`astream_with_tools()`**（`LLMService` / `LLMGateway`）：把 `bind_tools` + `astream` + 埋点收敛到一处，
  是 Agent 运行时的唯一正确入口。`runner` 改为调用它并透传 `space_id` / `conversation_id`
- **`llm_log` 归因与成本列**：`space_id` / `conversation_id`（**无外键**，见下）/ `routing_tier` / `cost_usd`，
  配 `idx_llm_log_space`、`idx_llm_log_conversation` 复合索引
- **`GET /api/v1/usage/stats`**：按空间 / 会话 / 时间窗口聚合，返回调用数、失败数、token、成本，
  以及按模型、按路由档位的分组
- **`config.pricing`**：自定义模型费率段，补齐 litellm 定价表未收录的厂商（如 `zai/*`），
  否则这些模型的金额永远算不出来

### Fixed

- **真实模型名被记成 `smart-router`**：`response_metadata["model"]` 是空键，兜底逻辑把所有调用都记成
  Router 的逻辑组名，而它没有任何定价。改为按 `deployment` → `routing_decision.routed_model` →
  `deployment_model_name` → `model_name` 的优先级取真实模型（实测拿到 `zai/glm-4-flash`）
- **流式 token 可能漏记**：原实现只看最后一个 chunk 的 `usage_metadata`，部分 provider 把 usage 放在
  中间 chunk，会静默记成 0。改为「保留最后一次非空」
- **成本未知被写成 0**：`litellm.cost_per_token` 对同一模型的行为会随成本表来源漂移
  （干净进程抛异常、远端表加载后返回 `0.0`）。改为直接查定价表，并强制
  `LITELLM_LOCAL_MODEL_COST_MAP=True` 关闭远端拉取，避免离线环境阻塞与结果漂移
- **历史脏数据**：修复前写入的 `cost_usd = 0.0`（实为未知）已清理为 NULL

### Changed

- `LLMGateway.get_model()` 标记为弃用，调用时抛 `DeprecationWarning`；业务代码已无引用
- `LLMService` 支持注入 `session_scope`，统计可跑在临时库上（此前硬编码全局 DB，无法单测）

### 设计取舍

- **归因列不建外键**：加 CASCADE 会连历史成本一起删掉，加 SET NULL 会变成无法归因的孤儿行。
  成本要能对账，不该随业务数据消灭（空间 ID 是雪花值，不会被复用）
- **`cost_usd` 的 NULL 与 0 严格区分**：NULL 表示「定价表查不到」，0 表示「真的免费」。
  API 用 `cost_usd`（仅已知成本）+ `unpriced_calls`（未计价次数）两个字段表达，
  避免把部分成本当成全部成本
- **每轮都记账**：ReAct 的每一轮都是独立计费调用，一轮对话产生 1~N 条记录（实测「读文件再回答」= 2 条）

### 验证

- 新增 41 项测试（`test_llm_usage.py` 23 / `test_runner_attribution.py` 6 / `test_usage_api.py` 12），
  全量 **490 passed**
- 真实链路实测：`start → tool_call → tool_result → text_delta → final`，2 轮调用 → 2 条 `llm_log`，
  归因与会话 ID 一致，`routing_tier=SIMPLE`
- 老库迁移幂等：补 4 列 + 2 索引，历史 6 行保留；二次启动不再补列

---

## [1.0.1] - 2026-10-20 · 文档全面对齐实现（`Implemented`）

1.0.0 只改了代码，文档仍停留在 LangGraph 时代。本次把「会误导读者照着写出错代码」的部分全部校准。

### Changed

- **[Architecture.md](./design/Architecture.md)**：升级 v1.0 并重写——§二 基础设施（`llm_client` → `llm_gateway`）、§四~§六 路由清单、原 §三「LangGraph 工作流」替换为「Agent 运行时」（四段式流水线 / ReAct 循环 / 模式白名单 / 工具清单 / SSE 协议 / prompt 组装），新增空间沙箱、Skills、记忆三章；同步配置段与前端目录/路由
- **[ER.md](./design/ER.md)**：补 4 张新表（`space_memory` / `knowledge_document` / `knowledge_chunk` / `skill`）与 `llm_log`；补 3 组新字段与 `mode` 取值变更；新增 CHECK 约束清单与「为什么 `skill` 不建 FK」的说明；图改为 Mermaid（图随文改，不再与 SVG 脱节），PlantUML 源保留供导出
- **[SystemFlowchart.md](./design/SystemFlowchart.md)**：整篇重写。旧版描述已删除的意图路由与图节点，新版讲四段式流水线、ReAct 循环的三个刻意取舍、六事件协议、工具沙箱约束、模式白名单，附「新旧流程对照」表
- **[DatabaseDesign.md](./design/DatabaseDesign.md)**：新增 `llm_log` 章节（此前「15 张表」只写了 14 张）；约束与索引名对齐代码（`ck_memory_category` / `ck_memory_status` / `idx_memory_space` / `idx_memory_category` / `idx_document_space` / `idx_chunk_doc` / `idx_chunk_space` / `idx_skill_scope` / `idx_skill_name`）；`skill` 补 `when_to_use` / `version` / `discovered_at` 并删除不存在的 `uq_skill_name_scope`；枚举速查改为 `agent`/`ask`/`plan` 并补 category / status / index_mode / scope
- **[UI-Design-Guidelines.md](./design/UI-Design-Guidelines.md)**：升级 v0.2.0，新增 §7.9~§7.13——模式分段控件（含「文案必须对齐真实权限边界」纪律）、技能多选器、工具调用卡片（三态配色 + 折叠规范）、上下文栏、三类页面骨架；检查清单补「执行过程必须可见」；文件索引修正已删除的 `security-chat.tsx`
- **[Mode-System-Design.md](./design/Mode-System-Design.md)**：状态从「待实现的目标架构」改为「核心已落地」，§九 由「落地建议」改写为逐条实现对照（✅ 13 项 / ❌ 3 项 / ⚠️ 1 项），并说明本项目**故意**让 `plan` 过滤写工具的理由与「若做审批续跑必须改回」的前提
- **[README.md](../README.md) / [README_zh.md](../README_zh.md)**：清除已删模块（`workflow.py` / `graph/` / `prompts/` / `security-chat`）、`.env` 与 `${ENV}` 插值、旧 provider 列表、`project`/`api_info` 旧表名；改为一屏说清「模式 = 工具白名单」「三选择器」「六事件」「三层记忆」，并补模式/工具/事件/记忆/技能对照表
- **[CONTRIBUTING.md](../CONTRIBUTING.md)**：更新技术栈描述，补「关键目录速查」与提交前自检（含 `allowed_tools` 静默裁工具这一坑）
- **`backend/config/config.yaml` / `config.yaml.example`**：按 `AppConfig` 重排为同一套 9 个段（`llm` / `model_list` / `database` / `chroma` / `embedding` / `workspace` / `skill` / `logging` / `langsmith`）。模板补此前缺失的 `embedding` / `workspace` / `skill` 三段与 `chroma.enabled`；删除失效的 `execution` 段；逐段加注释说明**开关联动规则**（向量检索需 `chroma.enabled` + `embedding.enabled` + `embedding.model` **三者同时**满足，否则静默降级为词法检索）、`smart-router` 仅异步路径生效、`database.url` 相对路径按进程 cwd 解析的坑

### Fixed

- **文档内的失效链接**：`CHANGELOG` 中指向已删除的 `Refactor-Remaining.md` 与两个 ADR 的链接，改为说明性文字（全库文档链接现零 404）
- **两处「六 tab」笔误**：空间详情实际是 7 个 tab（概览 / 会话 / 接口 / 环境 / 记忆 / 知识库 / 测试运行）
- **配置模板的 `langsmith.project` 字段名错误**：`LangSmithConfig` 的真实字段是 `space`，`project` 会被 Pydantic **静默丢弃**（未设 `extra="forbid"`），导致照模板配置的用户以为开了 LangSmith 却从未上报。已在两个配置文件与 Architecture §十 的 CAUTION 中标注该机制
- **本地 `config.yaml` 缺 `chroma.enabled`**：该实例配了远程 Chroma 地址与 Token，但缺总开关会走默认 `false`；补 `enabled: true` 的同时注明「`embedding` 未配置模型，因此仍不生效」——避免「配了远程库却没被用上」的静默降级

### Known Issues（文档侧记录的技术债）

- **HTTP 超时没有配置入口**：`send_request` 的超时是工具形参（默认 30s），`AppConfig` 里无对应字段；上一代执行引擎遗留的 `execution` 段已于本次从两个配置文件删除。要支持全局默认值需新增 `http` 配置段并接进 `http_tools`，不要复活旧段。已在 Architecture §十 与 README FAQ 标注
- ~~`LLMGateway.get_model()` 绕过 `llm_log` 埋点，对话链路不产生 token 统计~~ —— 已在 [1.0.2] 修复
- 用例生成 / 批量执行 / HTML 报告的代码在重构前已删除，`test_run` 与 `report` 目前只有读接口。README 与 Architecture §十二 已如实说明

---

## [1.0.0] - 2026-10-20 · Agent 运行时重构（`Implemented`）

按 `Refactor-Design.md` / `Refactor-Plan.md` 完成 P0–P5 全量重构（两份计划文档已在 2026-11-04 的文档重整中删除，需要时查 `git log`）。核心变化是**删掉 LangGraph 工作流，换成手写 ReAct 循环**，并把「模式」从 prompt 建议变成工具白名单硬约束。

### Added

- **Agent 运行时**（`backend/src/agent/runner.py`）：手写 ReAct 循环，单轮 `astream` → 累积工具调用分片 → 逐个执行 → `ToolMessage` 回灌。异常一律转成 `ok=false` 的工具结果，不打断流
- **模式策略**（`backend/src/agent/modes.py`）：`agent` / `ask` / `plan` 三模式落到工具白名单，`filter_tools` 在执行路径上闭环；skill 的 `allowed_tools` 只能**收窄不能放大**
- **SSE 事件协议**（`backend/src/agent/events.py`）：六种事件 `start` / `text_delta` / `tool_call` / `tool_result` / `final` / `error`，三行帧 + `seq` 递增；`final` 携带完整 answer，前端不靠 delta 拼接
- **空间工作目录（沙箱）**（`backend/src/workspace/`）：新建空间自动生成 `AGENTS.md` / `memory/MEMORY.md` / `docs/` / `testcases/` / `artifacts/`；所有路径 `resolve()` 后校验不得逃出空间根目录
- **Skills 子系统**（`backend/src/skill/`）：`SKILL.md` 文件夹规范（frontmatter + 正文），内置（`backend/skills/`）+ 空间私有（`workspaces/{id}/.skills/`）两级发现，zip 导入带 zip-slip 防护，前端可启停
- **记忆子系统**（`backend/src/memory/longterm.py`）：按 space 隔离的跨会话记忆，DB 为真源 + `memory/MEMORY.md` 全量镜像；召回用关键词抽取（ASCII 整词 + CJK 2-gram）而非整句 LIKE
- **知识库**（`backend/src/memory/knowledge.py`）：文档切片入库，向量检索（Chroma，默认关闭）失败时降级 SQLite 词法检索
- **工具集重写**（`backend/src/agent/tools/`）：17 个工具全部绑定空间上下文——`fs`（4）/ `db`（3）/ `http`（2，含生产环境闸门）/ `memory`（3）/ `knowledge`（1）/ `skill`（2）/ `executor`（2）
- **会话扩展字段**：`conversation.skill_names`（JSON）与 `conversation.environment_id`
- **数据库 v2 迁移**（`backend/src/data/migration/v2_agent_migration.py`）：`mode` 取值从 `Run/Ask/Plan` 归一到 `agent/ask/plan`，通过「PRAGMA foreign_keys=OFF + 重建表 + 重跑索引」绕过旧 CHECK 约束，且保证消息不丢
- **前端**：对话页三选择器（空间 / 模式 / 技能）+ 工具调用可折叠卡片；空间详情七 tab（概览 / 会话 / 接口 / 环境 / 记忆 / 知识库 / 测试运行）；技能管理页

### Changed

- **`POST /api/v1/chat/stream` 重写**：三种模式共用一条流式路径，模式差异只体现在工具白名单；缺 `space_id` 回 `error` 帧而非 400
- **`conversation.mode` 默认值** `Run` → `agent`，服务层统一 `normalize_mode` 兜底历史值
- **`GET /conversations`** 返回 `skill_names` 数组与 `environment_id`（DB 存 JSON 字符串，schema 层转换）
- **前端路由**：`/workflows/chat` → `/chat`（旧路径重定向保留书签可用），新增 `/skills`

### Removed

- **LangGraph 工作流**：`backend/src/graph/`（state / route / nodes）、`backend/src/workflow.py`。理由：只需要「模型 ↔ 工具」两节点循环，StateGraph / reducer / checkpoint 全用不上，却要多维护一套 state schema 与事件映射
- **旧 Prompt 体系**：`backend/src/prompts/`（builders / formatters / templates / loader）。system prompt 改由 `agent/context.py` 按「人设 → 模式指令 → 空间上下文 → 记忆 → skill → 工具规则」顺序拼装
- **死代码**：`KnowledgeService` 与 `POST /endpoints/reindex`、`WorkflowRunStreamRequest` 与 `/workflows/run/stream`、前端 `use-security-chat` / `use-workflows`（仅保留 `useParseOpenAPI`）

### Fixed

- **内置 skill 声明的工具名错误**：`api-test-design` / `api-regression-run` 里写的是 `get_endpoint_detail`，实际工具名是 `get_endpoint_detail_by_id`——会导致该工具被静默裁掉。已修正，并新增 `tests/agent/test_skill_tool_contract.py` 把「技能声明的工具必须真实存在且不能被模式放大」钉成契约

### 迁移说明

- 旧 `mode` 值（`Run`/`Ask`/`Plan`）无需手工改，服务层 `normalize_mode` 会归一化；启动时 `migrate_v2` 会重建表并回填
- 原有空间没有工作目录时会自动补建，不需要手工迁移文件

---

## [Unreleased]

### Added

- **剩余重构清单**（`design/Refactor-Remaining.md`，该文件后续已删除）：阶段 0/1 完成后，阶段 2–6 的未改动项（分层契约、工作流结构化、核心层拆分、前端整理、枚举与安全收尾），含文件证据与验收标准
- **架构设计文档**（[design/Architecture.md](./design/Architecture.md)）：跨前后端的整体架构总览，反映当前真实实现
  - 顶层架构、后端分层、LangGraph 工作流、数据模型（含新增对话表）、对话历史子系统、前端架构、LLM/Prompt、配置体系
  - 对既有文档做现状校准：对话历史已实现、对话入口已合并为单一 `/workflows/chat`、Ask/Plan 现状、Chroma 仍未接入

### Implemented（设计已落地到代码）

- **对话历史持久化**（原 ADR-001 §2.2 `Proposed` → 已实现）：
  - 新增 SQLite 表 `conversation` + `message`（雪花 ID、CASCADE），ORM/Schema/Repository/Service
  - 新增 `/conversations` CRUD API 与 `/conversations/{id}/messages`
  - `/chat/stream` 支持 `conversation_id`/`mode`、多轮上下文、消息落库、响应头 `X-Conversation-Id`
  - 前端 `SpacesSection` 接入真实会话（替换 mock），`security-chat.tsx` 改为多轮消息列表
- **单一对话入口**：合并「新建测试」与「安全对话」为 `/workflows/chat`；删除 `workflow-run.tsx` 与 `useRunTest`；`/workflows/run` 重定向；触发测试统一走 `POST /chat/stream`
- **fs_tools 安全决策（`run_command` 已禁用）**：
  - 决策：`graph/tools/fs_tools.py` 的 `run_command`（任意 Shell 命令 + 继承 `os.environ`）从工具导出中移除并删除，LLM 不再可调用系统命令
  - `read_file`/`list_directory`/`get_file_info` 增加仓库工作区（`_WORKSPACE_ROOT`）路径校验，越界拒绝
  - 依据：Refactor-Remaining.md 阶段 6.3「三选一」中的**禁用**方案（无命令白名单与沙箱维护成本最低，当前工作流不依赖命令执行）

### Changed

- **配置改为纯 YAML**：移除 `python-dotenv` 与 `${ENV}` 变量替换，`load_config()` 只从 `config.yaml` 读取；密钥需明文写入本地配置（`config.yaml` 已在 `.gitignore`）
- **LLM 单例接口**：`get_llm_client()` / `get_chat_model()` / `init_llm_client()` 恢复可选 `config` 参数（缺省回退全局配置），应用启动在 lifespan 中显式 `init_llm_client(config)`；新增 `deepseek` provider

### Removed

- **删除测试触发的旧接口**：移除后端 `POST /workflows/run/test` 与配套 `GET /workflows/status/{run_id}`（及 `BackgroundTasks`、`_running_tasks` 跟踪逻辑），以及前端死代码 `useWorkflowStatus` 与 `WorkflowStatus` 类型；触发测试统一由 `POST /chat/stream` 承担

### Proposed

- **ADR-001**：引入 Project 工作空间模型（每个 Project = 一个 Codex 式 workspace）
  - 文档：`adr/ADR_001_project-workspace-ask-plan-chroma.md`（文件已删除；相关决策已并入 [Architecture.md](./design/Architecture.md) 与 [Mode-System-Design.md](./design/Mode-System-Design.md)）
  - 状态：`Proposed`
- **对话模式 Ask / Plan / Run**：三种 `conversation_mode`，由 API 显式指定，不纳入意图 LLM 分类
  - Ask：RAG 问答，不执行 HTTP
  - Plan：生成测试计划 → 用户确认 → 执行
  - Run：现有 LangGraph 测试工作流
- **Chroma 语义检索层**：SQLite 为 Source of Truth，Chroma 仅作 per-project 向量索引
  - Collection 策略：单 Collection + `project_id` / `doc_type` metadata 过滤
  - 索引优先级：endpoint（P0）→ test_case / test_summary（P1）
- **API 边界调整（拟议）**：
  - `api_doc_file_path` 收窄为「工作空间内导入 OpenAPI」专用
  - Ask / Plan / Run 改为 `project_id` 驱动
  - 新增拟议路由：`/projects/{id}/chat/stream`、`/projects/{id}/plans`、`/projects/{id}/runs`
- **实施分阶段路线**：Phase 0（工作空间闭环）→ Phase 1（Ask）→ Phase 2（Plan）→ Phase 3（Chroma）→ Phase 4（历史知识）
- **风险验证清单**：ADR-001 待决事项与验证任务
  - 文档：`adr/ADR_001_risks-validation-todo.md`（文件已删除）

### Changed（设计层面，待实现）

- `doc/` 目录结构重组：
  - 设计文档迁入 `doc/design/`（系统流程图、数据库设计、ER 图）
  - 架构决策记录迁入 `doc/adr/`
  - 图示资源集中于 `doc/images/`（该目录已于 2026-11-04 移除，图改为文档内嵌 Mermaid）

### Open Questions

以下事项已在 ADR-001 中标记为待决，变更落地前需拍板：

| # | 事项 | 阻塞阶段 |
|---|------|----------|
| 1 | 同一 Project 重复导入 OpenAPI：覆盖 / 合并 / 版本化 | Phase 0 |
| 2 | 手动 Endpoint 与导入文档冲突时的优先级 | Phase 0 |
| 3 | Embedding Provider 是否与 LLM Provider 绑定 | Phase 3 |
| 4 | Plan 模式：仅确认 vs 可编辑后确认 | Phase 2 |
| 5 | Ask 对话历史是否跨会话持久化 | 待定 |

---

## [0.2.0] - 2026-07-07

### Added

- 新增 **ADR-001**：Project 工作空间、Ask/Plan 对话模式与 Chroma 语义检索（`Proposed`）
- 新增 **ADR-001 风险验证 Todo List**：汇总方案中不确定项与验证任务
- 新增本文件 `doc/CHANGELOG.md`（设计变更日志）

### Documented（现状分析写入 ADR）

- 记录当前实现与产品设想之间的差距：
  - 前端 `upload` / `parse` / `run` 三条路径未统一
  - Ask / Plan 仅前端 UI 占位，后端未实现
  - `ChromaManager` 已实现但未接入业务，缺少 Embeddings 配置
  - `api_doc_path` 在 chat 接口中被忽略
  - 缺少显式 `project_id` 作为工作空间锚点
- 识别待验证技术风险：API 层与工作流层 `TestRun` 双 ID 问题

---

## [0.1.0] - 2026-06-15

### Added

- **Monorepo 产品设计**：前后端分离，`backend/`（FastAPI + LangGraph）+ `frontend/`（React 19）
- **系统主流程设计**（[design/SystemFlowchart.md](./design/SystemFlowchart.md)）：
  - 意图识别分流：`parse_openapi` | `run_test`
  - 测试模式：`single`（单接口）| `flow`（业务流程）
  - Agent Tool Loop：`search_project` → `get_project_endpoints` → LLM 选接口
  - 执行链路：生成用例 → HTTP 执行 + 断言 → HTML 报告
- **数据库设计**（[design/DatabaseDesign.md](./design/DatabaseDesign.md)）：
  - SQLite 3 + SQLAlchemy 2.0
  - 核心实体：Project、Environment、Endpoint、TestRun、TestCase、TestResult、Report
  - Project 作为接口与测试运行的顶层容器
- **ER 拓扑图**（[design/ER.md](./design/ER.md)）
- **流式对话设计**（安全审计 + API 测试问答）：
  - `POST /api/v1/chat/stream`
  - 前置 `security_audit_node` 拦截非测试内容与安全风险
- **ChromaDB 连接层设计**（`ChromaManager`，配置项 `ChromaConfig`）：
  - HttpClient 单例、Collection/文档 CRUD、LangChain VectorStore 集成
  - 状态：基础设施就绪，**未定义业务索引与检索策略**

### Changed

- 移除 CLI 入口设计，统一为 FastAPI REST API 触发工作流
- CORS 改为环境变量配置，适配前端开发服务器

### Deprecated（设计意图，尚未完全收敛）

- `api_doc_file_path` 原设计仅服务于 `parse_openapi` 分支；前端引入后职责边界模糊，待 ADR-001 收窄

---

## [0.0.1] - 2026-05-28

### Added

- **初始架构设想**：
  - 自然语言驱动 API 自动化测试
  - LangGraph 有状态工作流编排
  - OpenAPI 解析入库 → 基于 DB 的接口挑选与用例生成
  - 多 LLM Provider 支持（OpenAI、Bedrock、智谱、千问）
- **Prompt 模板体系**：意图分类、接口挑选、单接口/流程用例生成、安全审计
- **测试执行设计**：`CacheResolver` 步骤间变量传递、`AssertionEngine` 断言评估

---

## 变更类型说明

| 类型 | 含义 |
|------|------|
| **Added** | 新增设计、文档、ADR、API 契约 |
| **Changed** | 已有设计发生变更 |
| **Deprecated** | 计划废弃但尚未移除的设计 |
| **Removed** | 已从设计中移除 |
| **Proposed** | 提议中、未采纳（`Unreleased` 区） |
| **Implemented** | 设计已落地到代码（需在对应版本注明） |
| **Documented** | 对现状的梳理记录，不一定是新设计 |

---

## 与其他文档的关系

```
doc/
├── CHANGELOG.md          ← 本文件（设计变更日志）
├── adr/                  ← 架构决策记录（ADR）
│   ├── ADR_001_*.md
│   └── ...
└── design/               ← 详细设计文档
    ├── SystemFlowchart.md
    ├── DatabaseDesign.md
    └── ER.md

CHANGELOG.md（根目录）    ← 代码发布变更日志
```

新增 ADR 或重大设计变更时，请同步更新本文件 `Unreleased` 区，采纳后归入版本号条目。

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1 | 2026-07-08 | 初稿：建立设计变更日志，回溯至初始架构，记录 ADR-001 |
