import React from 'react'
import { Row, Col, Card } from 'antd'
import ContactList from '../components/ContactList/ContactList'
import ChatHistory from '../components/ChatHistory/ChatHistory'
import UserProfile from '../components/UserProfile/UserProfile'
import StatisticsPanel from '../components/StatisticsPanel/StatisticsPanel'

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
  return (
    <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Top row — 3 columns */}
      <Row gutter={12} style={{ flex: '0 0 calc(60vh - 60px)' }}>
        <Col flex="240px">
          <Card
            size="small"
            title="联系人"
            bodyStyle={{ padding: 0, height: 'calc(60vh - 100px)', overflow: 'hidden' }}
            style={{ height: '100%' }}
          >
            <ContactList />
          </Card>
        </Col>

        <Col flex="1">
          <Card
            size="small"
            title="聊天记录"
            bodyStyle={{ padding: 0, height: 'calc(60vh - 100px)', overflow: 'hidden' }}
            style={{ height: '100%' }}
          >
            <ChatHistory />
          </Card>
        </Col>

        <Col flex="280px">
          <Card
            size="small"
            title="用户画像"
            bodyStyle={{ height: 'calc(60vh - 100px)', overflow: 'auto', padding: 0 }}
            style={{ height: '100%' }}
          >
            <UserProfile />
          </Card>
        </Col>
      </Row>

      {/* Bottom row — statistics */}
      <Card size="small" title="统计数据" style={{ flex: 1 }}>
        <StatisticsPanel />
      </Card>
    </div>
  )
}

export default DashboardPage
