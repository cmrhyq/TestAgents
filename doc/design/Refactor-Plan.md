# TestAgents 重构实施计划（v1.0）

> 依据：[Refactor-Design.md](Refactor-Design.md)
> 纪律：TDD（先红后绿）、每任务可独立验证、每阶段结束跑全量 `pytest` + 冒烟
> 工作目录：`backend/`（后端）、`frontend/`（前端）

---

## P0 · 止血（让项目能跑起来）

| # | 任务 | 文件 | 验证 |
|---|---|---|---|
| 0.1 | 删除对已删服务的引用 | `src/api/v1/endpoint.py`（去 `KnowledgeService`） | — |
| 0.2 | 删除已死的 `graph/nodes/__init__.py` 导入 | `src/graph/nodes/__init__.py` | — |
| 0.3 | 从 git 恢复断言引擎 | `src/agent/tools/assertion_engine.py`、`jsonpath.py`（`git show ed06370^:...`） | 单测通过 |
| 0.4 | 删除死测试（引用已删节点） | `tests/graph/node/*`、`tests/graph/test_agent_node.py`、`tests/graph/test_workflow*.py` | `pytest` 收集无错误 |
| 0.5 | 清理 router 中的 `workflow_service` 依赖 | `src/api/v1/router.py`、`space.py` | `import app` 成功 |
| 0.6 | 基线验证 | — | `python -c "import app"` + `pytest -q` 全绿 |

**出口**：应用能启动，测试全绿，`git commit -m "P0: 止血，恢复可运行基线"`

---

## P1 · 地基（空间 + 工作目录 + 迁移）

| # | 任务 | 文件 | 验证 |
|---|---|---|---|
| 1.1 | 配置新增 `workspace` / `embedding` / `chroma.enabled` | `src/core/config.py`、`config/config.yaml` | 加载成功 |
| 1.2 | 写 `WorkspaceManager` 测试（建目录 / 逃逸拒绝 / 删除归档） | `tests/workspace/test_manager.py` | 🔴 先红 |
| 1.3 | 实现 `WorkspaceManager` | `src/workspace/manager.py` | 🟢 |
| 1.4 | 初始文件模板（AGENTS.md / memory/MEMORY.md / docs/README.md） | `src/workspace/templates.py` | 测试断言内容 |
| 1.5 | `Space` 模型加 `workspace_path`；`Environment` 加 `is_production` | `src/data/models/*.py` | — |
| 1.6 | 新模型 `SpaceMemory` / `KnowledgeDocument` / `KnowledgeChunk` / `Skill` | `src/data/models/*.py` + `__init__.py` | 建表成功 |
| 1.7 | `conversation` 加 `skill_names` / `environment_id`，mode 改小写 | `src/data/models/conversation.py` | — |
| 1.8 | 迁移脚本 `v2_agent_migration.py`（补列 + 重建 conversation + 数据修正 + 幂等） | `src/data/migration/` | 旧库跑两次无异常 |
| 1.9 | `SpaceService.create_space` 同步建目录（失败回滚） | `src/data/services/space_service.py` | 建空间即见目录 |
| 1.10 | `GET /spaces/{id}/tree` | `src/api/v1/space.py` | 返回树 |
| 1.11 | `DELETE /spaces/{id}` 归档目录 | 同上 | — |

**出口**：建空间 → 目录与初始文件就位 → 树接口可用；`git commit -m "P1: 空间工作目录与数据模型"`

---

## P2 · 房间（Skills + 记忆 + 工具集）

### P2-A Skills

| # | 任务 | 文件 | 验证 |
|---|---|---|---|
| 2.1 | `manifest` 解析测试（正常/缺字段/非法 name） | `tests/skill/test_manifest.py` | 🔴 |
| 2.2 | 实现 `SkillManifest` + `parse_skill_md` | `src/skill/manifest.py` | 🟢 |
| 2.3 | `repository` 两级发现测试（同名覆盖） | `tests/skill/test_repository.py` | 🔴 |
| 2.4 | 实现 `SkillRepository` | `src/skill/repository.py` | 🟢 |
| 2.5 | `SkillService`：导入 zip（防 zip-slip）、启停、装配注入文本 | `src/skill/service.py` | 单测 |
| 2.6 | 内置 2 个示例 skill（`api-test-design`、`api-regression-run`） | `backend/skills/*/SKILL.md` | 可被发现 |
| 2.7 | 技能 API（列表/详情/导入/启停） | `src/api/v1/skill.py` | TestClient |

### P2-B 记忆

