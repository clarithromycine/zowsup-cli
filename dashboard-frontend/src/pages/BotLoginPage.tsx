/**
 * BotLoginPage.tsx
 * ─────────────────
 * Bot 综合管理界面
 *
 * Layout:
 *   Card 1 — Bot 账号列表  (list / import / export / one-click-start / mark-failed / delete)
 *   Card 2 — 登录管理 Tabs (启动已注册Bot / 扫描二维码 / 链接码登录)
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CheckCircleOutlined,
  CloudDownloadOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  LinkOutlined,
  PlayCircleOutlined,
  QrcodeOutlined,
  ReloadOutlined,
  StopOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import {
  postBotLoginScan,
  postBotLoginLinkcode,
  postBotStart,
  postBotLogout,
  fetchBotStatus,
  fetchBotAccounts,
  deleteBotAccount,
  patchToggleAccountFailed,
  deleteFailedAccounts,
  importBotAccounts,
  exportBotAccounts,
} from '../api/endpoints'
import type { BotAccount } from '../api/endpoints'
import { getApiToken } from '../api/client'

const { Paragraph, Text } = Typography

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
// Bot Accounts Table
// ────────────────────────────────────────────────────────────────────────────

const AccountsSection: React.FC = () => {
  const [accounts, setAccounts] = useState<BotAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedPhones, setSelectedPhones] = useState<string[]>([])
  const [rowLoading, setRowLoading] = useState<Record<string, boolean>>({})

  // Import modal
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<string | null>(null)

  // Export modal
  const [exportOpen, setExportOpen] = useState(false)
  const [exportText, setExportText] = useState('')
  const [exporting, setExporting] = useState(false)

  // One-click start modal
  const [startModalOpen, setStartModalOpen] = useState(false)
  const [startPhone, setStartPhone] = useState('')
  const [startLogs, setStartLogs] = useState<string[]>([])
  const [startPhase, setStartPhase] = useState<'starting' | 'streaming' | 'done' | 'error'>('starting')
  const esRef = useRef<EventSource | null>(null)
  const logsBottomRef = useRef<HTMLDivElement>(null)

  const [msgApi, contextHolder] = message.useMessage()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchBotAccounts()
      setAccounts(res.accounts)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    logsBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [startLogs])

  const setRowBusy = (phone: string, busy: boolean) =>
    setRowLoading((prev) => ({ ...prev, [phone]: busy }))

  // ── One-click start ──
  const handleQuickStart = async (phone: string) => {
    esRef.current?.close()
    setStartPhone(phone)
    setStartLogs([])
    setStartPhase('starting')
    setStartModalOpen(true)

    try {
      const res = await postBotStart(phone)
      setStartLogs([`▶ 启动成功 (PID=${res.pid})`])
      setStartPhase('streaming')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setStartLogs([`❌ 启动失败: ${msg}`])
      setStartPhase('error')
      return
    }

    const token = getApiToken()
    const url = `/api/bot/start-stream${token ? `?token=${encodeURIComponent(token)}` : ''}`
    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('log', (e) => setStartLogs((p) => [...p, e.data]))
    es.addEventListener('status', (e) => {
      try {
        const p = JSON.parse(e.data) as { type: string; jid?: string; pid?: number; msg?: string }
        if (p.type === 'connected') {
          es.close()
          setStartLogs((prev) => [...prev, `✅ 已连接: ${p.jid ?? ''}`])
          setStartPhase('done')
          load()
        } else if (p.type === 'error') {
          es.close()
          setStartLogs((prev) => [...prev, `❌ ${p.msg ?? '未知错误'}`])
          setStartPhase('error')
        } else if (p.type === 'timeout') {
          es.close()
          setStartLogs((prev) => [...prev, '⏱ 日志流结束（Bot 仍在后台运行中）'])
          setStartPhase('done')
          load()
        }
      } catch { /* ignore */ }
    })
    es.onerror = () => {
      es.close()
      setStartLogs((p) => [...p, '— 日志流已断开 —'])
      setStartPhase('done')
    }
  }

  const closeStartModal = () => {
    esRef.current?.close()
    setStartModalOpen(false)
  }

  // ── Delete ──
  const handleDelete = async (phone: string) => {
    setRowBusy(phone, true)
    try {
      await deleteBotAccount(phone)
      setAccounts((prev) => prev.filter((a) => a.phone !== phone))
      msgApi.success(`已删除 ${phone}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      msgApi.error(msg)
    } finally {
      setRowBusy(phone, false)
    }
  }

  // ── Toggle failed mark ──
  const handleToggleFailed = async (phone: string) => {
    setRowBusy(phone, true)
    try {
      const res = await patchToggleAccountFailed(phone)
      setAccounts((prev) =>
        prev.map((a) =>
          a.phone === phone
            ? { ...a, is_failed: res.is_failed, failed_at: res.is_failed ? new Date().toISOString() : null }
            : a
        )
      )
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      msgApi.error(msg)
    } finally {
      setRowBusy(phone, false)
    }
  }

  // ── Delete all failed ──
  const handleDeleteAllFailed = async () => {
    try {
      const res = await deleteFailedAccounts()
      msgApi.success(`已删除 ${res.deleted.length} 个失败账号`)
      load()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      msgApi.error(msg)
    }
  }

  // ── Import ──
  const handleImport = async () => {
    const lines = importText.split('\n').map((l) => l.trim()).filter(Boolean)
    if (!lines.length) return
    setImporting(true)
    setImportResult(null)
    try {
      const res = await importBotAccounts(lines)
      setImportResult(`导入完成：成功 ${res.imported} / 共 ${res.total}`)
      if (res.imported > 0) {
        load()
        setImportText('')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setImportResult(`错误: ${msg}`)
    } finally {
      setImporting(false)
    }
  }

  // ── Export ──
  const handleExport = async (phones: string[]) => {
    setExporting(true)
    setExportText('')
    setExportOpen(true)
    try {
      const res = await exportBotAccounts(phones)
      setExportText(res.lines.join('\n'))
      if (res.errors.length > 0) {
        msgApi.warning(`${res.errors.length} 个账号导出失败`)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      msgApi.error(msg)
    } finally {
      setExporting(false)
    }
  }

  const failedCount = accounts.filter((a) => a.is_failed).length

  const columns: ColumnsType<BotAccount> = [
    {
      title: '手机号',
      dataIndex: 'phone',
      key: 'phone',
      render: (phone: string) => <Text code>{phone}</Text>,
    },
    {
      title: '推送名',
      dataIndex: 'pushname',
      key: 'pushname',
      render: (v: string | null) => v ?? <Text type="secondary">—</Text>,
    },
    {
      title: '状态',
      key: 'status',
      width: 110,
      render: (_: unknown, record: BotAccount) => {
        if (record.is_running)
          return <Tag color="green" icon={<CheckCircleOutlined />}>运行中</Tag>
        if (record.is_failed)
          return <Tag color="red" icon={<WarningOutlined />}>登录失败</Tag>
        return <Tag color="default">离线</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      fixed: 'right' as const,
      width: 240,
      render: (_: unknown, record: BotAccount) => (
        <Space size={4}>
          <Tooltip title="一键启动">
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              disabled={record.is_running}
              loading={rowLoading[record.phone]}
              onClick={() => handleQuickStart(record.phone)}
            >
              启动
            </Button>
          </Tooltip>
          <Tooltip title={record.is_failed ? '取消失败标记' : '标记为登录失败'}>
            <Button
              size="small"
              icon={record.is_failed ? <CheckCircleOutlined /> : <WarningOutlined />}
              loading={rowLoading[record.phone]}
              onClick={() => handleToggleFailed(record.phone)}
            >
              {record.is_failed ? '取消标记' : '标记失败'}
            </Button>
          </Tooltip>
          <Tooltip title="导出六段号">
            <Button
              size="small"
              icon={<CloudDownloadOutlined />}
              onClick={() => handleExport([record.phone])}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此账号？"
            description="此操作不可撤销，将删除账号目录"
            onConfirm={() => handleDelete(record.phone)}
            okText="删除"
            okButtonProps={{ danger: true }}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={rowLoading[record.phone]}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const rowSelection = {
    selectedRowKeys: selectedPhones,
    onChange: (keys: React.Key[]) => setSelectedPhones(keys as string[]),
  }

  return (
    <Card
      title="Bot 账号列表"
      style={{ marginBottom: 24 }}
      extra={
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
          <Button
            icon={<CloudUploadOutlined />}
            onClick={() => { setImportOpen(true); setImportResult(null) }}
          >
            导入
          </Button>
          <Button
            icon={<CloudDownloadOutlined />}
            disabled={selectedPhones.length === 0}
            onClick={() => handleExport(selectedPhones)}
          >
            批量导出{selectedPhones.length > 0 ? ` (${selectedPhones.length})` : ''}
          </Button>
          <Popconfirm
            title={`确认删除全部 ${failedCount} 个失败账号？`}
            onConfirm={handleDeleteAllFailed}
            disabled={failedCount === 0}
            okText="全部删除"
            okButtonProps={{ danger: true }}
          >
            <Button danger disabled={failedCount === 0} icon={<DeleteOutlined />}>
              删除失败账号{failedCount > 0 ? ` (${failedCount})` : ''}
            </Button>
          </Popconfirm>
        </Space>
      }
    >
      {contextHolder}
      <Table
        dataSource={accounts}
        columns={columns}
        rowKey="phone"
        rowSelection={rowSelection}
        loading={loading}
        size="small"
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        scroll={{ x: 700 }}
        locale={{ emptyText: '暂无账号，请先导入六段号' }}
      />

      {/* ── Import modal ── */}
      <Modal
        title="导入六段号"
        open={importOpen}
        onOk={handleImport}
        onCancel={() => { setImportOpen(false); setImportResult(null) }}
        confirmLoading={importing}
        okText="导入"
        width={560}
      >
        <Paragraph type="secondary" style={{ marginBottom: 8 }}>
          每行一条，格式：<Text code>phone,pk1,sk1,pk2,sk2,sixth</Text>
        </Paragraph>
        <Input.TextArea
          rows={8}
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          placeholder="粘贴六段号数据，每行一条"
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
        {importResult && (
          <Alert
            style={{ marginTop: 12 }}
            type={importResult.startsWith('错误') ? 'error' : 'success'}
            message={importResult}
            showIcon
          />
        )}
      </Modal>

      {/* ── Export modal ── */}
      <Modal
        title="导出六段号"
        open={exportOpen}
        onCancel={() => setExportOpen(false)}
        footer={
          <Space>
            <Button
              onClick={() => {
                navigator.clipboard.writeText(exportText)
                msgApi.success('已复制到剪贴板')
              }}
              disabled={!exportText}
            >
              复制全部
            </Button>
            <Button onClick={() => setExportOpen(false)}>关闭</Button>
          </Space>
        }
        width={560}
      >
        {exporting ? (
          <Spin />
        ) : (
          <Input.TextArea
            rows={8}
            value={exportText}
            readOnly
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
        )}
      </Modal>

      {/* ── One-click start log modal ── */}
      <Modal
        title={`启动 Bot — ${startPhone}`}
        open={startModalOpen}
        onCancel={closeStartModal}
        footer={
          <Button onClick={closeStartModal}>
            {startPhase === 'done' || startPhase === 'error' ? '关闭' : '取消'}
          </Button>
        }
        width={560}
      >
        <div
          style={{
            background: '#111',
            color: '#d4d4d4',
            padding: '10px 14px',
            borderRadius: 8,
            fontFamily: 'monospace',
            fontSize: 12,
            lineHeight: 1.6,
            minHeight: 80,
            maxHeight: 300,
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {startLogs.length === 0 && startPhase === 'starting' && <Spin size="small" />}
          {startLogs.map((line, i) => <div key={i}>{line}</div>)}
          {startPhase === 'streaming' && <Spin size="small" tip="连接中…" style={{ marginTop: 4 }} />}
          <div ref={logsBottomRef} />
        </div>
      </Modal>
    </Card>
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
    <div style={{ padding: 24, background: '#f0f2f5', minHeight: '100vh' }}>
      {contextHolder}

      {/* Section 1: Account management */}
      <AccountsSection />

      {/* Section 2: Login management */}
      <Card
        title={
          <Space>
            <QrcodeOutlined style={{ fontSize: 18 }} />
            <span>登录管理</span>
          </Space>
        }
      >
        <Tabs
          defaultActiveKey="start"
          items={[
            {
              key: 'start',
              label: (<span><PlayCircleOutlined /> 启动已注册Bot</span>),
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
