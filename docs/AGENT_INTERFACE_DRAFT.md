# Agent 接口草案（Draft v0.1）

## 1. 文档目的

本文档给出 Backend <-> Agent 的接口草案，用于评审后进入实现阶段。

当前状态：**草案（Draft）**，允许调整字段与流程。

适用范围：

1. Backend 与 Agent 的认证与会话管理
2. Backend 向 Agent 下发命令（bot 管控）
3. Agent 向 Backend 上报状态/日志/事件
4. Bot 列表聚合（上报 + 拉取）

不在本文档范围：

1. Bot 内部 WhatsApp 协议栈细节
2. Frontend 页面 UI 设计
3. 具体数据库 migration SQL

---

## 2. 术语与角色

1. Backend
   - Dashboard 后端服务（控制平面）
2. Agent
   - 部署在 bot 所在机器上的中转进程
3. Bot
   - 实际执行消息收发能力的进程
4. Command
   - Backend -> Agent 的控制动作
5. Event
   - Agent -> Backend 的状态/日志/业务事件

---

## 3. 总体通信模型

建议使用：

1. HTTPS REST（一次性操作）
   - agent 注册、key 轮换、查询等
2. WebSocket（长连接主通道）
   - 命令下发、ACK、结果回传、事件上报、心跳

连接关系：

1. Agent 主动连接 Backend（避免 backend 反向访问内网机器）
2. 一个 Backend 支持多个 Agent 并发连接
3. 一个 Agent 支持管理多个 Bot 进程

---

## 4. 版本与兼容策略

协议版本字段：

1. `protocol_version`：如 `1.0`
2. `agent_version`：Agent 程序版本，如 `0.1.0`

兼容规则：

1. 小版本向后兼容（1.x）
2. 大版本不兼容（2.x）
3. Backend 返回支持的版本区间，Agent 决定是否降级

---

## 5. 认证与安全

## 5.1 Agent 凭证

每个 Agent 分配：

1. `agent_id`（全局唯一）
2. `agent_key`（明文仅发放一次）

Backend 仅存储 `agent_key_hash`。

## 5.2 会话流程（建议）

1. Agent 建立 WS 连接
2. 发送 `agent_auth` 消息（携带 `agent_id` + `agent_key`）
3. Backend 校验成功后返回 `agent_auth_ok`（附短期 `session_token`）
4. 后续所有消息带 `session_token`

## 5.3 安全建议

1. 强制 WSS（TLS）
2. `agent_key` 长度 >= 32 bytes
3. 支持 key 轮换（旧 key 短期并存）
4. 支持 agent 禁用与会话吊销

---

## 6. WebSocket 消息信封（Envelope）

所有消息统一结构：

```json
{
  "msg_id": "uuid-v4",
  "protocol_version": "1.0",
  "type": "command|command_ack|command_result|event|heartbeat|error",
  "name": "start_bot",
  "agent_id": "agent-cn-sh01",
  "timestamp": 1778445600,
  "session_token": "optional-before-auth",
  "payload": {},
  "trace_id": "optional"
}
```

字段说明：

1. `msg_id`
   - 全局唯一，幂等主键
2. `type`
   - 消息分类
3. `name`
   - 动作名称（命令名/事件名）
4. `timestamp`
   - Unix 秒级时间戳
5. `trace_id`
   - 跨链路追踪（可选）

---

## 7. 命令通道（Backend -> Agent）

## 7.1 命令状态机

状态建议：

1. `queued`
2. `sent`
3. `acked`
4. `succeeded | failed | timeout`

时序约束：

1. Agent 收到命令后应先回 `command_ack`
2. 执行完毕回 `command_result`
3. 超时由 Backend 判定并落库

## 7.2 命令定义（第一批）

### A. start_bot

请求 payload：

```json
{
  "phone": "8613800138000",
  "boot_mode": "normal",
  "env": {
    "proxy": "optional"
  }
}
```

结果 payload：

```json
{
  "ok": true,
  "phone": "8613800138000",
  "pid": 12345,
  "already_running": false,
  "bot_jid": null
}
```

### B. stop_bot

请求 payload：

```json
{
  "phone": "8613800138000",
  "force": false
}
```

结果 payload：

```json
{
  "ok": true,
  "phone": "8613800138000",
  "stopped": true
}
```

### C. get_bot_status

请求 payload：

```json
{
  "phone": "8613800138000"
}
```

结果 payload：

```json
{
  "phone": "8613800138000",
  "running": true,
  "pid": 12345,
  "bot_jid": "8613800138000@s.whatsapp.net",
  "started_at": 1778445600,
  "uptime_seconds": 120
}
```

### D. list_bots

请求 payload：

```json
{
  "include_stopped": true
}
```

结果 payload：

```json
{
  "snapshot_id": "snap-20260511-001",
  "bots": [
    {
      "phone": "8613800138000",
      "running": true,
      "pid": 12345,
      "bot_jid": "8613800138000@s.whatsapp.net",
      "last_seen": 1778445600
    }
  ]
}
```

### E. fetch_qr

请求 payload：

```json
{
  "phone": "8613800138000",
  "mode": "scan"
}
```

结果 payload：

```json
{
  "ok": true,
  "session_id": "qr-session-uuid"
}
```

QR 本体建议走事件流（见 `qr_updated` 事件）。

---

## 8. 事件通道（Agent -> Backend）

## 8.1 事件定义（第一批）

### A. agent_online

