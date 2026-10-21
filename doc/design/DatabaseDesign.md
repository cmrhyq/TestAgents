# ⛧ 数据库设计文档 — TestAgents ⛧

---

> *「数据库乃系统之基石，表结构即逻辑之骨架。此文档详录每一列、每一约束，以供后来者参阅。」*

---

## 〇、概述

| 项目         | 说明                                 |
|------------|------------------------------------|
| **数据库引擎**  | SQLite 3                           |
| **ORM 框架** | SQLAlchemy 2.0                     |
| **文件位置**   | `backend/db/TestAgents.db`（首次运行自动创建） |
| **ID 策略**  | 全局雪花算法（`next_id` 生成器），非自增          |
| **时间格式**   | `Text` 存储本地时间字符串（`local_now` 函数生成） |
| **表数量**    | 15 张（v1.0 新增 space_memory / knowledge_document / knowledge_chunk / skill） |

---

## 一、space — 空间表

> *「万事之始，皆立于空间。一个空间，统辖其下所有接口与测试。」*

### 字段定义

| 字段            | 类型      | 约束                   | 说明             |
|---------------|---------|----------------------|----------------|
| `id`          | Integer | **PK**, 非自增          | 全局唯一 ID        |
| `name`        | Text    | NOT NULL, **UNIQUE** | 空间名称           |
| `base_url`    | Text    | NOT NULL             | 默认基础 URL       |
| `description` | Text    | default=""           | 描述             |
| `workspace_path` | Text | default=""         | 工作目录相对路径（`workspaces/{id}`），Agent 文件沙箱根；v1.0 新增 |
| `status`      | Integer | NOT NULL, default=1  | 状态（1=启用，0=未启用） |
| `created_at`  | Text    | NOT NULL             | 创建时间           |
| `updated_at`  | Text    | NOT NULL             | 更新时间           |

### 索引

| 索引名              | 字段     |
|------------------|--------|
| `idx_space_name` | `name` |

### 关系

- 1:N → `environment`（CASCADE 级联删除）
- 1:N → `endpoint`（CASCADE 级联删除）
- 1:N → `test_run`（CASCADE 级联删除）
- 1:N → `conversation`（CASCADE 级联删除）

---

## 二、environment — 环境表

> *「同一接口，在不同环境中呈现不同面貌——开发、测试、生产，各有各的真相。」*

### 字段定义

| 字段            | 类型      | 约束                            | 说明         |
|---------------|---------|-------------------------------|------------|
| `id`          | Integer | **PK**, 非自增                   | 全局唯一 ID    |
| `space_id`    | Integer | **FK** → `space.id`, NOT NULL | 所属空间       |
| `name`        | Text    | NOT NULL                      | 环境名称       |
| `base_url`    | Text    | NOT NULL                      | 环境基础 URL   |
| `description` | Text    | default=""                    | 环境描述       |
| `variables`   | Text    | default="{}"                  | 环境变量（JSON） |
| `is_default`  | Integer | NOT NULL, default=1           | 是否默认环境     |
| `is_production` | Integer | NOT NULL, default=0         | 是否生产环境；为 1 时 `send_request` 直接拒绝请求（v1.0 新增） |
| `status`      | Integer | NOT NULL, default=1           | 状态         |
| `created_at`  | Text    | NOT NULL                      | 创建时间       |
| `updated_at`  | Text    | NOT NULL                      | 更新时间       |

### 索引

| 索引名             | 字段         |
|-----------------|------------|
| `idx_env_space` | `space_id` |

### 外键删除策略

| 外键         | 指向         | 策略      |
|------------|------------|---------|
| `space_id` | `space.id` | CASCADE |

---

## 三、endpoint — 接口表

> *「接口者，系统与外界沟通之门户也。路径、方法、参数，缺一不可。」*

### 字段定义

| 字段             | 类型      | 约束                            | 说明                  |
|----------------|---------|-------------------------------|---------------------|
| `id`           | Integer | **PK**, 非自增                   | 全局唯一 ID             |
| `space_id`     | Integer | **FK** → `space.id`, NOT NULL | 所属空间                |
| `operation_id` | Text    | NOT NULL                      | OpenAPI operationId |
| `name`         | Text    | NOT NULL                      | 接口名称                |
| `path`         | Text    | NOT NULL                      | 请求路径                |
| `method`       | Text    | NOT NULL                      | HTTP 方法             |
| `tags`         | Text    | default="[]"                  | 标签（JSON 数组）         |
| `summary`      | Text    | NULLABLE                      | 简要描述                |
| `description`  | Text    | default=""                    | 详细描述                |
| `params`       | Text    | NULLABLE                      | 路径/查询参数（JSON）       |
| `headers`      | Text    | default="{}"                  | 请求头定义（JSON）         |
| `body`         | Text    | NULLABLE                      | 请求体 Schema（JSON）    |
| `responses`    | Text    | default="[]"                  | 响应定义（JSON 数组）       |
| `security`     | Text    | default="[]"                  | 安全要求（JSON 数组）       |
| `content_type` | Text    | default="application/json"    | 内容类型                |
| `deprecated`   | Integer | NOT NULL, default=0           | 是否已废弃               |
| `status`       | Integer | NOT NULL, default=1           | 状态                  |
| `version`      | Integer | NOT NULL, default=1           | 版本号                 |
| `created_at`   | Text    | NOT NULL                      | 创建时间                |
| `updated_at`   | Text    | NOT NULL                      | 更新时间                |

