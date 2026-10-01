# Herdr R&D Organization

版本 v1.0.4。一个可复用的 Herdr 研发组织 Skill, 包含 Research、Orchestrator、Worker、独立 QA 与 Curator 的分工、通信、纠错和经验沉淀流程。

本版修补对抗式试用发现的创建身份、批量回收、并发回执与历史状态查询缺口。新 pane 的 workspace/tab/身份核验失败时停止，回收前核对最后观察到的完整身份。等待投递响应时释放状态锁；原始响应先留证，锁竞争后用同一消息补齐状态而不重复派工。任务引用绑定文件 hash，项目方法试用有明确终点。首次调用绑定与可见 pane 标题继续保留，具体步骤见 quickstart。

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
- [原样分享 ZIP](downloads/herdr-rd-organization-skill-20261001-v1.0.4.zip): SHA256 `50c2eccdac584c26efe9458ad5a3c94307a16ccc664e238e3cb752b06d8bccd4`。
- [资源清单](skills/herdr-rd-organization/PACKAGE_MANIFEST.json): 25 个源文件的 SHA256。
- [上一版 v1.0.1](downloads/herdr-rd-organization-skill-20260930-v1.0.1.zip)保留以供撤回。

本版由六组智能体分三轮模拟不同使用者与故障条件，并交叉复测。最终候选的 79 项回归全部通过、零跳过，Skill 格式验证通过。测试区分错误 API 返回、真实本地 CLI 子进程与真实 Herdr：在隔离 shell 会话中的四种原生入口场景通过，包括跨会话相同 ID、分屏和移动 pane；测试会话已清理。并发回执、慢速取证锁竞争与响应调和使用 fake transport 和真实本地子进程验证，没有新模型调用。

引用 hash 和有限试用边界是角色核查规则，运行器不强制业务授权或文件隔离。进程硬中断、嵌套模型会话身份、自动审批、五角色自主科研闭环及跨机器仍需要相应真实验证。不能据此宣称无人值守生产验收完成。

v1.0.2 已另行验证两个临时 shell pane 的 Worker/Independent QA 标题与身份, 随后关闭; 未启动 Agent。五角色命名和启动后标题丢失由 fixtures 覆盖。

此前 v1.0.1 另有真实 Herdr 两个临时 Worker/QA pane 的有界通信及收尾验证。上述证据不代表五角色完整科研验收、严格盲 QA、跨机器或其他 provider 已通过。

本仓库只发布可复用源码、模板与上述 ZIP, 不包含原项目日志、授权、账号凭据或实际运行 state。可以替代旧复制包的工具和模板, 历史证据与新项目验收仍需单独保留。项目内的目标、验收和授权不会因调用 Skill 自动变更。

自有资源的公开软件许可尚未选择; 第三方工具单独安装并遵守各自许可。
