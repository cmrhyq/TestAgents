# TestAgents 重构设计（v1.0）

> 版本：v1.0 ／ 日期：2026-10-20
> 定位：**目标态设计**。本轮重构的唯一依据文档。
> 上游决策：4 项已确认 —— ①记忆存储＝DB 真源 + 目录镜像 ②Skills＝SKILL.md 文件夹规范 ③工具沙箱＝文件读写限空间目录 + HTTP + 知识库（无 shell） ④范围＝完整落地 5 大目标
> 关联：[重构路线图](Testing-Agent-Roadmap.md)（分层哲学）、[模式设计](Mode-System-Design.md)（模式四层）、[差距分析](Mode-System-Gap-Analysis.md)（旧基线）

---

## 一、目标与验收

| # | 能力 | 验收标准 |
|---|---|---|
| 1 | 测试空间管理 | 能建/删/改空间，能上传 OpenAPI 解析入库，能管理环境与接口，能浏览空间工作目录 |
| 2 | 测试对话 | 选定空间后对话；三种工作模式（默认/问答/计划）行为符合定义；可选 Skill 参与；全程 SSE 流式 |
| 3 | 空间会话 | 建空间自动生成工作目录与初始文件；能列出空间下会话、历史消息、测试结果 |
| 4 | Skills 管理 | 发现内置/空间两级 Skill；可导入市面 SKILL.md 包；可启用禁用；导出的 SKILL.md 能被市面工具识别 |
| 5 | 记忆系统 | 三层各自可验证：上下文变动不影响持久化；跨会话记忆可增删改查且重启后仍在；知识库文档可检索出相关切片 |

**明确不做（本轮）**：L2 执行引擎重建（`engine/`）、用例资产化、run 间 diff、生产环境两阶段审批。

---

## 二、总体架构

### 2.1 分层

```
L4  Agent 运行时（agent/）      自然语言 → 工具调用；模式 = 工具权限策略
L3  Skills（skill/）            方法论注入 + 可复用测试套路（SKILL.md）
L2' 工具层（agent/tools/）      原子能力：DB 查询 / 文件 / HTTP / 知识库 / 记忆
L1  记忆（memory/）             上下文 / 跨会话记忆 / 领域知识库
L0  空间与目录（workspace/ + data/）  空间、接口、环境、工作目录
```

依赖方向严格向下：`agent` 可以调 `memory`、`skill`、`tools`；反过来一律禁止。`memory/` 不许 import `agent/`。

### 2.2 目录结构（后端）

```
backend/
├── skills/                    ★新  内置 Skill 库（随代码走，SKILL.md 文件夹）
├── workspaces/                ★新  空间工作目录根（git 忽略）
│   └── {space_id}/                   由 SpaceService 创建
├── src/
│   ├── agent/                 ★新  L4
│   │   ├── runner.py               一次对话的完整编排（组装 → ReAct 循环 → 事件）
│   │   ├── modes.py                模式策略（工具白名单 + 闸门）
│   │   ├── context.py              上下文组装（system prompt 拼装）
│   │   ├── events.py               内部事件 → SSE 帧
│   │   └── tools/                  L2' 工具集
│   │       ├── registry.py             工具注册与按模式/技能过滤
│   │       ├── db_tools.py             ← 迁移自 graph/tools
│   │       ├── fs_tools.py             ← 重写（空间沙箱）
│   │       ├── http_tools.py           ← 迁移 + 环境闸门
│   │       ├── openapi_tools.py        ← 迁移
│   │       ├── memory_tools.py         ★新  remember / recall / forget
│   │       ├── knowledge_tools.py      ★新  knowledge_search
│   │       └── skill_tools.py          ★新  list_skills / read_skill
│   ├── skill/                 ★新  L3
│   │   ├── manifest.py             SKILL.md frontmatter 解析
│   │   ├── repository.py           文件系统发现（两级）
│   │   └── service.py              导入 / 启用禁用 / 选中装配
│   ├── memory/                ★新  L1
│   │   ├── context.py              本轮上下文（纯组装，不持久化）
│   │   ├── longterm.py             跨会话记忆（DB + md 镜像）
│   │   └── knowledge.py            知识库（切片 + 向量检索 + 降级）
│   ├── workspace/             ★新  L0
│   │   ├── manager.py              目录创建 / 删除 / 路径沙箱
│   │   └── templates/              初始文件模板
│   ├── api/v1/                ✅保留 + 扩展
│   ├── core/                  ✅保留（config / llm / chroma / database / logging）
│   └── data/                  ✅保留 + 新增模型
├── graph/                     ❌删除（整体）
└── workflow.py                ❌删除
```

