# GitHub 发布准备

- 推荐名称：`zhisaotong-agent`
- 推荐简介：基于 LangChain、RAG 与 ChromaDB 的智能客服 Agent 系统，支持知识库检索、外部 API 工具调用及设备使用报告生成。
- 当前目录已初始化本地 Git，分支为 `main`，首次源码提交已完成；保留上游地址为 `upstream`，尚未配置 `origin`、创建公开仓库或 push。
- .gitignore 排除密钥文件、日志、向量库、MD5、IDE 配置、本地备份和本机复现报告。
- .env.example 仅列出环境变量名称，不会被程序自动加载。
- records.csv 为 10 个演示 ID、120 条合成样例；展示时明确非实时设备遥测，未加入真实个人信息。
- 上游 1 个 PDF 与 5 个 TXT 没有明确再分发许可证，保留在本机并由 `.gitignore` 排除；公开候选仅包含独立演示知识文档。
- README 图片来自真实界面；高德 Key 配置后已补测 IP、城市和天气服务，天气截图已更新为真实查询结果。
- 发布前核对 [来源说明](ATTRIBUTION.md)；当前未找到独立 LICENSE。
- 运行和安装命令使用项目相对路径；本机绝对路径只记录在被忽略的 PROJECT_REPRODUCTION_REPORT.md 中。

本地提交完成后，必须确认目标账户、仓库名称、Public 权限与 push 授权；不要使用强制添加把忽略文件提交进去。