### 约束

| 约束名                    | 类型     | 规则                                                                 |
|------------------------|--------|--------------------------------------------------------------------|
| `ck_api_method`        | CHECK  | `method IN ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')` |
| `uq_space_path_method` | UNIQUE | `(space_id, path, method)`                                         |

### 索引

| 索引名                         | 字段             |
|-----------------------------|----------------|
| `idx_endpoint_space`        | `space_id`     |
| `idx_endpoint_operation_id` | `operation_id` |

### 外键删除策略

| 外键         | 指向         | 策略      |
|------------|------------|---------|
| `space_id` | `space.id` | CASCADE |

---

## 四、test_run — 测试运行表

> *「每一次测试运行，都是一场审判——代码在此接受检验，真相在此大白。」*

### 字段定义

| 字段                | 类型      | 约束                                  | 说明         |
|-------------------|---------|-------------------------------------|------------|
| `id`              | Integer | **PK**, 非自增                         | 全局唯一 ID    |
| `space_id`        | Integer | **FK** → `space.id`, NOT NULL       | 关联空间       |
| `environment_id`  | Integer | **FK** → `environment.id`, NULLABLE | 关联环境       |
| `name`            | Text    | default=""                          | 运行名称       |
| `status`          | Text    | NOT NULL, default="pending"         | 运行状态       |
| `trigger_type`    | Text    | NOT NULL, default="manual"          | 触发方式       |
| `input_file`      | Text    | default=""                          | 输入文件路径     |
| `input_snapshot`  | Text    | default="{}"                        | 输入快照（JSON） |
| `config_snapshot` | Text    | default="{}"                        | 配置快照（JSON） |
| `llm_provider`    | Text    | default=""                          | LLM 提供商    |
| `llm_model`       | Text    | default=""                          | LLM 模型名称   |
| `total_cases`     | Integer | NOT NULL, default=0                 | 用例总数       |
| `passed_cases`    | Integer | NOT NULL, default=0                 | 通过数        |
| `failed_cases`    | Integer | NOT NULL, default=0                 | 失败数        |
| `skipped_cases`   | Integer | NOT NULL, default=0                 | 跳过数        |
| `error_cases`     | Integer | NOT NULL, default=0                 | 错误数        |
| `pass_rate`       | Float   | NOT NULL, default=0.0               | 通过率        |
| `started_at`      | Text    | NULLABLE                            | 开始时间       |
| `finished_at`     | Text    | NULLABLE                            | 结束时间       |
| `total_duration`  | Float   | NOT NULL, default=0.0               | 总耗时（秒）     |
| `error_message`   | Text    | default=""                          | 错误信息       |
| `created_at`      | Text    | NOT NULL                            | 创建时间       |
| `updated_at`      | Text    | NOT NULL                            | 更新时间       |

### 约束

| 约束名              | 类型    | 规则                                                                 |
|------------------|-------|--------------------------------------------------------------------|
| `ck_run_status`  | CHECK | `status IN ('pending','running','completed','failed','cancelled')` |
| `ck_run_trigger` | CHECK | `trigger_type IN ('manual','scheduled','ci')`                      |

### 索引

| 索引名             | 字段               |
|-----------------|------------------|
| `idx_run_space` | `space_id`       |
| `idx_run_env`   | `environment_id` |

### 外键删除策略

| 外键               | 指向               | 策略       |
|------------------|------------------|----------|
| `space_id`       | `space.id`       | CASCADE  |
| `environment_id` | `environment.id` | SET NULL |

---

## 五、test_case — 测试用例表

> *「用例乃测试之灵魂——每一条用例，都是对系统的一次质问。」*

### 字段定义

