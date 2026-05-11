# Agent 安全层 v0.6：Canonical 签名与测试向量

## 1. 目标

定义可跨语言复现的签名规则，消除不同实现间验签不一致问题。

本版本新增：

1. Canonical JSON 规则
2. 签名串构造规则
3. HMAC-SHA256 base64url 输出规则
4. 标准测试向量

---

## 2. Canonical JSON 规则

对待签名消息执行以下步骤：

1. 使用完整 Envelope 对象
2. 如果存在 security.signature 字段，先删除该字段
3. 保留 security 其余字段（kid alg nonce signed_at）
4. 使用 UTF-8 编码
5. 使用 JSON 序列化参数：
   - sort_keys = true
   - separators = ("," , ":")
   - ensure_ascii = false
6. 不添加任何额外空格或换行

说明：

1. 数字保持 JSON 原生数字类型
2. 布尔保持 true false
3. null 保持 null

---

## 3. 签名算法

算法：

1. hmac-sha256

计算：

1. signature_raw = HMAC_SHA256(key_bytes, canonical_json_utf8_bytes)
2. signature = base64url(signature_raw) 并去掉末尾等号

示例字段：

1. security.alg = hmac-sha256
2. security.signature = 计算结果

---

## 4. 验签规则

Backend 验签建议顺序：

1. 检查 security.kid 是否存在且可用
2. 检查 signed_at 是否在允许窗口内
3. 检查 nonce 是否重复
4. 重新 canonical 化消息（去除 signature）
5. 使用 kid 对应密钥重算签名
6. 常量时间比较 signature

---

## 5. 测试向量

测试向量文件：

1. docs/agent-protocol-fixtures/signing/vector_01_hmac_sha256.json

该向量包含：

1. key
2. message
3. canonical_json
4. expected_signature

期望签名：

1. 56oqes8bZRFi-oUnmhuutfZOY4owirRyZObURRW9r8w

---

## 6. 常见错误

1. 把 signature 本身也参与签名
2. 未排序 key 导致 canonical 串不一致
3. 使用普通 base64 而非 base64url
4. 输出未去掉等号
5. 使用了不同字符编码（非 UTF-8）

---

## 7. 建议实现清单

1. 提供统一 canonicalize 函数
2. 提供 sign 与 verify 两个基础函数
3. 在 CI 中加入向量回归测试
4. 版本升级时新增向量不覆盖旧向量

---

## 8. 变更记录

1. v0.6
   - 新增 canonical 签名规则
   - 新增首个跨语言对拍向量
