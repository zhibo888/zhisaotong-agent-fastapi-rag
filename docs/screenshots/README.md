# 真实运行截图与界面验证

| 文件 | 状态 | 内容 |
|---|---|---|
| 01_home.png | PASS | 真实 Streamlit 首页与环境状态 |
| 02_rag_qa.png | PASS | 实际 rag_summarize 调用、知识库回答及来源 |
| 03_weather.png | PASS | 实际 get_weather 调用、北京市天气与高德数据发布时间 |
| 04_report.png | PASS | 用户 1001、2025-01 的真实模型样例报告核心区 |
| 05_fastapi_swagger.png | PASS | FastAPI Swagger 中的 health、chat、RAG search 三个路由 |
| 06_streamlit_fastapi.png | PASS | Streamlit 显示后端已连接，并经 FastAPI 完成真实 RAG 问答 |

均为实际软件界面截屏，未使用 AI 绘图或伪造页面数据。
演示 ID 来自原始 CSV，不代表登录认证身份。报告明确标注非实时设备遥测。

02_rag_qa.png 的提问：
“扫地机器人吸力变弱了怎么办？请依据知识库，用三条简短建议回答，并注明资料来源。”
页面显示来源为扫地机器人100问2.txt、扫拖一体机器人100问.txt、故障排除.txt。

03_weather.png 在配置 AMAP_API_KEY、重启应用后重新拍摄。页面显示北京市天气为霾、
17℃、湿度 68%、西风≤3级，数据发布时间为 2026-10-08 19:40:10。
这些数值仅代表该次接口返回，不代表之后的实时天气。
4 张截图均来自真实运行页面。02_rag_qa.png 的来源文件属于本机完整验证知识库；
授权不明的上游知识文档不会随公开候选提交分发，公开仓库提供独立演示知识文档。

2026-10-09 完成 FastAPI 升级后，再次通过真实浏览器验证：

- Swagger 页面显示 `GET /health`、`POST /api/v1/chat`、`POST /api/v1/rag/search`。
- Streamlit 侧栏显示“FastAPI 后端已连接”。
- 从 Streamlit 提交吸力变弱问题，页面显示 `rag_summarize` 工具和后端完整回答。

本目录中的 01–04 图片保留作为既有功能验收记录；05–06 是升级后通过真实浏览器捕获的页面，没有使用合成图。

截图不得包含 Key、真实用户私人资料或终端环境变量值。
