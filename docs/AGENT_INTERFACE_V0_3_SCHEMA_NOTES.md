# Agent 协议 v0.3 机器可读草案说明

本次新增文件：

1. docs/agent-protocol.schema.json
2. docs/agent-asyncapi-v0.3.yaml
3. docs/agent-protocol-fixtures/valid/*.json
4. docs/agent-protocol-fixtures/invalid/*.json
5. script/validate_agent_protocol_fixtures.py

用途：

1. agent-protocol.schema.json
   - 用于单条消息 JSON 校验
   - 可在单元测试和联调前置校验中直接使用
2. agent-asyncapi-v0.3.yaml
   - 用于协议评审、消息目录和后续代码生成探索
3. fixtures + 校验脚本
   - 用于联调前置验证（valid 必须通过，invalid 必须失败）

---

## 建议评审顺序

1. 先审字段规范文档
   - docs/AGENT_INTERFACE_V0_2_FIELD_SPEC.md
2. 再审 JSON Schema 是否与字段表一致
   - docs/agent-protocol.schema.json
3. 最后审 AsyncAPI 的消息目录完整性
   - docs/agent-asyncapi-v0.3.yaml

---

## 建议下步动作

1. 冻结错误码枚举与命名（是否保留 snake_case）
2. 冻结命令超时策略（start_bot 是否 60s）
3. 确认 bot_log 是否落库
4. 评估是否补充签名字段（message signature）

---

## v0.4 校验执行方式

1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install jsonschema
```

2. 执行校验

```bash
python script/validate_agent_protocol_fixtures.py
```

3. 期望结果

- `docs/agent-protocol-fixtures/valid/` 下样例全部 PASS
- `docs/agent-protocol-fixtures/invalid/` 下样例全部 PASS invalid

---

## 变更记录

1. v0.3
   - 新增 JSON Schema 与 AsyncAPI 草案
   - 对齐 v0.2 字段冻结文档
2. v0.4
   - 新增 valid/invalid fixtures
   - 新增一键校验脚本
3. v0.5-draft
   - schema 增加 envelope security 扩展字段
   - 新增安全专项文档 AGENT_SECURITY_V0_5.md
4. v0.6
   - 新增 canonical 签名规范文档 AGENT_SECURITY_V0_6_CANONICAL_SIGNING.md
   - 新增签名测试向量 docs/agent-protocol-fixtures/signing/
   - 新增零依赖验签脚本 script/verify_agent_signing_vectors.py
5. v0.7
   - 新增 backend 验签状态机文档 AGENT_SECURITY_V0_7_BACKEND_VERIFICATION_STATE_MACHINE.md
   - 新增安全判定用例 docs/agent-protocol-fixtures/security/verification_cases.json
   - 新增零依赖评估脚本 script/evaluate_agent_security_cases.py
6. v0.8
   - 新增 backend 中间件接口草图 AGENT_SECURITY_V0_8_BACKEND_MIDDLEWARE_INTERFACE.md
   - 新增开发契约文件 app/dashboard/agent_security_contract.py
7. v0.9
   - 新增最小可运行 verifier 参考实现（app/dashboard/agent_security/）
   - v0.7 评估脚本切换到真实 verifier

---

## 无 venv 执行方式

若不使用 venv，可在受控环境中直接执行：

```bash
python3 script/verify_agent_signing_vectors.py
```

该脚本仅依赖 Python 标准库，不需要额外安装第三方包。

v0.7 也可无依赖执行：

```bash
python3 script/evaluate_agent_security_cases.py
```