| 字段                | 类型      | 约束                               | 说明            |
|-------------------|---------|----------------------------------|---------------|
| `id`              | Integer | **PK**, 非自增                      | 全局唯一 ID       |
| `run_id`          | Integer | **FK** → `test_run.id`, NOT NULL | 所属测试运行        |
| `endpoint_id`     | Integer | **FK** → `endpoint.id`, NULLABLE | 关联接口          |
| `case_id`         | Text    | NOT NULL                         | 用例业务 ID       |
| `case_name`       | Text    | NOT NULL                         | 用例名称          |
| `url`             | Text    | NOT NULL                         | 请求 URL        |
| `method`          | Text    | NOT NULL                         | HTTP 方法       |
| `scenario_type`   | Text    | NOT NULL, default="normal"       | 场景类型          |
| `priority`        | Text    | NOT NULL, default="P1"           | 优先级           |
| `headers`         | Text    | default="{}"                     | 请求头（JSON）     |
| `body`            | Text    | NULLABLE                         | 请求体（JSON）     |
| `params`          | Text    | NULLABLE                         | 查询参数（JSON）    |
| `cache_rules`     | Text    | NULLABLE                         | 缓存规则（JSON）    |
| `assert_rules`    | Text    | default="[]"                     | 断言规则（JSON 数组） |
| `expected_result` | Text    | default="成功"                     | 预期结果描述        |
| `description`     | Text    | default=""                       | 用例描述          |
| `remark`          | Text    | default=""                       | 备注            |
| `unique_hash`     | Text    | default=""                       | 去重哈希          |
| `generated_by`    | Text    | NOT NULL, default="llm"          | 生成方式          |
| `status`          | Integer | NOT NULL, default=1              | 状态            |
| `created_at`      | Text    | NOT NULL                         | 创建时间          |
| `updated_at`      | Text    | NOT NULL                         | 更新时间          |

### 约束

| 约束名                 | 类型    | 规则                                                                                                            |
|---------------------|-------|---------------------------------------------------------------------------------------------------------------|
| `ck_case_method`    | CHECK | `method IN ('GET','POST','PUT','DELETE','PATCH','HEAD','OPTIONS')`                                            |
| `ck_case_scenario`  | CHECK | `scenario_type IN ('normal','param_missing','param_type_error','boundary_value','permission_error','custom')` |
| `ck_case_priority`  | CHECK | `priority IN ('P0','P1','P2')`                                                                                |
| `ck_case_generated` | CHECK | `generated_by IN ('llm','manual','import')`                                                                   |

### 索引

| 索引名                | 字段            |
|--------------------|---------------|
| `idx_case_run`     | `run_id`      |
| `idx_case_api`     | `endpoint_id` |
| `idx_case_case_id` | `case_id`     |

### 外键删除策略

| 外键            | 指向            | 策略       |
|---------------|---------------|----------|
| `run_id`      | `test_run.id` | CASCADE  |
| `endpoint_id` | `endpoint.id` | SET NULL |

---

## 六、test_result — 测试结果表

> *「结果不会说谎——状态码、响应体、耗时，铁证如山。」*

### 字段定义

| 字段                     | 类型      | 约束                                | 说明          |
|------------------------|---------|-----------------------------------|-------------|
| `id`                   | Integer | **PK**, 非自增                       | 全局唯一 ID     |
| `run_id`               | Integer | **FK** → `test_run.id`, NOT NULL  | 所属测试运行      |
| `test_case_id`         | Integer | **FK** → `test_case.id`, NOT NULL | 关联测试用例      |
| `case_id`              | Text    | NOT NULL                          | 用例业务 ID（冗余） |
| `case_name`            | Text    | NOT NULL                          | 用例名称（冗余）    |
| `status`               | Text    | NOT NULL, default="pending"       | 执行状态        |
| `request_url`          | Text    | default=""                        | 实际请求 URL    |
| `request_method`       | Text    | default=""                        | 实际请求方法      |
| `request_headers`      | Text    | default="{}"                      | 实际请求头（JSON） |
| `request_body`         | Text    | NULLABLE                          | 实际请求体       |
| `query_params`         | Text    | NULLABLE                          | 实际查询参数      |
| `response_status_code` | Integer | NULLABLE                          | 响应状态码       |
| `response_headers`     | Text    | default="{}"                      | 响应头（JSON）   |
| `response_body`        | Text    | NULLABLE                          | 响应体         |
| `response_time`        | Float   | NOT NULL, default=0.0             | 响应时间（秒）     |
| `error_message`        | Text    | default=""                        | 错误信息        |
| `retry_count`          | Integer | NOT NULL, default=0               | 重试次数        |
| `started_at`           | Text    | NULLABLE                          | 开始时间        |
| `finished_at`          | Text    | NULLABLE                          | 结束时间        |
| `created_at`           | Text    | NOT NULL                          | 创建时间        |

### 约束

| 约束名                | 类型    | 规则                                                                    |
|--------------------|-------|-----------------------------------------------------------------------|
| `ck_result_status` | CHECK | `status IN ('pending','running','passed','failed','skipped','error')` |

### 索引

| 索引名               | 字段             |
|-------------------|----------------|
| `idx_result_run`  | `run_id`       |
| `idx_result_case` | `test_case_id` |

