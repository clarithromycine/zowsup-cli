# Agent 安全层 v0.7：Backend 验签与防重放状态机

## 1. 目标

将 v0.5 与 v0.6 的安全策略落到 Backend 可实现状态机，明确每一步输入、判定、输出与错误码。

覆盖范围：

1. Envelope security 字段校验
2. kid 查找与 key 状态检查
3. 时间窗口检查
4. nonce 去重检查
5. canonical 重建与签名比对
6. 通过后进入业务执行

---

## 2. 输入与依赖

输入：

1. 接收到的完整消息对象
2. 接收时间 now

依赖：

1. key 存储
   - 根据 security.kid 获取 key_record
2. nonce 存储
   - 查询与写入 (agent_id, nonce)
3. canonical + hmac 计算器

---

## 3. 状态机定义

状态列表：

1. S0_RECEIVED
2. S1_BASIC_SECURITY_FIELDS
3. S2_KEY_LOOKUP
4. S3_KEY_STATUS_CHECK
5. S4_TIME_WINDOW_CHECK
6. S5_NONCE_CHECK
7. S6_CANONICAL_REBUILD
8. S7_SIGNATURE_VERIFY
9. S8_MARK_NONCE_AND_ACCEPT
10. S9_REJECT

终态：

1. ACCEPT
2. REJECT

---

## 4. 转移规则

## 4.1 S0_RECEIVED -> S1_BASIC_SECURITY_FIELDS

条件：

1. 消息进入安全校验入口

动作：

1. 读取 security 对象

失败转移：

1. security 缺失且策略为 required -> REJECT(code=payload_invalid)

---

## 4.2 S1_BASIC_SECURITY_FIELDS -> S2_KEY_LOOKUP

检查项：

1. kid 存在
2. alg = hmac-sha256
3. nonce 存在且格式合法
4. signed_at 为整数时间戳
5. signature 存在

失败转移：

1. 任一字段不合法 -> REJECT(code=payload_invalid)

---

## 4.3 S2_KEY_LOOKUP -> S3_KEY_STATUS_CHECK

检查项：

1. 根据 kid 查到 key

失败转移：

1. 未找到 -> REJECT(code=key_not_found)

---

## 4.4 S3_KEY_STATUS_CHECK -> S4_TIME_WINDOW_CHECK

检查项：

1. key 未吊销
2. key 在有效期内

失败转移：

1. 已吊销 -> REJECT(code=key_revoked)
2. 过期 -> REJECT(code=key_revoked)

---

## 4.5 S4_TIME_WINDOW_CHECK -> S5_NONCE_CHECK

检查项：

1. abs(now - signed_at) <= window_seconds

失败转移：

1. 超窗 -> REJECT(code=signed_at_out_of_window)

---

## 4.6 S5_NONCE_CHECK -> S6_CANONICAL_REBUILD

检查项：

1. (agent_id, nonce) 在窗口内未出现

失败转移：

1. 已出现 -> REJECT(code=replay_detected)

---

## 4.7 S6_CANONICAL_REBUILD -> S7_SIGNATURE_VERIFY

动作：

1. 删除 security.signature
2. 对消息 canonical 序列化
3. 用 key 计算 hmac-sha256
4. base64url no padding 编码

失败转移：

1. canonical 失败 -> REJECT(code=internal_error)

---

## 4.8 S7_SIGNATURE_VERIFY -> S8_MARK_NONCE_AND_ACCEPT

检查项：

1. 常量时间比较 expected_signature 与 incoming_signature

失败转移：

1. 不匹配 -> REJECT(code=signature_invalid)

---

## 4.9 S8_MARK_NONCE_AND_ACCEPT -> ACCEPT

动作：

1. 写入 nonce 存储，TTL=window_seconds
2. 标记校验通过
3. 交由业务命令/事件处理链路

---

## 5. 错误码映射

| 场景 | 错误码 | retryable |
|---|---|---|
| security 字段缺失或格式错误 | payload_invalid | false |
| kid 不存在 | key_not_found | false |
| key 失效或吊销 | key_revoked | false |
| signed_at 超窗 | signed_at_out_of_window | true |
| nonce 重复 | replay_detected | false |
| signature 不匹配 | signature_invalid | false |
| 内部异常 | internal_error | true |

---

## 6. 观测与审计建议

必须记录：

1. agent_id
2. msg_id
3. kid
4. decision = accept reject
5. reject_code
6. now 与 signed_at 差值

告警建议：

1. 单 agent 五分钟内 replay_detected 超阈值
2. 单 agent 连续 signature_invalid 超阈值
3. key_not_found 高峰告警

---

## 7. 伪代码

```text
verify(message, now):
  sec = message.security
  if required and missing(sec): reject(payload_invalid)
  validate_basic(sec) or reject(payload_invalid)

  key = key_store.get(sec.kid)
  if not key: reject(key_not_found)
  if key.revoked or key.expired: reject(key_revoked)

  if abs(now - sec.signed_at) > WINDOW: reject(signed_at_out_of_window)
  if nonce_store.exists(message.agent_id, sec.nonce): reject(replay_detected)

  expected = sign(canonical_without_signature(message), key.secret)
  if not constant_time_equal(expected, sec.signature): reject(signature_invalid)

  nonce_store.put(message.agent_id, sec.nonce, ttl=WINDOW)
  accept()
```

---

## 8. 开发拆分任务

1. 实现 canonical 与 sign 基础库
2. 实现 security_verifier 模块
3. 接入 key_store 与 nonce_store 抽象
4. 加入 metrics 与 audit log
5. 集成到 websocket 消息入口中间件

---

## 9. 变更记录

1. v0.7
   - 新增 backend 验签状态机
   - 新增状态-错误码映射
   - 新增可开发拆分任务
