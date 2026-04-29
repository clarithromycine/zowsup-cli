import React, { useEffect, useState } from 'react'
import {
  Card,
  Form,
  Select,
  Input,
  Button,
  Table,
  Tag,
  Typography,
  message,
  Divider,
  Row,
  Col,
  Popconfirm,
  Alert,
} from 'antd'
import { ReloadOutlined, RollbackOutlined, GlobalOutlined, StopOutlined, CheckCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  fetchStrategy,
  fetchStrategyHistory,
  postApplyGlobalStrategy,
  postRollbackStrategy,
  patchToggleStrategy,
  deleteStrategyRow,
} from '../api/endpoints'
import { useDashboardStore } from '../store'
import type { StrategyRecord, StrategyConfig } from '../types'

const { Title, Text } = Typography
const { TextArea } = Input

const STYLE_OPTIONS = [
  { label: '正式', value: 'formal' },
  { label: '随意', value: 'casual' },
  { label: '简洁', value: 'concise' },
  { label: '详细', value: 'detailed' },
]

const TONE_OPTIONS = [
  { label: '礼貌', value: 'polite' },
  { label: '友好', value: 'friendly' },
  { label: '专业', value: 'professional' },
  { label: '同理心', value: 'empathetic' },
  { label: '中性', value: 'neutral' },
]

const LANG_OPTIONS = [
  { label: '自动', value: 'auto' },
  { label: '中文', value: 'zh' },
  { label: '英文', value: 'en' },
  { label: '混合', value: 'mixed' },
]

