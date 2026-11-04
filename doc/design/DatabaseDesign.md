# 数据库设计

> 版本：v2.0（对应 `feature/web_ui` 分支当前实现）
> 定位：以 `backend/src/data/models/*.py` 的 ORM 定义为准，逐表记录字段、约束、索引与外键策略；
> 并说明若干「看起来可以简化、实际不能改」的设计取舍。
>
> 关联文档：[架构设计](Architecture.md) · [ER 图](ER.md) · [系统流程图](SystemFlowchart.md)

---

## 一、总体约定

| 项目 | 取值 |
|---|---|
| 数据库引擎 | SQLite 3（连接建立时启用 WAL、外键约束、UTF-8） |
| ORM | SQLAlchemy 2.0（`DeclarativeBase` + `Mapped[]` 注解风格） |
| 文件位置 | `backend/db/TestAgents.db`，首次启动自动创建 |
| 主键策略 | 全局雪花 ID（`src/utils/id.py::next_id`），`autoincrement=False` |
| 时间字段 | `Text` 存本地时间字符串，由 `local_now()` 生成（形如 `2026-11-04 23:41:07`） |
| 表数量 | 12 张，见 `src/data/migration/migration.py::EXPECTED_TABLES` |
| 复合主键 | 无。所有表使用单列代理主键，业务唯一性由 UNIQUE 约束表达 |

### 1.1 为什么时间用 Text 而不是 DateTime

SQLite 没有原生时间类型，SQLAlchemy 的 `DateTime` 落到 SQLite 也只是字符串。既然物理存储相同，
显式用 `Text` 可以避免「取出来是 `datetime` 还是 `str`」的隐式转换差异，也让不同时区的导出结果
保持字面可比。代价是无法用 SQL 时间函数做区间计算，因此所有时间窗口筛选都靠字符串前缀比较
（`created_at >= '2026-11-01'`）完成，这也是 `llm_log` 上建 `(space_id, created_at)` 复合索引的原因。

### 1.2 表结构如何建立与演进

启动序列（`app.py` 的 lifespan → `init_database_from_orm()`）：

1. `Base.metadata.create_all()` —— 只建**不存在**的表。已存在的表不会被改动，包括新增列与索引。
2. `migrate_v2()` —— 重建 `conversation` 表以替换 CHECK 约束（SQLite 不能原地修改 CHECK），
   并对 `llm_log` 补归因列与索引。
3. `migrate_v3()` —— `test_run` 转 `agent_run`、新增 `agent_tool_call`、删除遗留用例三表
   （`test_case` / `test_result` / `test_summary`）。
4. `migrate_v4()` —— 删除 `report` 表，报告改为按 `run_id` 实时聚合 `agent_tool_call`。
5. 创建分析视图（`v_run_overview` 等）。

三个迁移脚本都是幂等的：重复启动不会重复建列，也不会丢数据。顺序不能调整，原因见各脚本的
模块注释——`v4` 必须排在 `v3` 之后，因为 `v3` 在历史库上会重建 `report` 表以改写外键。

新增表只需添加模型文件（`create_all` 会建）；给**已有表**加列或加索引必须写迁移脚本，
`create_all` 不会 ALTER 已存在的表。

---

## 二、space — 测试空间

空间是几乎所有数据的隔离边界。一个空间对应磁盘上一个工作目录，目录路径记在 `workspace_path`。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `name` | Text | NOT NULL，UNIQUE | 空间名称，全局唯一 |
| `description` | Text | default `""` | 描述 |
| `status` | Integer | NOT NULL，default 1 | 1=启用，0=停用 |
| `workspace_path` | Text | NOT NULL，default `""` | 工作目录相对路径，形如 `workspaces/{id}` |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

索引：`idx_space_name`（`name`）。

级联关系（ORM `cascade="all, delete-orphan"`，DB 侧对应 `ON DELETE CASCADE`）：
`environment`、`endpoint`、`agent_run`、`conversation`、`space_memory`、`knowledge_document`。

