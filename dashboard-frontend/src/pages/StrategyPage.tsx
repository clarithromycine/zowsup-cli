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
import { ReloadOutlined, RollbackOutlined, GlobalOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  fetchStrategy,
  fetchStrategyHistory,
  postApplyGlobalStrategy,
  postRollbackStrategy,
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
