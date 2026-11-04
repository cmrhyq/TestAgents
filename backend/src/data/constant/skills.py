import re

# Skill 名称规范：小写字母/数字/连字符，不允许下划线与大写，长度 1-64
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# Skill 前言部分分隔符
SKILL_FRONTMATTER_DELIMITER = "---"