> **`space` 没有 `base_url`**。基础 URL 属于环境（`environment.base_url`），一个空间可以有多个环境。
> 早期版本在 `space` 上放过 `base_url`，与「多环境」模型冲突，已删除。

> **删空间不删目录**。删除空间时工作目录被重命名为 `workspaces/.deleted-{id}-{时间戳}`，
> 保留现场供事后追查。数据库行消失、磁盘证据留存，这是一个刻意的非对称设计。

---

## 三、environment — 测试环境

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `space_id` | Integer | FK → `space.id`，NOT NULL，CASCADE | 所属空间 |
| `name` | Text | NOT NULL | 环境名，如 dev / staging / prod |
| `base_url` | Text | NOT NULL | 环境基础 URL |
| `description` | Text | default `""` | 描述 |
| `variables` | Text | default `"{}"` | 环境变量，JSON 对象字符串 |
| `is_default` | Integer | NOT NULL，default 1 | 是否默认环境 |
| `is_production` | Integer | NOT NULL，default 0 | 生产环境标记 |
| `status` | Integer | NOT NULL，default 1 | 1=启用，0=停用 |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

索引：`idx_env_space`（`space_id`）。

`is_production` 是安全闸门的唯一依据：为 1 时 `send_request` 拒绝任何写方法（POST / PUT / PATCH /
DELETE），并把拒绝原因作为工具结果回灌模型，而不是抛异常。它是**数据层的权威标记**，不依赖 prompt 约束。

---

## 四、endpoint — 接口定义

由 OpenAPI 文档解析产生，是 Agent 查接口的工具数据源。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `space_id` | Integer | FK → `space.id`，NOT NULL，CASCADE | 所属空间 |
| `operation_id` | Text | NOT NULL | OpenAPI `operationId` |
| `name` | Text | NOT NULL | 接口名 |
| `path` | Text | NOT NULL | 请求路径 |
| `method` | Text | NOT NULL | HTTP 方法 |
| `tags` | Text | default `"[]"` | 标签，JSON 数组字符串 |
| `summary` | Text | NULL | 简述 |
| `description` | Text | default `""` | 详述 |
| `params` | Text | NULL | 路径/查询参数定义，JSON |
| `headers` | Text | default `"{}"` | 请求头定义，JSON |
| `body` | Text | NULL | 请求体 Schema，JSON |
| `responses` | Text | default `"[]"` | 响应定义，JSON 数组 |
| `security` | Text | default `"[]"` | 安全要求，JSON 数组 |
| `content_type` | Text | default `"application/json"` | 内容类型 |
| `deprecated` | Integer | NOT NULL，default 0 | 是否废弃 |
| `status` | Integer | NOT NULL，default 1 | 1=启用，0=停用 |
| `version` | Integer | NOT NULL，default 1 | 版本号 |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

约束：

| 名称 | 类型 | 规则 |
|---|---|---|
| `ck_api_method` | CHECK | `method IN ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')` |
| `uq_space_path_method` | UNIQUE | `(space_id, path, method)` |

索引：`idx_endpoint_space`（`space_id`）、`idx_endpoint_operation_id`（`operation_id`）。

同一空间内「路径 + 方法」唯一：重复解析同一份 OpenAPI 文档不会产生重复接口。

---

## 五、agent_run — Agent 执行记录

一次 ReAct 对话对应一条记录。`conversation` / `message` 保存**说了什么**，
`agent_run` 保存**这一轮怎么得出结论**（用了哪些工具、成败、耗时、花了多少 token）。

