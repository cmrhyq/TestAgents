# TestAgents 模式功能差距分析

> **⚠️ 已归档（2026-10-20）**：本文是对 v0.1 破损状态的差距扫描，所列四项缺失
> （策略层 / 工具白名单 / 执行闸门 / 事件日志）已在 v1.0 重构中全部落地：
>
> | 原缺失项 | 现状 |
> |---|---|
> | 策略层 | `src/agent/modes.py::ModePolicy` |
> | 工具白名单 | `mode + skill.allowed_tools` 取交集，`filter_tools` 在执行路径闭环 |
> | 执行闸门 | `http_tools.send_request` 生产环境拦截 + 空间目录沙箱 |
> | 事件日志 | `src/agent/events.py` 六种 SSE 事件 + `llm_log` 统计落库 |
>
> 现状以 [Refactor-Design.md](./Refactor-Design.md) 为准，本文仅作历史记录。

> 版本：v0.1.0
> 扫描时间：2026-09-20
> 扫描基线：`git HEAD = ced5e4d`（"delete back-end report generate modules"）+ 工作区未提交改动（13 个节点文件 `D`）
> 对标文档：[Mode-System-Design.md](Mode-System-Design.md)
> 扫描范围：`backend/src/**`、`frontend/src/**`（排除 `.venv`、`node_modules`）

---

## 一、总体结论

> 🔴 **当前项目处于「半重构破损状态」，模式功能的地基尚不存在。**
>
> 三种模式中：`Run` 的图是空壳、`Ask` 的节点文件已被删除、`Plan` 只有一句占位文本。
> 后端 `backend/src/api/v1/chat.py` 目前**无法导入**，`/api/v1/chat/stream` 全链路不可用；
> 同时后端没有任何**策略层、工具白名单、执行闸门、检查点、事件日志**——即模式功能的四个强制点全部缺失。
>
> 因此本文档的优先级判断是：**先止血（P0 恢复可运行），再打地基（P1 模式四层），最后做前端（P2）。**

---

## 二、现状基线

| 维度 | 当前实现 | 位置 |
|---|---|---|
| 模式取值 | `Run` / `Ask` / `Plan`（裸字符串，**无枚举类**） | `schemas/conversation.py:69`、`models/conversation.py:38` |
| 模式约束 | DB `CHECK (mode IN ('Ask','Plan','Run'))` | `models/conversation.py:38` |
| 分流位置 | **API 路由层** `if/elif` | `api/v1/chat.py:117-130` |
| `run` 分支 | `TestWorkflow.astream` → SSE（`start`/`node`/`final`/`error`） | `api/v1/chat.py:122-124` |
| `ask` 分支 | `answer_question_node` + `run_in_threadpool` → text/plain | `api/v1/chat.py:39-52` |
| `plan` 分支 | 固定占位文本 `PLAN_PENDING_MESSAGE` | `api/v1/chat.py:36, 125-127` |
| 前端模式 UI | `MODES` 常量，Plan 项 `disabled: true` | `chat-input.tsx:24-43` |
| 前端模式状态 | `useState("Run")`，无持久化 | `use-security-chat.ts:47` |
| 前端渲染 | `answer: string` 字符串累加 | `use-security-chat.ts:95, 99` |
| 事件协议 | `data: {json}\n\n`，无 `event:` / `id:` 字段 | `api/v1/chat.py:88` |
| 数据表 | 11 张，**无事件 / 计划 / 审批表** | `grep __tablename__` |

---

## 三、P0 阻断问题（必须先修，否则一切无从谈起）

### P0-1 🔴 全部 Graph 节点已被删除，但引用未清理 → 后端无法导入

**证据：**

