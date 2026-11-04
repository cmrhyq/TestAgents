# 切片参数：800 字符约对应 400-600 个中文词；100 字符重叠避免答案被切断在边界
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# 知识库支持的文档最大大小 MB
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

# 知识库支持的文档文件类型
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".log", ".csv", ".sql", ".py"}

# 所支持的记忆分类
VALID_CATEGORIES = ("fact", "decision", "preference", "issue", "glossary")

# 记忆类别标题
CATEGORY_TITLES = {
    "decision": "决策",
    "preference": "偏好",
    "issue": "已知问题",
    "glossary": "术语",
    "fact": "事实",
}

# 召回默认条数：记忆过多会稀释提示词中的关键信息并挤占工具结果空间
DEFAULT_RECALL_LIMIT = 20