统计列在收尾时一次性算出并冗余落库，列表页因此不需要聚合明细表。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `space_id` | Integer | FK → `space.id`，NOT NULL，CASCADE | 所属空间 |
| `environment_id` | Integer | FK → `environment.id`，SET NULL | 使用的环境 |
| `conversation_id` | Integer | NULL，**无外键** | 关联会话，见下方说明 |
| `title` | Text | NOT NULL，default `""` | 取用户指令前 50 字 |
| `mode` | Text | NOT NULL，default `"agent"` | `agent` / `ask` / `plan` |
| `trigger_type` | Text | NOT NULL，default `"chat"` | `chat` / `manual` / `scheduled` / `ci` |
| `llm_provider` | Text | NOT NULL，default `""` | 模型厂商 |
| `llm_model` | Text | NOT NULL，default `""` | 模型名 |
| `status` | Text | NOT NULL，default `"running"` | `running` / `completed` / `failed` / `cancelled` |
| `started_at` | Text | NULL | 开始时间 |
| `finished_at` | Text | NULL | 结束时间 |
| `duration_ms` | Integer | NOT NULL，default 0 | 总耗时（毫秒） |
| `tool_call_count` | Integer | NOT NULL，default 0 | 工具调用总次数 |
| `ok_count` | Integer | NOT NULL，default 0 | 成功的工具调用数 |
| `error_count` | Integer | NOT NULL，default 0 | 失败的工具调用数 |
| `success_rate` | Float | NOT NULL，default 0.0 | 工具调用成功率，百分比 0–100 |
| `avg_response_time` | Float | NOT NULL，default 0.0 | 工具调用平均耗时（毫秒） |
| `llm_call_count` | Integer | NOT NULL，default 0 | 本轮 LLM 调用次数（一轮 ReAct 通常 > 1） |
| `total_tokens` | Integer | NOT NULL，default 0 | 输入 + 输出 token 之和 |
| `cost_usd` | Float | NOT NULL，default 0.0 | 预估成本（美元） |
| `error_message` | Text | NOT NULL，default `""` | 失败原因 |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

约束与索引：

| 名称 | 类型 | 规则 |
|---|---|---|
| `ck_agent_run_status` | CHECK | `status IN ('running','completed','failed','cancelled')` |
| `ck_agent_run_mode` | CHECK | `mode IN ('agent','ask','plan')` |
| `ck_agent_run_trigger` | CHECK | `trigger_type IN ('chat','manual','scheduled','ci')` |
| `idx_agent_run_space` | INDEX | (`space_id`, `created_at`) |
| `idx_agent_run_conv` | INDEX | (`conversation_id`, `created_at`) |
| `idx_agent_run_status` | INDEX | (`status`, `created_at`)，驱动清理任务 |
| `idx_agent_run_created` | INDEX | (`created_at`) |

> **没有 `pending` 状态**。记录插入即为 `running`，避免「进程崩溃后留下永远 pending 的行」——
> 那类行既不能算完成，也无法自动分辨是否该清理。进程被杀时记录停在 `running`，
> 由 `DELETE /api/v1/agent/runs/cleanup` 按 `(status, created_at)` 清理。

> **`conversation_id` 不建外键**。会话创建失败时执行记录仍需写入（记录的目的是留痕，
> 不是维持引用完整性）；反过来说，加 CASCADE 会让「删会话」连带删掉执行历史。

> **`cost_usd` 的 0 与 NULL 不同义**。本列 NOT NULL 且由 `llm_log` 聚合而来，
> 表示「本次执行已知成本之和」；单条 LLM 调用的成本是否为未知，看 `llm_log.cost_usd`。

---

## 六、agent_tool_call — 工具调用留痕

单次工具调用一行，同时容纳 `send_request`（HTTP 明细）与非 HTTP 工具（通用列）。

正文长度分三档，各有独立用途，**不要合并成同一个常量**：

| 用途 | 上限 | 落点 |
|---|---|---|
| 落库 | 2 MB | `response_body`，超限置 `response_body_truncated=1` |
| 回灌模型 | 8000 字符 | `runner._for_model` |
| SSE 下发 | 4000 字符 | `events.ToolResultEvent`，同 `result_preview` |

