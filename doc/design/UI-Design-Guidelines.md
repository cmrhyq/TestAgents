# TestAgents 页面设计准则（工业蓝图 · Blueprint）

> 版本：v2.0（对应当前前端实现）
> 技术栈：Tailwind CSS v4 + shadcn/ui + React 19
> 设计语言：**工业蓝图（Blueprint）** —— 像一张"活的工程图纸"
> 令牌来源：[`frontend/src/index.css`](../../frontend/src/index.css)、[
`frontend/tailwind.config.ts`](../../frontend/tailwind.config.ts)
> 设计上下文：项目根目录 [`.impeccable.md`](../../.impeccable.md)

---

## 一、设计目标

TestAgents 是一台 **AI 驱动的 API 测试精密工具**。界面气质对标**工程图纸 / 蓝图 / 技术标注**
：浅蓝纸底、工程蓝墨线、等宽标注、印章式徽章——精密、克制、有强烈辨识度，与市面上千篇一律的暗色 AI 界面区隔。

核心原则：

1. **墨线分层，而非阴影堆叠** — 容器用 1px 工程蓝墨线（`border`）+ 极轻阴影区分，不靠深色色块。
2. **图纸网格** — 全站背景带极淡 16px 工程网格，hero 区使用 24px 网格纹理（`.bg-blueprint-grid`）。
3. **等宽标注** — 表头、面包屑、编号、统计读数使用 mono 字体 + 大写 + 宽字距（`.annotation`），营造图纸标注感。
4. **语义化令牌优先** — 使用 `bg-background`、`text-muted-foreground` 等令牌；页面层禁止硬编码色值。
5. **组件复用优先** — 新页面组合 `components/ui/*` 与 `components/shared/*`，不重复写样式。

---

## 二、色彩体系

所有色值以 **oklch** 定义（构建时自动降级输出 hex / P3 / lab 三套，见 §12）。亮色图纸为默认，暗色「夜图」通过 `html.dark` 覆盖。

### 2.1 亮色图纸（默认）

| 令牌                           | oklch 值           | 用途                      |
|------------------------------|-------------------|-------------------------|
| `background`                 | `0.955 0.012 235` | 页面主背景（浅蓝图纸）             |
| `sidebar`                    | `0.93 0.015 235`  | 侧边栏背景（比主区略深）            |
| `card` / `popover` / `input` | `0.985 0.006 230` | 卡片、弹层、输入框（描图纸感）         |
| `foreground`                 | `0.30 0.05 250`   | 标题、正文（墨蓝）               |
| `muted`                      | `0.93 0.012 235`  | hover 背景、次要容器           |
| `secondary`                  | `0.90 0.015 235`  | 略深 hover、secondary 按钮   |
| `muted-foreground`           | `0.50 0.05 245`   | 说明文字、表头、占位符（≥4.5:1 对比度） |
| `border`                     | `0.78 0.035 240`  | 容器边框、分隔线（工程蓝墨线）         |
| `border-subtle`              | `0.87 0.022 240`  | 表格行分隔等更弱的分割             |

### 2.2 暗色夜图（`html.dark`）

| 令牌                             | oklch 值                                                 | 说明        |
|--------------------------------|---------------------------------------------------------|-----------|
| `background`                   | `0.18 0.025 250`                                        | 深海军蓝（非纯黑） |
| `card`                         | `0.22 0.028 250`                                        | 略亮于背景     |
| `sidebar`                      | `0.15 0.02 250`                                         | 比背景更深     |
| `foreground`                   | `0.90 0.02 230`                                         | 浅蓝白（非纯白）  |
| `primary`                      | `0.72 0.12 240`                                         | 提亮的工程蓝    |
| `border`                       | `0.34 0.04 245`                                         | 暗色墨线      |
| `success` / `warning` / `info` | 提亮档（`0.72 0.11 150` / `0.76 0.13 80` / `0.70 0.10 240`） | 保证对比度     |

### 2.3 语义色（产品逻辑）

| 令牌            | 亮色 oklch        | 用途                          |
|---------------|-----------------|-----------------------------|
| `primary`     | `0.50 0.13 255` | 主按钮、激活态、链接、focus 环（**工程蓝**） |
| `accent`      | `0.50 0.13 255` | 同 primary（品牌即强调）            |
| `destructive` | `0.52 0.17 25`  | 删除、失败（修订红）                  |
| `success`     | `0.55 0.11 150` | 通过、批准（印章绿）                  |
| `warning`     | `0.62 0.13 75`  | 警告、跳过（铅笔琥珀）                 |
| `info`        | `0.55 0.10 250` | 信息、运行中（蓝）                   |

