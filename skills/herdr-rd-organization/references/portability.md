# 能力与可移植边界

此 skill 提供可移植的组织契约和启动资料, 不保证任意项目免配置运行。首版适配 Windows/Grok/Herdr 0.9.1。换机器, 项目, provider, CLI, 模型或 effort 后重新预检, 再验一个有界真实任务。

## 已有证据的范围

原本机 Windows 的新 project_root 用 Herdr 0.9.1, 模型 grok-4.5, effort low 和 permission-mode default 完成两名临时 Worker/QA 的有界 helper 通信示例。helper 由操作者提供, 验证身份, 通信和运行规则, 不能当作 QA 自主设计验收或新项目五角色完整研发闭环。

| 能力 | 已有证据与限制 |
| --- | --- |
| 预检与计划 | 本机已验, 不创建 pane 或写运行 state |
| 角色身份与启动配置 | 新 Worker/QA 的显式 native UUID 与新鲜 API 匹配; grok-4.5/low/default 已验 |
| 消息与回执 | 角色真实提交三阶段回执, 核验 artifact/hash; 有界 helper 已验 |
| 去重与冲突 | 同 message ID 同正文不重复提交, 不同正文拒绝; 不证明外部副作用 exactly once |
| 暂停派工 | 本机拒绝 wrapper 暂停后的新派工已验; 不证明活动工具强停 |
| 捕获与回收 | 原始 recent/visible 文本留存已验; active 拒绝回收, 最后回执后捕获且新鲜 done 时回收已验 |
| 独立 QA | 主实验 QA 自行设计测试发现受控缺陷, 但范围外 memory 读取使其没有干净盲验结论 |
| Research 反馈 | 主实验已观察反馈; 新项目完整闭环未验 |
| Curator 有限试用 | 主实验实际使用, 撤回和独立核对已验; 新项目完整闭环未验 |
| 普通方法改善 | 未测, 需同类任务的效果与反例 |
| 自动审批与文件硬隔离 | 未提供 |
| 崩溃恢复, 跨机器, 其他 provider, Linux/macOS | 未验收 |

skill 运行程序沿用原接口与 20 项合成 fixture, 并作三项有界修订: 不按普通目录名 private 推定授权边界, 在每个角色 prompt 传播当前授权和资料边界, 保存当次完整模板/prompt 与 hash。范围仍由实际项目与用户授权决定, 不读取别的项目禁用资料。原 fixture 与 12 个模板资源保留原字节; 文档和初始化脚本按 skill 布局适配。

合成检查包括 capture 纯文本格式、cleanup idle/done、去重、未知提交、身份不一致和未决审批回归。初始化只生成 draft/pending 项目资料, 不运行 Herdr 或创建运行 state; 新任务引用不固定到初始 Worker 草案。真实 symlink 创建受 Windows 权限限制, 不能把跳过项称通过; 项目目录别名/逃逸可另用实际 junction 测试。执行 [本地 fixture](../scripts/fixtures/test_herdr_lab.py)不能替代真实任务验收。并发目录替换、业务 JSON 授权、候选状态与作者身份不是此运行器的技术强制检查。

本机本次测试依赖版本为 Python 3.14.2, Herdr 0.9.1/protocol 22, Grok Build CLI 1.0.44, Codex CLI 0.159.2; 这些是测试记录, 不是所有机器的固定要求。真实结果以接收者自己的新 run 为准。

## 已知身份与隔离缺口

主实验 Worker 执行含嵌套 headless Grok 调用的程序后, Herdr 的 pane agent_session 被更新为子会话身份。当前运行程序严格匹配启动时的 expected_native_session_id, 不一致就拒绝后续 send 或 cleanup, 不猜测或自动恢复父会话。简单 helper 没覆盖该嵌套场景, 问题尚未修复。嵌套 provider/CLI 项目需单独验证父子身份, 消息目标和回收, 必要时修订适配器再验收。

主实验一个 QA 审阅角色读取了任务范围外 memory。正确答案, 正常回执或其他链路通过不能消除这项缺口。角色提示和审计没有文件访问硬隔离, 共享 OS 账户下的回执也没有密码学作者认证。

[Herdr integrations](https://herdr.dev/docs/integrations/)区分会话身份与状态来源, [Agents 文档](https://herdr.dev/docs/agents/)说明屏幕状态匹配有 fallback 和 unknown。缺失或不一致身份需 fail closed, 不按 pane 标题猜测。idle, 回合完成和 exit 0 不是业务验收。

## 换项目与分享

1. 读取新项目规则, 工作树门禁和状态所有权; 用实际用户目标, 验收和授权生成新输入目录与 state_dir。
2. 配置自己的 session/workspace, provider, model, effort, 路径和角色资料, 不复制旧 manifest, 身份或授权。
3. preflight 和 plan 后, 跑一个可逆真实任务, 按项目现有门禁和独立 QA 留证。
4. 报告准确 OS/依赖版本, 模型/effort, 脚本 hash, 命令, 结果, QA 和缺口。跨机器可用需要该机器的新证据。

分享此 skill 的 SKILL.md, agents 元数据, scripts 源码与合成 fixture, references 和 assets/templates。不要附运行 state, 本地任务输入, captures, receipts, memory, 隐藏答案, 密钥, 用户配置, socket/PID, 原始 pane/session ID, 缓存或第三方二进制。

原创资源的公开源码许可证尚未选择, 由用户决定; 本次 skill 安装不替第三方依赖授予许可。Python, Herdr 和 Grok 由接收者按发行者说明安装与登录。当前 [Herdr 官方仓库许可](https://github.com/herdrdev/herdr/blob/master/LICENSE)为 Apache-2.0, 具体发行物仍以随版本提供的许可为准。此 skill 不捆绑第三方软件或原实验资料。
