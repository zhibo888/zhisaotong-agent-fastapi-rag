# 验证记录（2026-10-09，扩展验收）

## 结论

在指定的 Windows / Python 3.13.0 环境中，核心应用已达到本机可运行、可复现、可展示标准。
FastAPI/RAG 升级后的两阶段测试合计 **88 PASS、0 FAIL、0 SKIPPED**：
离线 78 PASS（12.97 秒），真实服务 10 PASS（24.12 秒）。分开执行真实套件以避免重复产生模型费用。
用户已配置 AMAP_API_KEY；从用户环境加载到测试进程并重启应用后，高德真实联网验证通过。

这不是跨平台、生产负载或回答准确率评测；不将样例 CSV 声称为实时设备数据。

## 最终测试结果

| 检查 | 状态 | 证据 |
|---|---|---|
| 指定 Python / pip | PASS | Python 3.13.0，原 rag_env |
| pip check | PASS | No broken requirements found |
| 依赖 dry-run | PASS | 当前包满足 requirements-dev.txt，未升级已有 Python 包 |
| 静态语法 / 核心模块导入 / Agent 初始化 | PASS | compileall，七项工具注册成功 |
| 离线自动化测试 | PASS | 78 个用例通过 |
| FastAPI 契约 | PASS | health、chat、RAG search、422 校验、503 脱敏与请求隔离 |
| Streamlit HTTP 边界 | PASS | 后端健康状态、成功回答、失败恢复、不写入伪造助手错误 |
| RAG 指标单元测试 | PASS | 首位/次位/无相关/多相关/重复/空结果/K 超界/非法标签 |
| 原生 Chroma 持久化与 MD5 去重 | PASS | 在子进程中使用真实 Chroma 临时库 |
| 部分写入失败后恢复 | PASS | 第 2 批模拟 Embedding 失败，再次运行补全，不新增重复 ID |
| PDF/TXT 实际读取与分块 | PASS | 本机 6 份上游文档为 326 个片段；公开演示 TXT 为 4 个片段 |
| 真实知识库初始化 | PASS | 公开演示文档新增 4 个向量，本机索引合计 330 |
| 重复初始化 | PASS | 已有文档新增 0 个向量，数量保持 330 |
| 文档 / MD5 / 索引一致性 | PASS | 本机 7 个文件摘要与 ledger、向量 metadata 完全一致 |
| DashScope 对话 | PASS | 真实 qwen3-max 响应 |
| DashScope Embedding | PASS | 真实 text-embedding-v4 返回 1024 维 |
| 真实 Top-K 检索 | PASS | k=3，问题“扫地机器人吸力变弱了怎么办”，返回包含吸力相关内容 |
| 真实 FastAPI Agent RAG | PASS | `/api/v1/rag/search` 返回 3 条真实结果；`/api/v1/chat` 调用 rag_summarize 并返回答案 |
| 真实 Agent 报告 | PASS | fill_context_for_report → fetch_external_data，包含样例记录中的 85% |
| 缺省报告参数 | PASS | 真实调用演示用户、当前月份和数据查询；无记录时不换月、不编造指标 |
| 不存在用户 / 不存在城市 | PASS | 如实返回无记录或高德服务失败，不生成虚假报告或天气 |
| 全量样例 CSV | PASS | 10 个用户、120 条用户月份记录逐条读取并核对字段 |
| 高德 IP / 城市解析 / 天气联网 | PASS | 真实调用三个 REST 接口；北京市天气含数据发布时间 |
| 高德 Mock 与失败处理 | PASS | 参数、HTTP/网络/JSON/API 错误及脱敏 |
| Streamlit HTTP 健康检查 | PASS | /_stcore/health 返回 ok |
| 浏览器首页与输入 | PASS | 新版页面显示 FastAPI 已连接并可提交问题 |
| 浏览器 Swagger | PASS | 三个路由及 Schema 可见；在 Swagger 执行 `/health` 返回 HTTP 200 与正确 JSON |
| 浏览器 RAG | PASS | 实际模型回答并列出 3 个知识库来源；02_rag_qa.png |
| 浏览器报告 | PASS | 实际样例报告明确标注本地 CSV、非实时遥测 |
| 浏览器同会话上下文 | PASS | 第二轮正确回答上一轮询问的城市“北京市” |
| 浏览器清空与会话隔离 | PASS | 清空后欢迎页恢复；独立会话不共享历史 |
| 浏览器实时天气 | PASS | 实际调用 get_weather，显示北京市天气、气温、湿度、风力和高德发布时间 |
| 自动化页面正常与异常路径 | PASS | Streamlit AppTest，Mock 模型，仅算离线验证 |
| 文档与发布候选文件检查 | PASS | 相对链接全部有效，4 张截图存在，未检出真实 Key 或机器专属路径 |
| Git 远程发布 | SKIPPED | 保留既有本地仓库与提交；本次改动未提交、未 push、未建立公开仓库 |

