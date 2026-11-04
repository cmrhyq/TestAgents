-- ============================================================================
-- TestAgents 数据库建表脚本 (SQLite)
--
-- 说明：
-- 1. 应用启动时由 SQLAlchemy Base.metadata.create_all() 建表，本脚本用于
--    手工初始化 / 种子数据参考，全部语句可重复执行（IF NOT EXISTS / OR IGNORE）。
-- 2. status 语义统一为 0=未启用，1=已启用（与前端 STATUS_MAP 一致）。
-- 3. environment.is_default 语义为 1=默认，0=不默认（布尔语义，与前端一致）。
-- 4. 本表结构必须与 src/data/models/*.py 保持一致，改表请同步改模型。
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
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT             DEFAULT '',
    status   INTEGER NOT NULL DEFAULT 1, -- 0=未启用，1=已启用
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
    id          INTEGER PRIMARY KEY,
    space_id  INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    base_url    TEXT    NOT NULL,
    description TEXT             DEFAULT '',
    variables   TEXT             DEFAULT '{}', -- 环境变量 KV
    is_default  INTEGER NOT NULL DEFAULT 1, -- 1=默认，0=不默认
    status   INTEGER NOT NULL DEFAULT 1, -- 0=未启用，1=已启用
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
    id           INTEGER PRIMARY KEY,
    space_id   INTEGER NOT NULL,
    operation_id TEXT    NOT NULL, -- OpenAPI operationId
    name         TEXT    NOT NULL,
    path         TEXT    NOT NULL,
    method       TEXT    NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS')),
    tags         TEXT             DEFAULT '[]',
    summary      TEXT             DEFAULT NULL,
    description  TEXT             DEFAULT '',
    params       TEXT             DEFAULT NULL,
    headers      TEXT             DEFAULT '{}',
    body         TEXT             DEFAULT NULL,
    responses    TEXT             DEFAULT '[]', -- 响应定义 JSON 数组
    security     TEXT             DEFAULT '[]', -- 接口级认证方案 JSON 数组
    content_type TEXT             DEFAULT 'application/json', -- 请求体 Content-Type
    deprecated   INTEGER NOT NULL DEFAULT 0, -- 0=正常，1=已废弃（来自 OpenAPI deprecated 标记）
    status    INTEGER NOT NULL DEFAULT 1, -- 0=未启用，1=已启用
    version      INTEGER NOT NULL DEFAULT 1,
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
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_run
(
    id              INTEGER PRIMARY KEY,
    space_id        INTEGER NOT NULL,
    environment_id  INTEGER,
    -- 刻意不建外键：ensure_conversation 失败时会传 0
    conversation_id INTEGER          DEFAULT NULL,
    title           TEXT    NOT NULL DEFAULT '',
    mode            TEXT    NOT NULL DEFAULT 'agent' CHECK (mode IN ('agent', 'ask', 'plan')),
    trigger_type    TEXT    NOT NULL DEFAULT 'chat' CHECK (trigger_type IN ('chat', 'manual', 'scheduled', 'ci')),
    llm_provider    TEXT    NOT NULL DEFAULT '',
    llm_model       TEXT    NOT NULL DEFAULT '',
    -- 无 pending：记录在本轮开始时才插入，插入即 running
    status          TEXT    NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    started_at      TEXT             DEFAULT NULL,
    finished_at     TEXT             DEFAULT NULL,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    ok_count        INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    success_rate    REAL    NOT NULL DEFAULT 0.0, -- 0-100
    avg_response_time REAL  NOT NULL DEFAULT 0.0, -- 毫秒
    llm_call_count  INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL    NOT NULL DEFAULT 0.0,
    error_message   TEXT    NOT NULL DEFAULT '',
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
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_tool_call
(
    id                      INTEGER PRIMARY KEY,
    run_id                  INTEGER NOT NULL,
    step_index              INTEGER NOT NULL DEFAULT 0,
    seq                     INTEGER NOT NULL DEFAULT 0,
    call_id                 TEXT    NOT NULL DEFAULT '',
    tool_name               TEXT    NOT NULL DEFAULT '',
    tool_type               TEXT    NOT NULL DEFAULT 'other' CHECK (tool_type IN (
                                                                                  'http', 'db', 'fs', 'exec',
                                                                                  'memory', 'knowledge', 'skill',
                                                                                  'search', 'other'
        )),
    args_json               TEXT    NOT NULL DEFAULT '{}',
    ok                      INTEGER NOT NULL DEFAULT 0 CHECK (ok IN (0, 1)),
    error_type              TEXT    NOT NULL DEFAULT '',
    error_message           TEXT    NOT NULL DEFAULT '',
    result_preview          TEXT    NOT NULL DEFAULT '',
    result_chars            INTEGER NOT NULL DEFAULT 0,
    duration_ms             INTEGER NOT NULL DEFAULT 0,
    -- HTTP 列（仅 send_request 填）
    http_method             TEXT             DEFAULT NULL,
    http_url                TEXT             DEFAULT NULL,
    http_status_code        INTEGER          DEFAULT NULL,
    request_headers         TEXT             DEFAULT NULL,
    request_params          TEXT             DEFAULT NULL,
    request_body            TEXT             DEFAULT NULL,
    response_headers        TEXT             DEFAULT NULL,
    response_body           TEXT             DEFAULT NULL,
    response_body_truncated INTEGER NOT NULL DEFAULT 0,
    response_size_bytes     INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
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
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversation
(
    id              INTEGER PRIMARY KEY,
    space_id        INTEGER             DEFAULT NULL,
    title           TEXT    NOT NULL DEFAULT '',
    -- v2 起 mode 归一化为小写三值（旧值 Ask/Plan/Run 已由 v2 迁移改写）
    mode            TEXT    NOT NULL DEFAULT 'agent' CHECK (mode IN ('agent', 'ask', 'plan')),
    skill_names     TEXT    NOT NULL DEFAULT '[]',
    environment_id  INTEGER             DEFAULT NULL,
    status          INTEGER NOT NULL DEFAULT 1 CHECK (status IN (0, 1)), -- 0=未启用，1=启用
    last_message_at TEXT                DEFAULT NULL,
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
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT    NOT NULL DEFAULT '',
    meta            TEXT    NOT NULL DEFAULT '{}',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (conversation_id) REFERENCES conversation (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_message_conv ON message (conversation_id);

-- ============================================================================
-- 11. LLM 调用记录表 (llm_log)
--    统计每次大模型请求的 token 用量与使用模型（来源：litellm usage_metadata）
-- ============================================================================
CREATE TABLE IF NOT EXISTS llm_log
(
    id               INTEGER PRIMARY KEY,
    model_name       TEXT    NOT NULL,
    provider         TEXT             DEFAULT '',
    request_type     TEXT             DEFAULT '',
    prompt_tokens    INTEGER          DEFAULT 0,
    completion_tokens INTEGER         DEFAULT 0,
    total_tokens     INTEGER          DEFAULT 0,
    duration_ms      INTEGER          DEFAULT 0,
    success          INTEGER          DEFAULT 1,
    error_message    TEXT             DEFAULT '',
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime'))
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
