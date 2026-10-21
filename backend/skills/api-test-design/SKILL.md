---
name: api-test-design
description: 为一组接口设计可执行的测试场景矩阵，覆盖正向、异常、边界与依赖链路
when_to_use: 当用户要求为某组接口设计测试用例、设计测试计划、或问"这些接口该怎么测"时
version: 1.0.0
allowed_tools: [get_space_endpoints, get_endpoint_detail_by_id, read_file, list_directory, write_file, knowledge_search]
---

# 接口测试场景设计方法论

## 第一步：摸清被测对象

1. 调 `get_space_endpoints(space_id)` 拿到全量接口清单，注意 `response_summary` 字段——
   它揭示了接口之间的**数据依赖**（哪个接口产出的字段是另一个接口的入参）。
2. 对目标接口调 `get_endpoint_detail_by_id(space_id, endpoint_id)` 拿到完整定义：
   `params` / `body` / `responses` / `security`。
3. 如果空间里有需求文档，先 `knowledge_search` 查一遍业务规则——**不要凭空猜业务语义**。

## 第二步：划场景矩阵

每个接口至少覆盖以下几类，不要只写正向：

| 类型 | 说明 | 例子 |
|---|---|---|
| 正向 | 必填参数齐全、取值合法 | 正常登录 |
| 必填缺失 | 逐个去掉必填参数 | 不传 password |
| 类型错误 | 参数类型与 schema 不符 | page 传 "abc" |
| 边界值 | 长度/数值/枚举的边界 | 昵称 0 字符、1 字符、max+1 字符 |
| 鉴权 | 无 token / 过期 token / 越权 | 用 A 用户 token 访问 B 用户资源 |
| 幂等/重复 | 重复提交 | 同一订单重复支付 |

## 第三步：写断言（分两层）

**第一层（从 OpenAPI 推导，必须写）**
- HTTP 状态码 ∈ 该接口声明的 2xx 集合
- `responses` 中 `required` 列出的字段必须存在
- 字段类型与 schema 一致

**第二层（业务语义，酌情写）**
- 业务码（如 `$.code == 0`）
- 列表接口的分页字段一致性（`total >= len(items)`）
- 关键字段的取值范围（金额非负、余额不为负）

## 第四步：避开两个常见坑

**坑 1：对易变字段下断言。** 以下字段每次请求都不同，断死必然失败：
`traceId` / `requestId` / `timestamp` / `nonce` / `serverTime` / `expireTime`。
需要时只断言「存在」或「类型正确」，不要断具体值。

**坑 2：零断言用例。** 一条没有断言的用例即使请求成功也**不能算通过**——
它只会污染通过率。没有可写断言时，明确标注「仅做冒烟，需人工确认」。

## 输出格式

用 Markdown 表格输出用例矩阵，列固定为：

`编号 | 接口 | 场景类型 | 入参要点 | 断言 | 预期`

设计完成后，把结果写入空间工作目录的 `testcases/{日期}-{主题}.md`，
不要只在对话里说一遍——文件才是可复用的资产。
