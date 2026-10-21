"""空间工作目录的初始文件模板。

每个新建空间会得到一套「开箱可用」的骨架文件：
- ``AGENTS.md``：空间级智能体指令，用户可直接编辑，会注入 system prompt
- ``memory/MEMORY.md``：跨会话记忆镜像（由 DB 渲染，只读）
- ``docs/README.md``：说明往哪里放需求/接口文档（知识库源目录）

模板用 ``str.format`` 占位，只暴露少量变量，避免模板里出现意外的花括号报错。
"""

from __future__ import annotations

AGENTS_MD_TEMPLATE = """# {space_name}

> 空间 ID：`{space_id}`
> 本文件会被拼进 Agent 的 system prompt，是「这个空间的长期约定」。
> 直接编辑即可生效，下一轮对话就会读到；不需要重启服务。

## 被测系统

- 名称：{space_name}
- 接口数量：{endpoint_count}
- 环境：{environment_summary}

## 测试约定

<!-- 在这里写这个空间特有的测试要求，例如： -->
<!-- - 所有写操作接口必须使用测试账号 test_user / Test@123 -->
<!-- - 响应体统一结构为 {{code, message, data}}，断言优先断 code -->
<!-- - 不允许调用 /admin/** 下的接口 -->

## 已知问题

<!-- 记录已知的、不要重复报告的缺陷 -->
"""

MEMORY_MD_TEMPLATE = """# 空间记忆

> 本文件由系统根据记忆库自动生成，**手改会被覆盖**。
> 要增删改记忆，请在前端「记忆」面板操作，或调用记忆 API。
> 最后更新：暂无

_（尚无记忆条目）_
"""

DOCS_README_TEMPLATE = """# 知识库目录

把**需求文档、接口文档、业务规则、历史缺陷单**放在这个目录下。

上传后系统会自动切片并建立索引，Agent 在对话中可通过语义检索查到相关内容。

支持格式：`.md` `.txt` `.json` `.yaml` `.pdf`
"""

GITKEEP = ""
