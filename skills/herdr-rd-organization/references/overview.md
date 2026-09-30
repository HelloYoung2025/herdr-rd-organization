# 工作流与资源入口

此 skill 用 Herdr 建立 Research Engineer, Engineering Orchestrator, Worker, 独立 QA 和 Curator 的项目研发组织。它提供角色契约, 可替换任务资料, 初始化脚本和运行程序。用户冻结目标与验收; Research 调整方法; Orchestrator 派工和汇总真实证据。

资源随 skill 一起使用, 不依赖另一个复制包或原实验目录。SKILL_ROOT 指实际安装目录, 其中应有 SKILL.md, scripts, references 和 assets。路径示例必须换成接收者实际位置。

## 按任务读取

- 初次使用或换项目: 读 [quickstart.md](quickstart.md), 用 [init_project.py](../scripts/init_project.py)生成项目内配置与资料副本。
- 拆分职责, 纠错, 方法试用或暂停: 读 [organization.md](organization.md)。
- 判断已验证能力, 嵌套会话问题或分享范围: 读 [portability.md](portability.md)。
- 运行接口: [herdr_lab.py](../scripts/runtime/herdr_lab.py)。本地合成检查: [test_herdr_lab.py](../scripts/fixtures/test_herdr_lab.py)。 归档回归: [test_message_archive.py](../scripts/fixtures/test_message_archive.py), 使用 --test-root 指向skill 安装目录之外的测试目录。

## 可生成的资料

| 资源 | 用途 |
| --- | --- |
| [配置模板](../assets/templates/config.example.json) | 项目路径, state_dir, session/workspace, provider, model, effort, role 和启动参数 |
| [Research 首条任务](../assets/templates/research-task.example.json) | 给出实际课题, 冻结验收和范围, 要求真实研究方案 |
| [Orchestrator 接收方案任务](../assets/templates/orchestrator-task.example.json) | 将实际方案及其回执交给总指挥, 路由 Worker/QA/Research/Curator |
| [通用任务](../assets/templates/task.example.json) | 有界 Worker 任务, 具体交付, QA, 预算和 rollback |
| [结果模板](../assets/templates/result.example.json) | 准确版本, 命令, 产物, 失败, 跳过项和未知 |
| [回执模板](../assets/templates/receipt.example.json) | received/started/completed/failed 的真实身份与证据 |
| [经验候选](../assets/templates/experience.example.json) | 来源, 适用条件, 独立核查, 有限试用, 反例与撤回 |

角色模板位于 [Research](../assets/templates/roles/research-engineer.md), [Orchestrator](../assets/templates/roles/orchestrator.md), [Worker](../assets/templates/roles/worker.md), [QA](../assets/templates/roles/qa.md)和 [Curator](../assets/templates/roles/curator.md)。初始化生成的副本供当前项目使用, 不直接改共享模板。

## 使用范围

首版适配 Windows/Grok/Herdr 0.9.1。项目既有 AGENTS.md, CLAUDE.md, 工作树门禁和状态所有权优先。已有用户授权继续有效; skill 被选择或资料被复制不会扩大操作范围。

start 只创建角色, 不自动开始科研。必须先 send Research 首条任务, 收真实研究方案与回执, 再 send Orchestrator 的接收任务。此工作流还需要实际审批核对, 真实回执和独立 QA, 不是完整无人值守系统。

共享 OS 账户下的职责约定没有文件访问硬隔离。pause 只阻止此 wrapper 后续派工。原实验的授权, pane/session 身份, 运行日志和结论不会随 skill 转移到新项目。
