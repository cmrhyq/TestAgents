# prompt 总长上限：过长会推高成本，并削弱模型对中段内容的注意力
AGENT_MAX_PROMPT_CHARS = 12_000

# 单条记忆的上限，避免单条超长记忆占满预算
AGENT_MAX_MEMORY_CHARS = 3_000

# 单个工具结果下发的字符上限，避免大响应体拖慢前端渲染
AGENT_MAX_TOOL_RESULT_CHARS = 4_000

# 默认模式的最大工具调用轮次。兜住模型陷入死循环的情况。
AGENT_DEFAULT_MAX_STEPS = 100

# 计划模式只需要读信息 + 输出计划，轮次更少
AGENT_PLAN_MAX_STEPS = 80

# 唯一会落 HTTP 请求/响应列的工具体（见 ``agent_run_recorder._extract_http``）
HTTP_TOOL_NAME = "send_request"

# Agent Run 清理时每批处理的执行记录条数
DEFAULT_BATCH_SIZE = 500

# 注入 LLM 的历史消息条数上限，同时控制 token 成本与超长上下文带来的指令漂移
MAX_HISTORY_MESSAGES = 20

# 空间约定文件与记忆镜像的路径，相对空间根目录
AGENTS_FILE = "AGENTS.md"
MEMORY_FILE = "memory/MEMORY.md"
