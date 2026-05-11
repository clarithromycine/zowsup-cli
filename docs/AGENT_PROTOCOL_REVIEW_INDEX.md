# Agent 协议评审索引

按阅读顺序建议：

1. 总体规划
   - PLAN.md
2. 接口草案 v0.1
   - docs/AGENT_INTERFACE_DRAFT.md
3. 字段冻结草案 v0.2
   - docs/AGENT_INTERFACE_V0_2_FIELD_SPEC.md
4. 机器可读协议 v0.3
   - docs/agent-protocol.schema.json
   - docs/agent-asyncapi-v0.3.yaml
   - docs/AGENT_INTERFACE_V0_3_SCHEMA_NOTES.md
5. 样例与校验 v0.4
   - docs/agent-protocol-fixtures/valid/
   - docs/agent-protocol-fixtures/invalid/
   - script/validate_agent_protocol_fixtures.py
6. 安全扩展 v0.5
   - docs/AGENT_SECURITY_V0_5.md
7. canonical 签名与测试向量 v0.6
   - docs/AGENT_SECURITY_V0_6_CANONICAL_SIGNING.md
   - docs/agent-protocol-fixtures/signing/vector_01_hmac_sha256.json
   - script/verify_agent_signing_vectors.py
8. backend 验签状态机 v0.7
   - docs/AGENT_SECURITY_V0_7_BACKEND_VERIFICATION_STATE_MACHINE.md
   - docs/agent-protocol-fixtures/security/verification_cases.json
   - script/evaluate_agent_security_cases.py
9. backend 中间件接口草图 v0.8
   - docs/AGENT_SECURITY_V0_8_BACKEND_MIDDLEWARE_INTERFACE.md
   - app/dashboard/agent_security_contract.py
10. 最小参考实现 v0.9
   - docs/AGENT_SECURITY_V0_9_REFERENCE_IMPLEMENTATION.md
   - app/dashboard/agent_security/
   - script/evaluate_agent_security_cases.py（已切到真实 verifier）

---

当前可直接执行（无 venv）：

1. 签名向量校验

```bash
python3 script/verify_agent_signing_vectors.py
```

2. 验签状态机用例评估

```bash
python3 script/evaluate_agent_security_cases.py
```

需要第三方依赖（jsonschema）后可执行：

1. 协议 fixtures 校验

```bash
python3 script/validate_agent_protocol_fixtures.py
```