### 通用列（所有工具都填）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `run_id` | Integer | FK → `agent_run.id`，NOT NULL，CASCADE | 所属执行记录 |
| `step_index` | Integer | NOT NULL，default 0 | ReAct 轮次，从 0 起 |
| `seq` | Integer | NOT NULL，default 0 | 本轮内调用序号 |
| `call_id` | Text | NOT NULL，default `""` | 模型给出的 `tool_call_id` |
| `tool_name` | Text | NOT NULL，default `""` | 工具名 |
| `tool_type` | Text | NOT NULL，default `"other"` | 工具分类，见下 |
| `args_json` | Text | NOT NULL，default `"{}"` | 入参，JSON 对象字符串 |
| `ok` | Integer | NOT NULL，default 0 | 1=成功，0=失败 |
| `error_type` | Text | NOT NULL，default `""` | 异常类名 / `validation` / `not_found` |
| `error_message` | Text | NOT NULL，default `""` | 异常原文，不截断 |
| `result_preview` | Text | NOT NULL，default `""` | 结果前 4000 字符 |
| `result_chars` | Integer | NOT NULL，default 0 | 结果总字符数（截断前） |
| `duration_ms` | Integer | NOT NULL，default 0 | 调用耗时（毫秒） |
| `created_at` | Text | NOT NULL | 创建时间 |

### HTTP 列（仅 `send_request` 填，其余工具为 NULL）

| 字段 | 类型 | 说明 |
|---|---|---|
| `http_method` | Text | 请求方法 |
| `http_url` | Text | 完整 URL |
| `http_status_code` | Integer | 响应状态码；无响应时 NULL |
| `request_headers` | Text | 请求头 JSON，敏感头已脱敏 |
| `request_params` | Text | 查询参数 JSON |
| `request_body` | Text | 请求体 |
| `response_headers` | Text | 响应头 JSON |
| `response_body` | Text | 响应体，上限 2 MB |
| `response_body_truncated` | Integer | 1=响应体超限已截断 |
| `response_size_bytes` | Integer | 响应体原始字节数 |

约束与索引：

| 名称 | 类型 | 规则 |
|---|---|---|
| `ck_tool_call_type` | CHECK | `tool_type IN ('http','db','fs','exec','memory','knowledge','skill','search','other')` |
| `ck_tool_call_ok` | CHECK | `ok IN (0,1)` |
| `idx_atc_run` | INDEX | (`run_id`, `seq`)，按执行回放轨迹 |
| `idx_atc_tool_created` | INDEX | (`tool_name`, `created_at`) |
| `idx_atc_tool_run` | INDEX | (`tool_name`, `run_id`)，专供报告聚合 |
| `idx_atc_http_url` | INDEX | (`http_url`) |

> **为什么 `ok` 与 HTTP 状态码分开记**。`send_request` 收到 4xx/5xx 不算工具失败——请求发出去了、
> 响应拿到了，`ok=1` 而 `http_status_code=500` 是合法组合。报告里的「成功」按 2xx 判定，
> 「异常」指拿不到状态码（网络错误、参数非法、被生产环境闸门拦截）。

> **`error_type` 独立成列**。`runner` 会把异常转成给模型看的话术，改写后无法再归因；
> 原始异常类名单独落库，才能统计「失败集中在哪里」。

---

## 七、conversation — 会话

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `space_id` | Integer | FK → `space.id`，NULL，CASCADE | 所属空间；可空以支持无空间会话 |
| `title` | Text | NOT NULL，default `""` | 会话标题 |
| `mode` | Text | NOT NULL，default `"agent"` | `agent` / `ask` / `plan` |
| `skill_names` | Text | NOT NULL，default `"[]"` | 会话选中的技能名，JSON 数组 |
| `environment_id` | Integer | FK → `environment.id`，NULL，SET NULL | 绑定环境 |
| `status` | Integer | NOT NULL，default 1 | 1=启用，0=停用 |
| `last_message_at` | Text | NULL | 最后一条消息时间 |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

