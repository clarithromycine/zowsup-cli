# 网络连接超时和中断处理改进方案

## 🔴 问题描述

**原始问题**：当服务器连不上（例如网络不好的情况），程序会卡住，Ctrl+C 也无法中止。

### 问题细节

1. **连接阶段无法中断**（特别是登录等待时）
   - 主线程在 `main.py` 的 `thread.join()` 处被完全阻塞
   - 子线程的 asyncio event loop 也在等待登录
   - 导致 Ctrl+C 信号无法被任何线程捕获

2. **网络超时问题**
   - Socket 连接没有超时限制
   - 协议读写没有超时限制

### 根本原因

1. **主线程阻塞** - `join()` 不允许中断
2. **子线程等待不可中断** - 登录等待循环不能被异步取消
3. **网络操作无超时** - socket 和协议层操作会无限等待

## ✅ 实施的修复

### 1. **main.py - 主线程中断响应**

```python
# 改进点：
- 改用带超时的 join() 循环替代阻塞的 join()
- 主线程现在能每 0.1 秒检查一次中断信号
- Ctrl+C 能立即被捕获并传递到子线程

# 代码改变：
# ❌ 之前：
thread.join()  # 完全阻塞，无法中断

# ✅ 之后：
while thread.is_alive():
    thread.join(timeout=0.1)  # 每 0.1 秒检查一次
```

### 2. **interactivethread.py - 异步等待优化**

```python
# 改进点：
- 登录等待不再使用固定循环，改用时间基准
- asyncio.sleep() 现在被 asyncio.wait_for() 包装，可被中断
- 添加了 CancelledError 异常处理

# 效果：
- 等待登录时按 Ctrl+C 现在能立即响应
- 不再需要等待 0.5 秒的检查间隔
```

### 3. **dispatcher_asyncio.py - 网络连接和读取超时**

```python
# 改进点：
- 为 asyncio.open_connection() 添加 timeout=CONNECT_TIMEOUT（30秒）
- 为 _read_loop() 中的 read() 添加 timeout=READ_TIMEOUT（60秒）
- 为 drain() 添加 timeout=WRITE_TIMEOUT（30秒）
```

### 4. **async_wa.py - 协议段读写超时**

```python
# 改进点：
- 为 readexactly(3) [读取头部] 添加 timeout=SEGMENT_READ_TIMEOUT（60秒）
- 为 readexactly(size) [读取数据] 添加 timeout=SEGMENT_READ_TIMEOUT（60秒）
- 为 drain() 添加 timeout=SEGMENT_WRITE_TIMEOUT（30秒）
```

### 5. **interactivethread.py - 信号处理改进**

```python
# 改进点：
- 添加了 signal.SIGINT 处理器（Unix/Linux 系统）
- 改进了 KeyboardInterrupt 异常处理（Windows 系统）
- 添加了优雅的 event loop 关闭流程
```

### 6. **network_config.py - 集中化超时配置**

```python
# 可配置的超时参数：
CONNECT_TIMEOUT = 30        # TCP 连接超时
READ_TIMEOUT = 60           # 读取超时
WRITE_TIMEOUT = 30          # 写入超时
SEGMENT_READ_TIMEOUT = 60   # 协议段读取超时
SEGMENT_WRITE_TIMEOUT = 30  # 协议段写入超时
```

## 📊 改进效果

| 场景 | 之前 | 之后 |
|------|------|------|
| 网络无响应 | 🔴 无限卡住 | 🟢 30秒后超时并重连 |
| 数据读取卡顿 | 🔴 无限等待 | 🟢 60秒后超时并重连 |
| **登录等待时 Ctrl+C** | 🔴 **完全无响应** | 🟢 **立即响应** |
| Ctrl+C 中止 | 🔴 可能不工作 | 🟢 立即响应，优雅关闭 |
| 连接错误恢复 | 🔴 手动重启 | 🟢 自动超时重连 |
| 资源清理 | 🔴 可能泄漏 | 🟢 完整清理 |

### 关键改进

✨ **登录等待时 Ctrl+C 现在有效**（这是本次修复的重点）
  - 主线程改用 `join(timeout=0.1)` 循环
  - 子线程登录等待改用 `asyncio.wait_for()` 包装
  - 用户现在能在连接阶段按 Ctrl+C 中断

## 🔧 自定义超时

如果需要根据网络环境调整超时时间，编辑 `conf/network_config.py`：

```python
# 网络很差的环境 - 增加超时时间
CONNECT_TIMEOUT = 60    # 改为 60 秒
READ_TIMEOUT = 120      # 改为 120 秒
SEGMENT_READ_TIMEOUT = 120  # 改为 120 秒

# 网络良好的环境 - 减少超时时间
CONNECT_TIMEOUT = 15    # 改为 15 秒
READ_TIMEOUT = 30       # 改为 30 秒
```

## 📝 日志示例

### 正常连接
```
INFO: Connected to 142.251.45.121:443
DEBUG: Read loop started
```

### 连接超时
```
ERROR: Connection timeout to 142.251.45.121:443 after 30s
ERROR: Connection failed: Connection to 142.251.45.121:443 timed out after 30s
```

### 读取超时
```
WARNING: Read timeout after 60s, disconnecting
ERROR: Read loop error: Connection closed
```

### Ctrl+C 中断
```
INFO: Received Ctrl+C signal, initiating shutdown...
DEBUG: Read loop cancelled
INFO: InteractiveThread shutting down
```

## 💡 技术细节

### 为什么 asyncio.wait_for() ？

```python
# ❌ 不行 - 没有超时
await stream.read(1024)

# ✅ 正确 - 有超时
await asyncio.wait_for(stream.read(1024), timeout=60)
```

### 超时异常处理链

```python
try:
    data = await asyncio.wait_for(read_operation, timeout=60)
except asyncio.TimeoutError:
    # 超时 - 断开连接，自动重连
    disconnect()
except asyncio.CancelledError:
    # 被取消 (Ctrl+C) - 优雅关闭
    return
except Exception:
    # 其他错误 - 记录日志，清理资源
    error_handler()
```

### 信号处理 (Unix/Linux)

```python
# 注册 SIGINT (Ctrl+C) 处理器
loop.add_signal_handler(signal.SIGINT, handle_interrupt, loop)

# 处理器：
def handle_interrupt(loop):
    loop.stop()  # 停止 event loop
```

## 🚀 后续优化建议

1. **指数退避重试**：改进连接失败时的重试策略
2. **连接池管理**：为频繁连接的场景添加连接复用
3. **心跳检测**：定期发送心跳包检测连接是否活跃
4. **自适应超时**：根据网络延迟动态调整超时时间

## ✨ 总结

通过添加超时控制和信号处理，解决了以下问题：
- ✅ 网络不好时程序不再卡死
- ✅ Ctrl+C 能立即响应
- ✅ 自动重连机制更可靠
- ✅ 资源清理更完整
- ✅ 错误日志更详细
