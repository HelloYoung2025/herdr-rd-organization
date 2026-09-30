# Herdr R&D Organization

版本 v1.0.1。一个可复用的 Herdr 研发组织 Skill, 包含 Research、Orchestrator、Worker、独立 QA 与 Curator 的分工、通信、纠错和经验沉淀流程。

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
- [原样分享 ZIP](downloads/herdr-rd-organization-skill-20260930-v1.0.1.zip): SHA256 `d56b022024032bc4f2aff1b32a3ca73fbde35ceeffc07185966c405010b1a819`。
- [资源清单](skills/herdr-rd-organization/PACKAGE_MANIFEST.json): 23 个源文件的 SHA256。

最终版冷副本的 37 项测试全部通过, 零跳过。另有真实 Herdr 两个临时 Worker/QA pane 的有界通信及收尾验证, 不代表五角色完整科研验收、严格盲 QA、跨机器或其他 provider 已通过。

本仓库只发布可复用源码、模板与上述 ZIP, 不包含原项目日志、授权、账号凭据或实际运行 state。可以替代旧复制包的工具和模板, 历史证据与新项目验收仍需单独保留。项目内的目标、验收和授权不会因调用 Skill 自动变更。

自有资源的公开软件许可尚未选择; 第三方工具单独安装并遵守各自许可。