约束与索引：

| 名称 | 类型 | 规则 |
|---|---|---|
| `ck_conversation_mode` | CHECK | `mode IN ('agent','ask','plan')` |
| `ck_conversation_status` | CHECK | `status IN (0,1)` |
| `idx_conversation_space` | INDEX | (`space_id`) |

> **CHECK 约束是重建表换来的**。早期约束为 `mode IN ('Ask','Plan','Run')`，会阻止写入小写 `agent`。
> SQLite 不支持修改 CHECK，`migrate_v2` 通过「关闭外键 → 建新表 → 拷贝数据 → 删旧表 → 改名 → 重建索引」
> 完成替换，并用测试钉死「重建过程不能丢 `message` 行」。服务层的 `normalize_mode()` 仍保留旧值兼容映射，
> 但数据库层只接受小写三值。

> **`mode` 与 `skill_names` 在每轮请求都可能变化**。它们记录的是「会话默认值」，
> 实际生效的模式以 `POST /chat/stream` 请求体中的 `mode` 为准，服务端每轮重新解析
> `ModePolicy`，不缓存到会话对象上。

---

## 八、message — 消息

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `conversation_id` | Integer | FK → `conversation.id`，NOT NULL，CASCADE | 所属会话 |
| `role` | Text | NOT NULL | `user` / `assistant` / `system` |
| `content` | Text | NOT NULL，default `""` | 消息正文 |
| `meta` | Text | NOT NULL，default `"{}"` | 元数据，JSON 对象字符串 |
| `created_at` | Text | NOT NULL | 创建时间 |

约束与索引：`ck_message_role`（`role IN ('user','assistant','system')`）、`idx_message_conv`（`conversation_id`）。

这张表只追加不修改。工具调用轨迹**不在这里**——它在 `agent_tool_call`，
`message.meta` 只承载轻量附加信息（如本轮 `run_id`）。

---

## 九、space_memory — 跨会话记忆

真源是这张表，`workspaces/{space_id}/memory/MEMORY.md` 是只读镜像：
每次写操作后由 `LongTermMemory.sync_markdown` 全量重建，不做增量同步，避免 DB 与文件漂移。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `space_id` | Integer | FK → `space.id`，NOT NULL，CASCADE | 归属空间，隔离边界 |
| `title` | Text | NOT NULL，default `""` | 要点标题，注入 prompt 时作为要点行 |
| `content` | Text | NOT NULL，default `""` | 内容正文 |
| `category` | Text | NOT NULL，default `"fact"` | 见枚举速查 |
| `tags` | Text | NOT NULL，default `"[]"` | 标签，JSON 数组 |
| `source_conversation_id` | Integer | FK → `conversation.id`，NULL，SET NULL | 产出该记忆的会话，可追溯 |
| `status` | Integer | NOT NULL，default 1 | 1=有效，0=软删 |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

约束与索引：

| 名称 | 类型 | 规则 |
|---|---|---|
| `ck_memory_category` | CHECK | `category IN ('fact','decision','preference','issue','glossary')` |
| `ck_memory_status` | CHECK | `status IN (0,1)` |
| `idx_memory_space` | INDEX | (`space_id`, `status`) |
| `idx_memory_category` | INDEX | (`space_id`, `category`) |

**检索方式：关键词 + `LIKE`，不是向量检索。**
记忆是几十到几百条结论型短文本，需要精确命中而非语义相似；`LIKE` 零外部依赖，
且能说清「命中了哪个关键词」。查询串先由 `extract_keywords` 拆成 ASCII 整词与 CJK 2-gram，
再多关键词 OR 匹配，默认返回 20 条（`DEFAULT_RECALL_LIMIT`）。

---

## 十、knowledge_document / knowledge_chunk — 知识库

文档原文件落在 `workspaces/{space_id}/docs/`，表里记路径与索引状态；切片表存切分后的正文。