| # | 任务 | 文件 | 验证 |
|---|---|---|---|
| 2.8 | `LongTermMemory` 测试（CRUD / 软删 / md 镜像一致） | `tests/memory/test_longterm.py` | 🔴 |
| 2.9 | 实现 `LongTermMemory` | `src/memory/longterm.py` | 🟢 |
| 2.10 | 切片器测试（长度/overlap/段落边界） | `tests/memory/test_chunker.py` | 🔴 |
| 2.11 | 实现 `chunk_text` | `src/memory/knowledge.py` | 🟢 |
| 2.12 | `KnowledgeBase`：摄取（含降级）+ 检索（Chroma / LIKE 双路径，mock） | `src/memory/knowledge.py` | 单测 |
| 2.13 | `ContextBuilder`（上下文层，纯组装 + 裁剪） | `src/memory/context.py` | 单测 |
| 2.14 | 记忆 API + 文档 API | `src/api/v1/memory.py`、`knowledge.py` | TestClient |

### P2-C 工具集

| # | 任务 | 文件 | 验证 |
|---|---|---|---|
| 2.15 | `fs_tools` 重写为空间沙箱（读写/列表/删除），逃逸测试 | `src/agent/tools/fs_tools.py` | 单测 |
| 2.16 | 迁移 `db_tools` / `openapi_tools` | `src/agent/tools/` | 单测 |
| 2.17 | `http_tools.send_request` + 生产环境闸门 | 同上 | 单测（mock） |
| 2.18 | `memory_tools`（remember / recall / forget） | 同上 | 单测 |
| 2.19 | `knowledge_tools`（knowledge_search） | 同上 | 单测 |
| 2.20 | `skill_tools`（list_skills / read_skill） | 同上 | 单测 |
| 2.21 | `registry`：按模式 + skill 取交集 | `src/agent/tools/registry.py` | 单测 |
| 2.22 | 删除 `src/graph/`、`src/workflow.py`、旧 `src/prompts/` | — | `import app` 仍成功 |

**出口**：三个子系统单测全绿；`git commit -m "P2: Skills / 记忆 / 工具集"`

---

## P3 · 引擎（Agent 运行时）

| # | 任务 | 文件 | 验证 |
|---|---|---|---|
| 3.1 | 模式策略测试（ask/plan 无写工具，agent 有） | `tests/agent/test_modes.py` | 🔴 |
| 3.2 | 实现 `modes.py`（`ModePolicy`） | `src/agent/modes.py` | 🟢 |
| 3.3 | 上下文组装测试（顺序 + 裁剪） | `tests/agent/test_context.py` | 🔴 |
| 3.4 | 实现 `agent/context.py` | 同上 | 🟢 |
| 3.5 | 事件帧测试 | `tests/agent/test_events.py` | 🔴 |
| 3.6 | 实现 `events.py`（内部事件 → SSE） | 同上 | 🟢 |
| 3.7 | runner 测试（mock model：纯文本 / 单工具 / 多轮 / 超步数 / 工具异常） | `tests/agent/test_runner.py` | 🔴 |
| 3.8 | 实现 `runner.py`（手写 ReAct 循环） | 同上 | 🟢 |
| 3.9 | 重写 `ChatStreamService`（会话落库 + 事件 + 保存回答） | `src/data/services/chat_stream_service.py` | 单测 |
| 3.10 | 重写 `POST /chat/stream`（新协议 + mode 校验） | `src/api/v1/chat.py` | TestClient 帧序 |
| 3.11 | 会话扩展 API（空间下会话列表 / 消息 / 删除） | `src/api/v1/conversation.py` | TestClient |

**出口**：三种模式行为可验证，流式帧序正确；`git commit -m "P3: Agent 运行时与对话流"`

---

## P4 · 界面

| # | 任务 | 文件 |
|---|---|---|
| 4.1 | `lib/types` 补新类型（mode / skill / memory / knowledge / event） | `frontend/src/lib/types/*` |
| 4.2 | `lib/stream.ts` 适配新事件协议 | `frontend/src/lib/stream.ts` |
| 4.3 | hooks：`use-chat`（重写）、`use-skills`、`use-memories`、`use-knowledge`、`use-workspace-tree` | `frontend/src/hooks/*` |
| 4.4 | 对话页重写：空间/模式/技能三选择器 + 工具调用卡片 | `pages/chat/*` |
| 4.5 | 空间详情 tabs：概览 / 会话 / 记忆 / 知识库 | `pages/space/tabs/*` |
| 4.6 | 技能管理页 | `pages/skills/*` |
| 4.7 | 路由与侧边栏更新 | `router.tsx`、`layout/sidebar.tsx` |

**出口**：手动验收 5 大目标全通过；`git commit -m "P4: 前端适配"`

---

## P5 · 收口

| # | 任务 |
|---|---|
| 5.1 | 更新 `Architecture.md` / `DatabaseDesign.md` |
| 5.2 | 删除 `Mode-System-Gap-Analysis.md`（已过期）或标注归档 |
| 5.3 | `CHANGELOG.md` 记录 v1.0 重构 |
| 5.4 | 全量 `pytest` + `npm run build` |
| 5.5 | 给合并建议（superpowers 收尾四选项） |