### 外键删除策略

| 外键             | 指向             | 策略      |
|----------------|----------------|---------|
| `run_id`       | `test_run.id`  | CASCADE |
| `test_case_id` | `test_case.id` | CASCADE |

---

## 七、test_summary — 测试汇总表

> *「汇总者，统观全局之眼也。通过率、响应时间、失败原因——一览无余。」*

### 字段定义

| 字段                  | 类型      | 约束                                           | 说明           |
|---------------------|---------|----------------------------------------------|--------------|
| `id`                | Integer | **PK**, 非自增                                  | 全局唯一 ID      |
| `run_id`            | Integer | **FK** → `test_run.id`, NOT NULL, **UNIQUE** | 关联测试运行（一对一）  |
| `total`             | Integer | NOT NULL, default=0                          | 用例总数         |
| `passed`            | Integer | NOT NULL, default=0                          | 通过数          |
| `failed`            | Integer | NOT NULL, default=0                          | 失败数          |
| `skipped`           | Integer | NOT NULL, default=0                          | 跳过数          |
| `error`             | Integer | NOT NULL, default=0                          | 错误数          |
| `pass_rate`         | Float   | NOT NULL, default=0.0                        | 通过率          |
| `avg_response_time` | Float   | NOT NULL, default=0.0                        | 平均响应时间       |
| `min_response_time` | Float   | NOT NULL, default=0.0                        | 最小响应时间       |
| `max_response_time` | Float   | NOT NULL, default=0.0                        | 最大响应时间       |
| `p95_response_time` | Float   | NOT NULL, default=0.0                        | P95 响应时间     |
| `total_duration`    | Float   | NOT NULL, default=0.0                        | 总耗时          |
| `failure_reasons`   | Text    | default="{}"                                 | 失败原因统计（JSON） |
| `started_at`        | Text    | NULLABLE                                     | 开始时间         |
| `finished_at`       | Text    | NULLABLE                                     | 结束时间         |
| `created_at`        | Text    | NOT NULL                                     | 创建时间         |

### 索引

| 索引名                     | 字段          |
|-------------------------|-------------|
| `idx_summary_run`       | `run_id`    |
| `idx_summary_pass_rate` | `pass_rate` |

### 外键删除策略

| 外键       | 指向            | 策略      |
|----------|---------------|---------|
| `run_id` | `test_run.id` | CASCADE |

---

## 八、report — 报告表

> *「报告乃测试之终章——将混沌的数据，锻造为可读的真知。」*

### 字段定义

| 字段             | 类型      | 约束                               | 说明       |
|----------------|---------|----------------------------------|----------|
| `id`           | Integer | **PK**, 非自增                      | 全局唯一 ID  |
| `run_id`       | Integer | **FK** → `test_run.id`, NOT NULL | 关联测试运行   |
| `format`       | Text    | NOT NULL                         | 报告格式     |
| `file_path`    | Text    | NOT NULL                         | 文件路径     |
| `file_size`    | Integer | default=0                        | 文件大小（字节） |
| `generated_at` | Text    | NOT NULL                         | 生成时间     |

### 约束

| 约束名                | 类型    | 规则                                             |
|--------------------|-------|------------------------------------------------|
| `ck_report_format` | CHECK | `format IN ('excel','html','markdown','json')` |

### 索引

| 索引名                 | 字段       |
|---------------------|----------|
| `idx_report_run`    | `run_id` |
| `idx_report_format` | `format` |

### 外键删除策略

| 外键       | 指向            | 策略      |
|----------|---------------|---------|
| `run_id` | `test_run.id` | CASCADE |

---

## 九、conversation — 会话表

> *「会话者，用户与智能体之间的对话历程也。每轮交互，皆有据可查。」*

### 字段定义

| 字段                | 类型      | 约束                            | 说明               |
|-------------------|---------|-------------------------------|------------------|
| `id`              | Integer | **PK**, 非自增                   | 全局唯一 ID          |
| `space_id`        | Integer | **FK** → `space.id`, NULLABLE | 关联空间（可空，支持无空间会话） |
| `title`           | Text    | NOT NULL, default=""          | 会话标题（首条 user 消息截断生成） |
| `mode`            | Text    | NOT NULL, default="agent"     | 工作模式 `agent` / `ask` / `plan` |
| `skill_names`     | Text    | NOT NULL, default="[]"        | 本会话选中的 skill 名（JSON 数组） |
| `environment_id`  | Integer | **FK** → `environment.id`, NULLABLE, ON DELETE SET NULL | 会话绑定的测试环境，供 `send_request` 解析 base_url 与生产环境闸门 |
| `status`          | Integer | NOT NULL, default=1           | 状态（1=启用，0=未启用）   |
| `last_message_at` | Text    | NULLABLE                      | 最后消息时间           |
| `created_at`      | Text    | NOT NULL                      | 创建时间             |
| `updated_at`      | Text    | NOT NULL                      | 更新时间             |

