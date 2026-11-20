# TestAgents 界面设计准则

> Tailwind CSS v4 + shadcn/ui + React 19
> 令牌：`frontend/src/index.css`　结构配置：`frontend/tailwind.config.ts`
> 主题：浅色为默认，`html.dark` 覆盖同名变量，组件只写语义类名

---

## 一、色彩

### 1.1 令牌

| 令牌 | 浅色 | 深色 | 用途 |
|---|---|---|---|
| `background` | `#ffffff` | `#1a1a1a` | 页面画布 |
| `sidebar` | `#f7f7f7` | `#1f1f1f` | 侧边栏 |
| `card` / `popover` / `input` | `#ffffff` | `#242424` | 卡片、浮层、输入框 |
| `secondary` | `#f2f2f2` | `#292929` | 次要按钮底 |
| `muted` | `#f2f2f2` | `#242424` | 表头、分段控件槽、代码块底 |
| `foreground` | `#000000` | `#ffffff` | 标题与正文 |
| `muted-foreground` | `#5d5d5d` | `#a6a6a6` | 说明、表头字、占位符 |
| `border` | `rgba(0,0,0,.08)` | `rgba(255,255,255,.14)` | 容器描边 |
| `border-subtle` | `rgba(0,0,0,.04)` | `rgba(255,255,255,.06)` | 表格行分隔、侧栏分区 |
| `border-strong` | `#dedede` | `#3d3d3d` | 输入框 hover |
| `hover` | `rgba(20,112,180,.055)` | `rgba(107,170,248,.10)` | 行与菜单项 hover |
| `hover-strong` | `rgba(20,112,180,.095)` | `rgba(107,170,248,.16)` | 小图标按钮 hover |
| `selected` | `rgba(20,112,180,.10)` | `rgba(107,170,248,.15)` | 导航激活、会话激活、用户消息底 |
| `primary` | `#1a1a1a` | `#f5f5f5` | 主按钮底、Tooltip 底 |
| `primary-foreground` | `#ffffff` | `#141414` | 主按钮字 |
| `accent` | `#1470b4` | `#6baaf8` | 链接、focus 描边、运行中 |
| `ring` | `rgba(20,112,180,.45)` | `rgba(107,170,248,.55)` | 焦点环 |

`muted-foreground` 是 12px 小字的最低可用值，不要再调浅。

### 1.2 状态色

| 语义 | 浅色 | 深色 | 用于 |
|---|---|---|---|
| `success` | `#0b8a4d` | `#3ecf8e` | 通过、2xx、启用 |
| `warning` | `#9a6700` | `#e6b84d` | 跳过、无响应、延迟偏高 |
| `destructive` | `#c9302f` | `#f07178` | 失败、删除 |
| `info` | `#2563eb` | `#6baaf8` | 运行中、信息 |

### 1.3 HTTP 方法色

| 方法 | 浅色 | 深色 |
|---|---|---|
| `GET` | `#0b8a4d` | `#3ecf8e` |
| `POST` | `#2563eb` | `#6baaf8` |
| `PUT` | `#9a6700` | `#e6b84d` |
| `DELETE` | `#c9302f` | `#f07178` |
| `PATCH` | `#7c3aed` | `#c792ea` |

### 1.4 轻底色

`surface-primary` 取 `selected`，其余由状态色混 10~18% 得到：

```css
--color-surface-success: color-mix(in srgb, var(--success) 12%, transparent);
--color-surface-accent-strong: color-mix(in srgb, var(--accent) 18%, transparent);
```

只用于状态胶囊、错误提示条、图标底、进度条槽，不整块铺页面。

### 1.5 浅蓝的落点

浅蓝是调和色，只出现在三个层面。画布、卡片、侧栏、面板一律保持中性。

| 层面 | 落点 | 写法 |
|---|---|---|
| 交互态 | 行 hover、菜单项、导航激活、会话激活、用户消息底、焦点环 | `bg-hover` / `bg-hover-strong` / `bg-selected` / `ring` |
| 强调元素 | 链接、激活导航的图标、指标卡图标底、运行中转圈、选中勾、空间图标 | `text-accent` + `bg-surface-accent` |
| 数据与标签 | 读数带首列主指标、信息类 Badge、进度条槽 | `tone="accent"`、`variant="info"`、`bg-surface-accent-strong` |

两条边界：

- 状态数据不上蓝。成功、失败、异常、通过率填色仍用 `success` / `warning` / `destructive`，蓝色只给没有成败语义的读数和标签。红绿在这个产品里是功能信息，不是装饰。
- 蓝色不铺面。出现面积上限是图标容器、Badge、进度条槽、hover 底这一级；卡片头、表头、侧栏、读数带容器都不加浅蓝底。

