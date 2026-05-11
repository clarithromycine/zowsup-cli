# Zowsup Agent 中间层改造规划（PLAN）

## 1. 结论先行

### 1.1 当前问题确认

结论：**是的，当前 bot 实际上只能和 backend 在同一台机器（或至少同一共享本地文件系统）下稳定工作**。

核心证据（已基于现有代码确认）：

1. backend 直接本机拉起 bot 进程
   - [script/dashboard_server.py](script/dashboard_server.py) 启动 Flask。
   - [app/dashboard/api/bot_control.py](app/dashboard/api/bot_control.py) 使用 `subprocess.Popen([python, script/main.py, phone])` 启停 bot。
2. backend 与 bot 的控制与数据交换依赖本地文件
   - [app/dashboard/utils/send_queue.py](app/dashboard/utils/send_queue.py): `data/send_queue.json` / `data/send_results.json`
   - [app/dashboard/utils/avatar_queue.py](app/dashboard/utils/avatar_queue.py): `data/avatar_queue.json` / `data/avatar_updates.json`
   - [app/dashboard/utils/bot_status.py](app/dashboard/utils/bot_status.py): `data/bot_status_<phone>.json`
3. bot 侧直接读写 dashboard 本地存储
   - [app/zowbot_layer.py](app/zowbot_layer.py) 轮询 send/avatar 本地队列。
   - [app/dashboard/bridge.py](app/dashboard/bridge.py) + [app/dashboard/config.py](app/dashboard/config.py) 直接依赖本地 `data/dashboard.db` 路径。
4. frontend 直接调用单一 backend 的 `/api/bot/*`，默认语义是 backend 直接管理 bot
   - [app/dashboard/frontend/src/api/endpoints.ts](app/dashboard/frontend/src/api/endpoints.ts)

因此，你提出的“backend 管 agent、agent 管 bot”的中间层方案是必要且方向正确的。

---

## 2. 目标架构

从当前架构：

`Frontend -> Backend -> Bot`

演进为：

`Frontend -> Backend <-> Agent -> Bot(多个)`

### 2.1 角色定义

1. Backend Server（控制平面）
   - 对接多个 agent。
   - 提供统一 API 给 frontend。
   - 不再直接 `subprocess` 拉起 bot。
   - 负责 agent 注册、认证、路由、审计、状态汇总。

2. Local Agent（新增，本地中转模块）
   - 和 backend 建立长连接（建议 WebSocket，支持心跳与重连）。
   - 在本机管理多个 bot 进程（start/stop/status/log）。
   - 本机 bot 与 backend 间的数据桥接由 agent 统一完成。

3. Bot Process（执行平面）
   - 保持现有协议栈与业务能力。
   - 逐步从“直接写 dashboard 本地文件/DB”迁移到“通过 agent 上报/取任务”。

---

## 3. 设计原则

1. 兼容优先：先让单机模式可继续运行，再逐步切到 agent 模式。
2. 渐进迁移：按控制链路、状态链路、消息链路分阶段迁移。
3. 可观测性：每一步都有状态、日志、错误码与审计。
4. 安全最小化：agent 与 backend 使用 key 认证，支持轮换与吊销。
5. 幂等与重试：网络抖动下命令不重复执行、事件可补偿。

---

## 4. 协议与数据模型（建议）

## 4.1 Agent <-> Backend 通信协议

建议两条逻辑通道：

1. 控制通道（Commands）
   - backend -> agent：`start_bot` / `stop_bot` / `fetch_qr` / `fetch_accounts` / `send_message` 等
   - agent -> backend：`ack` / `result` / `error`

2. 事件通道（Events）
   - agent -> backend：`agent_online` / `agent_heartbeat` / `bot_status_changed` / `bot_log` / `message_ingested` / `avatar_updated`

bot 列表同步策略（建议明确采用“上报 + 拉取”双机制）：

1. agent 在连接建立后上报完整 bot 快照（full snapshot）。
2. agent 在心跳周期里上报增量状态（status delta）。
3. backend 保留主动拉取能力（`fetch_accounts` / `list_bots`），用于校准与补偿。
4. frontend 的 bot 列表以 backend 聚合视图为准，不直接连 agent。

消息建议字段（统一 envelope）：

- `msg_id`（全局唯一）
- `type`（command/event）
- `name`（具体动作名）
- `agent_id`
- `timestamp`
- `payload`
- `trace_id`（可选）

## 4.2 认证与授权

