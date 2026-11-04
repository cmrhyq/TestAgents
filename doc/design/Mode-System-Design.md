# 模式系统设计

> 版本：v2.0（对应 `feature/web_ui` 分支当前实现）
> 定位：解释「工作模式」在前后端如何落地，以及为什么必须落在执行路径上而不是提示词里。
> 本文描述已实现的行为；未实现的部分集中在[§七](#七未实现的四件事)，
> 标注为缺口而不是设计意图。
>
> 关联文档：[架构设计](Architecture.md) · [系统流程图](SystemFlowchart.md) · [页面设计准则](UI-Design-Guidelines.md)

---

## 一、结论先行

模式不是换一套提示词，而是同一条请求管线上四个层面同时切换：

```
UI 状态  →  请求参数  →  后端策略对象  →  运行时执行闸门
```

前三层是**提示性**的：前端可能被绕过，请求参数可能被伪造，策略对象本身只是数据。
只有第四层是**强制**的：工具不进入模型的可调用列表，调用时还要再查一次表。

最常见的错误做法是在 system prompt 里加一句「当前为问答模式，请不要发请求」。这样做的结果是：
模型手里仍然握着 `send_request`，它会调用，因为工具列表里有它，而 prompt 里的约束只是建议。
**模式必须落到「模型拿不到这个工具」这个事实层面。**

---

## 二、四层流转

| 层 | 落点 | 具体表现 |
|---|---|---|
| UI 状态 | `components/chat/mode-selector.tsx` | 分段控件，三个模式同时可见；选中值随每次请求上行 |
| 请求参数 | `ChatStreamRequest.mode` | `agent` / `ask` / `plan`，缺省 `agent` |
| 策略对象 | `agent/modes.py::policy_for()` | 冻结的 `ModePolicy`：是否允许副作用、模式指令、最大步数 |
| 执行闸门 | `build_tools` + `runner` 内的二次过滤 | 白名单裁剪工具列表；执行前再查 `tool_map` |

```mermaid
flowchart LR
  ui["ModeSelector<br/>前端状态"] -->|"mode 随每次请求上行"| req["ChatStreamRequest.mode"]
  req --> norm["normalize_mode()<br/>归一化旧值"]
  norm --> pol["policy_for()<br/>ModePolicy（冻结）"]
  pol --> tools["build_tools()<br/>按白名单装配"]
  tools --> run["runner.run()<br/>filter_tools 再裁一次"]
  run --> gate["_execute()<br/>查 tool_map，缺失即拒绝"]
```

---

## 三、后端实现

### 3.1 策略对象

`src/agent/modes.py` 提供四个东西：

```python
Mode(StrEnum)              # AGENT / ASK / PLAN，值分别为 "agent" / "ask" / "plan"
SIDE_EFFECT_TOOL_NAMES     # 五个有副作用的工具名
READ_ONLY_TOOL_NAMES       # 十二个只读工具名

@dataclass(frozen=True)
class ModePolicy:
    mode: Mode
    allow_side_effects: bool     # 仅 agent 为 True
    instruction: str             # 注入 system prompt 的模式指令
    max_steps: int               # 循环上限
```

`frozen=True` 不是风格偏好：`policy` 会沿着 `RunRequest → runner → 工具装配` 传递，
用不可变对象可以保证「整轮的工具权限只由一处决定」，不存在中途被改写的可能。

`blocked_tool_names` 是一个派生属性：允许副作用时返回空集合，否则返回
`SIDE_EFFECT_TOOL_NAMES`。这样调用方不需要写 `if mode == ...` 的分支。

### 3.2 归一化

```python
def normalize_mode(raw: str | None) -> Mode:
    key = (raw or "").strip().lower()
    return _MODE_ALIASES.get(key, Mode.AGENT)   # 未知值一律退化为 agent
```

未知值退化为 `agent` 而不是报错，是权衡后的选择：历史前端传过 `Run` / `Ask` / `Plan`，
若直接 422，旧客户端会全部失败。代价是拼错的模式名（例如 `Agentt`）会静默变成执行模式——
这一点必须在服务端授权校验补上时一并处理（见 §七）。

### 3.3 工具裁剪

```python
def filter_tools(tools, policy, skill_allowed=None):
    blocked = policy.blocked_tool_names
    result = [t for t in tools if t.name not in blocked]
    if skill_allowed is not None:
        result = [t for t in result if t.name in skill_allowed]
    return result
```

顺序不能反。若先按技能声明取交集、再按模式剔除副作用工具，结果虽相同；
但若反过来写成「技能声明的工具可以绕过模式限制」，技能就成了提权通道。
`tests/agent/test_skill_tool_contract.py` 钉住了这个契约。

裁剪发生两次：

1. `build_tools()` 装配时——决定下发给模型的工具 schema 有哪些；
2. `runner.run()` 开头——`ToolBundle` 可能由调用方手工构造（测试就是如此），
   模式保证不能只依赖装配处。第二次裁剪是廉价的安全网。

### 3.4 执行前的二次校验

`runner._execute()` 的第一件事是查 `tool_map`：

```python
tool = tool_map.get(name)
if tool is None:
    return ToolOutcome(
        False,
        f"工具 {name} 不存在。当前可用工具：{...}。请只调用列表中存在的工具。",
        "not_found",
        f"tool {name} not found",
    )
```

模型编造工具名在生产里是常态（尤其小参数模型）。这里的处理原则是
**返回结构化结果而不是抛异常**：异常会炸掉整轮循环，用户只看到一句报错；
返回工具结果则让模型看到「我调错了」，它通常会自己改用正确工具或直接说明做不到。

同一条原则也适用于生产环境闸门：被拦下的请求返回 `ok=false` 的工具结果，
模型据此告知用户「该环境不允许写操作」，而不是让整个流失败。

---

## 四、前端实现

### 4.1 模式选择器

`components/chat/mode-selector.tsx` 用分段控件而非下拉框——三个模式需要同时可见、可横向比较。
选中态由 `use-chat.ts` 持有的当前会话状态决定。

界面文案必须描述**真实权限边界**，不允许「尽量不执行」这类模糊承诺（见[页面设计准则](UI-Design-Guidelines.md) §7.9）：

| 模式 | 标签 | 说明文案 |
|---|---|---|
| `agent` | 执行 | 自动选择工具：查接口、发请求、评估断言并落盘 |
| `ask` | 问答 | 只回答问题，可用工具全为只读，不会发任何请求 |
| `plan` | 计划 | 只输出测试计划（接口范围 / 用例矩阵 / 断言策略 / 风险） |

### 4.2 mode 随每轮请求上行

`mode` 不是一个「建会话时发送一次」的参数。用户会在会话中途切换模式（先规划、看计划、再执行），
因此 `use-chat.ts` 在每次提交时都把当前 `mode` 放进请求体：

```jsonc
POST /api/v1/chat/stream
{
  "instruction": "为登录接口设计一组测试用例",
  "space_id": 238452574070505472,
  "conversation_id": 238452574070505473,
  "mode": "plan",
  "skill_names": ["api-test-design"],
  "environment_id": 238452574070505474
}
```

会话行上的 `mode` 只记录「默认值」，不参与本轮判定。服务端每轮重新解析策略，
不把 `ModePolicy` 缓存在会话对象上——缓存了就会出现「中途切模式不生效」。

### 4.3 渲染

`use-chat.ts` 用事件归约而非字符串拼接：把 `ChatEvent` 流归约成「已落库消息 + 本轮 overlay」两份状态。
`tool_call` 与 `tool_result` 按 `id` 配对，落到同一张折叠卡片上；`ok=false` 着错误色，
展开后保留原始错误文本。

---

## 五、三模式的行为差异

| 维度 | `agent` | `ask` | `plan` |
|---|---|---|---|
| 可用工具数 | 17 | 12（只读） | 12（只读） |
| `send_request` | 有 | 无 | 无 |
| `write_file` / `delete_file` | 有 | 无 | 无 |
| `remember` / `forget` | 有 | 无 | 无 |
| 最大步数 | 100 | 100 | 80 |
| 典型产物 | 请求结果、落盘用例、记忆条目 | 分析结论 | 文字计划 |

三种模式的 system prompt 指令不同（`agent/prompt/agent.py::AGENT_MODE_INSTRUCTIONS`），
但那是**行为风格**的差异，不是权限的差异。权限差异全部由工具集承载。

`ask` 与 `plan` 的区别在于指令措辞：`ask` 要求直接回答，`plan` 要求输出结构化的计划
（测试目标、接口范围、用例矩阵、执行顺序与数据依赖、需要人工确认的风险点）。
两者共享同一套只读工具。

---

## 六、几个设计取舍

### 6.1 plan 模式也过滤掉写工具

通用建议是「Plan 模式保留写工具 schema，闸门判 RECORD，这样模型才能规划出写操作」。
本项目**故意反着做**，原因是产品语义不同：

- 那套建议的前提是「批准计划后由同一套 loop 续跑执行」，模型必须看得见写工具才能规划。
- 本项目的 `plan` 语义是「输出一份给人看的计划」，计划由人带走到 `agent` 模式重跑，
  不存在「在 plan 里排队等待执行」的步骤。因此直接砍掉写工具是更彻底的保证——
  模型连表达「我要写文件」的能力都没有。

若将来补上审批续跑，这条取舍必须一起改回去，否则计划里的写操作会缺 schema。

### 6.2 步数上限是兜底，不是成本控制

`agent` / `ask` 上限 100 步、`plan` 80 步。早期取 12 / 8，实测在真实回归场景里不够用：
「读 20 个接口定义 → 逐个发请求 → 逐条断言」必然超过 12 步，触发中止后用户只能重来。

上限的作用是兜住模型在两个工具之间来回试探的死循环。成本控制靠的是
token 统计（`llm_log`）与技能收窄工具集，不是靠砍步数。

### 6.3 技能只能收窄

`Skill.allowed_tools` 与模式白名单取交集，永不并集。技能是用户可导入的内容（zip 包），
如果它能放开模式禁用的工具，导入一个技能就等于提权。

### 6.4 未实现的通用建议：`Gate` 四态

设计上常把闸门抽象成 `ALLOW` / `RECORD` / `DENY` / `ESCALATE` 四态。
本项目只实现了 `ALLOW` 与 `DENY`（以「工具不在表中」的形式），
`RECORD` 与 `ESCALATE` 依赖审批流与检查点，当前没有（见 §七）。

---

## 七、未实现的四件事

这四项不是遗漏，是被明确推迟的，且互相依赖：

| # | 缺口 | 现状 | 补齐的前置条件 |
|---|---|---|---|
| 1 | 服务端模式授权 | `mode` 由前端传入，服务端只做归一化，不校验调用者是否有权使用该模式 | 需要用户/租户权限模型；当前系统无登录体系 |
| 2 | 人工审批 | 生产环境是硬拒绝，不是「挂起等确认」 | 需要审批卡组件 + 挂起/恢复机制 |
| 3 | 结构化计划 | `plan` 输出的是文字计划，没有可勾选、可批准的步骤对象 | 需要 `plan` / `plan_step` 表与计划卡 |
| 4 | 事件重放 | 事件只在流里存在，落库的只有消息与工具调用明细，断线无法续传 | 需要 `conversation_event` 表（`seq` / `type` / `payload`） |

这四项的共同前提是**会话状态缺一个可恢复的检查点**：当前一轮请求的生命周期完全绑在 HTTP 连接上，
连接断了就没有「这一轮跑到哪」的记录。`agent_run` + `agent_tool_call` 提供了**事后回放**能力
（能查、能看轨迹），但没有提供**断点续跑**能力（不能从第 5 步接着跑）。

补齐顺序建议：先做 4（事件落库），再做 3（计划结构化），最后做 2（审批）与 1（授权）。

---

## 八、修订记录

| 日期 | 说明 |
|---|---|
| 2026-11-04 | v2.0：改为实现优先的写法，删除与实际端点不符的示例代码；步数上限 12/8 → 100/80；补「三模式行为差异」与四项缺口；删除对已归档差距分析文档的引用 |
| 2026-10-20 | v0.2：核心落地，§九 增加设计↔实现逐条对照 |
