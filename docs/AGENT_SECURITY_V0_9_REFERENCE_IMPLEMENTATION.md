# Agent 安全层 v0.9：最小参考实现说明

## 1. 本版目标

在 v0.8 契约基础上，提供可运行最小实现，并用 v0.7 用例回归。

本版结果：

1. verifier 可运行
2. InMemoryKeyStore / InMemoryNonceStore 可运行
3. v0.7 用例脚本已切换到真实实现

---

## 2. 新增实现文件

1. app/dashboard/agent_security/canonical.py
2. app/dashboard/agent_security/stores.py
3. app/dashboard/agent_security/verifier.py
4. app/dashboard/agent_security/__init__.py

契约入口保持不变：

1. app/dashboard/agent_security_contract.py

---

## 3. 验证方式

1. 运行 v0.7 安全判定用例

```bash
python3 script/evaluate_agent_security_cases.py
```

2. 期望输出

- 所有 case PASS

---

## 4. 当前边界

1. 仅提供内存 nonce/key 存储实现
2. 未接入 websocket 网关真实入口
3. 未输出 metrics 与审计到生产链路

---

## 5. 下一步建议（v1.0 前）

1. 增加 RedisNonceStore
2. 增加 DBKeyStore 或 KMS 适配
3. 在 agent websocket 入口接入 verify_message_security
4. 增加 reject telemetry 与审计日志
5. 增加并发与时钟漂移测试

---

## 6. 变更记录

1. v0.9
   - 新增最小可运行参考实现
   - 评估脚本切换为调用真实 verifier