### 约束

| 约束名                      | 类型    | 规则                                |
|--------------------------|-------|-----------------------------------|
| `ck_conversation_mode`   | CHECK | `mode IN ('agent','ask','plan')`  |
| `ck_conversation_status` | CHECK | `status IN (0,1)`                 |

> **v1.0 迁移说明**：旧约束是 `mode IN ('Ask','Plan','Run')`，会阻止写入 `agent`。
> SQLite 不支持修改 CHECK，`migrate_v2` 采用「`PRAGMA foreign_keys=OFF` → 建新表 → 拷数据 →
> 删旧表 → 改名 → 重跑索引」的方式重建，并有测试锁死「重建不能丢 message」。
> 服务层同时用 `normalize_mode` 兜底历史值（`Run`/`Ask`/`Plan` → 小写标准值）。

### 索引

| 索引名                      | 字段         |
|--------------------------|------------|
| `idx_conversation_space` | `space_id` |

### 外键删除策略

| 外键               | 指向               | 策略         |
|------------------|------------------|------------|
| `space_id`       | `space.id`       | CASCADE    |
| `environment_id` | `environment.id` | SET NULL   |

---

## 九·补、space_memory — 跨会话记忆表（v1.0 新增）

> *「记忆者，跨会话之结论沉淀也。按空间隔离，可增删改，并镜像为可读文件。」*

真源是这张表；`workspaces/{space_id}/memory/MEMORY.md` 是**只读镜像**，
每次写操作后由 `LongTermMemory.sync_markdown` 全量重建（不做增量，避免与 DB 漂移）。

### 字段定义

| 字段                       | 类型      | 约束                        | 说明                          |
|--------------------------|---------|---------------------------|-----------------------------|
| `id`                     | Integer | **PK**, 非自增               | 全局唯一 ID                     |
| `space_id`               | Integer | **FK** → `space.id`, NOT NULL | 记忆归属空间（隔离边界）              |
| `title`                  | Text    | NOT NULL                  | 要点标题（注入 prompt 时的要点行）      |
| `content`                | Text    | NOT NULL, default=""      | 内容正文                        |
| `category`               | Text    | NOT NULL, default="fact"  | `fact` / `decision` / `preference` / `issue` / `glossary` |
| `tags`                   | Text    | NOT NULL, default="[]"    | 标签（JSON 数组），参与检索匹配          |
| `source_conversation_id` | Integer | **FK** → `conversation.id`, NULLABLE, ON DELETE SET NULL | 产出该记忆的会话，可追溯 |
| `status`                 | Integer | NOT NULL, default=1       | 1=有效，0=软删                   |
| `created_at`             | Text    | NOT NULL                  | 创建时间                        |
| `updated_at`             | Text    | NOT NULL                  | 更新时间（召回排序依据）                |

### 约束与索引

| 名称                  | 类型    | 规则                                  |
|---------------------|-------|-------------------------------------|
| `ck_memory_category` | CHECK | `category IN ('fact','decision','preference','issue','glossary')` |
| `ck_memory_status`   | CHECK | `status IN (0,1)`                   |
| `idx_memory_space`   | INDEX | (`space_id`, `status`)              |
| `idx_memory_category`| INDEX | (`space_id`, `category`)            |

### 检索方式

**不用向量检索**。记忆是几十到几百条「结论型短文本」，需要精确命中而非语义相似：
SQLite `LIKE` 足够，且零外部依赖、结果可解释（能说清命中哪个关键词）、可按更新时间排序。
查询会被 `extract_keywords` 拆成 ASCII 整词 + CJK 2-gram，多关键词 OR 匹配。

---

## 九·补二、skill — 技能表（v1.0 新增）

> *「技能者，可复用的测试方法论也。文件为真源，此表只记录启停与来源。」*

**内容是文件，不是表**：`SKILL.md` 才是有意义的数据，这张表只存前端需要的
「是否启用」和「装在哪」——重启后由 `SkillRegistry.sync` 从磁盘扫描重新对齐。

### 字段定义