### 2.4 HTTP 方法色（`--color-method-*`）

| 方法     | 语义           | 方法       | 语义                |
|--------|--------------|----------|-------------------|
| `GET`  | 印章绿（success） | `DELETE` | 修订红（destructive）  |
| `POST` | 蓝（info）      | `PATCH`  | 弱紫                |
| `PUT`  | 琥珀（warning）  | 未知       | `border-border` 灰 |

### 2.5 表面 tint（`surface-*`）

`color-mix(in oklab, <色> 8%, transparent)` 生成，用于导航激活背景、hero 卡底、图标底等**小面积点缀**，不可整页使用。

### 2.6 用色禁忌

- 禁止纯黑 `#000` / 纯白 `#fff`、GitHub 蓝灰暗色、AI-slop（青+深色、紫蓝渐变、霓虹）。
- 禁止硬编码 Tailwind 默认色（`emerald-500` 等）；统一语义令牌。
- 禁止用 `card`、`muted`、`secondary` 同值导致层次消失。
- 阴影透明度保持 ≤8%，避免"重阴影 + 深底"。

---

## 三、字体与排版

### 3.1 字体族（Google Fonts）

| 令牌               | 字体                | 用途                      |
|------------------|-------------------|-------------------------|
| `--font-sans`    | **Inter**         | 正文 UI，中文回退 Noto Sans SC |
| `--font-mono`    | **IBM Plex Mono** | 标注、表头、编号、代码、URL、统计读数    |
| `--font-display` | **Space Grotesk** | 页面大标题、统计大数字             |

```css
--font-sans:

"Inter"
,
-apple-system,

"Segoe UI"
,
"Noto Sans SC"
,
"PingFang SC"
,
sans-serif

;
--font-mono:

"IBM Plex Mono"
,
ui-monospace, Consolas, monospace

;
--font-display:

"Space Grotesk"
,
"Inter"
,
sans-serif

;
```

### 3.2 层级规范

| 元素   | 类名建议                                                                   | 说明                               |
|------|------------------------------------------------------------------------|----------------------------------|
| 页面标题 | `font-display text-2xl font-semibold tracking-tight`                   | 如「仪表盘」                           |
| 页头注解 | `.annotation`（`font-mono text-[11px] uppercase tracking-[0.1em]`）      | 如 `FIG.01 — OVERVIEW`、`SPACE_12` |
| 区块标题 | `font-display text-lg font-semibold`                                   | 如「空间」                            |
| 表头   | `font-mono text-[11px] uppercase tracking-wider text-muted-foreground` | DataTable 内置                     |
| 统计读数 | `font-display text-3xl font-semibold tabular-nums`                     | 读数带大数字                           |
| 等宽数据 | `font-mono text-xs`                                                    | URL、时间、文件大小、编号                   |
| 正文   | `text-sm`                                                              | 默认内容                             |
| 辅助说明 | `text-sm text-muted-foreground`                                        | 副标题、描述                           |

### 3.3 字重

- 以 Regular / Medium 为主；标题用 `font-semibold`（display 字体）。
- 数字一律 `tabular-nums` 保证等宽对齐。

---

## 四、圆角、边框与阴影

### 4.1 圆角（图纸工具感：锐利）

| 令牌             | 值   | 适用               |
|----------------|-----|------------------|
| `rounded-sm`   | 0   | 印章徽章、小元素         |
| `rounded-md`   | 2px | 按钮、输入框           |
| `rounded-lg`   | 4px | 卡片、表格容器、Composer |
| `rounded-xl`   | 6px | 弹层等稍大元素          |
| `rounded-full` | 50% | 仅发送按钮、色点         |

### 4.2 边框

- 标准容器：`border border-border`（1px 墨线）。
- 表格行：`border-border-subtle`；区块顶/底：`border-border`。
- **虚线**：`border-dashed` 用于"草稿/待定"语义（如 pending 状态徽章）。

### 4.3 阴影

定义于 `index.css` 的 `--shadow-*`（亮/暗双套），按 elevation 选用：

| 类名                          | 场景                              |
|-----------------------------|---------------------------------|
| `shadow-xs` / `shadow-card` | 卡片、按钮、输入框默认态                    |
| `shadow-elevated`           | 侧栏展开 FAB                        |
| `shadow-popover`            | Dropdown、Tooltip 弹层（带 1px 墨线环）  |
| `shadow-input`              | Input / Textarea focus 态（工程蓝光环） |

