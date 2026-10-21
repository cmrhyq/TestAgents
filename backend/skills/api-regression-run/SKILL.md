---
name: api-regression-run
description: 按依赖顺序真实调用接口，逐条断言并汇总结果，产出可复现的回归记录
when_to_use: 当用户要求"跑一遍""执行测试""验证这些接口是否正常"时
version: 1.0.0
allowed_tools: [get_space_endpoints, get_endpoint_detail_by_id, send_request, evaluate_assertions, extract_jsonpath, read_file, write_file, recall, remember]
---

# 接口回归执行流程

## 执行前：确认三件事

1. **环境**：确认 base_url 来自哪个环境。若环境被标记为生产环境，`send_request` 会被拦截——
   这时不要尝试绕过，直接告知用户切换环境。
2. **鉴权**：查 `recall("鉴权")` 看是否有历史记忆里存过 token 获取方式。
   没有就先调登录接口拿 token，用 `extract_jsonpath` 取出，后续请求带上。
3. **数据隔离**：写操作（POST/PUT/DELETE）一律使用带唯一后缀的测试数据，
   例如 `name = "autotest_${时间戳}"`，避免污染他人数据。

## 执行中：串行依赖，并行无依赖

- **有数据依赖的接口必须串行**：先创建 → 拿到 ID → 再查询/修改/删除。
  前一步失败时，后一步应当**跳过并标记 SKIP**，而不是硬跑出一条假失败。
- **无依赖的读接口可以连续调用**，但仍建议按清单顺序，便于对照排查。

每条用例的执行动作：

```
1. 拼 URL（环境 base_url + 接口 path）
2. send_request(...) 拿到 {status_code, response_time_ms, body}
3. evaluate_assertions(rules, body, status_code, response_time) 拿到断言明细
4. 记录：通过 / 失败 / 跳过 + 失败原因
```

## 执行后：汇总，不要只报通过率

汇总表必须包含：

| 指标 | 说明 |
|---|---|
| 总数 / 通过 / 失败 / 跳过 | 四项都要有，跳过不能隐含在通过里 |
| 失败清单 | 接口 + 断言规则 + 实际值 vs 期望值 |
| 耗时 Top 5 | 慢接口往往是性能问题的信号 |

**最重要的一条规则**：如果失败是「环境不可达」「鉴权拿不到」这类**前置问题**，
必须明确说明「本次测试无效」，不能产出一个「通过率 92%」的假报告。

## 产出

1. 汇总表直接回复给用户
2. 完整结果写入 `artifacts/{日期}-{主题}-regression.md`
3. 若发现了值得长期记住的结论（如「某个接口在 dev 环境一直返回 502」），
   调用 `remember` 写入记忆，下次不用重复踩坑
