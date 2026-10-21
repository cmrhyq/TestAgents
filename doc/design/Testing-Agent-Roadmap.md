# TestAgents 重构路线图：从零设计一个测试 Agent

> 版本：v0.1.0
> 定位：重构方向与实施顺序。回答三个问题——**从哪儿开始、怎么设计、注意什么**。
> 前置阅读：[模式功能设计](Mode-System-Design.md)（Agent 层怎么接）、[差距分析](Mode-System-Gap-Analysis.md)（当前代码状态）
> 关联：[架构设计](Architecture.md)、[数据库设计](DatabaseDesign.md)

---

## 零、先纠正一个判断

> **「老代码用处不大」只对了三成。**

被删掉的 13 个节点文件**确实该删**——它们把 LLM 放在了编排（orchestration）的位置，这是架构错误。

但同一次改动留下的这些**恰恰是最值钱的部分**，是重构的地基而非负债：

| 资产 | 位置 | 代码量 | 价值 |
|---|---|---|---|
| **断言引擎** | `src/graph/executor/assertion_engine.py` | 254 行 | 11 种断言运算符 + JSONPath 取值 + 数值/字符串分支处理。这是测试工具的核心竞争力，纯逻辑，无外部依赖 |
| **缓存依赖解析** | `src/graph/executor/cache_resolver.py` | 186 行 | 从响应提取字段 → 注入后续请求。**这就是「流程测试」的实现**（登录拿 token → 后续接口带 token）。很多开源工具做不到 |
| **用例执行器** | `src/graph/executor/test_executor.py` | 255 行 | 编排「反序列化 → 注入 → 请求 → 断言 → 提取 → 落库」完整链路，错误处理齐备 |
| **HTTP 客户端** | `src/utils/http/request.py` | — | 重试 + 重试间隔 + 超时分级 |
| **OpenAPI 解析器** | `src/utils/parser/openapi_parser.py` | — | 离线解析，产出 servers/endpoints/responses |
| **数据模型** | `src/data/models/` | 11 张表 | `test_case` 表设计相当到位：`unique_hash` / `generated_by` / `cache_rules` / `assert_rules` / `scenario_type` / `priority` |
| **LLM 网关** | `src/core/llm/llm_gateway.py` | — | 多模型路由 + `invoke_with_tools` + `astream_events` |
| **前端** | `frontend/src/` | — | React 19 + shadcn + 工业蓝图设计体系，报告页/运行详情页都可用 |

**判断依据**：你的 `test_case` 表里有 `unique_hash`、`generated_by IN ('llm','manual','import')`——这说明**当初就想过「用例是冻结的资产」这件事**，只是没走完。下面要做的，是把这个思路贯彻到底。

---

## 一、核心设计原则：两阶段分离

**测试工具和聊天机器人的根本区别：测试必须可复现。**

一个每次运行都用 LLM 重新生成用例的 Agent，不是测试工具，是演示品——今天的 50 条用例和明天的 50 条不一样，你无法回答「改了接口之后哪条挂了」这个测试工具存在的唯一理由。

所以整个系统必须切成两段：

