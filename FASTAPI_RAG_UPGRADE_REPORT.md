# FastAPI 与 RAG 评测升级报告

日期：2026-10-09（Asia/Shanghai）

公开仓库：<https://github.com/zhibo888/zhisaotong-agent-fastapi-rag>

## 完成结果

本次在原项目目录内完成升级，没有复制或重建仓库，没有删除或重建现有 `chroma_db/` 与 `md5.text`，没有执行 Git push。

- 新增 FastAPI 后端和 OpenAPI/Swagger 文档。
- Streamlit 改为 HTTP 调用 FastAPI，不再直接创建 Agent。
- Agent、RAG 调试接口与评测器共用 `VectorStoreService.search`。
- 新增可校验的 JSONL 评测集、Hit/Recall/MRR@1/3/5、延迟与错误统计。
- 新增 API、前端 HTTP 边界和 RAG 指标测试。
- 更新 README、架构说明、环境变量示例与评测报告。

## 请求链路

```text
浏览器 → Streamlit → POST /api/v1/chat → FastAPI 服务层
       → ReactAgent → 工具 → RAG/高德/样例 CSV → 完整 JSON 响应
```

后端接口：

| 接口 | 行为 |
|---|---|
| `GET /health` | 只返回存活状态，不初始化模型 |
| `POST /api/v1/chat` | 接收问题与会话历史，返回回答和工具名称 |
| `POST /api/v1/rag/search` | 返回 Top-K 片段、来源、元数据与 distance |

输入使用 Pydantic 严格校验：拒绝额外字段、空白问题、非法角色、超过 20 条的历史、超过 16000 字符的历史和超出 1–20 的 `top_k`。服务异常只返回固定中文提示，日志只记录异常类型，避免输出 Key、URL 参数或远端正文。

## 评测设计

当前公开演示知识包含 7 个主题，无法诚实支撑 30–50 个独立问题，因此提供 14 条草案样本，每个主题两条。所有标签是 `draft`；默认评测排除草案并标记 `PENDING`，只有显式传入 `--include-draft` 才生成探索性 `DRAFT` 结果。

相关性按来源文档标注。K 按 Chroma 返回的原始切片位置计算；同一来源的重复切片不会重复增加 Recall。MRR 使用第一个相关切片的倒数排名。空结果、无相关结果、多相关来源、重复来源、K 大于结果数和非法标签都有单元测试。

本机探索性结果：

| K | Hit@K | Recall@K | MRR@K |
|---:|---:|---:|---:|
| 1 | 0.2857 | 0.2857 | 0.2857 |
| 3 | 0.5000 | 0.5000 | 0.3690 |
| 5 | 0.5714 | 0.5714 | 0.3833 |

- 查询：14；错误：0。
- P50：140.77 ms；P95：378.31 ms。
- 索引：330 个向量，签名 `ee94189fffe9d7b3`。
- 本机索引包含公开演示文档和 6 份本地旧资料。旧资料与演示文档存在来源竞争，因此该结果适合定位检索问题，不能作为公开知识库的正式质量结论。

输出位于 `reports/rag_evaluation/`：

- `summary.json`：机器可读汇总、逐题结果、索引配置和来源清单。
- `query_results.csv`：逐题排名、distance、延迟和错误。
- `rag_evaluation_report.md`：人类可读摘要。
- `metrics.svg`：从真实汇总数值生成的指标图。
- `answer_review_template.csv`：前 14 个问题的正确性、证据支持、无依据内容和完整性人工评分空表。
- `answer_review_guide.md`：0/1/2 三档评分规则，覆盖正确性、证据支持、无依据内容和完整性。

## 运行方法

```powershell
# 后端
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# 前端（另一个终端）
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

# 草案检索评测
python -m scripts.evaluate_rag --include-draft
```