**原则：** 蓝图以墨线为主、阴影为辅——阴影透明度极低（≤8%），禁止大面积阴影。

---

## 五、签名元素（Signature Elements）

这些是让界面"一眼是蓝图"的记忆点，新增页面时应沿用：

1. **图纸网格** — `body` 自带 16px 极淡网格（主色 4% 透明度）；hero 卡用 `.bg-blueprint-grid`（24px，5%）铺底。
2. **等宽标注** — `.annotation` 类（mono 大写宽字距）：页头 `FIG.xx — TITLE`、空间卡 `SPACE_{id}`、顶栏 `~/页面名` 面包屑。
3. **印章式徽章** — 状态与 HTTP 方法均为**描边印章**：
   `rounded-[2px] border border-{color}/50 bg-{color}/5 font-mono text-[11px] uppercase`；`pending` 用虚线边框（草稿批注感）。
4. **图纸角标** — hero 卡四角十字墨线（`CornerMarks`，见 `dashboard.tsx`）。
5. **读数带** — 统计区不用"卡片套卡片"，改为**横排读数带**：`divide-x divide-border-subtle` 竖墨线分隔 + `font-display`
   大数字 + mono 色点标签（见 `dashboard.tsx`、`run-detail.tsx`、`report-view.tsx`）。
6. **终端提示符** — Composer 输入框带 mono `❯` 前缀；AI 空态欢迎页 `> _`。
7. **Agent 输出流** — 左侧 2px 工程蓝墨线 + mono `AGENT` 标注 + 虚线分隔（`message-bubbles.tsx`）。
8. **刻度进度条** — 通过率条为 3–6px 高圆角条，填充带垂直刻度线纹理（`pass-rate-bar.tsx`）。

---

## 六、布局结构

### 6.1 应用骨架

```
┌─────────────┬──────────────────────────────────┐
│  Sidebar    │  TopBar (40px sticky, ~/面包屑 + 主题切换 + 版本) │
│  250px      ├──────────────────────────────────┤
│  bg-sidebar │  Main (bg-background, p-6 lg:p-8) │
│  border-r   │  <Outlet /> 页面内容              │
└─────────────┴──────────────────────────────────┘
```

- 顶栏（`top-bar.tsx`）：`~/页面名` mono 面包屑 + `ThemeToggle` + 版本号，`backdrop-blur` 半透明。
- 主内容区统一 `p-6 lg:p-8`，路由切换带 fade + slide 过渡（300ms `ease-out-expo`）。
- Sidebar 收起宽度 0，300ms 过渡；展开按钮 `rounded-sm` 直角风格。

### 6.2 Sidebar 规范（`sidebar.tsx`）

- 背景：`bg-sidebar`；右边框：`border-r border-border`。
- 品牌区：**空心工程蓝方块** logo（`border-2 border-primary`）+ `font-display` 产品名 + mono 版本号。
- 导航项（`NavLink`）：
    - 默认：`border-l-2 border-transparent text-muted-foreground`
    - Hover：`hover:bg-muted hover:text-foreground`
    - 选中：`border-l-2 border-primary bg-surface-primary font-medium text-foreground`
    - 右侧 mono 编号（`01` ~ `05`，顺序固定：仪表盘 / 测试对话 / 测试空间 / 技能管理 / 测试报告）
    - 布局：`rounded-sm px-3 py-1.5 gap-2 text-sm`
- 导航分组上方有 mono 注解 `NAV_01`。

### 6.3 页头（`page-header.tsx`）

```tsx
<PageHeader
    title="仪表盘"
    annotation="FIG.01 — OVERVIEW"   // 可选 mono 注解
    description="API 测试空间概览。"
    actions={<Button ...>...</Button>}  // 可选右侧操作区
/>
```

---

## 七、组件使用准则

### 7.1 Card

```tsx
// 类：rounded-[4px] border border-border bg-card shadow-xs
<Card>...</Card>
```

- hero 卡可在卡片上用 `bg-surface-primary/50` + `.bg-blueprint-grid` + `CornerMarks`。
- 不要去掉边框仅靠阴影，不要深灰铺底。

### 7.2 Button