```
┌─────────────────────── 阶段 A：生成（LLM，一次性） ───────────────────────┐
│  OpenAPI Spec  →  [LLM 生成用例]  →  落库为 TestCase 数据  →  人工可审阅/编辑  │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓ 冻结（frozen artifact）
┌─────────────────────── 阶段 B：执行（纯代码，可重复 N 次） ─────────────────┐
│  读取 TestCase  →  注入变量  →  发请求  →  断言  →  落库  →  报告  →  对比  │
│                          ↑ 这里没有 LLM，一个都没有                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 三条推论

1. **LLM 只在生成阶段出现**。执行路径里出现任何 LLM 调用都是架构缺陷。
2. **用例是一等公民数据**，不是中间产物。它要能被版本化、审阅、手改、导出、diff。
3. **成本模型友好**：生成一次 → 执行一千次。而不是执行一次 → 生成一次。

---

## 二、从哪儿开始：Phase 0 是无头运行器

**不要从 LangGraph 开始。不要从 Agent 开始。不要从 API 开始。**

从一条命令行开始：

```bash
# 目标：离线跑通已落库的用例，全程不碰 LLM、不碰 Web 服务
python -m testagents run --space 123456 --env dev --run-id 7890
```

### 为什么要这一步

这是**唯一能验证地基是否牢固的方法**。因为：

| 如果做不到 CLI 运行 | 说明 |
|---|---|
| 执行器依赖 DB Session / ORM | 无法单元测试，无法并行，无法在 CI 里跑 |
| 执行器依赖全局单例 | 用例之间会互相污染，并行必然出错 |
| 执行器依赖 LLM | 用例不可复现，回归对比失效 |
| 执行器依赖 FastAPI 上下文 | 无法做批量回归，无法做定时任务 |

**Agent 只是这个 CLI 的自然语言外壳。** 先有能干活的 CLI，Agent 才有意义；反过来做，你得到的是一个「有时能跑通」的演示。

### Phase 0 验收标准

- [ ] `python -m testagents run --space X --env dev` 能跑通，不启动 Web 服务
- [ ] **确定性检查**：同一批 50 条用例连跑 10 次，passed/failed 集合完全一致
- [ ] 执行器核心函数签名不含 `Session`、不含 ORM 对象：

```python
# 目标签名：纯函数，无 DB、无 ORM、无全局状态
def run_case(case: CaseSpec, env: EnvSpec, ctx: RunContext) -> CaseResult: ...
```

- [ ] 并发跑 50 条用例，结果与串行一致（验证无共享可变状态）

---

## 三、怎么设计：五层架构

```
┌─────────────────────────────────────────────────────────────┐
│ L4  Agent 对话层（薄）                                        │
│     自然语言 → 工具调用。工具 = L0~L3 的操作，不多不少          │
│     模式（Agent/Plan/Ask）= 这层工具的权限策略                  │
├─────────────────────────────────────────────────────────────┤
│ L3  用例生成层（LLM，一次性）                                  │
│     Endpoint Schema → 用例矩阵。结构化输出 + 校验 + 修复        │
│     产出写入 L1，之后不再回头                                   │
├─────────────────────────────────────────────────────────────┤
│ L2  执行引擎层（纯代码，确定性）★ 工程质量 80% 花在这里          │
│     变量注入 → HTTP → 断言 → 提取 → 结果                       │
│     无 LLM、无 ORM、无全局单例，可并行、可单测                   │
├─────────────────────────────────────────────────────────────┤
│ L1  测试资产层（冻结数据）                                      │
│     TestCase 作为可版本化/审阅/手改的一等公民                    │
├─────────────────────────────────────────────────────────────┤
│ L0  规格摄入层（确定性）                                       │
│     OpenAPI → Space / Endpoint / Environment                  │
└─────────────────────────────────────────────────────────────┘
```

**依赖方向严格向下**。L2 不知道 L3 存在，L3 不知道 L4 存在。这条规矩保证了「删掉 LLM 系统依然可用」。

---

## 四、L2 执行引擎：重构重点

### 4.1 当前实现的三个硬伤

**硬伤 1：每个用例新建一个 HTTP 连接**

```python
# test_executor.py:104-109 —— 在 execute_single 内部创建
http_client = HttpRequest(base_url=base_url, ...)
...
# :146
http_client.close()
```

`execute_single` 每次调用都建客户端、用完关闭。50 条用例 = 50 次 TCP 握手，HTTPS 场景还要加上 50 次 TLS 握手。**这是当前最直接的可优化点**，改成 run 级别共享连接池即可。

**硬伤 2：缓存是进程级单例，破坏并行与隔离**

```python
# test_executor.py:40-43
self.cache_resolver = CacheResolver(cache=cache or CacheManager.get_instance())
```

`CacheManager.get_instance()` 是全局单例。结果：

- 两个并发 run 会互相污染缓存 → 串行通过、并行失败
- 上一个 run 的 token 泄漏到下一个 run
- 无法单测（测试之间共享状态）

**改法**：缓存实例由 `RunContext` 持有，生命周期与一次 run 绑定。

**硬伤 3：`TestExecutor` 与 ORM 强耦合**

```python
def execute_single(self, test_case: TestCase, run_id: int, session: Session) -> TestResult:
```

入参是 ORM 对象、出口是写库。这意味着**不连数据库就无法执行一条用例**，于是单测、CLI、并行全部受阻。

**改法**：拆成「执行」与「持久化」两件事。

```python
# 执行：纯函数，输入输出都是 dataclass
def run_case(case: CaseSpec, env: EnvSpec, ctx: RunContext) -> CaseResult: ...