### 1.6 规则

- 页面与业务组件不写 hex，不写 Tailwind 默认调色板。
- 主按钮用单色实心，不用彩色。彩色只给状态、链接、focus。
- 不用渐变、霓虹描边、紫蓝配色。
- 浅色阴影不透明度 ≤8%，且只给浮层。
- hover 用 `bg-hover`，不用 `bg-accent`。

---

## 二、字体

```css
--font-sans: "PingFang SC", -apple-system, BlinkMacSystemFont,
  "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI",
  "Microsoft YaHei", "Hiragino Sans GB", "Noto Sans CJK SC",
  "Source Han Sans SC", sans-serif;
--font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco,
  Consolas, "Liberation Mono", monospace;
--font-display: var(--font-sans);
```

不引外网字体。内网部署拉不到会整站掉到浏览器默认字体。

| 场景 | 写法 |
|---|---|
| 页面标题 | `text-[20px] font-semibold leading-7 tracking-[-0.01em]` |
| 区块标题 | `text-[14px] font-semibold leading-5` |
| 正文、按钮、输入、表格 | `text-[13px] leading-5` |
| 说明、表头、状态徽章 | `text-[12px] leading-4`（行内用 `leading-5`） |
| 极小标注（版本号、时长、分组名） | `text-[11px] font-medium leading-4` |
| 详情页读数 | `text-[24px] font-semibold leading-8 tracking-[-0.02em]` |
| 等宽数据 | `font-mono text-[11px]` 或 `text-[12px]` |

字距负值只给 20px 以上标题与 24px 读数。需要纵向对齐的数字一律 `tabular-nums`。

---

## 三、尺寸

### 3.1 圆角

| 令牌 | 值 | 用在哪 |
|---|---|---|
| `rounded-sm` | 4px | 徽章内部、小图标按钮 |
| `rounded-md` | 6px | 按钮、输入框、导航项、菜单项、工具卡片、状态徽章 |
| `rounded-lg` | 8px | 卡片、表格容器、分段控件槽、提示条 |
| `rounded-xl` | 12px | 对话输入框、对话框 |

一页不超过三档圆角。

### 3.2 高度

| 控件 | 值 |
|---|---|
| 按钮 `sm` / `icon-sm` | 28px |
| 按钮默认 / `icon` | 32px |
| 按钮 `lg` | 36px |
| 输入框、下拉触发器 | 32px |
| 侧栏导航项 | 32px |
| 顶栏 | 48px |
| 侧栏品牌区 / 底部工具条 | 56px / 44px |
| 分段控件槽 / 内部按钮 | 36px / 32px |

### 3.3 间距

| 场景 | 值 |
|---|---|
| 页面内容区 | `px-5 py-6`，≥lg `px-8 py-8` |
| 区块之间 | `gap-4` |
| 卡片内边距 | `p-4` |
| 单元格 | `px-3 py-2.5` |
| 表头单元格 | `px-3 py-2` |
| 侧栏内边距 | `px-2.5`，导航项 `gap-0.5` |
| 读数单元 | `px-4 py-3` |

---

## 四、阴影与焦点

| 令牌 | 用在哪 |
|---|---|
| `shadow-xs` | 激活的分段项、对话输入框 |
| `shadow-elevated` | 跳过导航链接 |
| `shadow-popover` | 下拉菜单、Tooltip |
| `shadow-dialog` | 对话框 |
| `shadow-input` | 输入框 focus 光环 |

卡片不加阴影，靠 8% 描边加白底分层。

焦点：全局 `:focus-visible` 给 2px `ring` + 1px offset；组件内部用 `focus-visible:ring-2 focus-visible:ring-ring/40`。

---

## 五、布局

```
┌──────────────┬───────────────────────────────────────┐
│ Sidebar 264  │ TopBar 48（面包屑，半透明 + 模糊）      │
│ bg-sidebar   ├───────────────────────────────────────┤
│              │ Main  max-w-[1400px]  px-5 py-6        │
│              │       ≥lg: px-8 py-8                   │
└──────────────┴───────────────────────────────────────┘
```

**侧栏**四段：品牌区 56px（24px 图标 + 产品名 13px 半粗 + 副标题 11px 灰）；主导航（分组名 11px 灰 + 仪表盘 / 测试空间 / 测试报告 / 技能管理）；空间会话区（可折叠，用 `.spaces-scroll` 细滚动条）；底部 44px（版本号 + 主题切换）。

导航项 `h-8 rounded-md px-2.5 text-[13px]`，激活 `bg-selected font-medium text-foreground`，激活态图标 `text-accent`。不用左边色条，不用实色底。

