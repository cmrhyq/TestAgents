# 贡献指南

我们非常欢迎并感谢您对本项目的贡献！

在您开始贡献之前，请花点时间阅读以下指导方针：

## 报告 Bug

* 在提交新的 Bug 报告之前，请**搜索**现有的 Issues，以确保该问题尚未被报告。
* 请提供清晰、简洁的标题。
* 在描述中，请提供重现该 Bug 的**完整步骤**、您的**操作系统**和**环境信息**。

## 提交新功能建议

* 在提交新功能建议之前，请**搜索**现有的 Issues。
* 请提供清晰、简洁的标题。
* 详细描述您希望添加的功能，以及它将如何解决现有的问题或带来价值。

## 开发环境配置

```bash
git clone https://github.com/cmrhyq/LLMTestAgent.git
cd LLMTestAgent

# 后端依赖
cd backend && uv sync --extra dev && cd ..

# 前端依赖
cd frontend && npm install && cd ..

# 安装 pre-commit hooks
cd backend && uv run pre-commit install && cd ..
```

## 提交代码更改 (Pull Request)

1. **Fork** 本仓库到您自己的 GitHub 账户。
2. 从 `main` 分支创建一个新的**分支**。
3. 在新分支上进行您的修改。
4. 确保代码通过 lint 检查（pre-commit hooks 会自动运行）。
5. 在提交时，请编写清晰、描述性的**提交信息**。
6. 提交 Pull Request (PR) 到本仓库的 `main` 分支。
7. 在 PR 描述中，清楚地说明您的更改内容和原因，并链接到相关的 Issue（例如：`Closes #123`）。

## 项目结构

```
LLMTestAgent/
├── backend/      # Python 后端（FastAPI + 手写 ReAct 运行时）
├── frontend/     # React 前端（Vite + Tailwind + shadcn/ui）
├── doc/          # 项目文档（架构 / 数据库 / 流程图 / 设计准则）
└── .github/      # CI 工作流
```

- 后端代码修改在 `backend/` 目录下进行
- 前端代码修改在 `frontend/` 目录下进行
- 根目录的 `.pre-commit-config.yaml` 统管前后端 lint

### 关键目录速查

| 改动内容 | 目录 |
|---|---|
| Agent 工具 / 模式白名单 / ReAct 循环 | `backend/src/agent/` |
| 空间沙箱与目录模板 | `backend/src/workspace/` |
| 技能解析与导入 | `backend/src/skill/`、`backend/skills/` |
| 记忆与知识库 | `backend/src/memory/` |
| 路由 / 服务 / 模型 | `backend/src/api/v1/`、`backend/src/data/` |
| 前端页面与 hook | `frontend/src/pages/`、`frontend/src/hooks/` |

### 提交前自检

```bash
cd backend && uv run pytest
cd frontend && npm run type-check && npm run lint && npm run build
```

> 若新增或改名了工具，请同步检查 `backend/skills/*/SKILL.md` 里的 `allowed_tools` ——
> 声明了不存在的工具**不会报错**，只会让那个工具被静默裁掉。`tests/agent/test_skill_tool_contract.py` 会拦这个。

感谢您的贡献！
