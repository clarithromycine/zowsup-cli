# Agent 接口字段冻结草案（v0.2）

## 1. 目的

本文档是字段级别规范，基于 docs/AGENT_INTERFACE_DRAFT.md 的 v0.1 草案做约束收敛。

目标：

1. 固化 Backend <-> Agent 协议字段
2. 明确必填、可选、类型、枚举、校验规则
3. 提供实现与联调验收基线

当前状态：Draft v0.2（待审核）。

---

## 2. 统一约定

## 2.1 数据类型

1. string
2. int
3. float
4. bool
5. object
6. array
7. null

## 2.2 时间与时区

1. Unix 时间戳字段统一使用秒级 int
2. 字符串时间字段统一使用 UTC 格式 YYYY-MM-DD HH:mm:ss

## 2.3 ID 约束

1. msg_id 使用 UUID v4 字符串
2. agent_id 仅允许 a-z A-Z 0-9 - _，长度 3-64
3. trace_id 可选，建议 UUID v4

## 2.4 枚举值大小写

1. type、name、error code 使用小写加下划线
2. level 使用大写（DEBUG INFO WARNING ERROR CRITICAL）

## 2.5 必填标记

1. Required: 是
2. Optional: 否

---

## 3. Envelope 规范

## 3.1 通用消息结构

```json
{
  "msg_id": "4fc9a8f1-a89a-45db-bf36-6f5e72f8ea79",
  "protocol_version": "1.0",
  "type": "command",
  "name": "start_bot",
  "agent_id": "agent-cn-sh01",
  "timestamp": 1778445600,
  "session_token": "token",
  "payload": {},
  "trace_id": "optional"
}
```

## 3.2 Envelope 字段表

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| msg_id | string | 是 | UUID v4 |
| protocol_version | string | 是 | 当前固定 1.0 |
| type | string | 是 | command command_ack command_result event heartbeat error |
| name | string | 是 | 见 4 和 5 节 |
| agent_id | string | 是 | 3-64，字符集限制见 2.3 |
| timestamp | int | 是 | Unix 秒级 |
| session_token | string | 否 | 鉴权后必须；auth 阶段可空 |
| payload | object | 是 | 可为空对象 |
| trace_id | string | 否 | 建议 UUID v4 |

## 3.3 通用校验规则

1. protocol_version 不匹配时返回 error，code 为 protocol_version_unsupported
2. msg_id 已处理过时，接收方应返回幂等 ACK，不重复执行
3. timestamp 与服务端时钟偏差超过 300 秒时记告警，不直接拒绝

---

## 4. 命令定义（Backend -> Agent）

## 4.1 start_bot

### 请求 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | 7-15 位数字 |
| boot_mode | string | 否 | normal safe，默认 normal |
| env | object | 否 | 允许空对象 |
| env.proxy | string | 否 | 代理配置字符串 |

### 结果 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| ok | bool | 是 | true false |
| phone | string | 是 | 与请求一致 |
| pid | int | 否 | 启动成功时必填 |
| already_running | bool | 否 | 已运行时 true |
| bot_jid | string | 否 | 已知时返回 |
| error | object | 否 | 失败时必填 |

---

## 4.2 stop_bot

### 请求 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | 7-15 位数字 |
| force | bool | 否 | 默认 false |

### 结果 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| ok | bool | 是 | true false |
| phone | string | 是 | 与请求一致 |
| stopped | bool | 是 | 是否真正停止 |
| error | object | 否 | 失败时必填 |

---

## 4.3 get_bot_status

### 请求 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | 7-15 位数字 |

### 结果 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | |
| running | bool | 是 | |
| pid | int | 否 | running=true 时建议返回 |
| bot_jid | string | 否 | |
| started_at | int | 否 | |
| uptime_seconds | int | 否 | |
| error | object | 否 | 异常时返回 |

---

## 4.4 list_bots

### 请求 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| include_stopped | bool | 否 | 默认 true |

### 结果 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| snapshot_id | string | 是 | 建议格式 snap-<ts>-<seq> |
| bots | array | 是 | bot 对象数组 |

bot 对象字段：

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | 7-15 位数字 |
| running | bool | 是 | |
| pid | int | 否 | |
| bot_jid | string | 否 | |
| last_seen | int | 否 | |
| health | string | 否 | ok warn error |

---

## 4.5 fetch_qr

### 请求 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | 7-15 位数字 |
| mode | string | 否 | scan link，默认 scan |

### 结果 payload

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| ok | bool | 是 | |
| session_id | string | 是 | UUID 或可追踪唯一值 |
| error | object | 否 | 失败时返回 |

---

## 4.6 command_ack

type 固定 command_ack，name 与原命令相同。

payload 字段：

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| ack_msg_id | string | 是 | 被确认的 command msg_id |
| accepted | bool | 是 | true 表示已接收 |
| reason | string | 否 | rejected 时原因 |

---

## 4.7 command_result

type 固定 command_result，name 与原命令相同。

payload 字段：

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| command_msg_id | string | 是 | 对应 command msg_id |
| status | string | 是 | succeeded failed timeout |
| result | object | 否 | succeeded 时建议返回 |
| error | object | 否 | failed timeout 时建议返回 |

---

## 5. 事件定义（Agent -> Backend）