**删除清单**：`src/graph/`（tools 迁移后删）、`src/workflow.py`、`src/prompts/`（旧 builder 依赖已删节点，本轮不用）、`src/api/v1/workflow.py`（OpenAPI 解析已并入 space 路由）。

**从 git 历史恢复**：`src/graph/executor/{assertion_engine,jsonpath,cache_resolver}.py` → 迁至 `src/agent/tools/`（`assertion_engine.py` / `jsonpath.py`），作为 `evaluate_assertions` / `extract_jsonpath` 的实现。`cache_resolver.py` 迁至 `src/memory/` 暂不使用（等 L2 执行引擎）。

---

## 三、核心概念

### 3.1 Space = 空间 + 工作目录（一一对应）

创建空间时同步创建 `workspaces/{space_id}/`。目录是 Agent 的沙箱根，也是测试资产的落地处。

```
workspaces/{space_id}/
├── AGENTS.md             空间级指令，注入 system prompt（用户可直接编辑）
├── memory/
│   └── MEMORY.md         跨会话记忆镜像（由 DB 全量渲染，**只读**，不要手改）
├── docs/                 领域知识库原始文档
│   └── README.md         说明：往这里放需求文档 / 接口文档 / 业务规则
├── testcases/            Agent 产出的用例与测试脚本
│   └── .gitkeep
└── artifacts/            响应体、报告、导出文件
    └── .gitkeep
```

沙箱规则：所有文件工具入参为**相对空间根的路径**，`Path.resolve()` 后必须 `is_relative_to(space_root)`，否则返回错误字符串（不抛异常，避免打断 Agent 循环）。

### 3.2 Conversation = 会话（承载模式 + 技能选择）

`conversation` 表扩展三列：

| 列 | 类型 | 说明 |
|---|---|---|
| `mode` | Text | `'agent' \| 'ask' \| 'plan'`，**统一小写**。旧值 `Run`→`agent`、`Ask`→`ask`、`Plan`→`plan` |
| `skill_names` | Text | JSON 数组，本会话选用的 Skill 名 |
| `environment_id` | Integer | 可空，指定测试环境（工具解析 base_url 用） |

消息表 `message.meta` 复用为 JSON：`{"tool_calls": [...], "usage": {...}, "mode": "..."}`，避免为过程数据加列。

### 3.3 三层记忆

| 层 | 存储 | 生命周期 | 谁写 | 谁读 |
|---|---|---|---|---|
| **上下文** | 进程内存（`memory/context.py`），拼进 prompt | 单轮请求 | runner 组装 | LLM |
| **跨会话记忆** | DB `space_memory` 为真源 + `memory/MEMORY.md` 镜像 | 永久，按 space 隔离 | Agent 的 `remember` 工具 / 前端 API | `recall` 工具 / 前端列表 |
| **领域知识库** | 原件 `docs/` + 切片 `knowledge_chunk` + 向量 Chroma | 永久，按 space 隔离 | 上传文档 API | `knowledge_search` 工具 |

**为什么跨会话记忆不用向量检索**：记忆条目是「结论型短文本」（偏好、决策、已知坑），量小（几十到几百条），需要**精确命中**而非语义相似。用 SQLite `LIKE` + 按更新时间倒序，简单、可解释、零外部依赖。知识库才需要向量——文档是「长文本、模糊检索」。

---

