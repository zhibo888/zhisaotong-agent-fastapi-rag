# 智扫通完整功能测试报告

测试日期：2026-10-09（Asia/Shanghai）

## 结论

FastAPI/RAG 升级后的本机两阶段测试合计 **88 PASS、0 FAIL、0 ERROR、0 SKIPPED**：离线 78 项（12.97 秒），真实服务 10 项（24.12 秒）。

- 78 项离线测试：既有配置、工具、Agent、Chroma 与页面测试，加上 FastAPI 契约、HTTP 客户端和 RAG 指标测试。
- 10 项真实服务测试：DashScope 对话与 Embedding、FastAPI Agent/RAG、历史报告、缺省本月报告、多轮上下文、高德定位/天气/无效城市。

## 七项 Agent 工具

| 工具 | 结果 | 实际验证 |
|---|---|---|
| `rag_summarize` | PASS | Top-K=3，模型给出维修建议并列出知识库来源 |
| `get_weather` | PASS | 北京市实况含天气、温湿度、风力、发布时间；无效城市不编造 |
| `get_user_location` | PASS | 服务端出口 IP 近似定位，并明确不是浏览器 GPS |
| `get_user_id` | PASS | 固定返回演示用户 1001 |
| `get_current_month` | PASS | 返回服务器当前月份 2026-10 |
| `fetch_external_data` | PASS | 10 个用户、120 条记录逐条核对；缺失记录如实提示 |
| `fill_context_for_report` | PASS | 报告模式只对当前请求生效，不能绕过模式直接读取报告数据 |

## 页面验收

| 场景 | 结果 | 证据 |
|---|---|---|
| 知识库问答 | PASS | [01_rag.png](screenshots/full-functional/01_rag.png) |
| 多轮上下文 | PASS | [02_memory.png](screenshots/full-functional/02_memory.png) |
| 清空对话 | PASS | [03_clear.png](screenshots/full-functional/03_clear.png) |
| 历史样例报告 | PASS | [04_report.png](screenshots/full-functional/04_report.png) |
| 北京市真实天气 | PASS | [05_weather.png](screenshots/full-functional/05_weather.png) |
| 无效城市错误处理 | PASS | [06_invalid_city.png](screenshots/full-functional/06_invalid_city.png) |
| 缺省本月报告 | PASS | 自动和页面双重验证：依次调用报告模式、演示用户、当前月份、样例查询；无记录时没有挪用历史指标 |

FastAPI 升级后又在真实浏览器中确认 Swagger 的三个路由，以及 Streamlit 显示“FastAPI 后端已连接”并通过 HTTP 完成 `rag_summarize` 问答。

## RAG 系统评测

14 条草案问题对当前 330 向量本机索引执行完成，0 错误。结果为 Hit@1 0.2857、Hit@3 0.5000、Hit@5 0.5714，延迟 P50 140.77 ms、P95 378.31 ms。标签尚未人工复核，报告明确标记为 DRAFT；完整结果见 [RAG 检索评测报告](../reports/rag_evaluation/rag_evaluation_report.md)。

## 索引与依赖

- 本机 6 份上游文档与 1 份公开演示文档共 330 个向量、7 条 MD5 记录，三者一致；重复初始化不新增向量。
- 授权不明的 6 份上游知识文档由 `.gitignore` 排除；全新克隆只对公开演示文档建立索引。
- `pip check` 返回 `No broken requirements found`。
- Streamlit 健康端点返回 `ok`，服务已使用修正后的代码重启。
- 发布候选代码和文档未写入实际 DashScope 或高德 Key。

## 测试中发现并修复的问题

无效城市触发高德 `30001` 时，原提示把原因笼统写为“检查 Key 与服务权限”。该 Key 已能成功查询北京市，提示会误导排障。现在 `300xx` 单独显示为高德服务响应失败，建议检查城市名称或请求参数并稍后重试；其他拒绝类错误仍提示检查 Key 与权限。修复后完整测试全部通过。

## 边界

这些结果证明当前 Windows 环境中的项目功能、失败路径和外部服务集成可运行，不等同于生产负载、安全渗透、跨平台或模型回答准确率认证。设备报告来自本地样例 CSV，不是实时设备遥测。