1. 每个 agent 分配独立 `agent_key`（至少 32 bytes 随机值）。
2. 首次握手：`agent_id + key`，backend 返回 session token（短期）。
3. 所有后续消息带 session token；token 过期自动刷新。
4. backend 支持：key 轮换、吊销、禁用 agent。

## 4.3 Backend 持久化（新增表建议）

1. `agents`
   - `agent_id`（PK）
   - `name` / `tags` / `host` / `version`
   - `status`（online/offline/degraded）
   - `last_seen_at`
   - `created_at` / `updated_at`

2. `agent_keys`
   - `id`（PK）
   - `agent_id`（FK）
   - `key_hash`
   - `is_active`
   - `expires_at`

3. `bot_instances`
   - `phone`（PK 或唯一）
   - `bot_jid`
   - `agent_id`（FK）
   - `pid`（agent 本机 PID，仅展示）
   - `running`
   - `last_status_at`

4. `agent_command_jobs`
   - `job_id`（PK）
   - `agent_id`
   - `command_name`
   - `request_payload`
   - `state`（queued/sent/acked/succeeded/failed/timeout）
   - `result_payload`
   - `error`
   - `created_at` / `updated_at`

---

## 5. 代码层改造蓝图

## 5.1 Backend（Flask）

现有 [app/dashboard/api/bot_control.py](app/dashboard/api/bot_control.py) 的本地 `subprocess` 逻辑需要抽象为 driver：

1. 新增 BotDriver 抽象层
   - `LocalBotDriver`（保留旧逻辑，兼容单机）
   - `AgentBotDriver`（通过 agent 下发命令）

2. API 层保持尽量不变
   - 例如 `POST /api/bot/start`、`POST /api/bot/logout` 仍可保留
   - 增加可选参数 `agent_id`（或按 phone 自动路由）

3. 新增 Agent 管理 API
   - `GET /api/agents`
   - `POST /api/agents`
   - `PATCH /api/agents/<id>`（启停、标签）
   - `POST /api/agents/<id>/rotate-key`
   - `GET /api/agents/<id>/bots`

4. 新增 Agent 网关（WebSocket）
   - backend 接收 agent 长连接
   - 维护在线 agent registry（内存 + DB）
   - 接收事件并转写 DB/广播 frontend

## 5.2 Agent（新增模块）

建议目录：`app/agent/`

1. `agent_main.py`
   - 读取本机配置（backend 地址、agent_id、agent_key）
   - 建立 websocket 长连
   - 启动心跳、重连、命令执行器

2. `bot_runtime.py`
   - 管理本机 bot 子进程（start/stop/restart/status）
   - 维护 `{phone -> process}` 映射

3. `collectors/`
   - 日志采集
   - bot 状态采集
   - send/avatar 队列过渡兼容采集（迁移期）

4. `protocol/`
   - envelope 编解码
   - command handler registry

日志链路改造要求：

1. agent 负责采集所在机器的 bot 日志并上报 `bot_log` 事件。
2. backend 在 agent 模式下不再依赖本地 `logs/*.log` tail 作为主链路。
3. local 单机兼容模式可继续保留现有 tail 实现，作为回退路径。

## 5.3 Bot（渐进迁移）

短期不改协议栈，仅改 integration 边界：

1. 先保留本地桥接逻辑，agent 作为“外层进程托管者”。
2. 中期把 `send_queue` / `avatar_queue` 从本地文件 IPC 升级为 agent 内部队列（内存/本地 sqlite）。
3. 最终 bot 不再依赖 dashboard 本地路径语义，由 agent 统一代理上报。

## 5.4 Frontend

在现有 bot 管理页基础上增加 agent 维度：

1. Agent 管理页（新增）
   - agent 列表、在线状态、最后心跳、版本、托管 bot 数量
   - key 轮换/禁用

2. Bot 管理页（增强）
   - 每个 bot 显示所属 agent
   - start/stop 时可指定 agent 或按默认路由

3. 实时态
   - WS 订阅新增 `agent_status_changed`、`agent_bot_status_changed`

---

## 6. 迁移阶段计划（建议 5 个里程碑）

## M0: 设计冻结与契约定义

目标：冻结协议与边界，不改业务逻辑。

交付：

1. Agent 协议文档（command/event schema）
2. 安全方案（key 生命周期）
3. 数据模型 DDL 草案
4. API 兼容矩阵

## M1: Backend 支持 Agent Registry（不切流）

目标：backend 具备 agent 注册/管理能力。

交付：

1. agent 表与管理 API
2. backend agent websocket 网关（仅接入、心跳）
3. frontend agent 管理只读页

## M2: Agent 托管 bot 进程（控制链路切换）