## 四、数据模型变更

### 4.1 新增表

**`space_memory`** — 跨会话记忆

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK 非自增 | 雪花 ID |
| `space_id` | Integer | FK space CASCADE | 所属空间 |
| `title` | Text | NOT NULL | 标题（列表展示） |
| `content` | Text | NOT NULL | 内容 |
| `category` | Text | NOT NULL DEFAULT 'fact' | `fact` / `decision` / `preference` / `issue` / `glossary` |
| `tags` | Text | DEFAULT '[]' | JSON 数组 |
| `source_conversation_id` | Integer | FK conversation SET NULL | 来源会话 |
| `status` | Integer | NOT NULL DEFAULT 1 | 0=已删除（软删，便于误删恢复） |
| `created_at` / `updated_at` | Text | NOT NULL | |

索引：`idx_memory_space(space_id, status)`、`idx_memory_category(space_id, category)`

**`knowledge_document`** — 知识库文档

| 列 | 说明 |
|---|---|
| `id` / `space_id`（FK CASCADE） | |
| `filename` / `file_path`（相对空间根） | |
| `mime` / `size` | |
| `chunk_count` | 切片数 |
| `status` | `pending` / `indexed` / `failed` |
| `error` | 失败原因 |
| `created_at` / `updated_at` | |

**`knowledge_chunk`** — 切片（DB 为真源，Chroma 存向量副本）

| 列 | 说明 |
|---|---|
| `id` / `document_id`（FK CASCADE）/ `space_id` | |
| `seq` | 文档内序号 |
| `content` | 切片正文 |
| `chroma_id` | 向量库中的 ID（便于精确删除） |
| `created_at` | |

索引：`idx_chunk_doc(document_id)`、`idx_chunk_space(space_id)`

**`skill`** — Skill 注册表（文件为内容真源，DB 存发现结果与开关）

| 列 | 说明 |
|---|---|
| `id` / `name`（唯一键 = scope+space_id+name） | |
| `scope` | `builtin` / `space` |
| `space_id` | 可空，builtin 为 NULL |
| `directory` | 相对 backend 根的目录 |
| `description` / `when_to_use` / `version` | 来自 frontmatter |
| `allowed_tools` | JSON 数组，可空＝不限制 |
| `enabled` | 1/0 |
| `discovered_at` | |

### 4.2 变更表

| 表 | 变更 |
|---|---|
| `space` | +`workspace_path` Text（相对 backend 根，默认 `workspaces/{id}`） |
| `conversation` | +`skill_names` Text、+`environment_id` Integer；`mode` 的 CHECK 改为 `('agent','ask','plan')` |
| `environment` | +`is_production` Integer DEFAULT 0（闸门依据） |

### 4.3 迁移策略

SQLite 无成熟的 ALTER 迁移框架，本轮新建 `src/data/migration/v2_agent_migration.py`：

1. `Base.metadata.create_all()` 自动建新表（幂等）
2. 对变更表做「探测列 → `ALTER TABLE ADD COLUMN`」的幂等补列
3. 数据修正：`UPDATE conversation SET mode='agent' WHERE mode='Run'` 等
4. 一次性把旧 CHECK 约束放宽：SQLite 不支持改约束，采用「若检测到旧 CHECK 则重建表」策略；若重建成本高，则在应用层校验（**优先应用层**，DB 约束保留旧的会导致插入 `agent` 失败 → 必须处理）

> ⚠️ 决策：`conversation.mode` 的旧 CHECK 会让写入 `'agent'` 直接失败。迁移采用 **重建表**（`CREATE TABLE conversation_new ... INSERT SELECT ... DROP RENAME`），在一次事务内完成，失败回滚。

---

## 五、Agent 运行时

### 5.1 请求协议

```http
POST /api/v1/chat/stream
Content-Type: application/json

{
  "instruction": "帮我测一下用户登录相关接口",
  "conversation_id": null,
  "space_id": "1234567890",
  "mode": "agent",              // agent | ask | plan
  "skill_names": ["api-test-design"],
  "environment_id": null
}
```