### 10.1 knowledge_document

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `space_id` | Integer | FK → `space.id`，NOT NULL，CASCADE | 归属空间 |
| `filename` | Text | NOT NULL | 原始文件名 |
| `file_path` | Text | NOT NULL | 相对空间根目录的路径 |
| `mime` | Text | NOT NULL，default `"text/plain"` | MIME 类型 |
| `size` | Integer | NOT NULL，default 0 | 字节数 |
| `chunk_count` | Integer | NOT NULL，default 0 | 切片数 |
| `status` | Text | NOT NULL，default `"pending"` | `pending` / `indexed` / `failed` |
| `index_mode` | Text | NOT NULL，default `"lexical"` | `vector` / `lexical` |
| `error` | Text | NOT NULL，default `""` | 索引失败原因 |
| `created_at` | Text | NOT NULL | 创建时间 |
| `updated_at` | Text | NOT NULL | 更新时间 |

约束：`ck_document_status`（`status IN ('pending','indexed','failed')`）、
`ck_document_index_mode`（`index_mode IN ('vector','lexical')`）。索引：`idx_document_space`（`space_id`）。

### 10.2 knowledge_chunk

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `document_id` | Integer | FK → `knowledge_document.id`，NOT NULL，CASCADE | 所属文档 |
| `space_id` | Integer | FK → `space.id`，NOT NULL，CASCADE | 冗余空间 ID，避免检索时多一次 join |
| `seq` | Integer | NOT NULL，default 0 | 切片序号，从 0 起 |
| `content` | Text | NOT NULL，default `""` | 切片正文 |
| `chroma_id` | Text | NULL | Chroma 中的向量 ID；词法模式为空 |
| `created_at` | Text | NOT NULL | 创建时间 |

索引：`idx_chunk_doc`（`document_id`, `seq`）、`idx_chunk_space`（`space_id`）。

### 10.3 切片与检索

- 切片：目标 800 字符、重叠 100 字符，优先在段落、句号、换行处断开，找不到自然断点才硬切。
  重叠是为了避免答案正好落在两个切片的接缝上。
- 检索双路径：向量检索（Chroma + embedding）失败或未启用时，自动降级为词法检索
  （`LIKE` + 词频加权打分），`index_mode` 记录该文档实际使用的路径。
- 向量生效需要三个条件同时满足：`chroma.enabled`、`embedding.enabled`、`embedding.model` 非空。
  缺任意一个都不会实例化向量检索，且**不报错**——知识库照常可用，只是走词法。

---

## 十一、skill — 技能登记

内容在文件，不在表里。`SKILL.md` 才是有意义的数据，这张表只存 UI 需要的「是否启用」「装在哪」，
重启时由 `SkillRegistry.sync` 从磁盘重新扫描对齐。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `name` | Text | NOT NULL | 技能名，`^[a-z0-9][a-z0-9-]{0,63}$` |
| `description` | Text | NOT NULL，default `""` | 简介，来自 frontmatter |
| `scope` | Text | NOT NULL，default `"builtin"` | `builtin` / `space` |
| `space_id` | Integer | NULL，**无外键** | 空间级技能的归属；内置为 NULL |
| `directory` | Text | NOT NULL，default `""` | 磁盘目录，供展示与排障 |
| `when_to_use` | Text | NOT NULL，default `""` | 适用场景，来自 frontmatter |
| `version` | Text | NOT NULL，default `""` | 版本号 |
| `allowed_tools` | Text | NOT NULL，default `"[]"` | 声明的工具名，JSON 数组 |
| `enabled` | Integer | NOT NULL，default 1 | 1=启用，0=禁用 |
| `discovered_at` | Text | NOT NULL | 最近一次发现/同步时间 |

约束与索引：

| 名称 | 类型 | 规则 |
|---|---|---|
| `ck_skill_scope` | CHECK | `scope IN ('builtin','space')` |
| `ck_skill_enabled` | CHECK | `enabled IN (0,1)` |
| `idx_skill_scope` | INDEX | (`scope`, `space_id`) |
| `idx_skill_name` | INDEX | (`name`) |