目标：`start/stop/status` 通过 agent 执行。

交付：

1. agent `start_bot/stop_bot/get_status` handler
2. backend BotDriver 接入 AgentBotDriver
3. `POST /api/bot/start` 可路由到 agent
4. 单机 LocalBotDriver 保留可回退

## M3: 消息与日志链路迁移（数据链路切换）

目标：bot 事件/日志通过 agent 回传 backend。

交付：

1. agent 侧日志/状态上报
2. backend 落库与 websocket 广播
3. frontend 实时视图兼容 agent 来源

## M4: 去本地文件耦合 + 稳定性加固

目标：弱化/移除 `data/*.json` 跨进程本地依赖。

交付：

1. send/avatar 队列 agent 化
2. 命令幂等、超时重试、死信
3. 故障演练：agent 掉线、重连、重复消息
4. 文档与运维手册更新

---

## 7. TODO 清单（执行级）

## 7.1 架构与协议

- [ ] 编写 `docs/agent-protocol.md`（消息 envelope + command/event 列表）
- [ ] 定义 command 状态机：`queued -> sent -> acked -> succeeded/failed/timeout`
- [ ] 定义幂等键规则（`msg_id` + `agent_id`）
- [ ] 定义 agent 重连与会话恢复机制

## 7.2 Backend 改造

- [ ] 新增 `app/dashboard/api/agents.py`（agent 管理 API）
- [ ] 新增 `app/dashboard/api/agent_gateway.py`（agent WS 接入）
- [ ] 新增 `app/dashboard/agent_registry.py`（在线 agent 管理）
- [ ] 抽象 `BotDriver` 并实现 `LocalBotDriver` + `AgentBotDriver`
- [ ] 改造 [app/dashboard/api/bot_control.py](app/dashboard/api/bot_control.py) 使用 driver，而非直接 `subprocess`
- [ ] 新增 DB migration（agents/agent_keys/bot_instances/agent_command_jobs）
- [ ] 增加 agent 认证中间件与 key 校验
- [ ] 实现 bot 列表聚合器（agent 全量上报 + 定时主动拉取校准）

## 7.3 Agent 模块新增

- [ ] 创建目录 `app/agent/`
- [ ] 实现 `agent_main.py`（启动、鉴权、心跳、重连）
- [ ] 实现 `bot_runtime.py`（bot 子进程池管理）
- [ ] 实现命令 handler：`start_bot` / `stop_bot` / `list_bots` / `get_status`
- [ ] 实现事件上报：`bot_status_changed` / `bot_log`
- [ ] 实现本地配置文件与 key 加载（建议 `conf/agent.conf`）
- [ ] 实现日志采集与背压控制（限速、批量、断线重传）

## 7.4 Frontend 改造

- [ ] 新增 agent API 客户端（`/api/agents*`）
- [ ] 新增 Agent 管理页面（列表/状态/key 轮换）
- [ ] Bot 管理页增加 `agent_id` 选择与展示
- [ ] WebSocket 订阅 agent 相关事件并更新 store

## 7.5 兼容与迁移

- [ ] 增加运行模式开关：`BOT_DRIVER_MODE=local|agent`
- [ ] 保留 local 模式回退路径（灰度期间必须）
- [ ] 提供数据迁移脚本：将现有 running bot 绑定到默认 agent
- [ ] 补充回归测试：单机旧链路 + agent 新链路

## 7.6 安全与运维

- [ ] agent key 只存 hash，明文只在创建时展示
- [ ] 支持 key 轮换（旧 key 短期并存）
- [ ] 增加 agent 审计日志（登录、命令执行、失败原因）
- [ ] 增加告警：agent 离线、命令超时、bot 启动失败率

---

## 8. 风险与未决事项

1. 是否允许一个 bot 被多个 agent 争抢托管（建议禁止，单主约束）
2. 事件语义是 at-most-once 还是 at-least-once（建议 at-least-once + 幂等）
3. agent 与 backend 断连期间的命令积压上限与丢弃策略
4. bot 日志回传是否采样/限速，避免压垮 backend websocket
5. 多机部署后，`dashboard.db` 是否继续单库 SQLite（建议中期评估迁移到 PostgreSQL）

---

## 9. 建议的实施顺序（最小可行）

1. 先做 M1（agent 注册 + 管理页）
2. 再做 M2（start/stop/status 走 agent）
3. 最后做 M3/M4（消息链路和文件耦合迁移）

这样可以最快拿到“backend 管多个 agent，agent 管多个 bot”的可运行闭环，同时把回滚风险降到最低。