Swagger 位于 <http://127.0.0.1:8000/docs>。本次已在真实浏览器中确认三个路由可见，并从 Swagger 执行 `/health` 得到 HTTP 200 和正确 JSON；随后通过新版 Streamlit 完成一次真实 RAG 问答，页面显示 FastAPI 已连接、调用工具 `rag_summarize` 和最终回答。真实截图为 `docs/screenshots/05_fastapi_swagger.png` 与 `docs/screenshots/06_streamlit_fastapi.png`。

## 测试与限制

最终两阶段测试合计 **88 PASS、0 FAIL、0 ERROR、0 SKIPPED**：离线 78 项（12.97 秒），真实服务 10 项（24.12 秒）。`pip check` 返回 `No broken requirements found`，全项目 `compileall` 通过。真实套件包括 FastAPI 的 RAG 检索与 Agent 对话、DashScope 对话/Embedding、高德定位/天气、报告和多轮上下文。

当前 API 是本地开发服务，没有身份认证、HTTPS、速率限制、分布式任务队列或多进程模型生命周期管理。服务层使用进程内单例缓存模型与向量库；请求历史和报告状态仍按每次调用传递，没有新增跨用户共享会话状态。部署到公网前必须增加认证、TLS、限流、审计和并发容量测试。

## 文件清单

- 新增：`api/`、`rag/evaluation/`、`scripts/evaluate_rag.py`、`data/evaluation/rag_eval.jsonl`、`tests/test_api.py`、`tests/test_rag_evaluation.py`、`reports/rag_evaluation/`。
- 修改：`app.py`、`rag/vector_store.py`、`rag/rag_service.py`、`tests/test_core.py`、`tests/test_functional.py`、`tests/test_live.py`、`README.md`、`docs/architecture.md`、`.env.example`、`requirements.txt`。

## GitHub 展示文档

README 已加入 FastAPI 设计、接口清单、双终端启动、评测方法、真实 Baseline 数值和两张新截图。`docs/architecture.md` 已加入 HTTP 服务层、共享检索路径和独立评测模块。`docs/screenshots/05_fastapi_swagger.png` 与 `06_streamlit_fastapi.png` 均来自本次真实运行页面，指标图由评测脚本根据真实结果生成。

## 尚未解决的问题

- 14 条相关性标签仍是 `draft`，需要人工核对后才能成为正式评测集。
- 本机索引混合公开演示资料与 6 份本地旧资料；正式公开基线应在仅包含可公开资料的独立索引上复测。
- API 只适用于本地开发，没有登录、TLS、限流、审计或生产并发验证。
- 当前仍使用 `langchain-community` 的 DashScope 集成并产生弃用提示，迁移要单独验证兼容性。
- 尚无稳定 chunk ID 级人工标签，因此只能报告文档级检索指标。

## 后续 Rerank 对比方法

保留本次 JSONL、索引签名、分块参数和 K=1/3/5 作为 Baseline。加入 Rerank 时先取得同一批候选，再只改变排序阶段；输出独立目录并比较同一问题的排名变化、Hit/Recall/MRR、延迟和错误。若数据或索引版本变化，应建立新 Baseline，不能把两种配置直接解释为 Rerank 提升。

## 可写入 AI Agent 实习简历的真实技术亮点

- 将 Streamlit 内嵌 Agent 改造成 Streamlit → FastAPI → LangChain Agent 的分层调用，使用 Pydantic 限制输入并实现异常脱敏。
- 复用现有 ReAct Agent、7 项工具和动态 Prompt，通过回调返回真实工具轨迹，没有重写业务流程。
- 为 ChromaDB 建立共享检索接口和文档级 Hit/Recall/MRR@1/3/5 评测，覆盖重复来源、空结果和多相关标签。
- 构建 14 条可追溯的草案数据，保存参考答案、证据、逐题结果、延迟分位数和人工 0/1/2 评分模板。
- 使用 78 项离线测试和 10 项真实集成测试验证 API、RAG、模型、高德、报告、多轮上下文和浏览器端完整链路。
