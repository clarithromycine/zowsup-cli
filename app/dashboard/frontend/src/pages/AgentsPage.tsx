/**
 * AgentsPage.tsx
 * ──────────────
 * Agent Management
 *
 * Design:
 *  - Agents are *defined* on the server (server knows which agents exist)
 *  - Each agent has an agent_id + auto-generated secret (part of its definition)
 *  - When the agent process connects it authenticates with that secret
 *  - The page shows all defined agents with their online/offline status
 *  - Adding an agent shows a one-time launch command to paste on the remote machine
 */

import React, { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CopyOutlined,
  DeleteOutlined,
  DisconnectOutlined,
  MinusCircleOutlined,
  PhoneOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  StopOutlined,
} from '@ant-design/icons'
import {
  fetchAgents,
  postAgent,
  deleteAgent,
  postAgentStartBot,
  postAgentStopBot,
} from '../api/endpoints'
import type { AgentInfo, AgentCreated } from '../api/endpoints'

const { Title, Text } = Typography

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

// ── Phone action row ──────────────────────────────────────────────────────────

interface PhoneRowProps {
  phone: string
  onRefresh: () => void
}

const PhoneRow: React.FC<PhoneRowProps> = ({ phone, onRefresh }) => {
  const [starting, setStarting] = useState(false)
  const [stopping, setStopping] = useState(false)

  const handleStart = async () => {
    setStarting(true)
    try {
      const res = await postAgentStartBot(phone)
      if (res.ok) {
        message.success(`Bot ${phone} 已启动`)
        onRefresh()
      } else {
        message.error(res.error ?? '启动失败')
      }
    } catch {
      message.error('请求失败')
    } finally {
      setStarting(false)
    }
  }

  const handleStop = async () => {
    setStopping(true)
    try {
      const res = await postAgentStopBot(phone)
      if (res.ok) {
        message.success(`Bot ${phone} 已停止`)
        onRefresh()
      } else {
        message.error(res.error ?? '停止失败')
      }
    } catch {
      message.error('请求失败')
    } finally {
      setStopping(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 0',
        borderBottom: '1px solid #f0f0f0',
      }}
    >
      <PhoneOutlined style={{ color: '#1677ff' }} />
      <Text style={{ flex: 1, fontFamily: 'monospace', fontSize: 13 }}>{phone}</Text>
      <Tooltip title="启动 Bot">
        <Button
          size="small"
          type="text"
          icon={<PlayCircleOutlined style={{ color: '#52c41a' }} />}
          loading={starting}
          onClick={handleStart}
        />
      </Tooltip>
      <Tooltip title="停止 Bot">
        <Popconfirm
          title={`停止 Bot ${phone}？`}
          onConfirm={handleStop}
          okText="停止"
          cancelText="取消"
        >
          <Button
            size="small"
            type="text"
            icon={<StopOutlined style={{ color: '#ff4d4f' }} />}
            loading={stopping}
          />
        </Popconfirm>
      </Tooltip>
    </div>
  )
}

// ── Agent card ────────────────────────────────────────────────────────────────

interface AgentCardProps {
  agent: AgentInfo
  onRefresh: () => void
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, onRefresh }) => {
  const handleDelete = async () => {
    try {
      await deleteAgent(agent.agent_id)
      message.success(`Agent "${agent.agent_id}" 已删除`)
      onRefresh()
    } catch {
      message.error('删除失败')
    }
  }

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      title={
        <Space>
          {agent.online ? <Badge status="success" /> : <Badge status="default" />}
          <Text strong style={{ fontFamily: 'monospace' }}>{agent.agent_id}</Text>
          {agent.note && (
            <Text type="secondary" style={{ fontWeight: 400, fontSize: 12 }}>
              — {agent.note}
            </Text>
          )}
        </Space>
      }
      extra={
        <Space>
          {agent.online
            ? <Tag icon={<CheckCircleOutlined />} color="success">在线</Tag>
            : <Tag icon={<MinusCircleOutlined />} color="default">离线</Tag>}
          <Popconfirm
            title={`删除 Agent "${agent.agent_id}"？`}
            description="Agent 进程将在下次重连时被拒绝。"
            onConfirm={handleDelete}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger type="text" icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      }
    >
      {agent.online ? (
        <>
          <Descriptions size="small" column={2} style={{ marginBottom: 10 }}>
            <Descriptions.Item label={<><ClockCircleOutlined /> 连接时间</>}>
              {agent.connected_at ? fmtTime(agent.connected_at) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="运行时长">
              {agent.uptime_seconds != null ? fmtUptime(agent.uptime_seconds) : '—'}
            </Descriptions.Item>
          </Descriptions>
          {agent.phones.length === 0 ? (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Agent 在线但暂无管理的手机号
            </Text>
          ) : (
            <>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                管理的手机号（{agent.phones.length} 个）
              </Text>
              {agent.phones.map((phone) => (
                <PhoneRow key={phone} phone={phone} onRefresh={onRefresh} />
              ))}
            </>
          )}
        </>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>
          Agent 离线 — 在目标机器上运行启动命令后将自动上线
          {agent.created_at && (
            <span style={{ marginLeft: 8 }}>（创建于 {fmtTime(agent.created_at)}）</span>
          )}
        </Text>
      )}
    </Card>
  )
}

