# Herdr R&D Organization

版本 v1.0.2。一个可复用的 Herdr 研发组织 Skill, 包含 Research、Orchestrator、Worker、独立 QA 与 Curator 的分工、通信、纠错和经验沉淀流程。

本版修复新建 pane 没有可见标题的问题: 创建时设置角色名和运行后缀, 启动 Agent 前后核对实际 label。命名失败会停止后续创建并保留记录。更新 Skill 不会自动改动已有窗口, 补名步骤见 quickstart。

## 使用

复制完整 `skills/herdr-rd-organization` 文件夹到客户端支持的 skill 目录, 保留 scripts、references、assets 的布局。在新会话确认客户端发现该 Skill, 再调用 `$herdr-rd-organization`。本机已验证 Codex 的 `~/.codex/skills`, 当前客户端文档也可能使用 `~/.agents/skills`。Grok 项目使用 `.grok/skills`。请只安装一份同名 Skill。

首次使用按需阅读 [quickstart](skills/herdr-rd-organization/references/quickstart.md), 并自行安装 Python、Herdr、Grok 及登录自己的账号。首版运行适配 Windows/Grok。

```text
使用 $herdr-rd-organization 为当前项目建立 Herdr 研发组织。
先读取项目规则, 确定目标、验收、范围和预算。
目标与验收由我决定, 保留主角色, 取证后关闭临时角色。
```

## 内容与验证

- [Skill 入口](skills/herdr-rd-organization/SKILL.md): 关键边界与按需文档入口。
- `scripts`: 初始化、运行身份、消息、回执、取证与临时角色收尾。
- `assets/templates`: 待填写角色和任务模板。
- [原样分享 ZIP](downloads/herdr-rd-organization-skill-20261001-v1.0.2.zip): SHA256 `e4b4d1caeeeb731c153b7635a3ea56fdfa2296b9d2e3abfb1cc0c968e9c19bd9`。
- [资源清单](skills/herdr-rd-organization/PACKAGE_MANIFEST.json): 23 个源文件的 SHA256。
- [上一版 v1.0.1](downloads/herdr-rd-organization-skill-20260930-v1.0.1.zip)保留以供撤回。

本版打包后冷副本的 41 项测试全部通过, 零跳过, Skill 格式验证通过。真实 Herdr 的两个临时 shell pane 已验证 Worker/Independent QA 标题与 pane/tab 身份, 随后关闭, 未启动 Agent 或发任务, 已有窗口标签未改变。五角色命名和 Agent 启动后丢失标题的情形由 fixtures 覆盖, 本次没有重新运行真实 Agent 启动。

此前 v1.0.1 另有真实 Herdr 两个临时 Worker/QA pane 的有界通信及收尾验证。上述证据不代表五角色完整科研验收、严格盲 QA、跨机器或其他 provider 已通过。

本仓库只发布可复用源码、模板与上述 ZIP, 不包含原项目日志、授权、账号凭据或实际运行 state。可以替代旧复制包的工具和模板, 历史证据与新项目验收仍需单独保留。项目内的目标、验收和授权不会因调用 Skill 自动变更。

自有资源的公开软件许可尚未选择; 第三方工具单独安装并遵守各自许可。