> **没有 `(name, space_id)` 唯一约束**。同名技能允许在 builtin 与多个空间下并存，
> 解析时按「空间优先覆盖内置」择一。加唯一约束会禁止这种覆盖关系。

> **`space_id` 不建外键**：文件系统才是真源。目录被手工删除后，若有外键会导致写入失败；
> 没有外键时，脏行可以由下一次 `sync` 直接清掉。

> **`allowed_tools` 的安全语义**：只能收窄，不能放宽。`filter_tools` 先按模式去掉副作用工具，
> 再与技能声明取交集，顺序不可颠倒——反了就成了提权通道。

---

## 十二、llm_log — LLM 调用账本

每次模型调用一行，包括 ReAct 循环中的每一轮。一轮对话通常产生 1~N 条。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | Integer | PK，非自增 | 雪花 ID |
| `model_name` | Text | NOT NULL | **实际命中**的模型，如 `zai/glm-4-flash` |
| `provider` | Text | default `""` | 厂商，取 `model_name` 前缀 |
| `request_type` | Text | default `""` | `invoke` / `ainvoke` / `stream` / `astream` / `tools` |
| `prompt_tokens` | Integer | default 0 | 输入 token 数 |
| `completion_tokens` | Integer | default 0 | 输出 token 数 |
| `total_tokens` | Integer | default 0 | 总 token 数 |
| `duration_ms` | Integer | default 0 | 调用耗时（毫秒） |
| `success` | Integer | default 1 | 1=成功，0=失败 |
| `error_message` | Text | default `""` | 失败原因 |
| `space_id` | Integer | NULL，**无外键** | 归因空间 |
| `conversation_id` | Integer | NULL，**无外键** | 归因会话 |
| `run_id` | Integer | NULL，**无外键** | 归因执行记录 |
| `routing_tier` | Text | default `""` | 路由档位：`SIMPLE` / `MEDIUM` / `COMPLEX` / `REASONING` |
| `cost_usd` | Float | **NULLABLE** | 估算成本（美元）；NULL 表示定价未知 |
| `created_at` | Text | NOT NULL | 创建时间 |

索引：

| 名称 | 字段 | 用途 |
|---|---|---|
| `idx_llm_log_model` | `model_name` | 按模型聚合 |
| `idx_llm_log_created` | `created_at` | 时间窗口筛选 |
| `idx_llm_log_space` | (`space_id`, `created_at`) | 按空间算成本 |
| `idx_llm_log_conversation` | (`conversation_id`, `created_at`) | 按会话算成本 |
| `idx_llm_log_run` | (`run_id`, `created_at`) | 按执行记录算成本 |

### 12.1 三个归因列为什么不建外键

- `ON DELETE CASCADE`：删空间会把历史成本一起删掉，账目断档。
- `ON DELETE SET NULL`：统计变成无法归因的孤儿行，等于白记。
- 不建外键：空间/会话删除后行保留，`space_id` 仍指向「曾经的那个空间」。
  雪花 ID 不复用，所以这个引用永远有效。

### 12.2 成本口径

- `cost_usd` 由定价表计算：优先 `config.pricing`（自定义费率），其次 `litellm.model_cost`。
- 定价表查不到的模型（如 `zai/*`）记为 **NULL**，与「免费」严格区分。
- `GET /api/v1/usage/stats` 同时返回 `cost_usd` 与 `unpriced_calls`：
  前者只累加已知成本，后者表示有多少次无法计价。只看金额会低估真实开销。

### 12.3 `model_name` 必须是真实模型

`response_metadata["model"]` 是空键，用它兜底会把所有调用记成 Router 的逻辑组名
（如 `smart-router`），而逻辑组名没有定价，成本将永远是 NULL。取值优先级为：
`deployment` → `routing_decision.routed_model` → `deployment_model_name` → `model_name` / `model`。