七项工具均有接口或功能测试。Mock 通过不计作真实联网通过。
索引证据在 [index-summary.json](test-results/index-summary.json)，汇总见
[full-functional-summary.json](test-results/full-functional-summary.json)，完整说明见
[完整功能测试报告](FULL_FUNCTIONAL_TEST_REPORT.md)。本机 JUnit 证据在
docs/test-results/full-functional.xml（含机器路径，已忽略）。

## 实际执行命令

所有 Python 命令均通过指定解释器运行；下列写法便于其他开发者复现：

```powershell
python -m pip check
python -m compileall -q app.py api agent rag model scripts utils tests
python -m pytest -q tests/test_core.py -k native_index
# 停止应用后执行入库，避免同时维护同一个索引
python -m rag.vector_store
$env:RUN_LIVE_TESTS = "1"
python -m pytest -q -m "not live"
python -m pytest -q -m live
Remove-Item Env:RUN_LIVE_TESTS
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

默认不设置 RUN_LIVE_TESTS 时，10 个真实服务用例均跳过。
full-functional.xml 是最新验收依据；final.xml、offline.xml、live-rag.xml 等先前文件保留历史结果，不代表当前状态。

## Windows 原生故障及恢复记录

1. 初始 Chroma 写入崩溃，退出码 3221225477 / 0xC0000005；独立临时库和单线程配置也失败。
2. 当时实际加载的 MSVCP140.dll 为 14.00.24215.1。
3. 使用微软官方安装包，签名验证为 Valid / Microsoft Corporation；用户完成 Windows 管理员授权。
4. 运行库更新到 **14.51.36247.0** 后，原生持久化、去重、部分失败恢复、真实入库和查询全部通过。
5. Python 与 Chroma/LangChain 包版本没有更换。复测支持旧 C++ 运行库与该原生故障有关。
6. 安装器返回 **3010（0xbc2，需重启）**，未自动重启 Windows。新启动的 Python 已通过全部相关测试；
   用户可在方便时重启系统以完成运行库维护，并重新启动应用。

同类现象参考 [Chroma 官方仓库问题 #6052](https://github.com/chroma-core/chroma/issues/6052)；
官方安装来源：[微软 C++ 运行库文档](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist/)。

## 历史问题的诚实记录

- 原依赖镜像 TLS 失败，切换官方 PyPI 后只新增 pypdf、pytest、iniconfig、pluggy。
- 原始完整离线测试为 31 PASS / 2 FAIL，真实服务为 3 PASS / 2 FAIL / 1 SKIPPED；
  运行库更新和真实入库后为 38 PASS / 1 SKIPPED；补齐高德 Key 并重启后最终为 39 PASS / 0 SKIPPED。
- 扩展测试首次为 55 PASS / 1 FAIL：无效城市触发高德 30001 时，程序把原因笼统归为 Key/权限；
  已按高德 300xx 引擎响应失败单独提示城市名称、请求参数和重试，复测为 59 PASS / 0 FAIL / 0 SKIPPED。
- 初版 RAG 测试只看“调用工具 + 关键词”，可能误把失败后的普通回答判作成功；
  已加强为真实非空索引、实际 RAG 工具返回来源和最终回答的联合验证。
- 首次页面连接曾早于服务启动；健康检查通过后浏览器成功访问。
- 原数据库为空却有 6 条 MD5，先备份后按真实向量恢复一致性；没有删除原始数据库或知识库文档。