| 字段              | 类型      | 约束                          | 说明                          |
|-----------------|---------|-----------------------------|-----------------------------|
| `id`            | Integer | **PK**, 非自增                 | 全局唯一 ID                     |
| `name`          | Text    | NOT NULL                    | skill 名（`^[a-z0-9][a-z0-9-]{0,63}$`） |
| `description`   | Text    | NOT NULL, default=""        | 简介（来自 frontmatter）           |
| `scope`         | Text    | NOT NULL, default="builtin" | `builtin`（随代码分发）/ `space`（用户导入） |
| `space_id`      | Integer | NULLABLE，**无 FK 约束**         | 空间级 skill 的归属；内置为 NULL。文件系统才是真源，不建 FK 避免「目录已删、行还挂着」导致写入失败 |
| `directory`     | Text    | NOT NULL, default=""        | 磁盘目录（展示 + 排障用）              |
| `when_to_use`   | Text    | NOT NULL, default=""        | 何时使用（frontmatter `when_to_use`） |
| `version`       | Text    | NOT NULL, default=""        | 技能版本号                        |
| `allowed_tools` | Text    | NOT NULL, default="[]"      | 声明的工具名（JSON 数组），与模式白名单**取交集** |
| `enabled`       | Integer | NOT NULL, default=1         | 1=启用，0=禁用                   |
| `discovered_at` | Text    | NOT NULL                    | 最近一次被发现/同步的时间                |

### 约束与索引

| 名称                | 类型    | 规则                            |
|-------------------|-------|-------------------------------|
| `ck_skill_scope`  | CHECK | `scope IN ('builtin','space')` |
| `ck_skill_enabled`| CHECK | `enabled IN (0,1)`             |
| `idx_skill_scope` | INDEX | (`scope`, `space_id`)          |
| `idx_skill_name`  | INDEX | (`name`)                      |

> **没有 (`name`,`space_id`) 唯一约束**：同名技能允许在 builtin 与多个 space 下并存，
> 解析时按「空间优先覆盖内置」的规则择一。

> **安全关键**：`allowed_tools` 只能**收窄**可用工具。`filter_tools` 先按模式去掉副作用工具，
> 再按 skill 声明取交集——顺序不能反，否则 skill 会成为提权通道。

---

## 九·补三、knowledge_document / knowledge_chunk — 知识库（v1.0 新增）

> *「知识库者，需求文档与接口文档之所归也。切为片段，可语义可词法。」*

### knowledge_document — 文档表

| 字段            | 类型      | 约束                          | 说明                       |
|---------------|---------|-----------------------------|--------------------------|
| `id`          | Integer | **PK**, 非自增                 | 全局唯一 ID                  |
| `space_id`    | Integer | **FK** → `space.id`, NOT NULL | 归属空间                     |
| `filename`    | Text    | NOT NULL                    | 原始文件名                    |
| `file_path`   | Text    | NOT NULL                    | 空间目录内相对路径（真源是磁盘文件）       |
| `mime`        | Text    | NOT NULL, default=""        | MIME 类型                  |
| `size`        | Integer | NOT NULL, default=0         | 字节数                      |
| `chunk_count` | Integer | NOT NULL, default=0         | 切片数                      |
| `status`      | Text    | NOT NULL, default="pending" | `pending` / `indexed` / `failed` |
| `index_mode`  | Text    | NOT NULL, default="lexical" | `vector`（Chroma）/ `lexical`（SQLite LIKE 降级） |
| `error`       | Text    | NOT NULL, default=""        | 索引失败原因                   |
| `created_at`  | Text    | NOT NULL                    | 创建时间                     |
| `updated_at`  | Text    | NOT NULL                    | 更新时间                     |

### knowledge_chunk — 切片表

| 字段            | 类型      | 约束                              | 说明                    |
|---------------|---------|---------------------------------|-----------------------|
| `id`          | Integer | **PK**, 非自增                     | 全局唯一 ID               |
| `document_id` | Integer | **FK** → `knowledge_document.id`, NOT NULL, CASCADE | 所属文档 |
| `space_id`    | Integer | **FK** → `space.id`, NOT NULL     | 冗余空间 ID，避免检索时多一次 join |
| `seq`         | Integer | NOT NULL                        | 切片序号（从 0 起）           |
| `content`     | Text    | NOT NULL                        | 切片正文                  |
| `chroma_id`   | Text    | NULLABLE                        | Chroma 中的向量 ID（词法模式为空）|
| `created_at`  | Text    | NOT NULL                        | 创建时间                  |

### 切片策略

固定窗口 + 自然断点回退：目标 800 字符、重叠 100 字符；优先在段落/句号/换行处断开，
找不到自然断点才硬切。重叠是为了避免「答案正好跨在两个切片的缝里」。

### 索引与约束

| 名称                          | 类型    | 规则                            |
|-----------------------------|-------|-------------------------------|
| `ck_document_status`     | CHECK | `status IN ('pending','indexed','failed')` |
| `ck_document_index_mode` | CHECK | `index_mode IN ('vector','lexical')` |
| `idx_document_space`     | INDEX | `space_id`                          |
| `idx_chunk_doc`          | INDEX | (`document_id`, `seq`)              |
| `idx_chunk_space`        | INDEX | `space_id`                          |

---

## 九·补四、llm_log — LLM 调用统计表

