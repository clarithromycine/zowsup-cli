# Agent 安全层草案（v0.5）

## 1. 目标

为 Backend <-> Agent 通信增加可审计、可轮换、可防重放的消息级安全能力。

本草案聚焦：

1. 消息签名
2. 防重放
3. key 管理与轮换
4. 失败处理策略

---

## 2. 威胁模型

重点防护：

1. 消息被篡改
2. 消息重放
3. 已失效 key 被继续使用
4. 时间漂移导致的错误拒绝

非目标（由传输层处理）：

1. 明文窃听（由 WSS/TLS 处理）
2. 中间人证书攻击（由证书校验和 pinning 策略处理）

---

## 3. 安全字段（Envelope 扩展）

```json
"security": {
  "kid": "agent-cn-sh01-key-202605",
  "alg": "hmac-sha256",
  "nonce": "Q9R2m3c1_Nxq8W0a",
  "signed_at": 1778445605,
  "signature": "base64url(...)"
}
```

字段说明：

1. kid
   - key 标识，用于后端定位验签 key
2. alg
   - 固定 hmac-sha256（首阶段不开放多算法）
3. nonce
   - 每条消息唯一随机串，防重放
4. signed_at
   - 签名时间戳
5. signature
   - 对 canonical 字符串做 HMAC-SHA256 后 base64url 编码

---

## 4. 签名流程

## 4.1 待签名字段

建议包含：

1. msg_id
2. protocol_version
3. type
4. name
5. agent_id
6. timestamp
7. session_token（如果存在）
8. payload
9. trace_id（如果存在）
10. security.kid
11. security.alg
12. security.nonce
13. security.signed_at

注意：

1. security.signature 本身不参与签名
2. 采用 canonical JSON，确保字段顺序稳定

## 4.2 验签流程

Backend 侧步骤：

1. 根据 kid 找到活跃 key
2. 检查 signed_at 与当前时间差是否在窗口内
3. 检查 nonce 是否已被使用
4. 复算 signature 并比较
5. 验签通过后再执行业务逻辑

---

## 5. 防重放策略

1. 时间窗口
   - 默认 300 秒
2. nonce 去重
   - 以 agent_id + nonce 作为唯一键
3. 去重存储
   - 使用内存缓存 + TTL（如 Redis 或本地 LRU）
4. 失败处理
   - 超窗或 nonce 重复返回 replay_detected

---

## 6. Key 生命周期

## 6.1 生成与存储

1. key 长度 >= 32 bytes
2. 后端仅保存 key hash 或密文
3. 明文只在创建时返回一次

## 6.2 轮换

1. 支持双 key 并存（旧 key + 新 key）
2. 轮换窗口建议 24 小时
3. 窗口结束后禁用旧 key

## 6.3 吊销

1. 支持按 kid 立即吊销
2. 吊销后 session 立即失效

---

## 7. 错误码扩展建议

新增错误码：

1. signature_invalid
2. replay_detected
3. signed_at_out_of_window
4. key_not_found
5. key_revoked

---

## 8. 落地顺序（建议）

1. 阶段 A
   - 保持 security 可选，仅记录验签结果
2. 阶段 B
   - 对 command 强制 security
3. 阶段 C
   - 对 event 也强制 security
4. 阶段 D
   - 启用 replay 拒绝与告警阈值

---

## 9. 验收清单

1. 同一消息篡改 payload 后验签失败
2. 同 nonce 重放在窗口内被拒绝
3. signed_at 超窗被拒绝
4. key 轮换窗口内新旧 key 均可通过
5. 旧 key 吊销后立即失败

---

## 10. 变更记录

1. v0.5-draft
   - 初版安全层设计
   - 增加签名、防重放、key 生命周期策略