const StrategyPage: React.FC = () => {
  const [form] = Form.useForm<StrategyConfig & { note?: string }>()
  const globalStrategy = useDashboardStore((s) => s.globalStrategy)
  const setGlobalStrategy = useDashboardStore((s) => s.setGlobalStrategy)
  const strategyHistory = useDashboardStore((s) => s.strategyHistory)
  const setStrategyHistory = useDashboardStore((s) => s.setStrategyHistory)
  const [applying, setApplying] = useState(false)
  const [rolling, setRolling] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [rowLoading, setRowLoading] = useState<Record<number, boolean>>({})

  // Load current global strategy on mount
  useEffect(() => {
    fetchStrategy()
      .then((r) => {
        setGlobalStrategy(r.global)
        form.setFieldsValue(r.global)
      })
      .catch(() => {})

    loadHistory()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function loadHistory() {
    setLoadingHistory(true)
    try {
      const r = await fetchStrategyHistory()
      setStrategyHistory(r.history)
    } catch {
      setStrategyHistory([])
    } finally {
      setLoadingHistory(false)
    }
  }

  async function handleApply(values: StrategyConfig & { note?: string }) {
    const { note, ...config } = values
    setApplying(true)
    try {
      await postApplyGlobalStrategy(config, note)
      setGlobalStrategy(config)
      message.success('全局策略已应用')
      loadHistory()
    } catch {
      message.error('应用策略失败')
    } finally {
      setApplying(false)
    }
  }

  async function handleRollback() {
    setRolling(true)
    try {
      await postRollbackStrategy(null, 1)
      message.success('已回滚至上一版本')
      // Refresh
      const r = await fetchStrategy()
      setGlobalStrategy(r.global)
      form.setFieldsValue(r.global)
      loadHistory()
    } catch {
      message.error('回滚失败')
    } finally {
      setRolling(false)
    }
  }

  async function handleToggle(record: StrategyRecord) {
    setRowLoading((prev) => ({ ...prev, [record.id]: true }))
    try {
      const result = await patchToggleStrategy(record.id)
      // Update history in store: flip is_active for affected rows
      setStrategyHistory(
        strategyHistory.map((r) => {
          // The activated row
          if (r.id === record.id) return { ...r, is_active: result.is_active }
          // If we activated this row, deactivate others of same type/jid
          if (
            result.is_active === 1 &&
            r.strategy_type === record.strategy_type &&
            r.user_jid === record.user_jid &&
            r.id !== record.id
          ) {
            return { ...r, is_active: 0 as const }
          }
          return r
        }),
      )
      message.success(result.is_active ? '策略已启用' : '策略已屏蔽')
    } catch {
      message.error('操作失败')
    } finally {
      setRowLoading((prev) => ({ ...prev, [record.id]: false }))
    }
  }

  async function handleDelete(record: StrategyRecord) {
    setRowLoading((prev) => ({ ...prev, [record.id]: true }))
    try {
      await deleteStrategyRow(record.id)
      setStrategyHistory(strategyHistory.filter((r) => r.id !== record.id))
      message.success('已删除')
    } catch {
      message.error('删除失败')
    } finally {
      setRowLoading((prev) => ({ ...prev, [record.id]: false }))
    }
  }

  const columns = [
    {
      title: '版本',
      dataIndex: 'version',
      width: 60,
      render: (v: number, r: StrategyRecord) => (
        <Tag color={r.is_active ? 'green' : 'default'}>{v}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 72,
      render: (active: 0 | 1) =>
        active ? (
          <Tag color="green" icon={<CheckCircleOutlined />}>激活</Tag>
        ) : (
          <Tag color="default" icon={<StopOutlined />}>已屏蔽</Tag>
        ),
    },
    {
      title: '类型',
      dataIndex: 'strategy_type',
      width: 80,
      render: (t: string) => (t === 'global' ? <GlobalOutlined /> : t),
    },
    {
      title: '风格',
      render: (_: unknown, r: StrategyRecord) => (
        <Text style={{ fontSize: 12 }}>{r.config?.response_style ?? '—'}</Text>
      ),
    },
    {
      title: '语气',
      render: (_: unknown, r: StrategyRecord) => (
        <Text style={{ fontSize: 12 }}>{r.config?.tone ?? '—'}</Text>
      ),
    },
    {
      title: '语言',
      render: (_: unknown, r: StrategyRecord) => (
        <Text style={{ fontSize: 12 }}>{r.config?.language ?? '—'}</Text>
      ),
    },
    {
      title: '备注',
      dataIndex: 'note',
      ellipsis: true,
      render: (n: string | null) => n ?? '—',
    },
    {
      title: '应用时间',
      dataIndex: 'applied_at',
      render: (t: string) => dayjs(t).format('MM-DD HH:mm'),
    },
    {
      title: '操作',
      width: 110,
      fixed: 'right' as const,
      render: (_: unknown, record: StrategyRecord) => (
        <div style={{ display: 'flex', gap: 4 }}>
          <Button
            size="small"
            loading={rowLoading[record.id]}
            icon={record.is_active ? <StopOutlined /> : <CheckCircleOutlined />}
            onClick={() => handleToggle(record)}
            title={record.is_active ? '屏蔽此策略' : '启用此策略'}
          >
            {record.is_active ? '屏蔽' : '启用'}
          </Button>
          <Popconfirm
            title="删除策略"
            description="此操作不可撤销，确定删除？"
            onConfirm={() => handleDelete(record)}
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={rowLoading[record.id]}
            />
          </Popconfirm>
        </div>
      ),
    },
  ]

  return (
    <div style={{ padding: 16 }}>
      <Title level={4}>策略管理</Title>

      <Alert
        message="全局策略会应用于所有用户（个人策略优先级更高）。修改后立即生效，可通过回滚恢复。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="编辑全局策略" size="small">
            <Form
              form={form}
              layout="vertical"
              initialValues={globalStrategy}
              onFinish={handleApply}
            >
              <Form.Item name="response_style" label="回复风格">
                <Select options={STYLE_OPTIONS} />
              </Form.Item>
              <Form.Item name="tone" label="语气">
                <Select options={TONE_OPTIONS} />
              </Form.Item>
              <Form.Item name="language" label="语言">
                <Select options={LANG_OPTIONS} />
              </Form.Item>
              <Form.Item name="custom_instructions" label="自定义指令">
                <TextArea rows={3} placeholder="输入额外指令（可选）" maxLength={500} showCount />
              </Form.Item>
              <Form.Item name="note" label="备注">
                <Input placeholder="本次修改备注（可选）" maxLength={200} />
              </Form.Item>

              <div style={{ display: 'flex', gap: 8 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={applying}
                  icon={<GlobalOutlined />}
                >
                  应用全局策略
                </Button>
                <Popconfirm
                  title="回滚全局策略"
                  description="将回滚至上一个历史版本，确定继续？"
                  onConfirm={handleRollback}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button icon={<RollbackOutlined />} loading={rolling} danger>
                    回滚
                  </Button>
                </Popconfirm>
              </div>
            </Form>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card
            title="策略历史"
            size="small"
            extra={
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={loadHistory}
                loading={loadingHistory}
              >
                刷新
              </Button>
            }
          >
            <Table
              dataSource={strategyHistory}
              columns={columns}
              rowKey="id"
              size="small"
              loading={loadingHistory}
              pagination={{ pageSize: 10, size: 'small' }}
              scroll={{ x: 500 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default StrategyPage
