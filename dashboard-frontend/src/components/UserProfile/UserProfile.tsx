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
} from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  EditOutlined,
  RollbackOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { fetchUserProfile, postApplyStrategy, postRollbackStrategy } from '../../api/endpoints'
import { useDashboardStore } from '../../store'
import type { StrategyConfig } from '../../types'

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

  useEffect(() => {
    if (!selectedJid) return
    setProfileLoading(true)
    fetchUserProfile(selectedJid)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setProfileLoading(false))
  }, [selectedJid]) // eslint-disable-line react-hooks/exhaustive-deps

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
      // Refresh profile to show updated strategy
      fetchUserProfile(selectedJid).then(setProfile).catch(() => null)
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
    } catch {
      message.error('回滚失败')
    } finally {
      setRolling(false)
    }
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
          <Tag color="blue">{profile.user_category ?? '—'}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="沟通风格">
          <Tag color="purple">{profile.communication_style ?? '—'}</Tag>
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
        width={480}
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
      </Modal>
    </div>
  )
}

export default UserProfile