# 持久化：由调用方负责
def persist_result(session: Session, run_id: int, result: CaseResult) -> None: ...
```

### 4.2 目标结构

```
src/engine/                     ← 新建，与 graph/ 彻底解耦
├── models.py        CaseSpec / EnvSpec / CaseResult / RunContext（纯 dataclass）
├── runner.py        run_case() 纯函数入口
├── http_client.py   连接池 + 超时 + 重试（run 级共享）
├── variables.py     变量解析 {{token}} / ${env.base_url}
├── assertions.py    ← 迁移自 graph/executor/assertion_engine.py
├── extractors.py    ← 迁移自 graph/executor/cache_resolver.py
└── errors.py        TransportError / AssertionError / EnvError 分类
```

`graph/` 目录整个删掉。执行引擎搬进 `engine/`，LangGraph 只在 L4 出现。

### 4.3 错误必须分类，否则无法判断测试是否可信

这是当前实现完全缺失的一环。现在只有 `passed / failed / error / skipped` 四种状态，但 `error` 里混着「被测接口 500」和「测试环境挂了」两种性质完全不同的问题。

| 分类 | 含义 | 处理策略 |
|---|---|---|
| `ASSERT_FAILED` | 断言不通过 | 真实缺陷，**不要重试** |
| `TRANSPORT_ERROR` | 连接超时 / DNS 失败 / TLS 错误 | 环境问题，可重试 |
| `SERVER_ERROR` | 5xx | 可能是被测系统缺陷，**不建议自动重试**（会掩盖问题） |
| `ENV_ERROR` | base_url 不可达 / 环境配置缺失 | 整批中止，不要假装测试完成 |
| `SKIPPED` | 依赖未满足 | 需要显式计数，不能混进通过率 |
| `CASE_INVALID` | 用例本身格式错误 | 用例质量问题，需回归到 L1 |

**关键**：`ENV_ERROR` 应当中止整批并明确报错。当前实现会把它当成一条失败用例继续跑完，产出一个「通过率 92%」的假报告——这是最危险的行为。

---

## 五、L3 用例生成：LLM 该做什么、不该做什么

### 5.1 职责边界

| 任务 | 该用 LLM 吗 | 理由 |
|---|---|---|
| 解析 OpenAPI 文档 | ❌ 用 `OpenAPIParser` | 确定性任务，解析器更快更准更省 |
| 选接口（"测登录相关"） | ⚠️ 优先用 tag/path 关键词过滤，LLM 兜底 | 关键词能覆盖 80% 场景，且可解释 |
| 从 Schema 推导参数组合 | ⚠️ 一半一半 | 必填/类型/枚举可直接推导，**边界值和业务语义才是 LLM 的价值** |
| 生成负向用例（缺参/类型错） | ✅ 用 LLM | 需要理解语义 |
| 生成断言规则 | ⚠️ Schema 推导为主，LLM 补充语义断言 | 见 5.2 |
| 执行用例 | ❌ **绝对不用** | 见第一章 |

### 5.2 断言生成：当前实现的问题

```python
# case_generation_service.py:188
if "code" in props:
    default_rules.append("$.code == 200")
```

硬编码了「响应体有个 `code` 字段」这个约定。这是国内 API 的常见约定，但不是通用规范——换个响应结构就失效，而且失败时是静默的（断言少了，测试显得"通过"）。

**正确做法：分层断言**

```
第 1 层（确定性，从 OpenAPI responses 推导）：
  - HTTP status code ∈ 声明的 2xx 集合
  - 必需字段存在性（从 response schema 的 required 推导）
  - 字段类型匹配（从 schema type 推导）

