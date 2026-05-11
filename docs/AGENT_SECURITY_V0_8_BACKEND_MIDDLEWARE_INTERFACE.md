# Agent 安全层 v0.8：Backend 中间件接口草图

## 1. 目标

把 v0.7 状态机转为可落地的 Backend 接口设计，便于直接分配开发任务。

覆盖：

1. 中间件入口函数
2. 输入输出结构
3. key_store 与 nonce_store 抽象
4. 错误返回契约
5. 在 websocket 接入链路的集成点

---

## 2. 建议模块结构

建议新增目录：

1. app/dashboard/agent_security/

建议文件：

1. interfaces.py
   - 协议与数据结构
2. verifier.py
   - verify_message_security 主逻辑
3. canonical.py
   - canonicalize_message 与 sign helpers
4. stores.py
   - key_store / nonce_store 适配层（内存版 + 生产版）
5. errors.py
   - SecurityError 枚举与工厂

---

## 3. 类型定义草图

## 3.1 VerifyContext

字段：

1. now_ts: int
2. require_security: bool
3. window_seconds: int

## 3.2 SecurityDecision

字段：

1. accepted: bool
2. code: string
3. message: string
4. retryable: bool
5. audit: object

说明：

1. accepted=true 时 code 固定 ok
2. accepted=false 时 code 为 reject code

## 3.3 KeyRecord

字段：

1. kid: string
2. secret: bytes
3. revoked: bool
4. expires_at: int

---

## 4. 存储接口契约

## 4.1 KeyStore

函数：

1. get_active_key(kid: string) -> KeyRecord | None

契约：

1. kid 不存在返回 None
2. secret 必须可直接用于 HMAC

## 4.2 NonceStore

函数：

1. exists(agent_id: string, nonce: string) -> bool
2. put(agent_id: string, nonce: string, ttl_seconds: int) -> None

契约：

1. exists 仅在窗口内返回 true
2. put 必须具备 TTL 语义

---

## 5. 核心中间件接口

建议函数签名：

1. verify_message_security(message: object, ctx: VerifyContext, key_store: KeyStore, nonce_store: NonceStore) -> SecurityDecision

行为：

1. 仅负责安全校验，不执行业务命令
2. 成功后由上层继续命令/事件处理
3. 失败时返回标准 SecurityDecision

---

## 6. 错误返回契约

标准返回：

```json
{
  "accepted": false,
  "code": "signature_invalid",
  "message": "signature mismatch",
  "retryable": false,
  "audit": {
    "agent_id": "agent-cn-sh01",
    "msg_id": "...",
    "kid": "agent-cn-sh01-key-202605",
    "signed_at": 1778445605,
    "now_ts": 1778445610,
    "delta_seconds": 5
  }
}
```

错误码沿用 v0.7：

1. payload_invalid
2. key_not_found
3. key_revoked
4. signed_at_out_of_window
5. replay_detected
6. signature_invalid
7. internal_error

---

## 7. 集成位置建议

## 7.1 WebSocket Agent 网关入口

建议在 agent 消息反序列化后立即调用：

1. parse json
2. schema validate
3. verify_message_security
4. accepted -> dispatch
5. rejected -> reply error + audit

## 7.2 与现有认证关系

建议顺序：

1. 连接级鉴权（agent_auth / session_token）
2. 消息级验签（security）

说明：

1. session_token 解决会话与权限
2. security 解决完整性与防重放

---

## 8. 观测指标建议

建议最少指标：

1. security_verify_total{result=accept|reject,code=*}
2. security_verify_latency_ms
3. security_replay_detected_total
4. security_signature_invalid_total

---

## 9. 开发任务拆分（直接可分派）

1. 实现 interfaces.py 与类型定义
2. 实现 canonical.py（与 v0.6 向量对齐）
3. 实现 verifier.py（对齐 v0.7 状态机）
4. 实现 InMemoryNonceStore（开发环境）
5. 预留 RedisNonceStore（生产环境）
6. 在 websocket 入口接入中间件
7. 输出审计日志与 metrics
8. 用 v0.7 用例回归

---

## 10. 验收标准

1. v0.7 用例全部通过
2. 签名向量回归通过
3. 重放消息被稳定拒绝
4. reject 返回结构稳定且可观测

---

## 11. 变更记录

1. v0.8
   - 新增 backend 中间件接口草图
   - 明确输入输出契约与集成位点