> *「调用留痕者，成本与排障之凭据也。表系于空间与会话，而不设外键——盖账要能对，不该随业务数据一同湮灭。」*

### 字段定义

| 字段                  | 类型      | 约束                    | 说明                                     |
|---------------------|---------|-----------------------|----------------------------------------|
| `id`                | Integer | **PK**, 非自增           | 全局唯一 ID                                |
| `model_name`        | Text    | NOT NULL              | **实际命中**的模型（如 `zai/glm-4-flash`），不是 Router 的 `smart-router` |
| `provider`          | Text    | default=""            | 厂商（`model_name` 前缀）                     |
| `request_type`      | Text    | default=""            | 调用类型：`invoke` / `ainvoke` / `stream` / `astream` / `tools` |
| `prompt_tokens`     | Integer | default=0             | 输入 token 数                             |
| `completion_tokens` | Integer | default=0             | 输出 token 数                             |
| `total_tokens`      | Integer | default=0             | 总 token 数                               |
| `duration_ms`       | Integer | default=0             | 调用耗时（毫秒）                              |
| `success`           | Integer | default=1             | 1=成功，0=失败                             |
| `error_message`     | Text    | default=""            | 失败原因（成功时为空）                             |
| `space_id`          | Integer | NULLABLE，**无 FK**      | 归因空间；空间删除后本列保留                         |
| `conversation_id`   | Integer | NULLABLE，**无 FK**      | 归因会话；会话清理后本列保留                         |
| `routing_tier`      | Text    | default=""            | smart-router 决策档位：`SIMPLE` / `MEDIUM` / `COMPLEX` / `REASONING` |
| `cost_usd`          | Float   | NULLABLE              | 估算成本（美元）。**NULL = 定价未知，0 = 真的免费**      |
| `created_at`        | Text    | NOT NULL              | 创建时间                                    |

### 索引

| 索引名                          | 字段                              | 用途               |
|------------------------------|---------------------------------|------------------|
| `idx_llm_log_model`          | `model_name`                    | 按模型聚合            |
| `idx_llm_log_created`        | `created_at`                    | 时间窗口筛选           |
| `idx_llm_log_space`          | (`space_id`, `created_at`)      | 按空间 + 时间算成本      |
| `idx_llm_log_conversation`   | (`conversation_id`, `created_at`) | 按会话 + 时间算成本     |

### 写入点

- 埋点在 `LLMService._record_usage`，由 `invoke` / `ainvoke` / `stream` / `astream` /
  `invoke_with_tools` / **`astream_with_tools`** 统一调用。
- `agent/runner.py` 每轮调用 `LLMGateway.astream_with_tools(...)` 并传入 `space_id` /
  `conversation_id`，因此**一轮 ReAct 对话会产生 1~N 条记录**（每轮都是一次独立计费调用）。
- `LLMGateway.get_model()` 是「直接取底层 `BaseChatModel`」的弃用快路径，
  **不经过埋点**，已加 `DeprecationWarning`，业务代码不得使用。

### 为什么归因列不建外键

- 加了 `ON DELETE CASCADE`：删空间会把历史成本一并删掉，账目断档。
- 加了 `ON DELETE SET NULL`：统计变成孤儿行，仍无法归因。
- 不建外键：空间/会话删除后行保留，`space_id` 仍能对应到「曾经的空间」，
  对账时可用（空间 ID 是雪花值，不会重用）。

### 成本口径

- `cost_usd` 由定价表计算：优先 `config.pricing`（自定义费率），其次 `litellm.model_cost`。
- 定价表查不到的模型（如 `zai/*`）记为 **NULL**，与「免费」严格区分。
- 查询口径见 `GET /api/v1/usage/stats`：`cost_usd` 只累加已知成本，
  `unpriced_calls` 单独暴露未计价次数，避免把部分成本当成全部成本。


---

## 十、message — 消息表

> *「消息为会话之血肉——append-only，不可修改，不可删除，唯有追加。」*

### 字段定义

| 字段                | 类型      | 约束                                   | 说明        |
|-------------------|---------|--------------------------------------|-----------|
| `id`              | Integer | **PK**, 非自增                          | 全局唯一 ID   |
| `conversation_id` | Integer | **FK** → `conversation.id`, NOT NULL | 所属会话      |
| `role`            | Text    | NOT NULL                             | 消息角色      |
| `content`         | Text    | NOT NULL, default=""                 | 消息内容      |
| `meta`            | Text    | NOT NULL, default="{}"               | 元数据（JSON） |
| `created_at`      | Text    | NOT NULL                             | 创建时间      |

### 约束

| 约束名               | 类型    | 规则                                      |
|-------------------|-------|-----------------------------------------|
| `ck_message_role` | CHECK | `role IN ('user','assistant','system')` |

### 索引

| 索引名                | 字段                |
|--------------------|-------------------|
| `idx_message_conv` | `conversation_id` |

