# Windows/Grok 项目启动

先读 [organization.md](organization.md)和 [portability.md](portability.md)。确定实际 SKILL_ROOT: 它包含 SKILL.md, scripts, references 和 assets。以下示例路径不指向原实验, 换成目标项目实际位置; 不需要旧工具包或已有实验 run。

## 安装与调用

复制完整 herdr-rd-organization 文件夹, 保留 scripts/references/assets 的相对布局。本次按 skill-creator 规范安装到 ~/.codex/skills/herdr-rd-organization, 并已在本机新会话实测发现。[当前 Codex 官方文档](https://learn.chatgpt.com/docs/build-skills)列出的用户位置是 ~/.agents/skills, 项目位置是 .agents/skills。接收者按自己的客户端版本选择一个发现位置, 不重复安装同名副本; 新会话可用 $herdr-rd-organization 调用并确认实际加载路径。Grok Build 的项目 skill 位置为 .grok/skills/herdr-rd-organization; 其他客户端按自己的发现规则安装, 不会自动共享 Codex 的用户目录。目录存在并不证明客户端已发现, 先在新的会话确认加载名称与路径。

## 环境与项目规则

需要 Python 3.10+, Herdr 和已登录的 Grok Build CLI。脚本只用 Python 标准库。用 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/)安装并用 python --version 核对解释器。