响应头 `X-Conversation-Id` 返回会话 ID（已有约定）。

### 5.2 五种模式的语义（强约束，落到工具白名单）

| 模式 | 语义 | 工具集 | 产物 |
|---|---|---|---|
| `ask` | 只回答问题，**零副作用** | 只读：`search_space` / `get_space_endpoints` / `get_endpoint_detail` / `read_file` / `list_directory` / `knowledge_search` / `recall` / `list_skills` / `read_skill` | 文本回答 |
| `plan` | 只出计划，**零执行** | 同 ask | 结构化计划文本（含接口清单、步骤、断言点、风险），**不调用 send_request** |
| `agent`（默认） | 自动选工具执行测试 | ask 集 + `send_request` / `write_file` / `remember` / `forget` | 回答 + 工具调用轨迹 |

**为什么模式落到工具白名单而不是 prompt**：prompt 只是建议，模型在工具列表里有 `send_request` 时迟早会调。白名单是**执行路径上的硬拦截**——这是 [模式设计](Mode-System-Design.md) 的核心结论，本轮兑现。

`plan` 模式额外在 system prompt 里注入输出格式约束（计划必须含：目标 / 接口范围 / 用例矩阵 / 断言策略 / 风险），但这只是锦上添花，**硬保证来自工具缺失**。

### 5.3 System Prompt 组装顺序

```
[1] 基础人设与通用规则（固定，代码内常量）
[2] 模式指令（ask / plan / agent 三选一）
[3] 空间上下文（空间名、接口数量、环境清单 base_url、AGENTS.md 全文）
[4] 记忆（该 space 最近 20 条 + 命中关键词的相关条目）
[5] Skill 指令（选中 skill 的 SKILL.md 正文，逐个包裹 <skill name="...">）
[6] 工具使用须知（沙箱路径规则、相对路径约束）
```

顺序有讲究：[1][2] 是**行为约束**必须最靠前；[4][5] 是**内容注入**靠后，避免稀释规则。总长度上限 12k 字符，超限时按 [5] → [4] 逆序裁剪。

### 5.4 ReAct 循环（手写，不用 LangGraph）

```python
async def run(request) -> AsyncIterator[Event]:
    ctx = build_context(request)          # system prompt + history
    tools = resolve_tools(request.mode, request.skill_names)
    model = llm_gateway.get_model().bind_tools(tools)
    messages = ctx.messages
    for step in range(MAX_STEPS):         # 默认 12，防死循环
        async for chunk in model.astream(messages):
            if chunk.content: yield TextDelta(chunk.content)
            accumulate tool_call deltas
        if not tool_calls:
            yield Final(answer); return
        for call in tool_calls:
            yield ToolCall(call)
            result = await execute(call, sandbox)   # 异常转错误字符串
            yield ToolResult(result)
            messages.append(ToolMessage(result, tool_call_id=call.id))
    yield Error("超过最大工具调用轮次")
```

**为什么不用 LangGraph**：这里只需要一个「模型 ↔ 工具」的两节点循环，LangGraph 的 StateGraph / reducer / checkpoint 能力全用不上，反而要为它维护一套 state schema 和事件映射。手写约 120 行，事件粒度完全可控（`tool_call` 要带 args、`tool_result` 要带耗时），单测也更直接。降低复杂度是首要目标。

### 5.5 SSE 事件协议

| event | data | 说明 |
|---|---|---|
| `start` | `{seq, conversation_id, space_id, mode, skills}` | 流开始 |
| `text_delta` | `{seq, content}` | 文本增量 |
| `tool_call` | `{seq, id, name, args}` | 工具调用开始 |
| `tool_result` | `{seq, id, name, ok, content, duration_ms}` | 工具返回（content 截断 4k） |
| `final` | `{seq, answer, usage}` | 最终回答 |
| `error` | `{seq, message}` | 失败 |

帧格式沿用 `id:` / `event:` / `data:` 三行 + 空行，与现有前端 `lib/stream.ts` 兼容。