### 外键删除策略

| 外键                | 指向                | 策略      |
|-------------------|-------------------|---------|
| `conversation_id` | `conversation.id` | CASCADE |

---

## 十一、枚举值速查

> *「标准化的值域，是数据完整性的守护者。」*

### test_run.status

| 值           | 含义   |
|-------------|------|
| `pending`   | 等待执行 |
| `running`   | 执行中  |
| `completed` | 已完成  |
| `failed`    | 执行失败 |
| `cancelled` | 已取消  |

### test_run.trigger_type

| 值           | 含义       |
|-------------|----------|
| `manual`    | 手动触发     |
| `scheduled` | 定时触发     |
| `ci`        | CI/CD 触发 |

### test_case.scenario_type

| 值                  | 含义     |
|--------------------|--------|
| `normal`           | 正常场景   |
| `param_missing`    | 参数缺失   |
| `param_type_error` | 参数类型错误 |
| `boundary_value`   | 边界值    |
| `permission_error` | 权限错误   |
| `custom`           | 自定义场景  |

### test_case.priority

| 值    | 含义          |
|------|-------------|
| `P0` | 最高优先级（冒烟测试） |
| `P1` | 高优先级（核心功能）  |
| `P2` | 普通优先级（边缘场景） |

### test_case.generated_by

| 值        | 含义       |
|----------|----------|
| `llm`    | LLM 自动生成 |
| `manual` | 人工编写     |
| `import` | 外部导入     |

### test_result.status

| 值         | 含义        |
|-----------|-----------|
| `pending` | 等待执行      |
| `running` | 执行中       |
| `passed`  | 通过        |
| `failed`  | 失败（断言不通过） |
| `skipped` | 跳过（依赖未满足） |
| `error`   | 错误（执行异常）  |

### conversation.mode

| 值        | 含义                    | 可用工具        |
|----------|-----------------------|-------------|
| `agent`  | 执行模式（默认）：自动挑工具并执行测试   | 全部 17 个      |
| `ask`    | 问答模式：只回答，不动手          | 12 个只读       |
| `plan`   | 计划模式：只出计划，不执行         | 12 个只读       |

> v1.0 前为 `Ask` / `Plan` / `Run`，已迁移为小写。旧值由 `normalize_mode()` 兼容映射，
> 但 DB 层 CHECK 只接受小写三值。

### space_memory.category

| 值            | 含义            |
|--------------|---------------|
| `fact`       | 客观事实（如鉴权头要求）  |
| `decision`   | 已定决策（如选用某环境）  |
| `preference` | 偏好（如命名规范）     |
| `issue`      | 已知问题 / 坑      |
| `glossary`   | 领域术语          |

### knowledge_document.status / index_mode

| 字段           | 值                        | 含义                     |
|--------------|--------------------------|------------------------|
| `status`     | `pending`                | 已入库，尚未索引               |
|              | `indexed`                | 索引完成                   |
|              | `failed`                 | 索引失败（原因见 `error`）      |
| `index_mode` | `vector`                 | 走向量检索（Chroma + embedding） |
|              | `lexical`                | 走词法检索（SQLite LIKE 降级）  |

### skill.scope

| 值         | 含义               |
|-----------|------------------|
| `builtin` | 随代码分发的内置技能       |
| `space`   | 用户为某个空间导入的技能     |

### message.role

| 值           | 含义   |
|-------------|------|
| `user`      | 用户消息 |
| `assistant` | 助手回复 |
| `system`    | 系统消息 |

### report.format

| 值          | 含义          |
|------------|-------------|
| `excel`    | Excel 格式    |
| `html`     | HTML 格式     |
| `markdown` | Markdown 格式 |
| `json`     | JSON 格式     |

### endpoint.method / test_case.method

| 值         |
|-----------|
| `GET`     |
| `POST`    |
| `PUT`     |
| `DELETE`  |
| `PATCH`   |
| `HEAD`    |
| `OPTIONS` |

---

## 十二、数据库重建

```bash
# Windows
del db\LLMTest.db

# macOS / Linux
rm db/LLMTest.db

# 重新运行程序即可自动重建所有表结构
python main.py "解析这份API文档并存储" --api-doc input/httpbin_service.json
```

---

## 十三、修订记录

| 日期         | 说明                                                                                                                                            |
|------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| 2026-08-27 | `project` → `space` 术语层重命名；`test_run.space_id` 改为 NOT NULL + CASCADE；新增 `conversation` / `message` 两表；枚举速查补充 conversation.mode / message.role |
| 旧版         | 初始版本（project 术语）                                                                                                                              |

---

> *「此文档终。数据库之道，尽在此间。」*

---

*📎 相关文档：[系统流程图](SystemFlowchart.md) · [ER 图](ER.md)*
