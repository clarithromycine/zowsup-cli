import React, { useEffect, useState } from 'react'
import {
  Card,
  Descriptions,
  Tag,
  Progress,
  Spin,
  Empty,
  Typography,
  Statistic,
  Row,
  Col,
  Button,
  Modal,
  Form,
  Select,
  Input,
  message,
  Divider,
  Tooltip,
  Space,
  Table,
  Popconfirm,
} from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  EditOutlined,
  RollbackOutlined,
  CheckOutlined,
  CloseOutlined,
  StopOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  HistoryOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  fetchUserProfile,
  postApplyStrategy,
  postRollbackStrategy,
  patchUserProfile,
  fetchStrategyHistory,
  patchToggleStrategy,
  deleteStrategyRow,
} from '../../api/endpoints'
import { useDashboardStore } from '../../store'
import type { StrategyConfig, StrategyRecord } from '../../types'

const { Title, Text } = Typography
const { TextArea } = Input

const CATEGORY_OPTIONS = [
  { label: 'VIP', value: 'VIP' },
  { label: '普通', value: 'regular' },
  { label: '新用户', value: 'new' },
  { label: '流失风险', value: 'at_risk' },
]

const COMM_STYLE_OPTIONS = [
  { label: '详细', value: 'detailed' },
  { label: '简洁', value: 'concise' },
  { label: '耐心', value: 'patient' },
  { label: '急躁', value: 'impatient' },
]

const CATEGORY_COLOR: Record<string, string> = {
  VIP: 'gold',
  regular: 'blue',
  new: 'green',
  at_risk: 'red',
}

const STYLE_COLOR: Record<string, string> = {
  detailed: 'purple',
  concise: 'cyan',
  patient: 'geekblue',
  impatient: 'orange',
}