### 5.6 执行闸门

`send_request` 工具在执行前查环境：`environment.is_production == 1` → 直接返回错误字符串：

> 「目标环境 X 标记为生产环境，已阻止请求。请先切换到测试环境，或明确要求用户确认后再试。」

同时 `agent` 模式下的写操作（`write_file`）限制在空间目录内。这两条构成**最小可行闸门**。完整的两阶段人工审批（暂停流 → 前端弹窗 → 恢复）留待后续。

---

## 六、Skills 子系统

### 6.1 Skill 包格式（对齐市面 Agent Skills 规范）

```
skills/api-test-design/
├── SKILL.md             必需
├── references/          可选：补充资料（按需读取）
├── scripts/             可选：可执行脚本（本轮不自动执行）
└── assets/              可选
```

`SKILL.md`：

```markdown
---
name: api-test-design
description: 为一组接口设计测试场景矩阵
when_to_use: 当用户要求为某组接口设计测试用例，或需要覆盖正向/异常/边界场景时
version: 1.0.0
allowed_tools: [get_space_endpoints, get_endpoint_detail, read_file, write_file]
---

# 接口测试场景设计方法论

## 步骤
1. 用 get_space_endpoints 拉全量接口清单...
```

**校验规则**：`name` 必填且 `^[a-z0-9][a-z0-9-]{1,63}$`；`description` 必填（≤200 字）；`when_to_use` 强烈建议；`allowed_tools` 若存在，则与模式白名单**取交集**（模式优先，防止 skill 越权）。

### 6.2 发现与优先级

| 优先级 | 位置 | 说明 |
|---|---|---|
| 1（高） | `workspaces/{space_id}/.skills/` | 空间私有，覆盖同名内置 |
| 2 | `backend/skills/` | 内置，随代码分发 |

`SkillRepository.discover(space_id)` 扫描两级目录，同名时空间级胜出。结果落 `skill` 表用于前端展示与启停；内容始终从文件读（**文件是真源**）。

### 6.3 导入

`POST /api/v1/skills/import`（multipart zip + `space_id`）：
1. 解压到临时目录，防 zip-slip（拒绝 `..` 与绝对路径）
2. 递归找 `SKILL.md`，校验 frontmatter
3. 移动到 `workspaces/{space_id}/.skills/{name}/`
4. 刷新注册表，返回 skill 列表

### 6.4 选择与注入

前端在对话页多选；请求带 `skill_names`；后端按名字取 SKILL.md **正文**（不含 frontmatter），包裹后注入 system prompt [5]。`allowed_tools` 与模式工具集取交集。

---

## 七、记忆子系统

### 7.1 跨会话记忆

**写入路径（两条）**：
- Agent 主动：`remember(title, content, category)` 工具（仅 `agent` 模式）
- 人工：`POST /api/v1/spaces/{id}/memories`

**同步镜像**：每次增删改后，`LongTermMemory.sync_markdown(space_id)` 全量重建 `memory/MEMORY.md`：

```markdown
# 空间记忆（自动生成，请勿手改）

> 由 space_memory 表渲染，最后更新：2026-10-20 22:00
> 修改请走前端「记忆」面板或 API。

## decision
- **登录接口用 v2 版本**：v1 已废弃，token 有效期 2h。
  `#auth #token`（2026-10-18）
```

**读取路径**：`recall(query)` 工具 → SQLite `LIKE`（title/content/tags）+ 最近 20 条；前端列表走 API。

**删除**：软删（`status=0`）；前端另有「彻底删除」调 `DELETE ... ?hard=true`。

### 7.2 知识库

**摄取流程**：

```
上传文件 → 存 workspaces/{space}/docs/{filename}
        → knowledge_document(status=pending)
        → 切片（800 字符 / 100 overlap，按段落边界优先）
        → 有 embedding 能力：写 knowledge_chunk + Chroma(space_knowledge_{id})
          无 embedding 能力：仅写 knowledge_chunk（status=indexed，mode=lexical）
        → status=indexed
