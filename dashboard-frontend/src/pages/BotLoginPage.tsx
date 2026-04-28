/**
 * BotLoginPage.tsx
 * ─────────────────
 * Phase 5: Bot login management page at route /login.
 *
 * Features:
 *  - Tab selector: 扫描二维码 / 链接码登录
 *  - QR tab: POST /api/bot/login-scan → opens SSE stream /api/bot/qr-stream
 *            QR lines drawn in a <pre> terminal block; auto-refreshes on expiry
 *  - Link-code tab: input phone → POST /api/bot/login-linkcode → show 8-char code
 *  - Successful login → navigate('/') after 2 s
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Space,
  Spin,
  Tabs,
  Typography,
  message,
  Tag,
} from 'antd'
import {
  QrcodeOutlined,
  LinkOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { postBotLoginScan, postBotLoginLinkcode, postBotStart, postBotLogout, fetchBotStatus } from '../api/endpoints'
import { getApiToken } from '../api/client'

const { Title, Paragraph, Text } = Typography

// ────────────────────────────────────────────────────────────────────────────
// QR Tab
// ────────────────────────────────────────────────────────────────────────────

const QrLoginTab: React.FC<{ onLoginSuccess: (jid: string) => void }> = ({ onLoginSuccess }) => {
  const [loading, setLoading] = useState(false)
  const [qrLines, setQrLines] = useState<string[]>([])
  const [statusMsg, setStatusMsg] = useState<string>('')
  const [streamError, setStreamError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  const startScan = useCallback(async () => {
    // Close any existing SSE connection
    esRef.current?.close()
    setQrLines([])
    setStatusMsg('')
    setStreamError(null)
    setLoading(true)

    try {
      await postBotLoginScan()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setStreamError(`启动扫码失败: ${msg}`)
      setLoading(false)
      return
    }

    // Open SSE stream
    const token = getApiToken()
    const url = `/api/bot/qr-stream${token ? `?token=${encodeURIComponent(token)}` : ''}`
    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('qr', (e) => {
      setLoading(false)
      setQrLines((prev) => [...prev, e.data])
    })

    es.addEventListener('status', (e) => {
      try {
        const payload = JSON.parse(e.data) as { type: string; jid?: string; msg?: string }
        if (payload.type === 'login_success') {
          es.close()
          setStatusMsg(`登录成功: ${payload.jid ?? ''}`)
          onLoginSuccess(payload.jid ?? '')
        } else if (payload.type === 'timeout') {
          es.close()
          setStreamError('二维码已超时，请重新生成')
          setLoading(false)
        } else if (payload.type === 'error') {
          es.close()
          setStreamError(payload.msg ?? '未知错误')
          setLoading(false)
        }
      } catch {
        // ignore parse errors
      }
    })

    es.onerror = () => {
      es.close()
      setStreamError('SSE 连接中断')
      setLoading(false)
    }
  }, [onLoginSuccess])

  useEffect(() => {
    return () => {
      esRef.current?.close()
    }
  }, [])

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Button
        type="primary"
        icon={<ReloadOutlined />}
        loading={loading}
        onClick={startScan}
      >
        {qrLines.length > 0 ? '刷新二维码' : '生成二维码'}
      </Button>

      {streamError && <Alert type="error" message={streamError} showIcon />}

      {statusMsg && <Alert type="success" message={statusMsg} showIcon />}

      {loading && <Spin tip="等待二维码..." />}

      {qrLines.length > 0 && !statusMsg && (
        <pre
          style={{
            background: '#000',
            color: '#fff',
            padding: 16,
            borderRadius: 8,
            fontFamily: 'monospace',
            fontSize: 11,
            lineHeight: 1.2,
            whiteSpace: 'pre',
            overflowX: 'auto',
            maxWidth: 600,
          }}
        >
          {qrLines.join('\n')}
        </pre>
      )}

      <Paragraph type="secondary" style={{ marginTop: 8 }}>
        用手机 WhatsApp → 设置 → 已连接的设备 → 连接设备，扫描上方二维码
      </Paragraph>
    </Space>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Link-code Tab
// ────────────────────────────────────────────────────────────────────────────

const LinkCodeTab: React.FC<{ onLoginSuccess: (jid: string) => void }> = ({ onLoginSuccess }) => {
  const [loading, setLoading] = useState(false)
  const [linkCode, setLinkCode] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm()

  const handleSubmit = async ({ phone }: { phone: string }) => {
    setLoading(true)
    setLinkCode(null)
    setError(null)
    try {
      const res = await postBotLoginLinkcode(phone.trim())
      if (res.ok) {
        setLinkCode(res.link_code)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(`获取链接码失败: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Form form={form} layout="inline" onFinish={handleSubmit}>
        <Form.Item
          name="phone"
          rules={[
            { required: true, message: '请输入手机号' },
            { pattern: /^\+\d{7,15}$/, message: '格式：+86xxxxxxxxxx' },
          ]}
        >
          <Input
            placeholder="+86xxxxxxxxxx"
            prefix="📱"
            style={{ width: 220 }}
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} icon={<LinkOutlined />}>
            获取链接码
          </Button>
        </Form.Item>
      </Form>

      {error && <Alert type="error" message={error} showIcon />}

      {linkCode && (
        <Card
          style={{ maxWidth: 300, textAlign: 'center', marginTop: 16 }}
          bordered
        >
          <Title level={2} style={{ letterSpacing: 8, fontFamily: 'monospace', margin: 0 }}>
            {linkCode}
          </Title>
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            在手机 WhatsApp → 已连接的设备 → 输入此码
          </Text>
          <Button
            type="link"
            style={{ marginTop: 8 }}
            onClick={() => onLoginSuccess('(linkcode登录)')}
          >
            已完成登录 →
          </Button>
        </Card>
      )}
    </Space>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Start-bot Tab  (启动已注册的 Bot)
// ────────────────────────────────────────────────────────────────────────────

type StartPhase = 'idle' | 'starting' | 'streaming' | 'connected' | 'error'

const StartBotTab: React.FC = () => {
  const [phase, setPhase] = useState<StartPhase>('idle')
  const [logs, setLogs] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [connectedJid, setConnectedJid] = useState<string | null>(null)
  const [botRunning, setBotRunning] = useState(false)
  const [runningPid, setRunningPid] = useState<number | null>(null)
  const [stopLoading, setStopLoading] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const logsBottomRef = useRef<HTMLDivElement>(null)
  const [form] = Form.useForm()

  // Poll bot status on mount so we show current state
  useEffect(() => {
    fetchBotStatus()
      .then((s) => {
        setBotRunning(s.running)
        setRunningPid(s.pid)
        if (s.running && s.jid) setConnectedJid(s.jid)
      })
      .catch(() => {})
  }, [])

  // Auto-scroll logs to bottom
  useEffect(() => {
    logsBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const handleStart = async ({ phone }: { phone: string }) => {
    esRef.current?.close()
    setLogs([])
    setError(null)
    setConnectedJid(null)
    setPhase('starting')

    try {
      const res = await postBotStart(phone.trim().replace(/^\+/, ''))
      setLogs([`▶ Bot 进程已启动 (PID=${res.pid})`])
      setPhase('streaming')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(`启动失败: ${msg}`)
      setPhase('error')
      return
    }

    // Open SSE log stream
    const token = getApiToken()
    const url = `/api/bot/start-stream${token ? `?token=${encodeURIComponent(token)}` : ''}`
    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('log', (e) => {
      setLogs((prev) => [...prev, e.data])
    })

    es.addEventListener('status', (e) => {
      try {
        const payload = JSON.parse(e.data) as {
          type: string
          jid?: string
          pid?: number
          msg?: string
        }
        if (payload.type === 'connected') {
          es.close()
          setConnectedJid(payload.jid ?? null)
          setBotRunning(true)
          setRunningPid(payload.pid ?? null)
          setPhase('connected')
          setLogs((prev) => [...prev, `✅ 已连接: ${payload.jid ?? '(未知JID)'}`])
        } else if (payload.type === 'error') {
          es.close()
          setError(payload.msg ?? '未知错误')
          setPhase('error')
        } else if (payload.type === 'timeout') {
          es.close()
          // Timeout just means the stream closed; bot may still be connecting in background
          setLogs((prev) => [...prev, '⏱ 日志流结束（Bot 仍在后台运行中）'])
          setPhase('idle')
          setBotRunning(true)
        }
      } catch {
        // ignore parse errors
      }
    })

    es.onerror = () => {
      es.close()
      if (phase === 'streaming') {
        setLogs((prev) => [...prev, '— 日志流已断开 —'])
        setPhase('idle')
      }
    }
  }

  const handleStop = async () => {
    setStopLoading(true)
    try {
      await postBotLogout()
      setBotRunning(false)
      setRunningPid(null)
      setConnectedJid(null)
      setPhase('idle')
      setLogs([])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(`停止失败: ${msg}`)
    } finally {
      setStopLoading(false)
    }
  }

  useEffect(() => {
    return () => {
      esRef.current?.close()
    }
  }, [])

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {/* Current status badge */}
      <Space>
        <Text>当前状态:</Text>
        {botRunning ? (
          <Tag color="green">运行中{runningPid ? ` (PID ${runningPid})` : ''}</Tag>
        ) : (
          <Tag color="default">未运行</Tag>
        )}
        {connectedJid && <Tag color="blue">{connectedJid}</Tag>}
      </Space>

      {botRunning ? (
        <Button
          danger
          icon={<StopOutlined />}
          loading={stopLoading}
          onClick={handleStop}
        >
          停止 Bot
        </Button>
      ) : (
        <Form form={form} layout="inline" onFinish={handleStart}>
          <Form.Item
            name="phone"
            rules={[
              { required: true, message: '请输入手机号' },
              {
                pattern: /^\+?\d{7,15}$/,
                message: '格式：+86xxxxxxxxxx 或 86xxxxxxxxxx',
              },
            ]}
          >
            <Input
              placeholder="989334018988"
              prefix="📱"
              style={{ width: 240 }}
              disabled={phase === 'starting' || phase === 'streaming'}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={phase === 'starting' || phase === 'streaming'}
              icon={<PlayCircleOutlined />}
            >
              启动 Bot
            </Button>
          </Form.Item>
        </Form>
      )}

      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          onClose={() => setError(null)}
        />
      )}

      {phase === 'connected' && connectedJid && (
        <Alert type="success" message={`Bot 已连接: ${connectedJid}`} showIcon />
      )}

      {/* Log output */}
      {logs.length > 0 && (
        <div
          style={{
            background: '#111',
            color: '#d4d4d4',
            padding: '10px 14px',
            borderRadius: 8,
            fontFamily: 'monospace',
            fontSize: 12,
            lineHeight: 1.6,
            maxHeight: 260,
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {logs.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
          <div ref={logsBottomRef} />
        </div>
      )}

      {phase === 'streaming' && (
        <Spin size="small" tip="等待 Bot 连接中…" />
      )}

      <Paragraph type="secondary" style={{ marginTop: 8 }}>
        输入已注册的手机号（完整国际格式，如 <Text code>989334018988</Text>），点击启动后
        Bot 会在后台运行，相当于执行 <Text code>python script/main.py &lt;phone&gt;</Text>。
      </Paragraph>
    </Space>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Page root
// ────────────────────────────────────────────────────────────────────────────

const BotLoginPage: React.FC = () => {
  const navigate = useNavigate()
  const [msgApi, contextHolder] = message.useMessage()

  const handleSuccess = useCallback(
    (jid: string) => {
      msgApi.success(`登录成功${jid ? ` — ${jid}` : ''}，正在跳转…`)
      setTimeout(() => navigate('/'), 2000)
    },
    [navigate, msgApi],
  )

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
      }}
    >
      {contextHolder}
      <Card
        style={{ width: 560, boxShadow: '0 4px 24px rgba(0,0,0,.08)' }}
        title={
          <Space>
            <QrcodeOutlined style={{ fontSize: 22 }} />
            <span>Bot 登录管理</span>
          </Space>
        }
      >
        <Tabs
          defaultActiveKey="start"
          items={[
            {
              key: 'start',
              label: (
                <span>
                  <PlayCircleOutlined /> 启动已注册Bot
                </span>
              ),
              children: <StartBotTab />,
            },
            {
              key: 'scan',
              label: '扫描二维码',
              children: <QrLoginTab onLoginSuccess={handleSuccess} />,
            },
            {
              key: 'linkcode',
              label: '链接码登录',
              children: <LinkCodeTab onLoginSuccess={handleSuccess} />,
            },
          ]}
        />
      </Card>
    </div>
  )
}

export default BotLoginPage
