import React, { useEffect, useState } from 'react'
import { List, Input, Badge, Avatar, Typography, Spin, Empty } from 'antd'
import { UserOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { fetchChatHistory, fetchContacts, fetchContactAvatar, refreshContactAvatar } from '../../api/endpoints'
import { useDashboardStore } from '../../store'

const { Text } = Typography

// ---- Helpers ----

function jidToName(jid: string): string {
  // Strip WhatsApp JID suffix for display
  return jid.replace(/@s\.whatsapp\.net$/, '').replace(/@.*$/, '')
}

/**
 * ContactList — shows all known contacts populated from chat history.
 *
 * In a real deployment the backend would provide a contacts endpoint.  Here
 * we derive the contact list from the first page of chat history per user,
 * stored in the Zustand store.
 */
const ContactList: React.FC = () => {
  const contacts = useDashboardStore((s) => s.contacts)
  const selectedJid = useDashboardStore((s) => s.selectedJid)
  const selectJid = useDashboardStore((s) => s.selectJid)
  const setContacts = useDashboardStore((s) => s.setContacts)
  const updateContactAvatar = useDashboardStore((s) => s.updateContactAvatar)
  const setMessages = useDashboardStore((s) => s.setMessages)
  const setMessagesLoading = useDashboardStore((s) => s.setMessagesLoading)
  const clearUnread = useDashboardStore((s) => s.clearUnread)

  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  // Bootstrap contacts from /api/contacts on first load
  useEffect(() => {
    setLoading(true)
    fetchContacts()
      .then((list) => {
        if (list.length > 0) {
          setContacts(
            list.map((c) => ({
              jid: c.user_jid,
              display_name: c.user_jid
                .replace(/@s\.whatsapp\.net$/, '')
                .replace(/@.*$/, ''),
              last_message: c.last_message,
              last_timestamp: c.last_timestamp,
              unread: 0,
              avatar_url: c.avatar_url ?? null,
            })),
          )
        }
      })
      .catch(() => {
        // If the API is unavailable, fall back gracefully to any WS-populated contacts
      })
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filtered = contacts.filter((c) =>
    jidToName(c.jid).toLowerCase().includes(search.toLowerCase()),
  )

  async function handleSelect(jid: string) {
    if (jid === selectedJid) return
    selectJid(jid)
    clearUnread(jid)
    setMessagesLoading(true)
    try {
      const res = await fetchChatHistory(jid, 1, 50)
      setMessages(res.messages, res.page, res.total)
    } catch {
      setMessages([], 1, 0)
    } finally {
      setMessagesLoading(false)
    }

    // Refresh avatar for this contact once in the background
    refreshContactAvatar(jid).catch(() => null)
    // Poll for the updated URL at 4 s, 10 s, 20 s after enqueue
    const delays = [4000, 10000, 20000]
    delays.forEach((ms) => {
      setTimeout(() => {
        fetchContactAvatar(jid)
          .then(({ avatar_url }) => {
            if (avatar_url) updateContactAvatar(jid, avatar_url)
          })
          .catch(() => null)
      }, ms)
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px 8px' }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索联系人"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="small"
          allowClear
        />
      </div>

      {loading ? (
        <Spin style={{ margin: 'auto' }} />
      ) : filtered.length === 0 ? (
        <Empty description="暂无联系人" style={{ marginTop: 40 }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          style={{ overflow: 'auto', flex: 1 }}
          dataSource={filtered}
          renderItem={(contact) => (
            <List.Item
              key={contact.jid}
              style={{
                padding: '10px 12px',
                cursor: 'pointer',
                background: contact.jid === selectedJid ? '#e6f7ff' : undefined,
                borderLeft: contact.jid === selectedJid ? '3px solid #1890ff' : '3px solid transparent',
              }}
              onClick={() => handleSelect(contact.jid)}
            >
              <List.Item.Meta
                avatar={
                  <Badge count={contact.unread} size="small">
                    <Avatar
                      src={contact.avatar_url ?? undefined}
                      icon={<UserOutlined />}
                      size={36}
                    />
                  </Badge>
                }
                title={
                  <Text strong style={{ fontSize: 13 }}>
                    {jidToName(contact.jid)}
                  </Text>
                }
                description={
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text type="secondary" ellipsis style={{ fontSize: 12, maxWidth: 120 }}>
                      {contact.last_message ?? '—'}
                    </Text>
                    {contact.last_timestamp && (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {dayjs.unix(contact.last_timestamp).format('HH:mm')}
                      </Text>
                    )}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      )}
    </div>
  )
}

export default ContactList