```

**检索流程**：

```
knowledge_search(query, top_k=5)
  → Chroma 可用：向量检索 → 取 chunk 正文 + 文档名
  → Chroma 不可用 / 无 embedding：降级 SQLite LIKE
  → 返回 [{document, seq, content, score}]
```

**降级是硬要求**：当前 `config.yaml` 里 Chroma 指向远程 `134.175.168.219:30081`，离线/断网会挂。降级让功能「差但可用」，也让单测不需要外部服务。

**Embedding 配置**（新增 `embedding` 段）：

```yaml
embedding:
  enabled: false            # 默认关，先跑通降级路径
  model: "zai/embedding-3"  # litellm 格式
  api_key: ""
  base_url: ""
  dimension: 2048
chroma:
  enabled: false            # 默认关，避免启动时连接超时
```

---

## 八、API 设计（新增/变更）

```
# ── 空间 ─────────────────────────────────────────────
POST   /spaces                      创建（同步建工作目录 + 初始文件）
GET    /spaces                      列表
GET    /spaces/{id}                 详情（含 workspace_path）
PUT    /spaces/{id}
DELETE /spaces/{id}                 删库 + 归档目录（改名 .deleted-{ts}，不物理删）
POST   /spaces/{id}/openapi         上传解析 OpenAPI（沿用，去掉 KnowledgeService 依赖）
GET    /spaces/{id}/tree            工作目录树
GET    /spaces/{id}/conversations   空间下会话列表          ★新
GET    /spaces/{id}/runs            空间下测试结果          ★新
# ── 记忆 ─────────────────────────────────────────────
GET    /spaces/{id}/memories                                 ★新
POST   /spaces/{id}/memories                                 ★新
PUT    /memories/{id}                                        ★新
DELETE /memories/{id}               ?hard=true 物理删除       ★新
# ── 知识库 ───────────────────────────────────────────
POST   /spaces/{id}/documents       上传（multipart）        ★新
GET    /spaces/{id}/documents                                ★新
DELETE /documents/{id}                                       ★新
POST   /documents/{id}/reindex                               ★新
# ── 技能 ─────────────────────────────────────────────
GET    /skills?space_id=                                     ★新
GET    /skills/{name}?space_id=     含 SKILL.md 正文          ★新
POST   /skills/import               multipart zip            ★新
PATCH  /skills/{id}                 启用/禁用                 ★新
# ── 会话 / 对话 ──────────────────────────────────────
GET    /conversations/{id}
GET    /conversations/{id}/messages
DELETE /conversations/{id}
POST   /chat/stream                 重写（SSE 新协议）
```

所有 ID 为雪花 ID，响应中按现有 `SafeJSONResponse` 以大整数字符串化（前端已有约定）。

---

## 九、前端改造

### 9.1 路由与导航

| 路由 | 页面 | 状态 |
|---|---|---|
| `/dashboard` | 仪表盘 | 保留 |
| `/chat` | 对话（新） | 替换 `/workflows/chat` |
| `/spaces` | 空间列表 | 保留 |
| `/spaces/:id` | 空间详情（tabs） | 扩展 |
| `/skills` | 技能管理（新） | 新增 |
| `/reports` | 报告 | 保留 |

侧边栏：仪表盘 / 对话 / 测试空间 / 技能 / 测试报告。

### 9.2 对话页

- 顶部：空间选择器（必选）+ 模式选择器（三态：默认/问答/计划）+ 技能多选器
- 消息流：用户气泡 / 助手气泡 / **工具调用卡片**（名称、参数折叠、结果折叠、耗时）
- 未选空间时：输入框禁用 + 提示「请先选择测试空间」
- 欢迎态快捷指令：3 个示例（"列出这个空间的接口" / "为登录相关接口设计测试计划" / "跑一遍用户模块的正向用例"）

### 9.3 空间详情 tabs

`概览 / 接口 / 环境 / 会话 / 记忆 / 知识库 / 测试结果`

- 概览：空间元信息 + 工作目录树 + AGENTS.md 编辑器
- 会话：该空间会话列表 → 点进去跳对话页带 `conversation_id`
- 记忆：卡片列表（分类筛选）+ 新建/编辑/删除
- 知识库：上传 + 文档列表（状态、切片数）+ 检索预览

### 9.4 技能页

卡片网格（名称、描述、scope 徽章、启用开关）+ 导入 zip + 详情抽屉展示 SKILL.md 渲染结果。

---

## 十、测试策略（TDD）

**每个模块先写测试，红 → 绿 → 重构。**

| 层 | 测试类型 | 关键用例 |
|---|---|---|
| `workspace/manager` | 纯单测（tmp_path） | 建目录结构完整；路径逃逸被拒（`../../etc/passwd`、绝对路径、符号链接） |
| `skill/manifest` | 纯单测 | frontmatter 正常解析；缺 name/description 报错；非法 name 格式报错 |
| `skill/repository` | 纯单测（tmp_path 造两级目录） | 同名时空间级覆盖内置；扫描跳过无 SKILL.md 的目录 |
| `memory/longterm` | 单测（内存 SQLite） | 增删改查；软删后不进 recall；md 镜像内容与 DB 一致 |
| `memory/knowledge` | 单测（mock embedding/chroma） | 切片长度不超限且有 overlap；Chroma 挂掉时降级 LIKE |
| `agent/modes` | 纯单测 | ask 工具集不含 send_request；plan 同；agent 含；skill allowed_tools 交集生效 |
| `agent/context` | 纯单测 | 拼装顺序正确；超长裁剪按 [5]→[4] |
| `agent/runner` | 单测（mock model） | 文本流；工具调用->结果回填->再调用；超步数报错；工具异常不炸流 |
| `api` | TestClient | 空间 CRUD + 目录生成；记忆 CRUD；技能列表；chat 流式帧序 |
| `migration` | 单测（旧 schema SQLite） | 旧 `mode='Run'` 迁移为 `agent`；新列补齐；幂等重跑 |

**基线要求**：改动前先让 `import app` 通过、`pytest` 全绿（当前有 6 个测试文件引用了已删节点，需先清理）。

---

## 十一、风险与取舍

| 风险 | 影响 | 对策 |
|---|---|---|
| Chroma 远程不可达 | 知识库检索不可用 | 默认关闭 + 降级 LIKE；配置可开 |
| Embedding 模型缺失 | 无法向量化 | `embedding.enabled=false` 默认走词法；接口预留 |
| 手写 ReAct 循环不如 LangGraph 成熟 | 需要自己处理 tool_call 分片 | 单测覆盖分片合并；限制 `MAX_STEPS` |
| 重构删除面大 | 可能破坏已有功能 | 分阶段提交，每阶段 `pytest` + 手动冒烟；旧目录归档不物理删 |
| 前端页面多 | 尾大不掉 | 先做对话页与空间 tabs，技能页最简可用 |
| 旧 DB 已有数据 | 迁移失败丢数据 | 迁移前自动备份 `TestAgents.db.bak-{ts}` |

---

## 十二、实施阶段（详见实施计划）

| 阶段 | 内容 | 出口条件 |
|---|---|---|
| **P0 止血** | 修导入、清理死测试、跑通 `import app` + `pytest` 基线 | 应用能起，测试全绿 |
| **P1 地基** | `workspace/` + 模型/迁移 + 空间 API 扩展 | 建空间即生成目录，测试通过 |
| **P2 房间** | `skill/` + `memory/` + 工具集重写 | 三个子系统单测全绿 |
| **P3 引擎** | `agent/` 运行时（模式/上下文/循环/事件）+ chat API 重写 | 三种模式行为符合定义，流式可用 |
| **P4 界面** | 前端对话页重写 + 空间 tabs + 技能页 | 端到端可手动验收 |
| **P5 收口** | 文档更新、清理、CHANGELOG | 全部验收项勾选 |
