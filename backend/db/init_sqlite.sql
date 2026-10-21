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
-- 4. 执行批次表 (test_run)
--    每次 CLI 运行产生一个批次，关联输入文件、配置快照和执行环境
-- ============================================================================
CREATE TABLE IF NOT EXISTS test_run
(
    id              INTEGER PRIMARY KEY,
    space_id      INTEGER NOT NULL,
    environment_id  INTEGER,
    name            TEXT             DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    trigger_type    TEXT    NOT NULL DEFAULT 'manual' CHECK (trigger_type IN ('manual', 'scheduled', 'ci')),
    input_file      TEXT             DEFAULT '',
    input_snapshot  TEXT             DEFAULT '{}',
    config_snapshot TEXT             DEFAULT '{}',
    llm_provider    TEXT             DEFAULT '',
    llm_model       TEXT             DEFAULT '',
    total_cases     INTEGER NOT NULL DEFAULT 0,
    passed_cases    INTEGER NOT NULL DEFAULT 0,
    failed_cases    INTEGER NOT NULL DEFAULT 0,
    skipped_cases   INTEGER NOT NULL DEFAULT 0,
    error_cases     INTEGER NOT NULL DEFAULT 0,
    pass_rate       REAL    NOT NULL DEFAULT 0.0,
    started_at      TEXT             DEFAULT NULL,
    finished_at     TEXT             DEFAULT NULL,
    total_duration  REAL    NOT NULL DEFAULT 0.0,
    error_message   TEXT             DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (space_id) REFERENCES space (id) ON DELETE CASCADE,
    FOREIGN KEY (environment_id) REFERENCES environment (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_run_space ON test_run (space_id);
CREATE INDEX IF NOT EXISTS idx_run_env ON test_run (environment_id);

-- ============================================================================
-- 5. 测试用例表 (test_case)
--    对应 workflow.py -> TestCase
--    由 LLM 生成或手工创建的用例
-- ============================================================================
CREATE TABLE IF NOT EXISTS test_case
(
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL,
    endpoint_id     INTEGER,
    case_id         TEXT    NOT NULL,
    case_name       TEXT    NOT NULL,
    url             TEXT    NOT NULL,
    method          TEXT    NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS')),
    scenario_type   TEXT    NOT NULL DEFAULT 'normal' CHECK (scenario_type IN (
                                                                               'normal', 'param_missing',
                                                                               'param_type_error',
                                                                               'boundary_value', 'permission_error',
                                                                               'custom'
        )),
    priority        TEXT    NOT NULL DEFAULT 'P1' CHECK (priority IN ('P0', 'P1', 'P2')),
    headers         TEXT             DEFAULT '{}',
    body            TEXT             DEFAULT NULL,
    params          TEXT             DEFAULT NULL,
    cache_rules     TEXT             DEFAULT NULL,
    assert_rules    TEXT             DEFAULT '[]',
    expected_result TEXT             DEFAULT '成功',
    description     TEXT             DEFAULT '',
    remark          TEXT             DEFAULT '',
    unique_hash     TEXT             DEFAULT '',
    generated_by    TEXT    NOT NULL DEFAULT 'llm' CHECK (generated_by IN ('llm', 'manual', 'import')),
    status       INTEGER NOT NULL DEFAULT 1, -- 0=未启用，1=已启用
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (run_id) REFERENCES test_run (id) ON DELETE CASCADE,
    FOREIGN KEY (endpoint_id) REFERENCES endpoint (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_case_run ON test_case (run_id);
CREATE INDEX IF NOT EXISTS idx_case_api ON test_case (endpoint_id);
CREATE INDEX IF NOT EXISTS idx_case_case_id ON test_case (case_id);

-- ============================================================================
-- 6. 测试结果表 (test_result)
--    对应 workflow.py -> TestResult
--    完整记录每条用例的执行请求/响应/状态
-- ============================================================================
CREATE TABLE IF NOT EXISTS test_result
(
    id                   INTEGER PRIMARY KEY,
    run_id               INTEGER NOT NULL,
    test_case_id         INTEGER NOT NULL,
    case_id              TEXT    NOT NULL,
    case_name            TEXT    NOT NULL,
    status               TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN (
                                                                              'pending', 'running', 'passed', 'failed',
                                                                              'skipped', 'error'
        )),
    request_url          TEXT             DEFAULT '',
    request_method       TEXT             DEFAULT '',
    request_headers      TEXT             DEFAULT '{}',
    request_body         TEXT             DEFAULT NULL,
    query_params         TEXT             DEFAULT NULL,
    response_status_code INTEGER          DEFAULT NULL,
    response_headers     TEXT             DEFAULT '{}',
    response_body        TEXT             DEFAULT NULL,
    response_time        REAL    NOT NULL DEFAULT 0.0,
    error_message        TEXT             DEFAULT '',
    retry_count          INTEGER NOT NULL DEFAULT 0,
    started_at           TEXT             DEFAULT NULL,
    finished_at          TEXT             DEFAULT NULL,
    created_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (run_id) REFERENCES test_run (id) ON DELETE CASCADE,
    FOREIGN KEY (test_case_id) REFERENCES test_case (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_result_run ON test_result (run_id);
CREATE INDEX IF NOT EXISTS idx_result_case ON test_result (test_case_id);

-- ============================================================================
-- 7. 测试摘要表 (test_summary)
--     对应 models.py -> TestSummary
--     每次执行批次聚合一条摘要记录
-- ============================================================================
CREATE TABLE IF NOT EXISTS test_summary (
    id                  INTEGER PRIMARY KEY,
    run_id              INTEGER NOT NULL UNIQUE,
    total               INTEGER NOT NULL DEFAULT 0,
    passed              INTEGER NOT NULL DEFAULT 0,
    failed              INTEGER NOT NULL DEFAULT 0,
    skipped             INTEGER NOT NULL DEFAULT 0,
    error               INTEGER NOT NULL DEFAULT 0,
    pass_rate           REAL    NOT NULL DEFAULT 0.0,
    avg_response_time   REAL    NOT NULL DEFAULT 0.0,
    min_response_time   REAL    NOT NULL DEFAULT 0.0,
    max_response_time   REAL    NOT NULL DEFAULT 0.0,
    p95_response_time   REAL    NOT NULL DEFAULT 0.0,
    total_duration      REAL    NOT NULL DEFAULT 0.0,
    failure_reasons     TEXT    DEFAULT '{}',
    started_at          TEXT    DEFAULT NULL,
    finished_at         TEXT    DEFAULT NULL,
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (run_id) REFERENCES test_run(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_summary_run       ON test_summary(run_id);
CREATE INDEX IF NOT EXISTS idx_summary_pass_rate ON test_summary(pass_rate);

-- ============================================================================
-- 8. 报告记录表 (report)
--     记录每次生成的报告文件路径与元信息
-- ============================================================================
CREATE TABLE IF NOT EXISTS report
(
    id           INTEGER PRIMARY KEY,
    run_id       INTEGER NOT NULL,
    format       TEXT    NOT NULL CHECK (format IN ('excel', 'html', 'markdown', 'json')),
    file_path    TEXT    NOT NULL,
    file_size    INTEGER          DEFAULT 0,
    generated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (run_id) REFERENCES test_run (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_report_run ON report (run_id);
CREATE INDEX IF NOT EXISTS idx_report_format ON report (format);

-- ============================================================================
-- 9. 会话表 (conversation)
--    记录一次多轮对话的元数据（对应 src/data/models/conversation.py）
-- ============================================================================
CREATE TABLE IF NOT EXISTS conversation
(
    id              INTEGER PRIMARY KEY,
    space_id        INTEGER             DEFAULT NULL,
    title           TEXT    NOT NULL DEFAULT '',
    mode            TEXT    NOT NULL DEFAULT 'Run' CHECK (mode IN ('Ask', 'Plan', 'Run')),
    status          INTEGER NOT NULL DEFAULT 1 CHECK (status IN (0, 1)), -- 0=未启用，1=启用
    last_message_at TEXT                DEFAULT NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')),
    FOREIGN KEY (space_id) REFERENCES space (id) ON DELETE CASCADE
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

CREATE TRIGGER IF NOT EXISTS trg_test_run_updated
    AFTER UPDATE
    ON test_run
BEGIN
    UPDATE test_run
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%f', 'now', 'localtime')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_test_case_updated
    AFTER UPDATE
    ON test_case
BEGIN
    UPDATE test_case
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
-- ============================================================================

-- 视图: 每次执行的概览（关联空间、环境、摘要）
CREATE VIEW IF NOT EXISTS v_run_overview AS
SELECT tr.id      AS run_id,
       p.name     AS space_name,
       e.name     AS environment_name,
       tr.status  AS run_status,
       tr.trigger_type,
       tr.llm_provider,
       tr.llm_model,
       tr.started_at,
       tr.finished_at,
       tr.created_at
FROM test_run tr
         LEFT JOIN space p ON tr.space_id = p.id
         LEFT JOIN environment e ON tr.environment_id = e.id;

-- 视图: 接口维度聚合（按 API URL 分组统计通过率）
CREATE VIEW IF NOT EXISTS v_api_pass_rate AS
SELECT tr.request_url,
       tr.request_method,
       COUNT(*)                                              AS total_executions,
       SUM(CASE WHEN tr.status = 'passed' THEN 1 ELSE 0 END) AS passed_count,
       SUM(CASE WHEN tr.status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
       ROUND(
               SUM(CASE WHEN tr.status = 'passed' THEN 1.0 ELSE 0 END)
                   / NULLIF(COUNT(*), 0) * 100, 2
       )                                                     AS pass_rate,
       ROUND(AVG(tr.response_time), 2)                       AS avg_response_time,
       ROUND(MIN(tr.response_time), 2)                       AS min_response_time,
       ROUND(MAX(tr.response_time), 2)                       AS max_response_time
FROM test_result tr
WHERE tr.status IN ('passed', 'failed')
GROUP BY tr.request_url, tr.request_method;

-- 视图: 场景类型分布（统计各场景类型的测试覆盖情况）
CREATE VIEW IF NOT EXISTS v_scenario_distribution AS
SELECT tc.scenario_type,
       COUNT(*)                                              AS total_cases,
       SUM(CASE WHEN tr.status = 'passed' THEN 1 ELSE 0 END) AS passed,
       SUM(CASE WHEN tr.status = 'failed' THEN 1 ELSE 0 END) AS failed,
       SUM(CASE WHEN tr.status = 'error' THEN 1 ELSE 0 END)  AS errors,
       ROUND(
               SUM(CASE WHEN tr.status = 'passed' THEN 1.0 ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN tr.status IN ('passed', 'failed') THEN 1 ELSE 0 END), 0) * 100, 2
       )                                                     AS pass_rate
FROM test_case tc
         LEFT JOIN test_result tr ON tr.test_case_id = tc.id
GROUP BY tc.scenario_type;

-- ============================================================================
-- 初始数据（ID 由应用层雪花算法生成，此处使用固定种子值；OR IGNORE 保证可重复执行）
-- ============================================================================
INSERT OR IGNORE INTO space (id, name, description, status)
VALUES (100000000000001, 'HTTP Bin Space', '', 1);

INSERT OR IGNORE INTO environment (id, space_id, name, base_url, description, variables, is_default, status)
VALUES (200000000000001, 100000000000001, 'httpbin dev', 'https://httpbin.org', 'dev env', '{"name": "alan"}', 1, 1);
INSERT OR IGNORE INTO environment (id, space_id, name, base_url, description, variables, is_default, status)
VALUES (200000000000002, 100000000000001, 'httpbin prod', 'https://httpbin.org', 'prod env', '{"name": "anna"}', 0, 1);
