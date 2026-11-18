"""接口标签的约束常量。

标签以 JSON 数组字符串存在 ``endpoint.tags`` 列中，写入前由
``src.data.schemas.endpoint.normalize_tags`` 归一化。这里的上限同时约束
API 入参与 OpenAPI 导入，避免同一份文档导入后因超长标签被拒。
"""

# 单个标签的最大字符数
TAG_MAX_LENGTH = 32

# 单个接口最多允许的标签数量
TAG_MAX_COUNT = 10

# 标签中禁止出现的字符。
# 双引号会破坏以 ``"标签"`` 为边界的 LIKE 精确匹配，反斜杠会破坏 ESCAPE 转义；
# 二者的共同点是都无法在不引入歧义的前提下参与 JSON 数组的字符串匹配。
TAG_FORBIDDEN_CHARS = ('"', "\\")
