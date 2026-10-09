# GitHub 发布报告

发布日期：2026-10-09（Asia/Shanghai）

## 仓库

- GitHub：<https://github.com/zhibo888/zhisaotong-agent-fastapi-rag>
- 可见性：Public
- 默认分支：`main`
- 本地来源远程：`upstream`（只读）
- 本地发布远程：`origin`

公开仓库使用单提交发布快照。提交身份采用 GitHub noreply 邮箱，不公开本机原有 QQ 邮箱；本地既有 `main` 历史继续保留，没有强制改写。

## 公开内容

- FastAPI：`/health`、`/api/v1/chat`、`/api/v1/rag/search` 与 Swagger。
- Streamlit：通过 HTTP 调用 FastAPI，保留聊天、工具轨迹、天气和样例报告。
- RAG：ChromaDB 共享检索函数、14 条草案评测数据、Hit/Recall/MRR@1/3/5、延迟和错误分析。
- 测试：78 项离线测试、10 项真实服务测试，合计 88 PASS、0 FAIL。
- 文档：README、架构、升级报告、真实页面截图和评测报告。

## 发布边界

- 未提交真实 `DASHSCOPE_API_KEY` 或 `AMAP_API_KEY`。
- 未提交 `.env`、日志、虚拟环境、本机 ChromaDB、`md5.text` 或本机临时文件。
- 未提交授权不明的上游 1 个 PDF 与 5 个 TXT；公开仓库只包含品牌无关演示知识文档。
- 保留上游项目链接、致谢和贡献边界，不把原始 Agent/RAG 架构声明为全新原创。
- 上游未提供可识别的独立 LICENSE，本仓库没有擅自新增许可证；使用者应自行核实再分发权利。

## 简历建议

项目名称可写为“智扫通智能客服 Agent 工程化升级”。描述自己的实际贡献：FastAPI 服务化、Streamlit HTTP 解耦、Pydantic 校验与错误脱敏、共享 Chroma 检索、RAG 系统化评测、自动化测试和真实集成验证。不要把上游基础代码写成个人从零原创。