| Variant       | 场景                                                            |
|---------------|---------------------------------------------------------------|
| `default`     | 主操作 — 工程蓝底白字 + `border border-primary`，hover `brightness-110` |
| `outline`     | 次要操作 — 白底 + 墨线边框                                              |
| `ghost`       | 表格行内、工具栏图标按钮                                                  |
| `secondary`   | 低强调填充按钮                                                       |
| `destructive` | 删除确认（修订红）                                                     |
| `link`        | 行内文字链                                                         |

- 圆角 `rounded-[2px]`；高度 `h-8`；过渡 `duration-200 ease-out-expo`。

### 7.3 Input / Textarea

- `rounded-[2px] border border-border bg-input shadow-xs`
- Focus：`focus-visible:border-primary/60 focus-visible:shadow-input`
- URL / 代码类字段可用 `font-mono`（如 base_url 以 mono chip 呈现）。

### 7.4 DataTable（`data-table.tsx`）

- 容器：`rounded-[4px] border border-border bg-card shadow-xs`
- 表头：`bg-muted/50` + mono 11px 大写宽字距
- 行 hover：`hover:bg-muted/50`；行分隔：`border-border-subtle`
- 分页脚：mono `PAGE x / y` + `rounded-sm` 墨线按钮

### 7.5 Composer（AI 对话输入）

```tsx
<div className="rounded-[4px] border border-border bg-card px-3 py-2.5 shadow-xs
                focus-within:border-primary/50 focus-within:shadow-input">
    <span className="font-mono text-sm font-semibold text-primary">❯</span>
    <textarea className="bg-transparent ..."/>
    {/* 工具栏：rounded-full 胶囊按钮 + 发送圆形按钮 */}
</div>
```

### 7.6 徽章与状态

- 状态：`StatusBadge` — 描边印章式；`running` 带 pulse；`pending` 虚线。
- HTTP 方法：`HttpMethodBadge` — 描边印章式，色来自 `--color-method-*`。
- 空间启用状态：shadcn `Badge`（`default` 启用 / `secondary` 未启用）。

### 7.7 Tabs

下划线式：`border-b border-border` 列表 + 激活项 `border-b-2 border-primary` + mono 大写宽字距标签。

### 7.8 链接

- 全局 `<a>` 默认 `color: accent`；表格内链接 `font-medium text-accent hover:text-accent/80`。
- 导航使用 `NavLink`，不依赖全局下划线。

### 7.9 模式选择器（`chat/mode-selector.tsx`）

分段控件，不是下拉——三个模式要**同时可见可比**。选中态工程蓝底白字，容器 `rounded-[3px]` + 1px 边框 + `p-0.5`。

| 值 | 图标 | 标签 | 说明文案（必须对齐真实行为） |
|:--|:--|:--|:--|
| `agent` | `Zap` | 执行 | 自动选择工具：查接口、发请求、评估断言并落盘 |
| `ask` | `MessageSquare` | 问答 | 只回答问题，可用工具全为只读，不会发任何请求 |
| `plan` | `ListTodo` | 计划 | 只输出测试计划（接口范围 / 用例矩阵 / 断言策略 / 风险） |

> **文案纪律**：`ask` / `plan` 的「不会执行」是后端工具白名单保证的事实，不是营销措辞。
> 任何新模式上线，`hint` 必须描述**该模式的真实权限边界**，不允许写「尽量不执行」这类模糊承诺。

### 7.10 技能选择器（`chat/skill-selector.tsx`）

`DropdownMenu` + 多选，触发器为胶囊按钮（`Sparkles` 图标 + 已选数量 + `ChevronDown`），
面板宽 `w-72` + `shadow-popover`。每项：`font-mono` 技能名 + 一行截断描述 + 选中 `Check`。
未选中任何技能时显示「未选择技能（使用内置能力）」，**不要**默认勾选——默认勾选会让用户失去「到底用了什么」的判断。

### 7.11 工具调用卡片（`chat/tool-call-card.tsx`）

Agent 的执行轨迹必须**默认折叠但可展开**，标题行永远可见：

```tsx
<div className="rounded-[3px] border border-border bg-background/60">
  <button className="flex w-full items-center gap-2 px-2.5 py-1.5">
    <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
    <span className="truncate font-mono text-xs font-medium">{call.name}</span>
    <span className="ml-auto font-mono text-[10px] uppercase tracking-widest">200ms</span>
  </button>
  {/* 展开区：ARGS / RESULT 两段，label 用 .annotation */}
</div>
```

| 状态 | 图标与配色 |
|:--|:--|
| 运行中 | `Loader2` + `animate-spin` + `text-primary` |
| 成功 | `Check` + `text-success` |
| 失败 | `AlertTriangle` + `text-destructive`，并在展开区保留原始错误文本 |