---

## 十三、枚举速查

### agent_run.status

| 值 | 含义 |
|---|---|
| `running` | 执行中（插入即此态） |
| `completed` | 正常收尾，产出 `final` |
| `failed` | 产出 `error` 事件或抛出未捕获异常 |
| `cancelled` | 客户端断流，未走到明确终态 |

### agent_run.mode / conversation.mode

| 值 | 含义 | 可用工具 |
|---|---|---|
| `agent` | 执行模式（默认） | 全部 17 个 |
| `ask` | 问答模式，只读 | 12 个只读 |
| `plan` | 计划模式，只读 | 12 个只读 |

### agent_run.trigger_type

| 值 | 含义 |
|---|---|
| `chat` | 对话触发（当前唯一来源） |
| `manual` | 手工触发 |
| `scheduled` | 定时触发 |
| `ci` | CI 触发 |

### agent_tool_call.tool_type

| 值 | 归属工具 |
|---|---|
| `http` | `send_request`、`list_environments` |
| `db` | `get_space_endpoints`、`get_endpoint_detail_by_id` |
| `fs` | `read_file`、`write_file`、`list_directory`、`delete_file` |
| `exec` | `evaluate_assertions`、`extract_jsonpath` |
| `memory` | `recall`、`remember`、`forget` |
| `knowledge` | `knowledge_search` |
| `skill` | `list_skills`、`read_skill` |
| `search` | `search_space` |
| `other` | 未分类 |

### space_memory.category

| 值 | 含义 |
|---|---|
| `fact` | 客观事实，如鉴权头要求 |
| `decision` | 已定决策，如选定某环境 |
| `preference` | 约定与偏好，如命名规范 |
| `issue` | 已知问题与坑 |
| `glossary` | 领域术语 |

### knowledge_document.status / index_mode

| 字段 | 值 | 含义 |
|---|---|---|
| `status` | `pending` | 已入库，尚未索引 |
| | `indexed` | 索引完成 |
| | `failed` | 索引失败，原因见 `error` |
| `index_mode` | `vector` | 向量检索（Chroma + embedding） |
| | `lexical` | 词法检索（`LIKE` 降级） |

### skill.scope

| 值 | 含义 |
|---|---|
| `builtin` | 随代码分发，位于 `backend/skills/` |
| `space` | 空间级导入，位于 `<space>/.skills/` |

### message.role

| 值 | 含义 |
|---|---|
| `user` | 用户消息 |
| `assistant` | 助手回复 |
| `system` | 系统消息 |

### endpoint.method

`GET` · `POST` · `PUT` · `DELETE` · `PATCH` · `HEAD` · `OPTIONS`

---

## 十四、重建数据库

```bash
# 停止后端进程后删除库文件
rm backend/db/TestAgents.db          # macOS / Linux
del backend\db\TestAgents.db         # Windows

# 重新启动即自动建 12 张表并跑完 v2 / v3 / v4 迁移
cd backend && uv run python app.py
```

库文件删除不影响 `backend/workspaces/` 下的空间目录：目录与数据行是两套独立存储，
重建后需要重新创建空间，旧目录会以 `workspaces/.deleted-*` 的形式留在磁盘上，可手工回收。

---

## 十五、修订记录

| 日期 | 说明 |
|---|---|
| 2026-11-04 | v2.0：按当前 ORM 全量重写。删除 `test_run` / `test_case` / `test_result` / `test_summary` / `report` 五张表的章节（已由 v3/v4 迁移删除）；新增 `agent_run` / `agent_tool_call`；补 `space.base_url` 已移除的说明；`llm_log` 增补 `run_id` 与 `idx_llm_log_run`；表数量由 15 更正为 12 |
| 2026-10-21 | 补 `llm_log` 章节与归因列 |
| 2026-08-27 | `project` → `space` 术语层重命名；新增 `conversation` / `message` |