/** Inline editable tag: shows tag + pencil; on click shows a Select + confirm */
function InlineTagEditor({
  value,
  isManual,
  options,
  colorMap,
  defaultColor,
  onSave,
}: {
  value: string | null
  isManual: boolean
  options: { label: string; value: string }[]
  colorMap: Record<string, string>
  defaultColor: string
  onSave: (v: string | null) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [pending, setPending] = useState<string | null>(value)
  const [saving, setSaving] = useState(false)

  const tagColor = value ? (colorMap[value] ?? defaultColor) : 'default'
  const labelText = options.find((o) => o.value === value)?.label ?? value ?? '—'

  const handleConfirm = async () => {
    setSaving(true)
    try {
      await onSave(pending)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <Space size={4}>
        <Select
          size="small"
          style={{ width: 120 }}
          value={pending}
          options={options}
          allowClear
          placeholder="自动推断"
          onChange={(v) => setPending(v ?? null)}
          autoFocus
        />
        <Button
          size="small"
          type="primary"
          icon={<CheckOutlined />}
          loading={saving}
          onClick={handleConfirm}
        />
        <Button
          size="small"
          icon={<CloseOutlined />}
          onClick={() => { setPending(value); setEditing(false) }}
        />
      </Space>
    )
  }

  return (
    <Space size={4}>
      <Tag color={tagColor} style={{ margin: 0 }}>{labelText}</Tag>
      {isManual && (
        <Tooltip title="已手动设置（优先于自动推断）">
          <Tag color="volcano" style={{ margin: 0, fontSize: 10, padding: '0 4px' }}>手动</Tag>
        </Tooltip>
      )}
      <Tooltip title="手动设置">
        <Button
          type="text"
          size="small"
          icon={<EditOutlined style={{ fontSize: 11, color: '#8c8c8c' }} />}
          style={{ padding: '0 2px', height: 'auto' }}
          onClick={() => { setPending(value); setEditing(true) }}
        />
      </Tooltip>
    </Space>
  )
}

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

function TrendIndicator({ direction, pct }: { direction: string; pct?: number | null }) {
  const pctStr = pct != null ? `${pct.toFixed(1)}%` : '—'
  if (direction === 'up')
    return <Text type="success"><ArrowUpOutlined /> {pctStr}</Text>
  if (direction === 'down')
    return <Text type="danger"><ArrowDownOutlined /> {pctStr}</Text>
  return <Text type="secondary"><MinusOutlined /> {pctStr}</Text>
}

const UserProfile: React.FC = () => {
  const selectedJid = useDashboardStore((s) => s.selectedJid)
  const profile = useDashboardStore((s) => s.profile)
  const profileLoading = useDashboardStore((s) => s.profileLoading)
  const setProfile = useDashboardStore((s) => s.setProfile)
  const setProfileLoading = useDashboardStore((s) => s.setProfileLoading)

  const [modalOpen, setModalOpen] = useState(false)
  const [applying, setApplying] = useState(false)
  const [rolling, setRolling] = useState(false)
  const [form] = Form.useForm<StrategyConfig & { note?: string }>()

  const [personalHistory, setPersonalHistory] = useState<StrategyRecord[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [rowLoading, setRowLoading] = useState<Record<number, boolean>>({})

  useEffect(() => {
    if (!selectedJid) return
    setProfileLoading(true)
    fetchUserProfile(selectedJid)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setProfileLoading(false))
    loadPersonalHistory(selectedJid)
  }, [selectedJid]) // eslint-disable-line react-hooks/exhaustive-deps

  function loadPersonalHistory(jid: string) {
    setHistoryLoading(true)
    fetchStrategyHistory(jid)
      .then((r) => setPersonalHistory(r.history))
      .catch(() => setPersonalHistory([]))
      .finally(() => setHistoryLoading(false))
  }

  const handleOpenModal = () => {
    form.resetFields()
    setModalOpen(true)
  }

  const handleApply = async () => {
    if (!selectedJid) return
    try {
      const values = await form.validateFields()
      const { note, ...config } = values
      setApplying(true)
      await postApplyStrategy(selectedJid, config as StrategyConfig, note)
      message.success('策略已应用，下一条 AI 回复立即生效')
      setModalOpen(false)
      fetchUserProfile(selectedJid).then(setProfile).catch(() => null)
      loadPersonalHistory(selectedJid)
    } catch {
      // validation error — form shows inline
    } finally {
      setApplying(false)
    }
  }

  const handleRollback = async () => {
    if (!selectedJid) return
    setRolling(true)
    try {
      await postRollbackStrategy(selectedJid)
      message.success('已回滚到上一版本策略')
      fetchUserProfile(selectedJid).then(setProfile).catch(() => null)
      loadPersonalHistory(selectedJid)
    } catch {
      message.error('回滚失败')
    } finally {
      setRolling(false)
    }
  }

  async function handleToggleRow(record: StrategyRecord) {
    setRowLoading((prev) => ({ ...prev, [record.id]: true }))
    try {
      const result = await patchToggleStrategy(record.id)
      setPersonalHistory((prev) =>
        prev.map((r) => {
          if (r.id === record.id) return { ...r, is_active: result.is_active }
          if (result.is_active === 1 && r.id !== record.id) return { ...r, is_active: 0 as const }
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

  async function handleDeleteRow(record: StrategyRecord) {
    setRowLoading((prev) => ({ ...prev, [record.id]: true }))
    try {
      await deleteStrategyRow(record.id)
      setPersonalHistory((prev) => prev.filter((r) => r.id !== record.id))
      message.success('已删除')
    } catch {
      message.error('删除失败')
    } finally {
      setRowLoading((prev) => ({ ...prev, [record.id]: false }))
    }
  }

  const historyColumns = [
    {
      title: '版本',
      dataIndex: 'version',
      width: 52,
      render: (v: number, r: StrategyRecord) => (
        <Tag color={r.is_active ? 'green' : 'default'} style={{ margin: 0 }}>v{v}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 68,
      render: (active: 0 | 1) =>
        active ? (
          <Tag color="green" icon={<CheckCircleOutlined />} style={{ margin: 0, fontSize: 11 }}>激活</Tag>
        ) : (
          <Tag color="default" icon={<StopOutlined />} style={{ margin: 0, fontSize: 11 }}>屏蔽</Tag>
        ),
    },
    {
      title: '备注',
      dataIndex: 'note',
      ellipsis: true,
      render: (n: string | null) => <span style={{ fontSize: 12 }}>{n ?? '—'}</span>,
    },
    {
      title: '时间',
      dataIndex: 'applied_at',
      width: 80,
      render: (t: string) => <span style={{ fontSize: 11 }}>{dayjs(t).format('MM-DD HH:mm')}</span>,
    },
    {
      title: '操作',
      width: 88,
      fixed: 'right' as const,
      render: (_: unknown, record: StrategyRecord) => (
        <Space size={4}>
          <Button
            size="small"
            loading={rowLoading[record.id]}
            icon={record.is_active ? <StopOutlined /> : <CheckCircleOutlined />}
            onClick={() => handleToggleRow(record)}
            title={record.is_active ? '屏蔽此策略' : '启用此策略'}
          />
          <Popconfirm
            title="删除策略"
            description="此操作不可撤销，确定删除？"
            onConfirm={() => handleDeleteRow(record)}
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
        </Space>
      ),
    },
  ]

  const handleSaveCategory = async (val: string | null) => {
    if (!selectedJid) return
    await patchUserProfile(selectedJid, { user_category: val })
    message.success(val ? `用户分类已设置为 ${val}` : '已清除手动分类（恢复自动推断）')
    fetchUserProfile(selectedJid).then(setProfile).catch(() => null)
  }

  const handleSaveStyle = async (val: string | null) => {
    if (!selectedJid) return
    await patchUserProfile(selectedJid, { communication_style: val })
    message.success(val ? `沟通风格已设置为 ${val}` : '已清除手动沟通风格（恢复自动推断）')
    fetchUserProfile(selectedJid).then(setProfile).catch(() => null)
  }

  if (!selectedJid) return <Empty description="请选择联系人" style={{ marginTop: 40 }} />
  if (profileLoading) return <Spin style={{ display: 'block', marginTop: 40 }} />
  if (!profile) return <Empty description="暂无用户画像" style={{ marginTop: 40 }} />

  const topTopics = Object.entries(profile.topic_preferences ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  return (
    <div style={{ padding: 12 }}>
      <Title level={5} style={{ marginBottom: 12 }}>
        用户画像
      </Title>

      <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
        <Col span={12}>
          <Card size="small">
            <Statistic title="总互动次数" value={profile.total_interactions} />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small">
            <Statistic
              title="满意度"
              value={
                profile.satisfaction_score != null
                  ? `${(profile.satisfaction_score * 100).toFixed(0)}%`
                  : '—'
              }
            />
          </Card>
        </Col>
      </Row>

      <Descriptions size="small" column={1} bordered style={{ marginBottom: 12 }}>
        <Descriptions.Item label="用户分类">
          <InlineTagEditor
            value={profile.user_category}
            isManual={profile.user_category_is_manual ?? false}
            options={CATEGORY_OPTIONS}
            colorMap={CATEGORY_COLOR}
            defaultColor="blue"
            onSave={handleSaveCategory}
          />
        </Descriptions.Item>
        <Descriptions.Item label="沟通风格">
          <InlineTagEditor
            value={profile.communication_style}
            isManual={profile.communication_style_is_manual ?? false}
            options={COMM_STYLE_OPTIONS}
            colorMap={STYLE_COLOR}
            defaultColor="purple"
            onSave={handleSaveStyle}
          />
        </Descriptions.Item>
        <Descriptions.Item label="当前策略">
          <Tag color="green">{profile.current_strategy ?? '默认'}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="首次访问">
          {profile.first_seen ? dayjs(profile.first_seen).format('YYYY-MM-DD') : '—'}
        </Descriptions.Item>
        <Descriptions.Item label="最后访问">
          {profile.last_seen ? dayjs(profile.last_seen).format('YYYY-MM-DD HH:mm') : '—'}
        </Descriptions.Item>
      </Descriptions>

      {/* Strategy quick-action buttons */}
      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col span={14}>
          <Button
            type="primary"
            icon={<EditOutlined />}
            block
            size="small"
            onClick={handleOpenModal}
          >
            调整此会话策略
          </Button>
        </Col>
        <Col span={10}>
          <Button
            icon={<RollbackOutlined />}
            block
            size="small"
            loading={rolling}
            onClick={handleRollback}
          >
            回滚策略
          </Button>
        </Col>
      </Row>

      {profile.trend_7d && (
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary">7日趋势: </Text>
          <TrendIndicator
            direction={profile.trend_7d.direction}
            pct={profile.trend_7d.change_pct}
          />
        </div>
      )}

      {topTopics.length > 0 && (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            热门话题
          </Text>
          {topTopics.map(([topic, count]) => {
            const maxCount = topTopics[0][1] || 1
            return (
              <div key={topic} style={{ marginTop: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  <Text style={{ fontSize: 12 }}>{topic}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {count}
                  </Text>
                </div>
                <Progress
                  percent={Math.round((count / maxCount) * 100)}
                  size="small"
                  showInfo={false}
                  strokeColor="#1890ff"
                />
              </div>
            )
          })}
        </div>
      )}

      {/* Per-user strategy modal */}
      <Modal
        title={`调整策略 — ${selectedJid}`}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleApply}
        confirmLoading={applying}
        okText="立即应用"
        cancelText="取消"
        width={640}
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          此策略仅对 <strong>{selectedJid}</strong> 生效，覆盖全局策略。
          下一条 AI 回复即时生效。
        </Text>
        <Form form={form} layout="vertical" size="small">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label="回复风格" name="response_style">
                <Select options={STYLE_OPTIONS} placeholder="保持全局默认" allowClear />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="语气" name="tone">
                <Select options={TONE_OPTIONS} placeholder="保持全局默认" allowClear />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label="语言" name="language">
                <Select options={LANG_OPTIONS} placeholder="自动" allowClear />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="最大回复长度" name="max_response_length">
                <Input type="number" placeholder="不限制" min={1} />
              </Form.Item>
            </Col>
          </Row>
          <Divider style={{ margin: '8px 0' }} />
          <Form.Item label="自定义指令（追加到系统提示词）" name="custom_instructions">
            <TextArea
              rows={3}
              placeholder="例如：这个用户是我们的VIP客户，请格外耐心，并主动询问是否需要升级套餐"
            />
          </Form.Item>
          <Form.Item label="备注（记录原因）" name="note">
            <Input placeholder="例如：用户反馈AI回复太正式" />
          </Form.Item>
        </Form>

        <Divider style={{ margin: '12px 0 8px' }}>
          <Space size={4}>
            <HistoryOutlined />
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>策略历史</span>
          </Space>
        </Divider>

        {personalHistory.length === 0 && !historyLoading ? (
          <Empty description="暂无策略记录" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: '8px 0' }} />
        ) : (
          <Table
            dataSource={personalHistory}
            columns={historyColumns}
            rowKey="id"
            size="small"
            loading={historyLoading}
            pagination={{ pageSize: 5, size: 'small', hideOnSinglePage: true }}
            scroll={{ x: 420 }}
          />
        )}
      </Modal>
    </div>
  )
}

export default UserProfile