```
$ git status --short
D  backend/src/graph/nodes/answer_question.py
D  backend/src/graph/nodes/base_case_generation.py
D  backend/src/graph/nodes/end_node.py
D  backend/src/graph/nodes/error_node.py
D  backend/src/graph/nodes/execute_flow_tests_node.py
D  backend/src/graph/nodes/execute_single_tests_node.py
D  backend/src/graph/nodes/generate_flow_cases_node.py
D  backend/src/graph/nodes/generate_report_node.py
D  backend/src/graph/nodes/generate_single_cases_node.py
D  backend/src/graph/nodes/parse_input_node.py
D  backend/src/graph/nodes/security_audit_node.py
D  backend/src/graph/nodes/select_endpoints_node.py
D  backend/src/graph/nodes/start_node.py
```

`backend/src/graph/nodes/` 目录下实际只剩 `__init__.py`，但：

| 文件 | 行 | 悬挂引用 |
|---|---|---|
| `backend/src/graph/nodes/__init__.py` | 5-11 | import 7 个已删除模块 |
| `backend/src/api/v1/chat.py` | 26 | `from src.graph.nodes.answer_question import ...` |

**实测结果：**

```
$ python -c "import src.api.v1.chat"
FAIL chat: ModuleNotFoundError No module named 'src.graph.nodes.execute_flow_tests_node'
```

**测试连带崩溃：**

```
$ pytest --collect-only -q
ERROR tests/api/v1/test_chat_stream.py
ERROR tests/graph/node/test_generate_single_cases_node.py
ERROR tests/graph/node/test_security_audit_node.py
217 tests collected, 3 errors
```

**影响**：`api/v1/router.py` 导入 `chat_router` 时即失败 → **整个 `/api/v1` 路由不可用**（不只是 chat）。

**修复方向**：二选一，必须先决策——

- (a) 节点是被**误删**：从 commit `ced5e4d` 的上一个版本恢复节点文件
- (b) 节点是被**有意移除**（准备重写）：清理 `nodes/__init__.py` 与 `chat.py` 的悬挂 import，并同步废弃 `tests/graph/node/*`、`tests/api/v1/test_chat_stream.py`

---

### P0-2 🔴 `build_graph()` 是空图，没有任何节点和边

```python
# backend/src/workflow.py:52-63
def build_graph() -> CompiledStateGraph:
    workflow = StateGraph(AgentState)
    return workflow.compile()          # ← 无 add_node / add_edge
```

**影响**：即使修好导入，`run` 模式也没有任何节点可执行，`TestWorkflow.run/stream/astream/astream_events` 全部沦为无操作。

