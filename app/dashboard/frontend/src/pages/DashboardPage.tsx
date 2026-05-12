import React, { useCallback } from 'react'
import { Row, Col, Card, Space, Switch, Tooltip } from 'antd'
import { RobotOutlined, TranslationOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import ContactList from '../components/ContactList/ContactList'
import ChatHistory from '../components/ChatHistory/ChatHistory'
import UserProfile from '../components/UserProfile/UserProfile'
import GroupInfo from '../components/GroupInfo/GroupInfo'
import StatisticsPanel from '../components/StatisticsPanel/StatisticsPanel'
import { useDashboardStore } from '../store'
import { saveAiSettings } from '../api/endpoints'

/**
 * Main Dashboard page.
 *
 * Layout (desktop):
 *   ┌──────────────┬──────────────────────────────┬───────────────┐
 *   │ ContactList  │       ChatHistory            │  UserProfile  │
 *   │  (240px)     │                              │   (280px)     │
 *   └──────────────┴──────────────────────────────┴───────────────┘
 *   │                   StatisticsPanel                           │
 *   └─────────────────────────────────────────────────────────────┘
 */
const DashboardPage: React.FC = () => {
  const { t } = useTranslation()
  const selectedJid = useDashboardStore((s) => s.selectedJid)
  const isGroup = selectedJid?.endsWith('@g.us') ?? false

  const translationEnabled = useDashboardStore((s) => s.translationEnabled)
  const toggleTranslation = useDashboardStore((s) => s.toggleTranslation)
  const aiDisabledJids = useDashboardStore((s) => s.aiDisabledJids)
  const toggleAiForJid = useDashboardStore((s) => s.toggleAiForJid)

  const handleAiToggle = useCallback(async (jid: string) => {
    const currentlyDisabled = !!aiDisabledJids[jid]
    const newEnabled = currentlyDisabled        // toggling: if disabled → enable, if enabled → disable
    toggleAiForJid(jid)
    try {
      await saveAiSettings(jid, newEnabled)
    } catch {
      // best-effort backend sync; local state already updated
    }
  }, [aiDisabledJids, toggleAiForJid])

  const chatHeaderExtra = selectedJid ? (
    <Space size={12}>
      <Tooltip title={aiDisabledJids[selectedJid] ? t('chat.aiEnable') : t('chat.aiDisable')}>
        <Space size={4} style={{ cursor: 'pointer' }}>
          <RobotOutlined
            style={{ fontSize: 14, color: aiDisabledJids[selectedJid] ? '#d9d9d9' : '#52c41a' }}
          />
          <Switch
            size="small"
            checked={!aiDisabledJids[selectedJid]}
            onChange={() => handleAiToggle(selectedJid)}
          />
        </Space>
      </Tooltip>
      <Tooltip title={translationEnabled[selectedJid] ? t('translate.disableFor') : t('translate.enableFor')}>
        <Space size={4} style={{ cursor: 'pointer' }}>
          <TranslationOutlined
            style={{ fontSize: 14, color: translationEnabled[selectedJid] ? '#1890ff' : '#d9d9d9' }}
          />
          <Switch
            size="small"
            checked={!!translationEnabled[selectedJid]}
            onChange={() => toggleTranslation(selectedJid)}
          />
        </Space>
      </Tooltip>
    </Space>
  ) : null
  return (
    <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Top row — 3 columns */}
      <Row gutter={12} style={{ flex: '0 0 calc(60vh - 60px)' }}>
        <Col flex="288px">
          <Card
            size="small"
            title={t('dashboard.contacts')}
            bodyStyle={{ padding: 0, height: 'calc(60vh - 100px)', overflow: 'hidden' }}
            style={{ height: '100%' }}
          >
            <ContactList />
          </Card>
        </Col>

        <Col flex="1">
          <Card
            size="small"
            title={t('dashboard.chatHistory')}
            extra={chatHeaderExtra}
            bodyStyle={{ padding: 0, height: 'calc(60vh - 100px)', overflow: 'hidden' }}
            style={{ height: '100%' }}
          >
            <ChatHistory />
          </Card>
        </Col>

        <Col flex="420px">
          <Card
            size="small"
            title={isGroup ? t('dashboard.groupInfo') : t('dashboard.userProfile')}
            bodyStyle={{ height: 'calc(60vh - 100px)', overflow: 'auto', padding: 0 }}
            style={{ height: '100%' }}
          >
            {isGroup ? <GroupInfo jid={selectedJid!} /> : <UserProfile />}
          </Card>
        </Col>
      </Row>

      {/* Bottom row — statistics */}
      <Card size="small" title={t('dashboard.statistics')} style={{ flex: 1 }}>
        <StatisticsPanel />
      </Card>
    </div>
  )
}

export default DashboardPage
