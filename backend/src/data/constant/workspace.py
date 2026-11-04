# 目录树与文件遍历时跳过的噪音目录
WORKSPACE_SKIP_DIRS = frozenset({"__pycache__", ".git", ".idea", ".mypy_cache", ".pytest_cache", ".ruff_cache", "node_modules"})

# 归档目录前缀：删除空间时只改名保留现场
WORKSPACE_ARCHIVE_PREFIX = ".deleted-"