顶栏只有面包屑 `TestAgents / 当前页`，不设全局搜索、通知、头像。

**页头**统一用 `PageHeader`：标题 20px 半粗，`annotation` 为标题上方一行 12px 灰字，`meta` 跟在标题右侧（状态徽章），`description` 13px 最宽 3xl，`actions` 靠右。

---

## 六、组件

| 组件 | 关键样式 |
|---|---|
| `Button` | `rounded-md text-[13px] gap-1.5`；`default` 单色实心，`secondary` 灰底描边，`outline` 白底描边，`ghost` 仅 hover 出底，`destructive` 红底，`link` accent 色 |
| `Input` / `Textarea` / `Select` | `h-8 rounded-md border bg-card px-2.5 text-[13px]`；hover `border-strong`，focus `accent/60` + `shadow-input`，禁用 `bg-muted opacity-60` |
| `Card` | `rounded-lg border bg-card`，无阴影；`CardHeader` `gap-1 p-4`，`CardContent` `p-4 pt-0` |
| `Badge` | `rounded-md px-1.5 text-[12px]`，surface 底 + 语义字色，无描边；中性信息标签（模式、触发方式、内置/空间）用 `variant="info"` |
| `StatusBadge` | 同 Badge；`running` 带 `animate-pulse` 圆点；数值状态 1 启用 / 2 未启用 / 3 删除 / 4 废弃 |
| `HttpMethodBadge` | `h-5 w-14 rounded font-mono text-[11px] font-semibold`，定宽对齐 |
| `Tabs` | 分段控件：List `h-9 rounded-lg bg-muted p-0.5`，Trigger `h-8 rounded-md`，激活 `bg-card shadow-xs` |
| `DataTable` | `rounded-lg border bg-card`；表头 `bg-muted` 12px 灰；单元格 `px-3 py-2.5` 13px；行分隔 `border-subtle`，hover `bg-hover` |
| `Readout` | 标签 12px 灰 + 数值 24px 半粗 `tabular-nums`；`tone` 取 `default` / `accent` / `success` / `warning` / `danger`，无成败语义的指标用 `accent`，且只给读数带首列 |
| `ReadoutBand` | `grid-cols-2`，`sm` 三列，`lg` 六列 + `divide-x divide-border-subtle` |
| `PassRateBar` | 20×6 圆角条，槽 `bg-surface-accent-strong`；填充 ≥80% 绿，≥50% 琥珀，其余红；总数 0 显示 `—` |
| `ToolCallCard` | `rounded-md border-subtle bg-card`；默认折叠；参数 `pre max-h-40`，结果 `max-h-60` |
| `Composer` | `rounded-xl border bg-card p-2.5`，`focus-within:border-accent/50` + `shadow-input`；发送按钮 32×32 |
| `Dialog` | 遮罩 `bg-black/30 backdrop-blur-[2px]`（深色 `/55`），面板 `rounded-xl border bg-card p-5 shadow-dialog` |
| `DropdownMenu` | `rounded-lg border bg-popover p-1 shadow-popover`；项 `rounded-md px-2 py-1.5 text-[13px]`，hover `bg-hover`，图标统一灰 |
| `Tooltip` | `bg-primary px-2 py-1 rounded-md text-[12px] max-w-xs` |
| `ModeSelector` | 容器 `h-6 rounded bg-muted`，激活项 `bg-card shadow-xs` |
| `DownloadReportButton` | 页头 `outline sm` 带文案，表格行 `ghost icon-sm` 只留图标；导出中显示 `Loader2` + `导出中 3/18`，行内按钮须拦 `click` 与 `keydown` 冒泡 |

### 组件规则

- 整行可点击的表格，`onRowClick` 必须同时补 `tabIndex` 与 Enter / Space 响应。
- 长内容（工具参数、响应体、目录树）放 `max-h` 滚动容器，不靠换行撑高页面。
- 空态写清为什么空，不写「暂无数据」。加载态给骨架，错误态给重试。
- 工具栏顺序：影响本轮行为的选项在左，动作在右。

### 模式选择器文案

| 值 | 标签 | 文案 |
|---|---|---|
| `agent` | 执行 | 自动选择工具：查接口、发请求、评估断言并落盘 |
| `ask` | 问答 | 只回答问题，可用工具全为只读，不会发任何请求 |
| `plan` | 计划 | 只输出测试计划（接口范围 / 用例矩阵 / 断言策略 / 风险） |

三条文案对应后端工具白名单的真实边界，不允许改成「尽量不执行」这类模糊承诺。

---

## 七、页面骨架