**修复方向**：随 P0-1 的决策一并处理。若重写，建议按 [设计文档 §5](Mode-System-Design.md#五后端处理管线) 的管线顺序一次性挂好节点。

---

### P0-3 🔴 导入路径前缀不一致，`src.` 缺失

| 文件 | 行 | 错误写法 | 应为 |
|---|---|---|---|
| `backend/src/workflow.py` | 15 | `from data.constant.constants import NodeName` | `from src.data.constant.constants import ...` |
| `backend/src/graph/route.py` | 6 | `from data.constant.constants import NodeName, TestMode, UserIntent` | 同上 |

**实测结果：**

```
$ python -c "import src.workflow"
FAIL workflow: ModuleNotFoundError No module named 'data'
```

**注**：同文件的其他 import 都正确带 `src.` 前缀（如 `src.core.config`、`src.graph.state`），属于局部笔误。

---

### P0-4 🟠 `AgentState` 字段声明严重不完整

`backend/src/graph/state.py:35-48` 只声明了 3 个字段：

```python
class AgentState(MessagesState):
    raw_input: str
    next_node: str
    space_id: int | None
```

但代码实际读写的字段远不止这些：

| 实际使用字段 | 使用位置 | 是否已声明 |
|---|---|---|
| `user_intent` | `route.py:35`、`chat.py:57` | ❌ |
| `answer_content` | `chat.py:47, 59` | ❌ |
| `test_results_summary` | `chat.py:61` | ❌ |
| `report_path` | `chat.py:68` | ❌ |
| `error_message` | `workflow.py:131, 185` | ❌ |
| `run_status` | `workflow.py:132` | ❌ |
| `test_mode` | `route.py:44` | ❌ |
| `messages` | 继承自 `MessagesState` | ✅ |

**影响**：LangGraph 的 `TypedDict` 状态中，未声明的键不会进入状态通道、不参与 reducer 合并 → 即使补回节点，状态也会在节点间丢失。这是"补回节点后仍然跑不通"的隐性坑。

**修复方向**：改为 `class AgentState(MessagesState, total=False)` 或补齐全部字段声明（推荐后者，类型更严格）。

---

## 四、P1 模式功能缺口（对标设计文档的四层）

### 4.1 四层强制点对照

| # | 设计文档要求 | 当前实现 | 结论 |
|---|---|---|---|
| ① | **策略解析**：`ResolvedPolicy` 冻结对象，服务端唯一可信来源 | 无。mode 是裸 `str`，直接在路由层 `if/elif` 分流 | ❌ **完全缺失** |
| ② | **Prompt 装配**：按 mode 注入策略片段 | `prompts/builders/` 有 5 个 builder（intent / select_endpoints / case / flow_case / system_safety），**无一按 mode 变化** | ❌ **完全缺失** |
| ③ | **工具白名单**：按 mode 过滤下发给 LLM 的 tools | `graph/tools/__init__.py:10-31` 全量导出 13 个工具，无 mode 维度 | ❌ **完全缺失** |
| ④ | **执行闸门**：唯一拦截点，返回 tool result 而非抛异常 | 无。`fs_tools._ensure_within_workspace` 是唯一类似物，但只覆盖 2/3 个函数且是路径校验而非权限模型 | ❌ **完全缺失** |

> **值得注意**：③④ 缺失目前**尚未造成安全事故**，原因是当前工具集里**根本没有写文件 / 执行命令工具**（详见 §六-3）。一旦补上写工具，没有闸门就是直接的越权风险。反过来看，现在正是插入闸门的**最佳时机**——成本最低、风险最小。

### 4.2 支撑能力对照

| # | 能力 | 当前实现 | 结论 |
|---|---|---|---|
| ⑤ | **Plan buffer**（`PlanStep` 记录 + 计划产物） | `plan` 分支只有固定占位文本 `"计划模式开发中，请使用 Run 或 Ask 模式。"` | ❌ 缺失 |
| ⑥ | **人工审批**（`permission_request` 事件 + resume token + 审批端点） | 无任何事件类型、无端点、无幂等机制 | ❌ 缺失 |
| ⑦ | **检查点**（跨请求续跑） | 全仓 `grep checkpoint / MemorySaver / SqliteSaver` → **0 命中**；`build_graph()` 未传 checkpointer | ❌ 缺失 |
| ⑧ | **事件协议**（`id:` + `event:` 字段，支持 `Last-Event-ID` 补发） | 只发 `data: {json}\n\n`；前端 `stream.ts:122` 手工 `split("\n\n")` 解析 | ❌ 缺失 |
| ⑨ | **事件落库** | 11 张表全是业务表，`message` 仅存 `role / content / meta`；**无事件日志表** | ❌ 缺失 |
| ⑩ | **真 token 流** | `run` 模式仅节点级；`ask` 模式是**伪流式**——`run_in_threadpool` 全量生成后按 **8 字符**切片输出 | ⚠️ 部分（能力已具备但未使用） |
| ⑪ | **前端时间线 reducer** | `answer: string` 字符串累加；`formatRunEvent` 把结构化事件**拍平成文本** | ❌ 缺失 |
| ⑫ | **前端模式持久化 + 双源一致** | `useState("Run")`，刷新即重置；`conversation.mode` 只在**新建会话**时写入 | ❌ 缺失 |

**关于 ⑩ 的说明**：`workflow.py:243-292` 的 `astream_events()` 已经能产出 `token` 级事件（基于 `graph.astream_events(version="v2")` + `on_chat_model_stream`），但这个能力**只在 `/workflows/run/stream?include_tokens=true` 暴露**，`chat.py` 的 `run` 分支用的是 `astream()`（节点级），`ask` 分支则完全没有用。属于"有工具没用上"。

**关于 ⑫ 的双源不一致**：

```python
# chat_stream_service.py:27-32
if conversation_id is None:
    conversation = service.create_conversation(
        ConversationCreate(space_id=body.space_id, title="", mode=body.mode)   # 仅新建时写 mode
    )
```

存量会话中途切换 mode 后，`conversation.mode` **不会更新**（`ChatStreamRequest.mode` 只用于当次分流），导致 DB 里的会话模式与实际执行的模式不一致 → 历史回放、审计、列表页展示全部失真。

---

## 五、P2 前端缺口明细

| 文件 | 现状 | 差距 |
|---|---|---|
| `frontend/src/hooks/use-security-chat.ts` | `answer: string` 单字符串累加（`:95`、`:99`） | 缺事件 reducer + `TimelineNode[]` |
| 同上 `:16-41` | `formatRunEvent` 将事件转为 `▸ 节点 xxx 完成` 纯文本 | 工具调用入参/结果、计划、审批、产物信息**全部丢失**，无法渲染卡片 |
| `frontend/src/lib/stream.ts` | 两个函数：`streamChat`（纯文本，`:39`）+ `streamRunEvents`（SSE，`:88`） | 同一端点两种解析器，是 media type 分裂的连带产物；应合并为一套 SSE 解析 |
| `frontend/src/components/chat/chat-input.tsx:24-43` | `MODES` 常量含 `Run`/`Ask`/`Plan`，Plan `disabled: true` | 缺模式持久化；`description` 仅靠 Tooltip 展示 |
| `frontend/src/components/chat/message-bubbles.tsx` | 仅 `UserBubble` / `AssistantBubble` / `StreamingAssistantMessage` | 缺 `plan-card` / `tool-call-card` / `permission-request-card` / `artifact-card` |
| 全前端 | `grep localStorage` → 仅 `use-theme.ts` 使用 | 模式未持久化，刷新页面即回到 `Run` |

---

## 六、其他隐患（协议与数据模型层）

### 1. 同一端点返回两种 media type

```python
# api/v1/chat.py:122-130
if mode == "run":
    media_type = "text/event-stream; charset=utf-8"
elif mode == "plan":
    media_type = "text/plain; charset=utf-8"
else:  # ask
    media_type = "text/plain; charset=utf-8"
```

`POST /api/v1/chat/stream` 按 mode 返回 `text/event-stream` **或** `text/plain`。这直接导致前端必须维护两套解析逻辑，且任何"统一处理响应"的中间层（拦截器、日志、重试）都要分支。

**建议**：**一律返回 SSE**，`ask` 模式只是事件类型更少（只有 `status` / `text_delta` / `done`），协议层不需要分支。

### 2. `ensure_conversation` 吞异常并返回 `0`

```python
# chat_stream_service.py:35-39
except RuntimeError as exc:
    logger.warning("会话持久化暂不可用，继续执行流式对话", error=str(exc))
    return body.conversation_id or 0        # ← 返回 0
```

DB 不可用时会返回 `conversation_id = 0`，后续 `append_message(0, ...)` 可能产生孤儿数据；且**未校验** `body.conversation_id` 是否真的属于 `body.space_id`（跨空间越权读写的隐患）。

### 3. 无写文件 / 执行命令工具（与 docstring 不符）

`backend/src/graph/tools/fs_tools.py:1-5` 的模块 docstring 写着：

> 提供文件读取、目录列表、**命令执行**等工具

但实际只定义了 3 个：`read_file`、`list_directory`、`get_file_info`。**没有 `write_file`，也没有 `execute_command`。**

当前 13 个工具的实际副作用分类：

| 工具 | 副作用 | 是否需要闸门 |
|---|---|---|
| `read_file` / `list_directory` / `get_file_info` | 只读 | 否 |
| `search_space` / `get_space_endpoints` | 只读 DB | 否 |
| `parse_openapi` / `search_endpoint` / `get_endpoint_detail` | 只读 | 否 |
| `evaluate_assertions` / `extract_jsonpath` / `resolve_cache` | 纯计算 | 否 |
| `render_report` | 纯字符串渲染 | 否 |
| `send_request` | ⚠️ **对外发起 HTTP 请求**（影响被测系统） | ✅ **需要** |
| `extract_cache` | ⚠️ **写入缓存**（`CacheManager.set`，`:110`） | ✅ **需要** |

即：**当前已有 2 个 mutating 工具需要闸门保护**，只是尚未被识别（`MUTATING` 集合不存在）。且 `MUTATING` 的划分不能只看"是否写文件"——`send_request` 会打到生产环境的被测接口，在 Plan 模式里同样不该真发。

### 4. `_ensure_within_workspace` 覆盖不一致

| 函数 | 行 | 是否做工作区校验 |
|---|---|---|
| `read_file` | `:38-40` | ✅ 有 |
| `list_directory` | `:76-78` | ✅ 有 |
| `get_file_info` | `:112-124` | ❌ **无** |

`get_file_info` 可以探测工作区外的任意路径（文件是否存在、大小、时间戳），是一条信息泄露路径。属于"同一个文件里三种写法"的典型不一致缺陷。

### 5. `message.role` 约束不支持 `tool` 角色

```python
# models/message.py:38
CheckConstraint("role IN ('user','assistant','system')", name="ck_message_role")
```

标准 tool-calling 消息序列需要 `role='tool'`（承载 tool result）。当前约束下，工具调用过程**无法按标准格式落库**，只能塞进 `meta` 字段或将结果拼进 assistant 文本——这会破坏后续的上下文重建与调试能力。

### 6. `conversation.mode` 的 CHECK 约束把取值焊死

```python
CheckConstraint("mode IN ('Ask','Plan','Run')", name="ck_conversation_mode")
```

未来新增模式（如 `Debug` / `Explore`）必须改表 + 数据迁移。且模式名大小写（`Run`）与设计文档的小写规范（`agent`/`plan`/`ask`）不一致，建议统一为**小写常量 + 枚举类**，DB 层放宽为长度约束或直接由应用层校验。

---

## 七、建议补齐顺序

### 阶段一：P0 止血（恢复可运行）

- [ ] **决策 1**：13 个节点文件是「误删」还是「有意移除」
- [ ] 按决策清理 `nodes/__init__.py:5-11` 与 `chat.py:26` 的悬挂 import（或恢复节点文件）
- [ ] 修 `workflow.py:15`、`route.py:6` 的 `data.` → `src.data.` 前缀
- [ ] 补齐 `AgentState` 字段声明（`total=False` 或逐字段声明）
- [ ] 让 `build_graph()` 至少挂上 `START` / `END`，保证图可编译
- [ ] 同步废弃/重写 `tests/graph/node/*`、`tests/api/v1/test_chat_stream.py`
- [ ] **验收**：`pytest --collect-only` 0 error；`GET /docs` 可打开；`import src.api.v1.chat` 成功

### 阶段二：P1 打地基（模式四层）

- [ ] 新增 `backend/src/graph/policy.py`：`AgentMode` 枚举 + `ResolvedPolicy` + `resolve_policy()`
- [ ] 新增 `backend/src/graph/gate.py`：执行闸门（4 种判定）+ `MUTATING` 工具集合（含 `send_request`、`extract_cache`）
- [ ] 新增 `backend/src/graph/plan.py`：`PlanStep` + plan buffer + 落库
- [ ] 改造 `api/v1/chat.py`：**统一返回 SSE**，事件补 `id:` / `event:` 字段
- [ ] 新增事件类型枚举，覆盖 `status` / `text_delta` / `tool_call` / `tool_result` / `plan` / `permission_request` / `done`
- [ ] 配置 checkpointer（`langgraph.checkpoint.sqlite`），Plan 审批走 `interrupt()` + `resume_token`
- [ ] `ask` 模式改用 `astream_events` / `llm_gateway.astream_events`，去掉 8 字符伪分块
- [ ] 新增 `conversation_event` 表（`seq` / `type` / `payload` / `created_at`）
- [ ] 修复 `get_file_info` 缺失的工作区校验
- [ ] 修复 `ensure_conversation` 返回 `0` 与跨 space 校验缺失
- [ ] **验收**：Ask 模式工具列表不含写工具；Plan 模式执行后产出计划且零副作用；批准后可续跑

### 阶段三：P2 前端与体验

- [ ] `use-security-chat.ts` 改为事件 reducer + `TimelineNode[]`
- [ ] 新增 `plan-card.tsx` / `tool-call-card.tsx` / `permission-request-card.tsx`
- [ ] `stream.ts` 合并为单一 `streamChatEvents`，删除按 media type 分支
- [ ] 模式持久化到 `localStorage`，并在切换时回写 `conversation.mode`
- [ ] 断线重连：携带 `Last-Event-ID` 拉取缺失事件
- [ ] **验收**：刷新页面模式不丢；流式中断后时间线不重复不丢失

---

## 八、证据索引

| 结论 | 文件:行 |
|---|---|
| 节点文件全部删除 | `git status` → 13 个 `D backend/src/graph/nodes/*.py` |
| 节点包悬挂 import | `backend/src/graph/nodes/__init__.py:5-11` |
| chat 路由悬挂 import | `backend/src/api/v1/chat.py:26` |
| 空图 | `backend/src/workflow.py:52-63` |
| 导入前缀错误 | `backend/src/workflow.py:15`、`backend/src/graph/route.py:6` |
| 状态字段不全 | `backend/src/graph/state.py:35-48` |
| 模式分流在 API 层 | `backend/src/api/v1/chat.py:117-130` |
| Plan 占位文本 | `backend/src/api/v1/chat.py:36` |
| ask 伪流式（8 字符切片） | `backend/src/api/v1/chat.py:35, 44-52` |
| 两种 media type | `backend/src/api/v1/chat.py:124, 127, 130` |
| 工具无 mode 维度 | `backend/src/graph/tools/__init__.py:10-31` |
| `get_file_info` 缺校验 | `backend/src/graph/tools/fs_tools.py:112-124` |
| `extract_cache` 有写副作用 | `backend/src/graph/tools/executor_tools.py:110` |
| 无 checkpointer | `grep -rn "checkpoint\|MemorySaver\|SqliteSaver" backend/src` → 0 命中 |
| mode CHECK 约束 | `backend/src/data/models/conversation.py:38` |
| role CHECK 约束 | `backend/src/data/models/message.py:38` |
| 仅新建时写 mode | `backend/src/data/services/chat_stream_service.py:27-32, 39` |
| 前端字符串累加 | `frontend/src/hooks/use-security-chat.ts:95, 99` |
| 事件拍平成文本 | `frontend/src/hooks/use-security-chat.ts:16-41` |
| 两个流式解析器 | `frontend/src/lib/stream.ts:39, 88` |
| Plan 项禁用 | `frontend/src/components/chat/chat-input.tsx:41` |
| 模式未持久化 | `frontend/src/hooks/use-security-chat.ts:47`；`grep localStorage frontend/src` → 仅 `use-theme.ts` |
| 测试收集失败 | `pytest --collect-only -q` → 3 errors / 217 collected |