## 5.1 agent_online

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| hostname | string | 是 | 1-255 |
| ip | string | 否 | IPv4 IPv6 |
| agent_version | string | 是 | semver |
| capabilities | array | 是 | string 数组 |
| tags | array | 否 | string 数组 |

---

## 5.2 agent_heartbeat

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| load | object | 是 | |
| load.cpu_pct | float | 否 | 0-100 |
| load.mem_pct | float | 否 | 0-100 |
| bot_count | int | 是 | >=0 |
| running_count | int | 是 | >=0 |
| queue_backlog | int | 否 | >=0 |

---

## 5.3 bot_snapshot

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| snapshot_id | string | 是 | 唯一快照号 |
| bots | array | 是 | 同 4.4 bot 对象 |

规则：

1. Agent 连接后 3 秒内必须至少发送一次
2. Backend 收到后覆盖该 Agent 的 bot 全量视图

---

## 5.4 bot_status_changed

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | |
| running | bool | 是 | |
| pid | int | 否 | |
| bot_jid | string | 否 | |
| reason | string | 否 | manual_stop crash restart login_success |
| changed_at | int | 是 | Unix 秒级 |

---

## 5.5 bot_log

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | |
| level | string | 是 | DEBUG INFO WARNING ERROR CRITICAL |
| logger | string | 否 | |
| message | string | 是 | 建议 <= 4000 字符 |
| ts | string | 是 | UTC 字符串 |
| seq | int | 是 | 每 phone 单调递增 |
| dropped_count | int | 否 | 背压丢弃计数 |

规则：

1. 同一 phone 下 seq 必须递增
2. Backend 可按 seq 去重与缺口检测

---

## 5.6 qr_updated

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| session_id | string | 是 | 对应 fetch_qr 返回 |
| format | string | 是 | ascii png_base64 |
| content | string | 是 | 数据本体 |
| expires_at | int | 否 | Unix 秒级 |

---

## 5.7 message_ingested（可后置）

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| phone | string | 是 | |
| message_id | string | 是 | 全局消息 ID |
| user_jid | string | 是 | |
| direction | string | 是 | in out |
| timestamp | int | 是 | Unix 秒级 |

---

## 6. 错误对象规范

## 6.1 错误对象结构

```json
{
  "code": "bot_start_failed",
  "message": "failed to spawn process",
  "retryable": true,
  "detail": {
    "phone": "8613800138000"
  }
}
```

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| code | string | 是 | 见 6.2 |
| message | string | 是 | 人类可读 |
| retryable | bool | 是 | |
| detail | object | 否 | 附加信息 |

## 6.2 错误码枚举（首批）

1. auth_failed
2. agent_disabled
3. session_expired
4. payload_invalid
5. command_not_supported
6. bot_already_running
7. bot_not_found
8. bot_start_failed
9. command_timeout
10. internal_error
11. protocol_version_unsupported

---

## 7. 幂等、重试、超时

## 7.1 幂等

1. 去重键：(agent_id, msg_id)
2. 保留窗口：建议 24 小时
3. 重复 command：返回同一 command_result，不重复执行副作用

## 7.2 超时

| 命令 | 建议超时 |
|---|---|
| start_bot | 60 秒 |
| stop_bot | 30 秒 |
| get_bot_status | 10 秒 |
| list_bots | 15 秒 |
| fetch_qr | 20 秒 |

## 7.3 重试

1. Backend command 重试次数：最多 2 次
2. command 非幂等场景禁止自动重试
3. Agent event 发送失败采用指数退避，最大 30 秒

---

## 8. Bot 列表一致性规则

1. 主视图来源：Backend 聚合表
2. 聚合输入：bot_snapshot + bot_status_changed + 主动 list_bots 校准
3. 冲突处理：同 phone 仅允许一个主 Agent
4. 校准周期：默认 30 秒，可配置

---

## 9. 日志链路约束

1. Agent 模式以 bot_log 事件作为主链路
2. Local 模式允许继续本地 tail 作为兼容
3. 每 bot 建议上限 200 行每秒，超限触发 dropped_count
4. message 超长按 4000 字符截断并标记 truncated

---

## 10. 安全扩展字段（v0.5 提案）

Envelope 可选字段：security

| 字段 | 类型 | Required | 约束 |
|---|---|---|---|
| security | object | 否 | 启用签名后必填 |
| security.kid | string | 是 | key 标识，1-128 |
| security.alg | string | 是 | hmac-sha256 |
| security.nonce | string | 是 | 16-128，base64url 字符集 |
| security.signed_at | int | 是 | Unix 秒级 |
| security.signature | string | 是 | base64url 字符串 |

规则建议：

1. 签名串采用 canonical JSON（固定字段顺序，不含 security.signature）
2. 签名算法为 HMAC-SHA256
3. 防重放窗口默认 300 秒
4. nonce 在窗口内不可重复

---

## 11. 评审清单

请重点确认：

1. 字段命名是否全部接受
2. 错误码命名风格是否接受
3. list_bots 校准周期是否接受默认 30 秒
4. bot_log seq 递增规则是否接受
5. 是否要求 bot_log 持久化入库
6. 是否启用 envelope security 签名扩展

---

## 12. 变更记录

1. v0.2
   - 新增字段级规范
   - 固化 Required Optional 类型与校验
   - 固化首批命令事件错误码
2. v0.5-draft
  - 新增 security 扩展字段与防重放规则建议