| 路由 | 结构 |
|---|---|
| `/dashboard` | 页头 + 4 个指标卡（`grid-cols-2 lg:grid-cols-4`）+ 左侧「最近执行」列表占 2 列 + 右侧「快捷入口」「统计口径」 |
| `/spaces` | 页头 + 筛选行（搜索 320px、状态下拉、右侧创建）+ `DataTable` |
| `/spaces/:id` | 页头（空间名 + 状态 + 描述 + 开始对话）+ 7 个页签：概览 / 会话 / 接口 / 环境 / 记忆 / 知识库 / 执行记录 |
| `/spaces/:spaceId/chat` | 顶部空间栏 + 消息流 `max-w-3xl` 居中 + 底部 Composer |
| `/reports` | 页头 + 筛选行（空间、状态、右侧口径说明）+ `DataTable`，一行一次执行，整行点击进详情，行尾图标可单独导出 |
| `/reports/:runId` | 页头（含「下载报告」）+ `ReadoutBand` 6 格 + 逐条请求表，点行才拉正文 |
| `/runs/:id` | 页头 + `ReadoutBand` 6 格 + 工具调用留痕表，可选「加载全部正文」 |
| `/skills` | 页头 + 导入 / 刷新 + 技能卡片列表 + 详情侧栏 |

报告详情只统计 `send_request`（真的发出去了的 HTTP），执行详情统计整轮所有工具调用。两边成功率不是同一件事，口径说明跟着页面走。

---

## 八、主题

1. `localStorage["lta-theme"]` 存用户显式选择；没存过则跟随 `prefers-color-scheme`。
2. `index.html` 内联脚本在 React 挂载前读一次并加 `html.dark`，同时设 `backgroundColor` 与 `colorScheme`，避免刷新闪白。
3. `use-theme.ts` 负责切换、写回、监听系统偏好（仅在用户未显式选择时跟随）。
4. 联动：sonner Toaster 绑 `theme`；Shiki 靠 `html.dark .shiki span { color: var(--shiki-dark) }`；Mermaid 按 `theme` 选 `neutral` / `dark` 并重渲染。

字体、圆角、缓动放在 `@theme`，开关主题不动；只有颜色与阴影在 `html.dark` 下覆盖。

---

## 九、文案口径

- 成功率 = HTTP 2xx / 总请求数，不用 `ok` 字段。
- 异常 = 没拿到状态码的调用（网络错误 / 参数不合法 / 被网关拦截）。
- 仪表盘「近期成功率」取最近 8 次执行按调用次数加权，卡片底下必须写这句。
- 按钮与菜单用中文。保留英文的只有 `RUN` 列头、`Agent`、`Tokens`、HTTP 方法名、代码与 URL。

---

## 十、检查清单

- [ ] 无硬编码色值
- [ ] 容器靠描边分层，没靠阴影
- [ ] 圆角落在 4 / 6 / 8 / 12 里
- [ ] 页头用 `PageHeader`，返回按钮 `variant="ghost" size="sm"` 放 `actions` 第一位
- [ ] 统计区用 `ReadoutBand`，不是卡片套卡片
- [ ] 状态用 `StatusBadge`，方法用 `HttpMethodBadge`
- [ ] 导出文件按 HTTP 状态判成败，不认工具层 `ok`；不跟随应用主题，固定浅色底
- [ ] 浅蓝只落在交互态、强调元素、数据与标签；画布、卡片、侧栏、面板没有浅蓝底
- [ ] 数字加 `tabular-nums`
- [ ] 表格用 `DataTable`，整行可点时补了键盘支持
- [ ] 长内容在滚动容器里
- [ ] 空态写了原因，错误态有重试
- [ ] 工具调用有卡片，不是只给最终答案
- [ ] 浅色与深色都验过
- [ ] `tsc --noEmit`、`eslint`、`prettier --check`、`npm run build` 全过

---

## 十一、修订记录

| 日期 | 说明 |
|---|---|
| 2026-11-20 | v3.2：报告导出入口（页头 + 列表行尾），导出文件固定浅色、按 HTTP 状态判成败 |
| 2026-11-20 | v3.1：浅蓝作为调和色，落在交互态、强调元素、数据与标签三处；画布与卡片保持中性 |
| 2026-11-20 | v3.0：改为浅色 / 深色双主题令牌体系；单色主行动按钮；圆角 4/6/8/12；补尺寸、间距、组件与页面骨架规范 |
| 2026-11-04 | v2.0：补报告、报告详情、执行详情页面骨架与口径差异 |
| 2026-10-20 | v0.2.0：补模式选择器、技能选择器、工具调用卡片、上下文栏 |