- 参数与结果都用 `<pre max-h-40 overflow-auto font-mono text-[11px]>`，长内容靠滚动而非换行撑高页面。
- 一轮多个调用时，上方加一条 `TOOL_TRACE · {n}` 的 `annotation` 汇总条。

### 7.12 上下文栏与空间选择器

对话页顶部固定一行 `border-b border-border px-4 py-2`，左侧 `SpaceSelector`，右侧 `annotation`
（`Context · Space`）——等宽大写仅作装饰性标注，不承载信息。未选空间时整页替换为空态，
**不要**让用户先输入再提示「请选择空间」。

### 7.13 页面骨架模板

| 页面 | 骨架 |
|:--|:--|
| 测试对话 `/chat` | 左侧 `ConversationListPanel`（220px，`md` 以下隐藏）+ 右侧对话区（消息流 `max-w-3xl` 居中）+ 底部固定 Composer |
| 空间详情 `/spaces/:id` | `PageHeader` + 7 个 `TabsContent`（概览 / 会话 / 接口 / 环境 / 记忆 / 知识库 / 执行记录），每个 tab 内部自带 `space-y-4` |
| 技能管理 `/skills` | `PageHeader` + zip 导入按钮 + 技能卡片列表（名称 mono、scope 徽章、启停开关、声明工具数） |
| 测试报告 `/reports` | `PageHeader` + 筛选条（空间 / 状态）+ `DataTable`（每行一个 `run_id` 的聚合：请求数 / 成功数 / 失败数 / 异常数 / 成功率） |
| 报告详情 `/reports/:id` | 顶部读数带（成功率 / 请求数 / P95 耗时）+ 逐请求列表；响应正文按需加载，不随列表一次性拉取 |
| 执行详情 `/runs/:id` | 顶部读数带（工具调用数 / 成功率 / 平均耗时 / token / 成本）+ `TOOL_TRACE` 轨迹列表，每行可展开入参与结果 |

执行详情与报告详情的数据来源不同，不要混用：报告读的是 `send_request` 调用（只统计 HTTP），
执行详情读的是整轮 `agent_run` 的全部工具调用（含读文件、查记忆等非 HTTP 工具）。
两者的「成功率」因此可能不一致，页面上应当把口径写清楚。

---

## 八、间距与密度

| 场景      | 建议                          |
|---------|-----------------------------|
| 页面级垂直间距 | `space-y-6` / `gap-8`       |
| 读数带内边距  | `px-6 py-5`                 |
| 卡片网格    | `grid gap-4 md:grid-cols-3` |
| 侧栏导航项   | `px-3 py-1.5`，项间距 `gap-0.5` |
| 表格单元格   | `px-4 py-3`                 |

保持"可呼吸"——图纸标注式排版需要充足留白，避免元素贴边。

---

## 九、主题切换（亮色图纸 ⇄ 暗色夜图）

1. **默认亮色**：`localStorage["lta-theme"]` 缺省 `light`；`index.html` 内联防闪烁脚本在 React 挂载前设置 `html.dark`
   类与初始背景色。
2. **切换**：`use-theme.ts` 同步 `documentElement.classList.toggle("dark", ...)` + localStorage；顶栏 `ThemeToggle`
   （Sun/Moon）。
3. **联动**：
    - sonner Toaster 绑定 `theme`（`main.tsx`）。
    - Shiki 代码高亮：双主题输出 `--shiki-dark` CSS 变量，`html.dark .shiki span { color: var(--shiki-dark) !important }`
      切换（见 `markdown.css`）。
    - Mermaid：`markdown-mermaid-block.tsx` 依据 `useTheme` 选 `neutral` / `dark`，以 theme 为 key 重渲染。
4. `color-scheme` 同步设置，保证原生控件跟随。

---

## 十、暗色夜图要点

- 令牌在 `html.dark` 下于 `index.css` 统一覆盖，组件只需语义类名。
- 网格纹理颜色随 `--color-primary` 变化，暗色下自动提亮。
- 夜图底色为**深海军蓝**（非纯黑），保持「侧栏略深、主区略浅」的层次。

---

## 十一、新页面检查清单

