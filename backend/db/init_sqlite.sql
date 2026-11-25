-- ============================================================================
-- TestAgents 数据库建表脚本 (SQLite)
--
-- 说明：
-- 1. 应用启动时由 SQLAlchemy Base.metadata.create_all() 建表，本脚本用于
--    手工初始化 / 种子数据参考，全部语句可重复执行（IF NOT EXISTS / OR IGNORE）。
-- 2. status 语义统一为 0=未启用，1=已启用（与前端 STATUS_MAP 一致）。
-- 3. environment.is_default 语义为 1=默认，0=不默认（布尔语义，与前端一致）。
-- 4. 本表结构必须与 src/data/models/*.py 保持一致，改表请同步改模型。
--
-- 字段注释约定：
--   * id：主键一律由应用层 next_id() 生成，关闭数据库自增（autoincrement=False）。
--   * *_at：时间列为 TEXT，格式 YYYY-MM-DDTHH:MM:SS.mmm（本地时间），
--           可直接按字符串排序比较；updated_at 由 trg_*_updated 触发器刷新。
--   * *_id：外键列，注释中标注指向表与删除策略（CASCADE / SET NULL / 无外键）。
--   * JSON 列：存序列化字符串，NULL 与 '{}' / '[]' 语义不同，不可互相替代。
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
-- 注意：SQLite 的 encoding 为建库期属性，对已存在的数据库执行此 PRAGMA 会静默无效。

-- ============================================================================
-- 1. 空间表 (space)
--    管理多个被测服务，支持多空间隔离
-- ============================================================================
CREATE TABLE IF NOT EXISTS space
(
    id          INTEGER PRIMARY KEY,                                    -- 主键，next_id() 生成
    name        TEXT    NOT NULL UNIQUE,                                -- 空间名，全库唯一
    description TEXT             DEFAULT '',                            -- 空间描述
    status      INTEGER NOT NULL DEFAULT 1,                             -- 0=未启用，1=已启用
    -- 时间列：created_at 创建时间，updated_at 更新时间（trg_space_updated 维护）
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_space_name    ON space(name);

-- ============================================================================
-- 2. 测试环境表 (environment)
--    记录执行时的运行环境信息，支持多环境对比
-- ============================================================================
CREATE TABLE IF NOT EXISTS environment
(
    id          INTEGER PRIMARY KEY,                                    -- 主键，next_id() 生成
    space_id    INTEGER NOT NULL,                                       -- 所属空间，space.id；级联删除
    name        TEXT    NOT NULL,                                       -- 环境名（如 dev/uat/prod）
    base_url    TEXT    NOT NULL,                                       -- 基础地址，不含末尾斜杠；URL = base_url + path
    description TEXT             DEFAULT '',                            -- 环境描述
    variables   TEXT             DEFAULT '{}',                          -- 环境变量 JSON 对象，占位符来源
    is_default  INTEGER NOT NULL DEFAULT 1,                             -- 1=空间内默认环境，0=非默认
    status      INTEGER NOT NULL DEFAULT 1,                             -- 0=未启用，1=已启用
    -- 时间列：created_at 创建时间，updated_at 更新时间（trg_environment_updated 维护）
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (space_id) REFERENCES space (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_env_space ON environment (space_id);

-- ============================================================================
-- 3. API 定义表 (endpoint)
--    持久化 API 接口定义，支持版本化和复用
-- ============================================================================
CREATE TABLE IF NOT EXISTS endpoint
(
    id           INTEGER PRIMARY KEY,                                   -- 主键，next_id() 生成
    space_id     INTEGER NOT NULL,                                      -- 所属空间，space.id；级联删除
    operation_id TEXT    NOT NULL,                                      -- 来源标识：OpenAPI operationId 或生成的稳定标识
    name         TEXT    NOT NULL,                                      -- 接口名称
    path         TEXT    NOT NULL,                                      -- 接口路径，含路径参数占位符
    method       TEXT    NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS')), -- HTTP 方法
    tags         TEXT             DEFAULT '[]',                         -- 标签 JSON 数组，用于分组筛选
    summary      TEXT             DEFAULT NULL,                         -- 接口一句话摘要，NULL=未采集
    description  TEXT             DEFAULT '',                           -- 接口详细说明
    params       TEXT             DEFAULT NULL,                         -- 请求参数定义 JSON 对象，NULL=未采集
    headers      TEXT             DEFAULT '{}',                         -- 请求头定义 JSON 对象
    body         TEXT             DEFAULT NULL,                         -- 请求体定义 JSON 对象，NULL=无请求体
    responses    TEXT             DEFAULT '[]',                         -- 响应定义 JSON 数组，按状态码分项
    security     TEXT             DEFAULT '[]',                         -- 接口级认证方案 JSON 数组
    content_type TEXT             DEFAULT 'application/json',           -- 请求体 Content-Type
    deprecated   INTEGER NOT NULL DEFAULT 0,                            -- 0=正常，1=已废弃（OpenAPI deprecated 标记）
    status       INTEGER NOT NULL DEFAULT 1,                            -- 0=未启用，1=已启用
    version      INTEGER NOT NULL DEFAULT 1,                            -- 定义版本号，每次变更递增，用于判断前端缓存失效
    -- 时间列：created_at 创建时间，updated_at 更新时间（trg_endpoint_updated 维护）
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    UNIQUE(space_id, path, method),
    FOREIGN KEY (space_id) REFERENCES space (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_endpoint_space ON endpoint (space_id);
CREATE INDEX IF NOT EXISTS idx_endpoint_operation_id ON endpoint (operation_id);

-- ============================================================================
-- 4. Agent 执行记录表 (agent_run)
--    一轮 ReAct 对话 = 一条记录，含工具调用统计与 LLM 成本归因
--    统计列在收尾时一次算出并冗余落库，列表页不再聚合明细表
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_run
(
    id              INTEGER PRIMARY KEY,                                -- 主键，next_id() 生成
    space_id        INTEGER NOT NULL,                                   -- 所属空间，space.id；级联删除
    environment_id  INTEGER,                                            -- 执行所用环境，environment.id；环境删除置 NULL
    -- 刻意不建外键：ensure_conversation 失败时会传 0
    conversation_id INTEGER          DEFAULT NULL,                      -- 关联会话，conversation.id；空=无会话
    title           TEXT    NOT NULL DEFAULT '',                        -- 执行标题，取指令摘要
    mode            TEXT    NOT NULL DEFAULT 'agent' CHECK (mode IN ('agent', 'ask', 'plan')), -- 工作模式：agent=自动执行，ask=只回答，plan=只出计划
    trigger_type    TEXT    NOT NULL DEFAULT 'chat' CHECK (trigger_type IN ('chat', 'manual', 'scheduled', 'ci')), -- 触发来源：对话/手动/定时/CI
    llm_provider    TEXT    NOT NULL DEFAULT '',                        -- LLM 提供商名
    llm_model       TEXT    NOT NULL DEFAULT '',                        -- LLM 模型名
    -- 无 pending：记录在本轮开始时才插入，插入即 running
    status          TEXT    NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')), -- 生命周期状态
    started_at      TEXT             DEFAULT NULL,                      -- 开始执行时间
    finished_at     TEXT             DEFAULT NULL,                      -- 执行结束时间
    duration_ms     INTEGER NOT NULL DEFAULT 0,                         -- 本轮总耗时，毫秒
    tool_call_count INTEGER NOT NULL DEFAULT 0,                         -- 工具调用总次数
    ok_count        INTEGER NOT NULL DEFAULT 0,                         -- 成功调用次数
    error_count     INTEGER NOT NULL DEFAULT 0,                         -- 失败调用次数
    success_rate    REAL    NOT NULL DEFAULT 0.0,                       -- 工具调用成功率，0-100
    avg_response_time REAL  NOT NULL DEFAULT 0.0,                       -- 工具调用平均耗时，毫秒
    llm_call_count  INTEGER NOT NULL DEFAULT 0,                         -- LLM 调用次数
    total_tokens    INTEGER NOT NULL DEFAULT 0,                         -- 输入与输出 token 之和
    cost_usd        REAL    NOT NULL DEFAULT 0.0,                       -- 预估成本，美元
    error_message   TEXT    NOT NULL DEFAULT '',                        -- 失败原因，成功时为空
    -- 时间列：created_at 创建时间，updated_at 更新时间（trg_agent_run_updated 维护）
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (space_id) REFERENCES space (id) ON DELETE CASCADE,
    FOREIGN KEY (environment_id) REFERENCES environment (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_run_space    ON agent_run (space_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_run_conv     ON agent_run (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_run_status   ON agent_run (status, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_run_created  ON agent_run (created_at);

-- ============================================================================
-- 5. 工具调用留痕表 (agent_tool_call)
--    每次工具调用的入参、结果与完整 HTTP 请求/响应。
--    通用列必填，HTTP 列可空 —— 一张表容纳所有工具类型。
--    正文长度台阶：落库上限 2MB，给模型 8000 字符，SSE 下发 4000 字符。
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_tool_call
(
    id                      INTEGER PRIMARY KEY,                        -- 主键，next_id() 生成
    run_id                  INTEGER NOT NULL,                           -- 所属执行记录，agent_run.id；级联删除
    -- ── 通用列（所有工具都填）──
    step_index              INTEGER NOT NULL DEFAULT 0,                 -- ReAct 轮次序号，从 0 开始
    seq                     INTEGER NOT NULL DEFAULT 0,                 -- 本轮内调用序号，同一次执行内递增
    call_id                 TEXT    NOT NULL DEFAULT '',                -- 模型给出的 tool_call_id，用于回填结果
    tool_name               TEXT    NOT NULL DEFAULT '',                -- 工具名（如 send_request）
    tool_type               TEXT    NOT NULL DEFAULT 'other' CHECK (tool_type IN (
                                                                                  'http', 'db', 'fs', 'exec',
                                                                                  'memory', 'knowledge', 'skill',
                                                                                  'search', 'other'
        )),                                                             -- 工具分类，决定前端展示方式
    args_json               TEXT    NOT NULL DEFAULT '{}',              -- 工具入参 JSON 对象字符串
    ok                      INTEGER NOT NULL DEFAULT 0 CHECK (ok IN (0, 1)), -- 1=成功，0=失败
    error_type              TEXT    NOT NULL DEFAULT '',                -- 异常类型，用于统计失败原因
    error_message           TEXT    NOT NULL DEFAULT '',                -- 异常信息
    result_preview          TEXT    NOT NULL DEFAULT '',                -- 结果前 4000 字，与 SSE 下发口径一致
    result_chars            INTEGER NOT NULL DEFAULT 0,                 -- 结果总字符数（截断前）
    duration_ms             INTEGER NOT NULL DEFAULT 0,                 -- 调用耗时，毫秒
    -- ── HTTP 列（仅 send_request 填，其余工具为 NULL）──
    http_method             TEXT             DEFAULT NULL,              -- 请求方法
    http_url                TEXT             DEFAULT NULL,              -- 完整请求 URL，报告按此聚合
    http_status_code        INTEGER          DEFAULT NULL,              -- 响应状态码，NULL=未拿到响应
    request_headers         TEXT             DEFAULT NULL,              -- 请求头 JSON 对象，敏感值已脱敏
    request_params          TEXT             DEFAULT NULL,              -- 查询参数 JSON 对象
    request_body            TEXT             DEFAULT NULL,              -- 请求体
    response_headers        TEXT             DEFAULT NULL,              -- 响应头 JSON 对象
    response_body           TEXT             DEFAULT NULL,              -- 响应体，超 2MB 时截断
    response_body_truncated INTEGER NOT NULL DEFAULT 0,                 -- 1=响应体超 2MB 已截断，0=完整
    response_size_bytes     INTEGER NOT NULL DEFAULT 0,                 -- 响应体原始大小，字节
    created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')), -- 调用发生时间
    FOREIGN KEY (run_id) REFERENCES agent_run (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_atc_run          ON agent_tool_call (run_id, seq);
CREATE INDEX IF NOT EXISTS idx_atc_tool_created ON agent_tool_call (tool_name, created_at);
CREATE INDEX IF NOT EXISTS idx_atc_tool_run     ON agent_tool_call (tool_name, run_id);
CREATE INDEX IF NOT EXISTS idx_atc_http_url     ON agent_tool_call (http_url);


-- 测试报告不再建表：报告 = 按 run_id 聚合 agent_tool_call 中 tool_name='send_request' 的行


-- ============================================================================
-- 9. 会话表 (conversation)
--    记录一次多轮对话的元数据（对应 src/data/models/conversation.py）
--    消息正文存 message 表，本表只留归属、模式、选中 skill 与环境绑定
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversation
(
    id              INTEGER PRIMARY KEY,                                -- 主键，next_id() 生成
    space_id        INTEGER             DEFAULT NULL,                   -- 所属空间，space.id；可空，级联删除
    title           TEXT    NOT NULL DEFAULT '',                        -- 会话标题
    -- v2 起 mode 归一化为小写三值（旧值 Ask/Plan/Run 已由 v2 迁移改写）
    mode            TEXT    NOT NULL DEFAULT 'agent' CHECK (mode IN ('agent', 'ask', 'plan')), -- 工作模式：与 skill_names 一起决定工具白名单
    skill_names     TEXT    NOT NULL DEFAULT '[]',                      -- 本会话选中的 skill 名 JSON 数组，空数组=不额外限制
    environment_id  INTEGER             DEFAULT NULL,                   -- 绑定环境，environment.id；用于解析 base_url 与生产环境拦截
    status          INTEGER NOT NULL DEFAULT 1 CHECK (status IN (0, 1)), -- 0=未启用（逻辑删除），1=启用
    last_message_at TEXT                DEFAULT NULL,                   -- 最后一条消息时间，用于会话列表排序
    -- 时间列：created_at 创建时间，updated_at 更新时间（trg_conversation_updated 维护）
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (space_id) REFERENCES space (id) ON DELETE CASCADE,
    FOREIGN KEY (environment_id) REFERENCES environment (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_conversation_space ON conversation (space_id);

-- ============================================================================
-- 10. 消息表 (message)
--     会话中的单条消息（append-only，对应 src/data/models/message.py）
-- ============================================================================
CREATE TABLE IF NOT EXISTS message
(
    id              INTEGER PRIMARY KEY,                                -- 主键，next_id() 生成
    conversation_id INTEGER NOT NULL,                                   -- 所属会话，conversation.id；级联删除
    role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')), -- 消息角色
    content         TEXT    NOT NULL DEFAULT '',                        -- 消息正文
    meta            TEXT    NOT NULL DEFAULT '{}',                      -- 附加信息 JSON 对象：token 用量、附件路径、关联 run_id
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')), -- 发送时间
    FOREIGN KEY (conversation_id) REFERENCES conversation (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_message_conv ON message (conversation_id);

-- ============================================================================
-- 11. LLM 调用记录表 (llm_log)
--    统计每次大模型请求的 token 用量与使用模型（来源：litellm usage_metadata）
-- ============================================================================
CREATE TABLE IF NOT EXISTS llm_log
(
    id                INTEGER PRIMARY KEY,                              -- 主键，next_id() 生成
    model_name        TEXT    NOT NULL,                                 -- 实际命中的模型（如 zai/glm-4-flash）
    provider          TEXT             DEFAULT '',                      -- 厂商，取 model_name 前缀
    request_type      TEXT             DEFAULT '',                      -- 调用类型：invoke/ainvoke/stream/astream/tools
    prompt_tokens     INTEGER          DEFAULT 0,                       -- 输入 token 数
    completion_tokens INTEGER          DEFAULT 0,                       -- 输出 token 数
    total_tokens      INTEGER          DEFAULT 0,                       -- 总 token 数
    duration_ms       INTEGER          DEFAULT 0,                       -- 调用耗时，毫秒
    success           INTEGER          DEFAULT 1,                       -- 1=成功，0=失败
    error_message     TEXT             DEFAULT '',                      -- 失败原因，成功时为空
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')) -- 调用发生时间
);

CREATE INDEX IF NOT EXISTS idx_llm_log_model ON llm_log (model_name);
CREATE INDEX IF NOT EXISTS idx_llm_log_created ON llm_log (created_at);

-- ============================================================================
-- 触发器：自动更新 updated_at 字段
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS trg_space_updated
    AFTER UPDATE
    ON space
BEGIN
    UPDATE space
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_environment_updated
    AFTER UPDATE
    ON environment
BEGIN
    UPDATE environment
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_endpoint_updated
    AFTER UPDATE
    ON endpoint
BEGIN
    UPDATE endpoint
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_agent_run_updated
    AFTER UPDATE
    ON agent_run
BEGIN
    UPDATE agent_run
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_conversation_updated
    AFTER UPDATE
    ON conversation
BEGIN
    UPDATE conversation
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')
    WHERE id = NEW.id;
END;

-- ============================================================================
-- 常用分析视图
-- 说明：视图一律 DROP + CREATE，不用 IF NOT EXISTS —— SQLite 不会更新已存在
-- 的视图定义，语义变更后旧定义会永久留在库里，表现为「查询一个不存在的表」。
-- ============================================================================

DROP VIEW IF EXISTS v_run_overview;
DROP VIEW IF EXISTS v_api_pass_rate;
DROP VIEW IF EXISTS v_scenario_distribution;
DROP VIEW IF EXISTS v_tool_call_stats;
DROP VIEW IF EXISTS v_http_endpoint_stats;

-- 视图: 每次执行的概览（关联空间、环境）
--   run_status  执行状态（同 agent_run.status）
--   success_rate 工具调用成功率 0-100；avg_response_time 工具调用平均耗时（毫秒）
--   cost_usd    本轮 LLM 预估成本（美元）；started_at/finished_at 为空表示未开始/未收尾
CREATE VIEW v_run_overview AS
SELECT r.id AS run_id,
       s.name AS space_name,
       e.name AS environment_name,
       r.status AS run_status,
       r.mode,
       r.title,
       r.tool_call_count,
       r.ok_count,
       r.error_count,
       r.success_rate,
       r.avg_response_time,
       r.duration_ms,
       r.llm_call_count,
       r.total_tokens,
       r.cost_usd,
       r.started_at,
       r.finished_at,
       r.created_at
FROM agent_run r
         LEFT JOIN space s ON r.space_id = s.id
         LEFT JOIN environment e ON r.environment_id = e.id;

-- 视图: 工具维度聚合（哪个工具最常失败、哪个最慢）
--   total_calls/ok_calls/error_calls 调用次数与成功失败拆分
--   success_rate 成功率百分比；min/max_response_time 耗时区间（毫秒）
CREATE VIEW v_tool_call_stats AS
SELECT tool_name,
       tool_type,
       COUNT(*)                                  AS total_calls,
       SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END)   AS ok_calls,
       SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END)   AS error_calls,
       ROUND(SUM(CASE WHEN ok = 1 THEN 1.0 ELSE 0 END)
                 / NULLIF(COUNT(*), 0) * 100, 2) AS success_rate,
       ROUND(AVG(duration_ms), 2)                AS avg_response_time,
       MIN(duration_ms)                          AS min_response_time,
       MAX(duration_ms)                          AS max_response_time
FROM agent_tool_call
GROUP BY tool_name, tool_type;

-- 视图: 接口维度聚合（替代旧的 v_api_pass_rate，口径改为 HTTP 状态码）
--   success_count 2xx 次数；error_count 4xx/5xx 或未拿到响应的次数
--   avg_response_time 平均耗时（毫秒）
CREATE VIEW v_http_endpoint_stats AS
SELECT http_url,
       http_method,
       COUNT(*)                                                                             AS total_executions,
       SUM(CASE WHEN http_status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END)                AS success_count,
       SUM(CASE WHEN http_status_code >= 400 OR http_status_code IS NULL THEN 1 ELSE 0 END) AS error_count,
       ROUND(AVG(duration_ms), 2)                                                           AS avg_response_time
FROM agent_tool_call
WHERE http_url IS NOT NULL AND http_url <> ''
GROUP BY http_url, http_method;