```json
{
  "hostname": "bot-host-01",
  "ip": "10.0.1.25",
  "agent_version": "0.1.0",
  "capabilities": ["start_bot", "stop_bot", "list_bots", "log_stream"]
}
```

### B. agent_heartbeat

```json
{
  "load": {
    "cpu_pct": 23.1,
    "mem_pct": 45.2
  },
  "bot_count": 12,
  "running_count": 8
}
```

### C. bot_snapshot（全量）

```json
{
  "snapshot_id": "snap-20260511-001",
  "bots": [
    {
      "phone": "8613800138000",
      "running": true,
      "pid": 12345,
      "bot_jid": "8613800138000@s.whatsapp.net",
      "last_seen": 1778445600
    }
  ]
}
```

### D. bot_status_changed（增量）

```json
{
  "phone": "8613800138000",
  "running": false,
  "pid": 12345,
  "reason": "manual_stop",
  "changed_at": 1778445700
}
```

### E. bot_log

```json
{
  "phone": "8613800138000",
  "level": "INFO",
  "logger": "zowbot",
  "message": "Connected",
  "ts": "2026-05-11 15:05:01",
  "seq": 10231
}
```

### F. qr_updated

```json
{
  "session_id": "qr-session-uuid",
  "format": "ascii|png_base64",
  "content": "...",
  "expires_at": 1778445900
}
```

### G. message_ingested（可选，后续阶段）

```json
{
  "phone": "8613800138000",
  "message_id": "wamid....",
  "user_jid": "8613911111111@s.whatsapp.net",
  "direction": "in",
  "timestamp": 1778445710
}
```

---

## 9. Bot 列表同步策略（重点）

采用双机制：

1. Agent 主动上报
   - 连接成功后立即发送 `bot_snapshot`
   - 运行中用 `bot_status_changed` 发送增量
2. Backend 主动拉取
   - 定时（如 30s~60s）发送 `list_bots` 进行校准
   - 当检测到心跳恢复、状态异常或数据漂移时立即触发拉取

聚合规则（Backend）：

1. 单一 phone 只允许绑定一个主 Agent（避免双主冲突）
2. 若同一 phone 收到多个来源，以“最近心跳 + 主绑定”决策
3. 前端展示只读取 Backend 聚合结果

---

## 10. 日志链路改造（重点）

## 10.1 现状问题

当前 backend 通过本地 tail `logs/*.log` 推送实时日志，适用于同机部署；远程 agent/bot 不适用。

## 10.2 目标方案

1. Agent 采集本机 bot 日志并发送 `bot_log` 事件
2. Backend 接收后：
   - 写入内存 ring buffer（用于 ws snapshot）
   - 按需持久化（可选）
   - 广播给前端订阅房间
3. 单机模式保留本地 tail 作为兼容 fallback

## 10.3 日志背压建议

1. 批量上报（每 100ms 或每 50 条）
2. 限速（每 bot 每秒最大 N 条）
3. 超限策略：降采样 + `dropped_count` 统计
4. 断线重连后可按 `seq` 补偿最近窗口（可选）

---

## 11. 幂等与重试

## 11.1 幂等键

建议使用 `(agent_id, msg_id)` 作为幂等主键。

## 11.2 重试策略

1. Backend 对 command 在 `timeout` 后可重试（最多 2~3 次）
2. Agent 对 event 发送失败可本地短缓存重投
3. 所有重复消息必须可安全去重

---

## 12. 错误码草案

统一错误对象：

```json
{
  "code": "AGENT_AUTH_FAILED",
  "message": "invalid agent key",
  "retryable": false,
  "detail": {}
}
```

建议错误码：

1. 认证类
   - `AGENT_AUTH_FAILED`
   - `AGENT_DISABLED`
   - `SESSION_EXPIRED`
2. 命令类
   - `COMMAND_NOT_SUPPORTED`
   - `BOT_ALREADY_RUNNING`
   - `BOT_NOT_FOUND`
   - `BOT_START_FAILED`
   - `COMMAND_TIMEOUT`
3. 系统类
   - `INTERNAL_ERROR`
   - `RATE_LIMITED`
   - `PAYLOAD_INVALID`

---

## 13. 最小可行接口集（MVP）

MVP 必选：

1. `agent_auth` / `agent_auth_ok`
2. `agent_online` / `agent_heartbeat`
3. `start_bot` / `stop_bot` / `list_bots`
4. `command_ack` / `command_result`
5. `bot_snapshot` / `bot_status_changed`
6. `bot_log`

MVP 可后置：

1. `fetch_qr` / `qr_updated`
2. `message_ingested`
3. 断线日志补偿

---

## 14. Backend 对 Frontend 的兼容约束

1. 保持现有 `/api/bot/*` 语义，内部由 driver 路由到 Local 或 Agent。
2. 前端不直接连接 agent，仅连接 backend。
3. 前端增加 agent 维度字段，不破坏旧字段兼容。

---

## 15. 待评审问题（请重点确认）

1. `list_bots` 的主动拉取周期（建议 30s）
2. `bot_log` 是否需要持久化入库（还是仅内存 ring buffer）
3. 单机 fallback 保留时长（灰度结束后是否下线）
4. `bot_snapshot` 是否要求全量字段（例如版本、环境、账号健康度）
5. 一个 phone 是否允许手动迁移到新 agent（建议需要显式迁移操作）

---

## 16. 变更记录

1. v0.1
   - 初版草案
   - 覆盖 bot 列表同步与远程日志改造
