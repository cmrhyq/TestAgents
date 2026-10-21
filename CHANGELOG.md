# Changelog

本文件记录项目所有值得注意的变更，格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-06-15

### Added

- 新增前端项目（React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui）
- 新增前端 CI 工作流（`.github/workflows/frontend.yml`）
- 新增前端 pre-commit hooks（ESLint、Prettier、TypeScript 类型检查）
- 新增前端文档（`frontend/README.md`）

### Changed

- 项目重构为 Monorepo 结构：`backend/` + `frontend/`
- 后端代码全部迁移至 `backend/` 目录
- 移除 CLI 入口（`main.py`），仅保留 FastAPI API 服务
- CI 工作流拆分为 `backend.yml` + `frontend.yml`，按路径触发
- `.pre-commit-config.yaml` 更新为统管前后端 lint
- 中英文 README 更新为 Monorepo 结构说明
- CORS 配置改为通过环境变量控制

## [1.0.0] - 2026-05-28

### Added
- 新增 pytest 测试框架配置（pytest-cov、pytest-asyncio、pytest-mock、pytest-xdist、pytest-timeout）
- 新增 `conftest.py` 全局 fixtures（project_root、mock_llm_client、mock_chat_model 等）
- 新增 `pyproject.toml` 统一管理项目元数据、依赖和工具配置
- 新增中英文 README 文档
- 集成 LangSmith 观测和追踪
- 集成 ChromaDB 向量数据库依赖

### Changed
- 数据访问层全面重构为 Repository Pattern
- 报告生成节点改为输出 HTML 格式报告
- 雪花 ID 生成器改造，ORM 和数据库表的 id 字段迁移为雪花 ID

### Fixed
- 修复列表查询类接口返回数据 id 相同的问题
- 修复 `generate_report_node.py` 缺少 `TestRun` 导入的问题

## [0.9.0] - 2026-05-20

### Added
- 新增 RESTful API 入口（FastAPI），支持通过 HTTP 接口调用测试流程
- 新增 start、end、error 节点及相关路由跳转逻辑
- 新增 flow test（业务流程测试）与 single test（单接口测试）双模式
- parse_input 节点支持判断 test mode 自动路由

### Changed
- 日志系统统一改为 structlog + f-string 格式化
- Prompt 管理模块优化，分离 builder / formatter / loader 三层架构

### Fixed
- 修复新增 environment 到数据库时的报错问题

## [0.8.0] - 2026-05-11

### Added
- 新增 LLM 接口选择节点（select_endpoints_node），支持 Tool Calling 自动挑选接口
- 新增 `build_graph()` 顶层函数，使用 START/END 常量和 `tools_condition` 条件边
- 新增文件系统与命令执行 Tool（fs_tools、db_tools）
- 新增测试用例生成、测试执行、测试报告生成节点

### Changed
- 删除手动 tool calling 循环，改为 LangGraph 内建 ToolNode + tools_condition 自动循环
- LLM Client 重构：删除 4 个重复子类，改为工厂函数 `create_chat_model()` 直接返回 BaseChatModel
- 所有节点改为纯函数，返回部分状态更新字典
- State 重构：删除废弃 GraphState，新增 TestGraphState（TypedDict）和 AgentState（MessagesState）
- TestWorkflow 类精简为配置持有 + `run()` 入口

### Fixed
- 修复 LLM 使用工具查询接口时遗忘 SystemMessage 的问题
- 修复 LLM 返回非标准 JSON 的解析问题
- 修复获取数据库 session 的方式

## [0.7.0] - 2026-05-06

### Added
- 新增单元测试用例
- 新增 input 示例文件（OpenAPI 格式测试数据）
- 新增携带工具调用 LLM 的方法
- 新增 workflow 相关编排内容

### Changed
- 代码拆分优化，模块职责更清晰
- 数据库表结构调整

### Fixed
- 修复批量查重失败的问题

## [0.6.0] - 2026-04-29

### Added
- OpenAPI 文档解析存储实现
- 新增 Schema、Service 层代码
- 新增数据库连接管理器
- 新增数据库操作层 Entity、Repository 代码
- 新增从配置中初始化数据库并返回 session

### Fixed
- 使用 TYPE_CHECKING + `from __future__ import annotations` 解决 SQLAlchemy 循环引用问题

## [0.5.0] - 2026-04-22

### Added
- 新增 OpenAPI 文档解析器（openapi_parser）
- 新增 API 文档存储器（api_doc_storage）
- 新增 OpenAPI 格式测试数据

## [0.4.0] - 2026-04-10

### Added
- 新增 HTTP Request 工具模块
- 新增全局数据缓存器（data_cache）
- 新增 Prompt 配置和分层管理（prompts 模块）

### Changed
- 流程新增 params、domain 字段
- api_url 字段重命名为 url

### Fixed
- 修复发送请求时占位符未替换的问题
- 修复接口依赖关系字段逻辑

## [0.3.0] - 2026-04-03

### Added
- 新增数据库模块（SQLite + SQLAlchemy ORM）
- 新增数据库 Schema 文件和 ER 图
- 新增系统流程图文档

## [0.2.0] - 2026-03-26

### Added
- 新增 prompts 目录分层模块
- 新增 structlog 日志框架
- 新增 CONTRIBUTING.md 贡献指南

### Changed
- 调整代码结构，模块化重组

## [0.1.0] - 2026-03-24

### Added
- 项目初始化
- 基础配置管理（YAML + 环境变量）
- LLM Client 基础架构
- LangChain + LangGraph 核心依赖集成