Herdr 按 [官方安装说明](https://herdr.dev/docs/install/)操作。复现已测版本时, 从 [0.9.1 发布页](https://github.com/herdrdev/herdr/releases/tag/v0.9.1)选择 herdr-windows-x86_64.zip, 保留完整解压目录及 app-local ConPTY, 不只复制 exe。启动 Herdr 并核对自己的 session 和 workspace。

Grok 使用 [官方安装入口](https://docs.x.ai/build/overview)的 Windows PowerShell tab。首次运行按提示完成浏览器认证, 或按 [CLI 登录说明](https://docs.x.ai/build/cli/reference)使用 grok login/device-auth。自行核对实际 CLI 版本, 可用模型和 effort, 不复用分享者登录。

herdr --skill 的内置指南假定调用者处在 Herdr pane 内, 要求 HERDR_ENV=1。外部宿主可先进行本地 init 与 plan; 不操作 UI focused session。只有用户明确授权外部控制某个 named session 与范围时, 才能使用配置中的显式 --session 进行 preflight/控制; 否则在 Herdr pane 内执行。不要伪造环境变量。状态查询 status 只返回保存的 manifest, 不证明当前 pane 或工具状态; 控制前按授权核对新鲜 snapshot。

初始化之前读取目标项目 AGENTS.md, CLAUDE.md, 工作树门禁和状态所有权。若项目要求预检或写入门禁, 先按现有流程完成。用户目标, 验收和操作范围使用本次真实决定, 不因 skill 被选择而扩大。

## 生成本地资料

### 先核对调用位置

首次在真实 Herdr pane 内调用时, 先运行只读检查, 不直接拿继承的 w2 或 w2:p8 查默认 session:

```powershell
$skillRoot = 'C:/Skills/herdr-rd-organization' # 换成实际加载的 Skill 路径
python -B "$skillRoot/scripts/check_context.py"
```

成功后用 result.binding 的 session 与 workspace_id 初始化, 所有后续 Herdr RPC 显式带 --session。检查只读取 session 清单、目标 workspace 清单和指定 pane 的元数据, 不读取终端正文、创建角色或改运行记录。同一个 w1:p1 可以出现在不同 session, 不能用 ID 或标题反推 session。

Herdr 0.9.1 未显式指定 --session 时, HERDR_SOCKET_PATH 可优先于 HERDR_SESSION; 检查按 socket 与本机 session 清单匹配, 不猜 default。继承的 pane/workspace 是启动时环境; pane 移动后原 ID 可由同一个服务器的原生别名解析, 以 pane get 返回的当前身份为准。[官方 CLI 说明](https://herdr.dev/docs/cli-reference/)与 [0.9.1 session 实现](https://github.com/herdrdev/herdr/blob/v0.9.1/src/session.rs)说明此路由与环境行为。

若 socket 无对应 session, pane 已不存在, 或身份冲突, 检查返回失败与可核对的清单。不要因失败重建 pane、改环境变量或切到 focused 窗口。返回当前仍存活的 Herdr pane 重新调用; 或确认任务实际指向的 session/workspace 后显式检查:

```powershell
python -B "$skillRoot/scripts/check_context.py" --session 'REPLACE_WITH_VERIFIED_SESSION' --workspace 'REPLACE_WITH_VERIFIED_WORKSPACE'
```

显式 workspace 只验证指定目标, 不声称它是调用者, 不继承其他 session 的 pane ID。外部宿主只能在用户已授权的目标与范围内用此方式检查, 不伪造 HERDR_ENV。已有 run 使用下面命令核对原配置; 不因调用者位置变化重写 config、manifest 或接管新窗口:

```powershell
python -B "$skillRoot/scripts/check_context.py" --config $labConfig
```

### 填写并初始化

init_project.py 只生成配置与模板副本, 不启动 Herdr, 不创建 pane/manifest, 不把草稿授权提升为已批准。先把下面 session, workspace 和 model 的 REPLACE 值改成实际值再运行; 初始化拒绝这些占位值。

```powershell
$skillRoot = 'C:/Skills/herdr-rd-organization'
$projectRoot = 'C:/Projects/demo'
$labInputs = "$projectRoot/.herdr-rd-input"
$labState = "$projectRoot/.herdr-rd-state"
$runId = 'demo-run-001'
python -B "$skillRoot/scripts/init_project.py" --project-root $projectRoot --input-dir $labInputs --state-dir $labState --session 'REPLACE_WITH_SESSION' --workspace 'REPLACE_WITH_WORKSPACE' --model 'REPLACE_WITH_AVAILABLE_GROK_MODEL' --effort low --run-id $runId
$labConfig = "$labInputs/lab-config.json"
```

全部参数必填。project_root 必须已存在。input_dir 必须是项目内尚不存在的新目录, 不能等于项目根。state_dir 也必须在项目内, 与 input_dir 不重叠; 初始化只填入该路径, 不创建运行 state。路径均使用绝对路径, 生成文本为 UTF-8 无 BOM。输入与状态不能在已安装 skill 内; state_dir 已存在时必须是目录。Windows 路径分量不能以点或空格结束。

生成文件为 lab-config.json, research-task.json, orchestrator-task.json, task.json, result.json, receipt.json, experience.json 和 roles 下五个角色模板。角色的当前任务、独立验收包和证据包以每次 TASK BODY 为准; project_root/state_dir/run_id 留给 send 按真实 run 渲染。业务目标/验收仍为草稿, 授权仍为 pending, REPLACE 值仍需填写。不覆盖现有输入目录; 修改生成的项目副本, 不修改共享 skill。I/O 中断时报告已写文件和失败路径, 保留部分草案; 检查后用新的 input_dir 重试, 不自动删除或覆盖。共享 OS 下的并发目录替换仍不是硬隔离。

填写 research-task.json 的实际课题, 冻结目标, 可观察验收, 允许输入, 写入范围, 预算, deadline 和交付。根据真实用户决定填写状态和依据。填写 orchestrator-task.json 的范围与授权, Research 真正完成后再填方案与回执路径。运行程序不技术强制执行业务 JSON 的文件范围或验收。

Orchestrator intake 中目标, 方案和完成回执的路径必须同时填原始文件字节的 SHA256。可用 Get-FileHash -Algorithm SHA256 -LiteralPath <实际路径> 获取。接收角色使用前核对, 不匹配或缺失时停止并报告 gap。send 只冻结任务正文, 不冻结正文引用的文件; QA 也要检查准确版本。Curator 的 experience.json 另需填有限任务列表, 正整数 max_tasks, UTC 结束时间与停止条件。

检查 lab-config.json 中 Herdr executable, session/workspace, 五个角色的 provider/model/effort, template_file 和 temporary。首版只支持 grok, 无跨 provider 或模型静默回退。默认使用 permission-mode default, no-subagents 和 disable-web-search。需要不同角色模型或 effort 时显式修改配置, 再核对实际启动结果。

session_args 是额外的字面参数数组, 不能覆盖 model/effort/cwd/session 或其短参数。拒绝 always-approve, yolo 和 --auto。项目确有相应授权时可显式指定一个支持的 --permission-mode: default, acceptEdits, auto, dontAsk 或 plan; 名称本身不构成项目授权。实际审批需核对操作, 本 skill 没有自动选项批准引擎。

## 预检与创建角色

```powershell
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig preflight
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig plan --roles research,orchestrator,worker,qa,curator
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig start --run-id $runId --roles research,orchestrator,worker,qa,curator
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig status --run-id $runId
```

preflight 读取配置, Herdr 版本/snapshot; plan 只输出计划, 两者不写运行 state 或操作 pane。start 创建本 run 的新角色并记录身份, 不接管原窗口, 不自动派科研任务。每个新 Grok 角色有明确 native UUID; send 用新鲜 API 核对, 缺失, 陈旧或不一致即拒绝派工。

plan 和 status 不要求本机已安装 Herdr; status 只读已有 manifest, 缺失时报告错误且不创建 state。start 核对创建结果确为新 pane, 位于指定 workspace/tab 且与新鲜元数据一致, 才能命名和启动。creation_uncertain 阻止新派工, 保留证据供核查, 不盲目重跑或接管。

start 为每个新 pane 设置固定角色标题, 例如 Research Engineer | 1234abcd、Engineering Orchestrator | 1234abcd、Worker | 1234abcd、Independent QA | 1234abcd 和 Skills Curator | 1234abcd。后缀是 run_id 的最后 8 个字符。Agent 的内部 name 与 pane 的显示 label 是独立字段: 程序在启动 Agent 前调用 pane rename, 并通过 pane get 核对 pane_id、tab_id 和 label; 启动后再次检查标题是否保留。命名失败或实际标题不匹配时保留本 run 的已创建窗口与记录, 返回 creation_uncertain, 不继续创建其他角色。不要盲目重跑 start。

已有窗口不会因更新 Skill 自动改名。仅在已授权且确认所属运行与角色后, 使用实际 session 和 pane_id 补名, 例如 herdr --session <session> pane rename <pane_id> "Worker | <run-suffix>", 再用 pane get 核对 label。不要按侧栏位置或终端自身动态 title 猜测角色。标题只供人识别, 不能代替 pane/tab/native session 身份验证。Herdr CLI 文档: https://herdr.dev/docs/cli-reference/#panes。

角色模板只允许 send 自动填 project_root, state_dir 和 run_id。初始化已填其他基础变量; 若自行修改后仍有双花括号业务变量, 必须先填完整, 否则派工拒绝。

## 先派 Research, 再激活 Orchestrator

```powershell
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig send --run-id $runId --role research --message-id research-initial-001 --body-file "$labInputs/research-task.json"
```

Research 收到任务后实际提交 received, started, 完成研究方案后再提交 completed 或 failed。send 成功只证明提交, 不证明收件或完成。拿到真实方案 artifact 及完成回执, 将它们填入 orchestrator-task.json, 再发送:

```powershell
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig send --run-id $runId --role orchestrator --message-id orchestrator-intake-001 --body-file "$labInputs/orchestrator-task.json"
```

Orchestrator 用初始化时写入的真实 wrapper_argv_prefix 路由 Worker, 独立 QA, Research 反馈和有界 Curator 证据包。它需先写具体 body-file 再 send, 每个收件角色提交自己的真实回执。下面只展示有界 Worker 派工接口, task.json 必须先填写具体任务; 已由 Orchestrator 派工则不要重复手动派同一任务。

```powershell
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig send --run-id $runId --role worker --message-id worker-task-001 --body-file "$labInputs/task.json"
```

send 在提交前保存正文、已渲染角色模板和完整 prompt 及 hash; 它们属于项目运行证据, 不随 skill 分享。

消息准备和结果合并使用短状态锁, 等待 Herdr prompt 响应期间释放锁, 让角色回执和 pause 可写入。state 表示回执进度, submission_state 单独记录投递结果; 响应不会把 completed/failed 等真实回执退回 submitted。已保存的投递 intent 属于在途尝试, pause 不撤销它。并发同 ID 去重; 进程硬中断后仍需核查在途结果, 不盲目重放。

wrapper 收到响应或异常后先在该消息的 message-evidence/submission.json 保存不可变结果证据, 再合并 manifest。长取证等操作占锁超过 5 秒时明确报告合并未完成和证据路径。原写入结束后, 用同一 message ID, 同一角色和未改正文重试 send, 只核对并合并原结果, 不重新提交 prompt。状态查询不会自动修复记录。没有结果证据的在途记录仍需人工核查, 不能认定已送达或自动重派。此证据由同一 wrapper 写入, 不提供共享账户下的作者认证。

同 message ID 的正文不可替换。相同正文去重不证明外部副作用 exactly once。效果未知时核查原尝试, 不盲目重放。完整研发闭环仍要按当前项目的真实任务独立验收。

## 角色回执与证据

send 附 TASK HEADER, 实际角色绑定和各阶段 receipt 的完整 CLI argv。收件角色自己写 UTF-8 JSON 到 state_dir/runs/<run-id>/agent-evidence, 再实际调用对应 argv。操作者不能因为 send 成功就替角色合成回执。

从当次头部原样复制 run_id, message_id, destination_role, pane_id, session_ref, expected_native_session_id 和 body_sha256。receipt.json 中 session_ref 的 null 只是占位: 必须替换成完整实际对象, 保留 agent/source/kind/value 及其他返回字段, 不凭 UUID 重建或沿用旧 run。缺真实头部时记录 gap。

completed 要先有 received 和 started, 并至少包含一个真实 artifact 的绝对 path 与准确 sha256。completed/failed 必须显式含 pending_tools_or_approvals 数组, 如实列出未决事项; [] 只表示没有观察到未决事项, 不是 OS 工具停止证明。

以下说明接口, 实际角色使用它收到的精确 argv 与实际文件路径:

```powershell
$agentEvidence = "$labState/runs/$runId/agent-evidence"
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig receipt --run-id $runId --message-id research-initial-001 --phase received --evidence-file "$agentEvidence/research-initial-001-received.json"
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig receipt --run-id $runId --message-id research-initial-001 --phase started --evidence-file "$agentEvidence/research-initial-001-started.json"
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig receipt --run-id $runId --message-id research-initial-001 --phase completed --evidence-file "$agentEvidence/research-initial-001-completed.json"
```

wrapper 核对声明身份和 hash, 共享 OS 账户下不认证作者。消息 completed 不等于课题 accepted, Orchestrator 仍需独立 QA 和冻结验收。

## 暂停与临时回收

```powershell
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig pause --run-id $runId
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig status --run-id $runId
```

pause 只阻止此 wrapper 新派工, 不强停活动工具或撤销已有副作用。检查未决审批与工具效果, 未知则记 uncertain。得到相应恢复指令且核对身份与范围后才 resume。

```powershell
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig resume --run-id $runId
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig capture --run-id $runId
python -B "$skillRoot/scripts/runtime/herdr_lab.py" --config $labConfig cleanup --run-id $runId --roles worker,qa,curator
```

cleanup 会关闭真实 pane, 仅用于本 run 已授权回收的临时角色。要求所有消息终态, pending_tools_or_approvals 均为 [], 最后回执后已 capture, 身份匹配, 新鲜 pane/agent 明确 idle 或 done。capture 保存原始 recent/visible UTF-8 .txt, snapshot .json 及身份/hash。working, blocked, unknown 不能回收; Research/Orchestrator 保留, 原有或未知窗口不纳入管理。

state_dir/runs/<run-id>/manifest.json 由 wrapper 唯一写入, 不手工改成成功。业务结论继续由 Orchestrator 的项目状态源管理。分享 skill 时不包含项目输入或 state; 下一项目重新初始化, 填契约, 预检并验真实任务。