// ── New agent modal (two-step: fill form → show secret once) ─────────────────

interface NewAgentModalProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

const NewAgentModal: React.FC<NewAgentModalProps> = ({ open, onClose, onCreated }) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AgentCreated | null>(null)

  const copy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => message.success('已复制'))
  }

  const handleOk = async () => {
    const values = await form.validateFields()
    setLoading(true)
    try {
      const created = await postAgent(values.agent_id, values.note || '')
      setResult(created)
      onCreated()
    } catch (err: any) {
      message.error(err?.response?.data?.error ?? '创建失败')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setResult(null)
    form.resetFields()
    onClose()
  }

  // Step 1: form
  if (!result) {
    return (
      <Modal
        title={<Space><ApartmentOutlined />新建 Agent</Space>}
        open={open}
        onOk={handleOk}
        onCancel={handleClose}
        okText="创建"
        confirmLoading={loading}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item
            name="agent_id"
            label="Agent ID"
            rules={[
              { required: true, message: 'Agent ID 不能为空' },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: '只允许字母、数字、连字符、下划线' },
            ]}
            extra="唯一标识，例如 server-hk-01。Agent 进程启动时需与此一致。"
          >
            <Input placeholder="server-hk-01" />
          </Form.Item>
          <Form.Item name="note" label="备注（可选）">
            <Input placeholder="香港机器" />
          </Form.Item>
        </Form>
      </Modal>
    )
  }

  // Step 2: show secret once
  return (
    <Modal
      title={<Space><CheckCircleOutlined style={{ color: '#52c41a' }} />Agent 创建成功</Space>}
      open={open}
      footer={
        <Button type="primary" onClick={handleClose}>
          我已保存，关闭
        </Button>
      }
      onCancel={handleClose}
      width={660}
    >
      <Alert
        type="warning"
        showIcon
        message="Secret 只显示一次，关闭后无法再查看。请立即复制保存启动命令。"
        style={{ marginBottom: 16 }}
      />
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Agent ID">
          <Text code>{result.agent_id}</Text>
        </Descriptions.Item>
        {result.note && (
          <Descriptions.Item label="备注">{result.note}</Descriptions.Item>
        )}
        <Descriptions.Item label="Secret (hex)">
          <Space wrap>
            <Text code style={{ wordBreak: 'break-all', fontSize: 11 }}>{result.secret}</Text>
            <Button size="small" icon={<CopyOutlined />} onClick={() => copy(result.secret)}>
              复制
            </Button>
          </Space>
        </Descriptions.Item>
      </Descriptions>
      <Divider>在 Agent 机器上运行以下命令</Divider>
      <div
        style={{
          background: '#1a1a1a',
          color: '#e6e6e6',
          borderRadius: 6,
          padding: '10px 14px',
          fontFamily: 'monospace',
          fontSize: 12,
          wordBreak: 'break-all',
          position: 'relative',
          paddingRight: 72,
        }}
      >
        {result.launch_cmd}
        <Button
          size="small"
          icon={<CopyOutlined />}
          style={{ position: 'absolute', top: 8, right: 8 }}
          onClick={() => copy(result.launch_cmd)}
        >
          复制
        </Button>
      </div>
    </Modal>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

const AgentsPage: React.FC = () => {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [showNew, setShowNew] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchAgents()
      setAgents(res.agents)
    } catch {
      message.error('获取 Agent 列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 15_000)
    return () => clearInterval(timer)
  }, [load])

  const onlineCount = agents.filter((a) => a.online).length
  const phoneCount = agents.reduce((s, a) => s + a.phones.length, 0)

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <ApartmentOutlined style={{ fontSize: 22, color: '#1677ff' }} />
        <Title level={4} style={{ margin: 0 }}>
          Agent 管理
        </Title>
        <div style={{ flex: 1 }} />
        <Text type="secondary" style={{ fontSize: 12 }}>
          每 15 秒自动刷新
        </Text>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          刷新
        </Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowNew(true)}>
          新建 Agent
        </Button>
      </div>

      {/* Summary */}
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col>
          <Card size="small" style={{ minWidth: 130, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700 }}>{agents.length}</div>
            <Text type="secondary">已定义</Text>
          </Card>
        </Col>
        <Col>
          <Card size="small" style={{ minWidth: 130, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: '#52c41a' }}>{onlineCount}</div>
            <Text type="secondary">在线</Text>
          </Card>
        </Col>
        <Col>
          <Card size="small" style={{ minWidth: 130, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: '#1677ff' }}>{phoneCount}</div>
            <Text type="secondary">管理的手机号</Text>
          </Card>
        </Col>
      </Row>

      {/* Agent list */}
      <Spin spinning={loading && agents.length === 0}>
        {agents.length === 0 && !loading ? (
          <Card>
            <Empty
              image={<DisconnectOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
              imageStyle={{ height: 60 }}
              description={
                <>
                  <div>暂无 Agent</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    点击「新建 Agent」，复制启动命令在远程机器上运行
                  </Text>
                </>
              }
            />
          </Card>
        ) : (
          agents.map((agent) => (
            <AgentCard key={agent.agent_id} agent={agent} onRefresh={load} />
          ))
        )}
      </Spin>

      <NewAgentModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreated={load}
      />
    </div>
  )
}

export default AgentsPage
