import React, { useEffect, useState } from 'react'
import { Layout, Menu, Badge, Tooltip, Typography, Space } from 'antd'
import logoSrc from '../../assets/zowsup-logo.png'
import {
  DashboardOutlined,
  SettingOutlined,
  WifiOutlined,
  DisconnectOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useDashboardStore } from '../../store'
import { fetchBotStatus, BotStatus } from '../../api/endpoints'

const { Sider, Header, Content } = Layout
const { Text } = Typography

interface AppLayoutProps {
  children: React.ReactNode
}

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const wsConnected = useDashboardStore((s) => s.wsConnected)
  const collapsed = useDashboardStore((s) => s.siderCollapsed)
  const setSiderCollapsed = useDashboardStore((s) => s.setSiderCollapsed)
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null)

  // Poll bot status every 10 s
  useEffect(() => {
    const load = () => {
      fetchBotStatus()
        .then(setBotStatus)
        .catch(() => setBotStatus(null))
    }
    load()
    const timer = setInterval(load, 10_000)
    return () => clearInterval(timer)
  }, [])

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '仪表板',
    },
    {
      key: '/strategy',
      icon: <SettingOutlined />,
      label: '策略管理',
    },
    {
      key: '/login',
      icon: <RobotOutlined />,
      label: 'Bot 管理',
    },
  ]

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setSiderCollapsed}
        theme="dark"
        width={200}
      >
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            userSelect: 'none',
            overflow: 'hidden',
            padding: '0 8px',
          }}
        >
          {collapsed ? (
            <span style={{ color: '#4ade80', fontWeight: 700, fontSize: 16, letterSpacing: 1 }}>
              ZS
            </span>
          ) : (
            <img src={logoSrc} alt="ZOWSUP" style={{ height: 34, objectFit: 'contain' }} />
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <Text strong style={{ fontSize: 16 }}>
          
          </Text>
          <Space size={20}>
            {/* Bot online status */}
            <Tooltip
              title={
                botStatus?.running
                  ? `Bot 在线${botStatus.jid ? ` — ${botStatus.jid}` : ''}`
                  : 'Bot 离线'
              }
            >
              <Badge
                status={botStatus?.running ? 'success' : 'default'}
                text={
                  botStatus?.running ? (
                    <span style={{ color: '#52c41a' }}>
                      <RobotOutlined style={{ marginRight: 4 }} />
                      {botStatus.jid
                        ? botStatus.jid.replace('@s.whatsapp.net', '')
                        : '在线'}
                    </span>
                  ) : (
                    <span style={{ color: '#8c8c8c' }}>
                      <RobotOutlined style={{ marginRight: 4 }} />
                      离线
                    </span>
                  )
                }
              />
            </Tooltip>

            {/* WebSocket connection status */}
            <Tooltip title={wsConnected ? 'WebSocket 已连接' : 'WebSocket 未连接'}>
              <Badge
                status={wsConnected ? 'success' : 'error'}
                text={
                  wsConnected ? (
                    <span>
                      <WifiOutlined style={{ color: '#52c41a', marginRight: 4 }} />
                      实时
                    </span>
                  ) : (
                    <span>
                      <DisconnectOutlined style={{ color: '#ff4d4f', marginRight: 4 }} />
                      断开
                    </span>
                  )
                }
              />
            </Tooltip>
          </Space>
        </Header>

        <Content style={{ overflow: 'auto', background: '#f0f2f5' }}>{children}</Content>
      </Layout>
    </Layout>
  )
}

export default AppLayout
