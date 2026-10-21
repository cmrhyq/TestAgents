# LLMTestAgent Frontend

LLMTestAgent 的 Web 前端，基于 React + TypeScript + Vite 构建。

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 6.x | 类型安全 |
| Vite | 8.x | 构建工具 & 开发服务器 |
| Tailwind CSS | 4.x | 原子化 CSS 框架 |
| shadcn/ui | latest | UI 组件库（按需复制） |
| ESLint | 10.x | 代码检查 |
| Prettier | 3.x | 代码格式化 |

## 环境要求

- Node.js >= 22
- npm >= 10

## 快速开始

```bash
# 安装依赖
cd frontend
npm install

# 启动开发服务器（默认 http://localhost:5173）
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

## 可用脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动 Vite 开发服务器（HMR） |
| `npm run build` | TypeScript 编译 + Vite 生产构建 |
| `npm run preview` | 预览生产构建结果 |
| `npm run lint` | ESLint 检查 |
| `npm run lint:fix` | ESLint 检查并自动修复 |
| `npm run format` | Prettier 格式化 |
| `npm run format:check` | Prettier 格式检查（不修改） |
| `npm run type-check` | TypeScript 类型检查（不生成文件） |

## 项目结构

```
frontend/
├── public/                 # 静态资源（直接复制到 dist/）
├── src/
│   ├── components/         # 业务组件
│   │   └── ui/             # shadcn/ui 组件（自动生成）
│   ├── hooks/              # 自定义 React Hooks
│   ├── lib/
│   │   └── utils.ts        # 工具函数（cn() 等）
│   ├── App.tsx             # 根组件
│   ├── main.tsx            # 应用入口
│   └── index.css           # Tailwind CSS 入口
├── components.json         # shadcn/ui 配置
├── eslint.config.js        # ESLint flat config
├── .prettierrc.json        # Prettier 配置
├── tsconfig.json           # TypeScript 项目引用配置
├── tsconfig.app.json       # 应用 TypeScript 配置
├── tsconfig.node.json      # Node 端 TypeScript 配置
├── vite.config.ts          # Vite 配置
└── package.json
```

## 添加 shadcn/ui 组件

项目已配置 shadcn/ui，可以按需添加组件：

```bash
# 添加按钮组件
npx shadcn@latest add button

# 添加对话框组件
npx shadcn@latest add dialog

# 添加表格组件
npx shadcn@latest add table
```

组件会自动生成到 `src/components/ui/` 目录，可直接导入使用。

## 路径别名

项目配置了 `@/` 路径别名指向 `src/`：

```typescript
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
```

## API 代理

开发模式下，`/api` 前缀的请求会自动代理到后端服务器 `http://localhost:8000`：

```typescript
// 实际请求 http://localhost:8000/api/v1/projects
const response = await fetch("/api/v1/projects");
```

确保后端服务已启动：

```bash
cd ../backend
uv run python app.py
```

## 代码规范

前端代码质量由根目录的 `.pre-commit-config.yaml` 统一管理：

- **ESLint**：TypeScript + React Hooks 规则
- **Prettier**：统一格式化（semi、双引号、2空格缩进）
- **TypeScript**：严格模式类型检查

提交代码时 pre-commit 会自动运行检查和修复。