第 2 层（LLM 补充，语义级）：
  - 业务规则断言（"余额不能为负"）
  - 列表长度、排序、分页字段一致性

第 3 层（人工，针对关键接口）：
  - 精确值/快照比对
```

### 5.3 必须防的两个 LLM 陷阱

**陷阱 1：断言漂移（assertion drift）**——LLM 对易变字段下断言

```python
# 危险：这些字段每次请求都不同，断言必然失败
"$.data.traceId == 'abc123'"
"$.timestamp > 1758900000"
"$.requestId exists"     # 看起来合理，但某些实现会省略
```

**改法**：维护一个易变字段黑名单（`traceId`/`requestId`/`timestamp`/`nonce`/`serverTime`），生成后做一次后置校验，命中就降级为「存在性检查」或直接剔除。

**陷阱 2：用例重复膨胀**——同一接口生成 20 条几乎一样的用例

`unique_hash` 字段已经建好了，但**全仓没有任何地方用它做去重查询**（只有写入，没有读取）。这是必须补上的一环：

```python
# 生成后落库前，先按 hash 去重
existing = case_repo.find_by_hashes(run_space_id, [c.unique_hash for c in new_cases])
new_cases = [c for c in new_cases if c.unique_hash not in existing]
```

---

## 六、注意什么：十个坑

### 6.1 架构类

| # | 坑 | 后果 | 对策 |
|---|---|---|---|
| 1 | **LLM 进入执行路径** | 用例不可复现，回归对比失去意义 | 执行引擎的 import 里不允许出现 `llm` / `langchain` |
| 2 | **每次运行重新生成用例** | 无法回答"改了接口后哪条挂了"；成本 ×1000 | 两阶段分离，用例冻结为数据 |
| 3 | **全局单例状态**（`CacheManager.get_instance()`） | 并行即错，测试互相污染 | 状态放 `RunContext`，随 run 创建销毁 |
| 4 | **执行器依赖 DB/ORM** | 无法单测、无法 CLI、无法并行 | 核心函数只吃 dataclass |

### 6.2 质量类

| # | 坑 | 后果 | 对策 |
|---|---|---|---|
| 5 | **错误不分类** | 环境故障被算成"测试失败"，产出假通过率 | 六类错误码（见 §4.3），`ENV_ERROR` 中止整批 |
| 6 | **用例无 teardown** | 造数据的接口留下垃圾数据 → 后续用例失败 → 偶发 flaky | `TestCase` 增加 `setup` / `teardown` 字段，或用唯一后缀隔离数据 |
| 7 | **断言易变字段** | 用例永远失败，被当成"已知问题"忽略掉 | 易变字段黑名单 + 生成后校验 |
| 8 | **无快照/差异对比** | 无法回答"这次和上次比，多了哪些失败" | 落库时记录 run 与上一个 run 的 diff，报告里体现 |

### 6.3 工程类

| # | 坑 | 后果 | 对策 |
|---|---|---|---|
| 9 | **每个用例新建 HTTP 连接** | 50 用例 = 50 次握手，慢且浪费 | run 级连接池 |
| 10 | **`send_request` 打到生产环境** | 真实数据被污染/删除 | 环境标记 `is_production` + 执行闸门（见模式设计文档 §5.4） |

### 6.4 一个常被忽略的坑：**"通过"必须是可信的**

测试工具最坏的情况不是报错，而是**报了一个假的通过率**。

当前实现里，以下几种情况都会产出"通过"：

- `assert_rules` 为空数组 → `evaluate_all([], ...)` 返回 `(True, [])` → passed
- 断言因字段路径写错而取不到值 → 取决于 `_resolve_value` 的实现
- 缓存依赖未满足 → 标为 `skipped`，但 `pass_rate` 计算里可能没排除

**必须建立一条规矩**：**没有断言的用例不允许标记为 passed**，应当是 `CASE_INVALID`。一个零断言的"通过"会持续污染你的通过率指标，而它比一条失败更危险——因为它看起来是好的。

---

## 七、实施顺序

### Phase 0 · 无头运行器（地基）
- [ ] 定义 engine 的纯 dataclass：`CaseSpec` / `EnvSpec` / `CaseResult` / `RunContext`
- [ ] 拆 `TestExecutor` → `run_case()` 纯函数（不碰 ORM）
- [ ] 连接池提升到 run 级
- [ ] 缓存实例改为 `RunContext` 持有
- [ ] 六类错误码
- [ ] CLI：`python -m testagents run --space X --env dev`
- [ ] **验收：同批用例连跑 10 次，结果集合完全一致；并发与串行结果一致**

### Phase 1 · 用例资产化
- [ ] `unique_hash` 真正参与去重查询
- [ ] 用例版本化 / 人工编辑接口
- [ ] 零断言用例拦截为 `CASE_INVALID`
- [ ] run 之间的 diff 计算（新增失败 / 修复 / 新增用例）
- [ ] **验收：能回答"这次比上次多了哪 3 个失败"**

### Phase 2 · LLM 生成层
- [ ] 生成走结构化输出（JSON Schema 约束）+ 校验 + 修复重试
- [ ] 断言分层（Schema 推导第 1 层 + LLM 第 2 层）
- [ ] 易变字段黑名单后置校验
- [ ] 生成结果写入 L1 后**冻结**，执行路径不回头
- [ ] **验收：同一 spec 生成两次，用例集合一致性 > 80%；人工可编辑修正**

### Phase 3 · 数据依赖与流程测试
- [ ] 变量系统正式化（`{{token}}` 取代隐式 cache_rules）
- [ ] setup / teardown 支持
- [ ] **验收：登录 → 查询 → 修改 → 删除 全链路可重复执行且不留垃圾数据**

### Phase 4 · Agent 层
- [ ] 按 [模式功能设计](Mode-System-Design.md) 实现 L4：工具 = L0~L3 的操作
- [ ] 执行闸门 + Plan 模式 + 审批（生产环境强制）
- [ ] **验收：Ask 模式零副作用；Plan 模式产出计划且不执行**

---

## 八、和你当前进度的衔接

| 现有资产 | 处理方式 |
|---|---|
| `graph/executor/assertion_engine.py` | **迁移**到 `engine/assertions.py`，逻辑基本不动 |
| `graph/executor/cache_resolver.py` | **迁移**到 `engine/extractors.py`，去掉单例依赖 |
| `graph/executor/test_executor.py` | **重写**为 `engine/runner.py`（当前与 ORM 耦合） |
| `graph/executor/jsonpath.py` | 迁移 |
| `graph/tools/*` | 保留，作为 L4 的 Agent 工具；但 `send_request` 需加环境防护 |
| `graph/nodes/*`（已删） | ✅ 删除正确，不要恢复 |
| `workflow.py` / `route.py` | 删除或重写（空图 + 前缀错误） |
| `data/models/*` | **保留**，11 张表设计可用；`test_case` 补 `setup`/`teardown` 字段 |
| `data/services/*` | 大部分保留（CRUD）；`case_generation_service` 的断言推导需重做 |
| `prompts/*` | `case_builder` / `flow_case_builder` 可复用；需补结构化输出的 schema 约束 |
| 前端 | 保留，等 L4 时按事件协议改造 |

**一句话**：把 `graph/executor/` 提升为 `engine/`，删掉 `graph/nodes/` 和 `workflow.py`，`graph/` 只保留 L4 的 Agent 编排——分层就顺了。

---

## 附：一页速查

```
从哪儿开始   →  Phase 0：命令行跑通已落库用例，全程不碰 LLM
怎么设计     →  两阶段分离（生成一次 / 执行 N 次）+ 五层架构 + 依赖严格向下
注意什么     →  ①LLM 不进执行路径 ②错误必须分类 ③"通过"必须可信
             ④状态不放单例 ⑤用例要能去重、能编辑、能 diff ⑥造数据要能清理
```
