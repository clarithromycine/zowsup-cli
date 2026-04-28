import React, { useEffect } from 'react'
import { Row, Col, Card, Statistic, Spin } from 'antd'
import {
  MessageOutlined,
  TeamOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { fetchStatistics } from '../../api/endpoints'
import { useDashboardStore } from '../../store'

const StatisticsPanel: React.FC = () => {
  const stats = useDashboardStore((s) => s.stats)
  const statsLoading = useDashboardStore((s) => s.statsLoading)
  const setStats = useDashboardStore((s) => s.setStats)
  const setStatsLoading = useDashboardStore((s) => s.setStatsLoading)

  // Initial fetch (SSE hook will keep it updated afterwards)
  useEffect(() => {
    setStatsLoading(true)
    fetchStatistics()
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (statsLoading || !stats) {
    return <Spin style={{ display: 'block', margin: '40px auto' }} />
  }

  const aiRate =
    stats.total_messages > 0
      ? ((stats.ai_responses / stats.total_messages) * 100).toFixed(1)
      : '0.0'

  // Pie chart: message composition
  const pieOption = {
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { fontSize: 12 } },
    series: [
      {
        name: '消息构成',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        label: { show: false },
        data: [
          { value: stats.ai_responses, name: 'AI回复' },
          { value: stats.total_messages - stats.ai_responses, name: '其他' },
        ],
      },
    ],
  }

  // Bar chart placeholder: today vs total
  const barOption = {
    tooltip: {},
    xAxis: { data: ['今日消息', '总消息', '活跃用户', 'AI回复'] },
    yAxis: {},
    series: [
      {
        name: '数量',
        type: 'bar',
        data: [
          stats.today_messages,
          stats.total_messages,
          stats.active_users,
          stats.ai_responses,
        ],
        itemStyle: { color: '#1890ff' },
        barMaxWidth: 40,
      },
    ],
  }

  return (
    <div style={{ padding: '0 8px' }}>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="总消息数"
              value={stats.total_messages}
              prefix={<MessageOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="活跃用户"
              value={stats.active_users}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="AI回复"
              value={stats.ai_responses}
              prefix={<RobotOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="今日消息"
              value={stats.today_messages}
              prefix={<ThunderboltOutlined />}
              suffix={<small style={{ fontSize: 11 }}>AI率 {aiRate}%</small>}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[12, 12]}>
        <Col xs={24} sm={12}>
          <Card title="消息构成" size="small">
            <ReactECharts option={pieOption} style={{ height: 200 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card title="数量概览" size="small">
            <ReactECharts option={barOption} style={{ height: 200 }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default StatisticsPanel