- [ ] 未硬编码 Tailwind 调色板色或 hex 色值（全部使用语义令牌）
- [ ] 容器使用 `border-border` + 轻 `shadow-*`，圆角遵循 0/2/4/6px 阶梯
- [ ] 页头使用 `PageHeader`（含 `annotation` 注解），标题 `font-display`
- [ ] 统计区使用「读数带」而非卡片套卡片
- [ ] 状态 / HTTP 方法使用印章式徽章（`StatusBadge` / `HttpMethodBadge`）
- [ ] 数字使用 `tabular-nums` + mono / display 字体
- [ ] 列表使用 `DataTable`，未重复实现表格样式
- [ ] 链接与状态色使用语义令牌（`accent` / `primary` / `destructive` / `success`）
- [ ] 新文本沿用 mono 大写标注规范（`.annotation`）
- [ ] Agent 执行过程可见：工具调用必须有卡片，不允许「只显示最终答案」
- [ ] 模式/技能说明文案与后端真实权限边界一致（见 §7.9 文案纪律）
- [ ] 长内容（工具参数、响应体、目录树）使用滚动容器，不撑高页面
- [ ] 亮色图纸与暗色夜图两种模式下均验证可读性
- [ ] 通过 `tsc --noEmit` 与 `npm run build`

---

## 十二、技术说明

- **令牌架构**：`index.css` 用「纯 CSS 变量（`--background` 等）+ `@theme inline` 映射
  `--color-background: var(--background)`」模式；Lightning CSS 构建时会自动为 oklch 生成 hex / `display-p3` / `lab` 三套
  `@supports` 兜底（勿在 `html.dark` / `:root` 内直接写 `--color-*` 覆盖，会被构建管线重排丢弃）。
- **动效**：统一 `ease-out-expo`（`cubic-bezier(0.16,1,0.3,1)`），时长 150 / 200 / 300ms；流式光标为 1px 闪烁竖线（
  `animate-cursor-blink`，step-end）。
- **字体加载**：Google Fonts（Inter / IBM Plex Mono / Space Grotesk），如需内网可换 `@fontsource-variable/*` 自托管。

---

## 十三、相关文件索引

| 类型                  | 路径                                                                                                            |
|---------------------|---------------------------------------------------------------------------------------------------------------|
| 设计上下文               | `.impeccable.md`                                                                                              |
| 色彩 / 字体 / 主题令牌      | `frontend/src/index.css`                                                                                      |
| 阴影 / 动画结构令牌         | `frontend/tailwind.config.ts`                                                                                 |
| 主题 hook             | `frontend/src/hooks/use-theme.ts`                                                                             |
| 主题切换按钮              | `frontend/src/components/shared/theme-toggle.tsx`                                                             |
| 应用布局 / 顶栏 / 侧栏 / 页头 | `frontend/src/components/layout/{app-layout,top-bar,sidebar,page-header}.tsx`                                 |
| 共享组件                | `frontend/src/components/shared/*`                                                                            |
| UI 基元               | `frontend/src/components/ui/*`                                                                                |
| 对话组件                | `frontend/src/components/chat/*`                                                                              |
| Markdown 子系统        | `frontend/src/components/markdown/*`、`frontend/src/styles/markdown.css`                                       |
| 参考页面                | `frontend/src/pages/dashboard.tsx`（读数带 + 角标）、`frontend/src/pages/chat/chat.tsx`（三选择器 + Composer + 工具轨迹）、`frontend/src/pages/space/space-detail.tsx`（7 tabs）、`frontend/src/pages/run/run-detail.tsx`（执行轨迹）、`frontend/src/pages/report/report-view.tsx`（逐请求报告） |
| 类型定义                | `frontend/src/lib/types/*`（按域拆分：conversation / skill / memory / knowledge / space / agent-run / report …）                                                     |
| 流式协议客户端             | `frontend/src/lib/stream.ts`（三行帧 → `ChatEvent` 判别联合）                                                                              |

---

## 十四、演进说明

本准则随前端实现迭代。调整全局风格时**优先改令牌层**（`index.css`），再改基元组件，最后才改个别页面；单次改版避免同时改动配色、圆角、布局三套体系，便于
review 与回退。

---

## 十五、修订记录

| 日期 | 说明 |
|---|---|
| 2026-11-04 | v2.0：补测试报告、报告详情、执行详情三个页面骨架；空间页签「测试运行」更正为「执行记录」；补报告与执行详情的统计口径差异说明；文件索引补 `agent-run` / `report` 类型与参考页面 |
| 2026-10-20 | v0.2.0：补模式选择器、技能选择器、工具调用卡片、上下文栏与页面骨架 |
