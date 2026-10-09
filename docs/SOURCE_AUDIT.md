# 首次源码审计（2026-10-08）

审计对象为用户提供的原项目目录，未重新下载、复制成新项目或更换架构。

| 模块 | 原始行为 / 问题 | 处理方向 |
|---|---|---|
| app.py | 只显示历史，未传入模型；取 response_messages[-1] 可能空列表；逐字 sleep | 传入历史、捕获异常、完整保存最终回答 |
| ReactAgent | stream_mode=values 将最后一条任意类型消息输出 | 只输出更新中的最终 AIMessage；工具名单单独展示 |
| 七项工具 | 随机 ID / 随机 2025 年月份；CSV split(',')；返回值与注解不符 | 固定演示身份、真实系统月份、DictReader 和 JSON 字符串 |
| 动态 Prompt | 可切换，但工具失败向外抛出，日志打印参数和消息正文 | 转为错误 ToolMessage；日志仅记录工具名、数量和异常类型 |
| 高德 | REST 调用，但 YAML 存 Key；公网 IP 辅助服务；错误可能含完整 URL | 只读 AMAP_API_KEY；直接高德出口 IP 定位；脱敏错误 |
| RAG | 导入即创建服务；打印全部 Prompt；没有自动初始化 | 延迟创建；显式 CLI 入库；空库提示；保留来源 |
| Chroma / MD5 | 6 条 MD5，实际向量为 0；随机向量 ID；异常后继续 | 先备份；依据实际 ID 检查、可重试入库、原子写记录 |
| 配置 | FullLoader，缺少参数校验；相对路径工具已正确锚定根目录 | safe_load、范围校验，保留原路径结构 |
| 依赖 | 清单与 rag_env 版本不同；缺少 pypdf 和 pytest | 先 dry-run、保留已安装版本、补缺失包 |
| README | OPENAI_API_KEY 与实际不符；REST 被称 MCP；宣称自动入库 | 按实际源码重写，写明样例和功能边界 |
| Git / 版权 | 当前不是 Git 仓库；无独立 LICENSE；README 有上游链接和致谢 | 保留出处，不推送、不自行宣称新许可 |

原始数据包括 1 个 PDF、5 个 TXT、一个 records.csv；全部保留在本机。
由于上游没有明确许可证，1 个 PDF 与 5 个 TXT 被排除在公开候选提交之外；公开候选改用独立编写的 `data/demo_knowledge.txt`。
源码与原始数据库、MD5、README 的本地备份位于 .local/backups/，不进入发布材料。
