import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'
import { useDashboardStore } from '../store'
import type { WsNewMessagePayload, WsProfileUpdatedPayload, WsStrategyAppliedPayload } from '../types'
import type { BotLogEntry } from '../store'

/**
 * Manages a Socket.IO connection with auto-reconnect.
 *
 * - Connects once on mount.
 * - Subscribes to the currently selected JID's room whenever it changes.
 * - Dispatches real-time events into the Zustand store.
 */
export function useWebSocket(): void {
  const socketRef = useRef<Socket | null>(null)
  const selectedJid = useDashboardStore((s) => s.selectedJid)
  const selectedLogBotId = useDashboardStore((s) => s.selectedLogBotId)
  const setWsConnected = useDashboardStore((s) => s.setWsConnected)
  const prependMessage = useDashboardStore((s) => s.prependMessage)
  const updateMessageTranslation = useDashboardStore((s) => s.updateMessageTranslation)
  const setProfile = useDashboardStore((s) => s.setProfile)
  const setCurrentStrategy = useDashboardStore((s) => s.setCurrentStrategy)
  const setGlobalStrategy = useDashboardStore((s) => s.setGlobalStrategy)
  const incrementUnread = useDashboardStore((s) => s.incrementUnread)
  const updateContactAvatar = useDashboardStore((s) => s.updateContactAvatar)
  const appendBotLog = useDashboardStore((s) => s.appendBotLog)
  const appendBotLogs = useDashboardStore((s) => s.appendBotLogs)
  const setActiveBots = useDashboardStore((s) => s.setActiveBots)

  // Helper: fetch bot list from API and update store
  const fetchBotList = async (token: string) => {
    try {
      const res = await fetch('/api/bot/list', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) {
        const data = await res.json()
        setActiveBots(data.bots ?? [])
      }
    } catch {
      // non-fatal
    }
  }

  // Connect once on mount
  useEffect(() => {
    const socket = io('/', {
      path: '/socket.io',
      transports: ['polling'],   // WS upgrade fails through Vite proxy; polling is sufficient
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10_000,
    })
    socketRef.current = socket

    socket.on('connect', () => {
      setWsConnected(true)
      // Subscribe to log room on every (re)connect
      const { selectedLogBotId: botId, apiToken } = useDashboardStore.getState()
      socket.emit('subscribe_logs', botId ? { bot_id: botId } : {})
      // Refresh bot list on connect
      fetchBotList(apiToken)
    })

    socket.on('disconnect', () => {
      setWsConnected(false)
    })

    socket.on('new_message', (payload: WsNewMessagePayload) => {
      const { selectedJid: currentJid, translationEnabled, translationTargetLang, apiToken } = useDashboardStore.getState()
      const msg = payload.message
      prependMessage(msg)
      if (payload.jid !== currentJid) {
        incrementUnread(payload.jid)
      }

      // Auto-translate incoming text messages when the toggle is on for this JID
      if (
        msg.direction === 'in' &&
        !msg.media_path &&
        msg.content?.trim() &&
        translationEnabled[payload.jid]
      ) {
        fetch('/api/translation/translate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
          },
          body: JSON.stringify({
            text: msg.content,
            from_lang: 'auto',
            to_lang: translationTargetLang || 'zh',
          }),
        })
          .then((r) => (r.ok ? r.json() : null))
          .then((data) => {
            if (data?.translated && data.translated !== msg.content) {
              updateMessageTranslation(msg.id, data.translated)
              // Persist translation to DB for audit and cross-device consistency
              const { apiToken: tok } = useDashboardStore.getState()
              fetch(`/api/translation/message/${msg.id}`, {
                method: 'PATCH',
                headers: {
                  'Content-Type': 'application/json',
                  ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
                },
                body: JSON.stringify({ translated_content: data.translated }),
              }).catch(() => { /* non-fatal */ })
            }
          })
          .catch(() => { /* silent — original content remains visible */ })
      }
    })

    socket.on('profile_updated', (payload: WsProfileUpdatedPayload) => {
      const { selectedJid: currentJid } = useDashboardStore.getState()
      if (payload.jid === currentJid) {
        setProfile(payload.profile)
      }
    })

    socket.on('strategy_applied', (payload: WsStrategyAppliedPayload) => {
      if (payload.jid === null) {
        // Global strategy
        setGlobalStrategy(payload.strategy)
      } else {
        const { selectedJid: currentJid } = useDashboardStore.getState()
        if (payload.jid === currentJid) {
          setCurrentStrategy(payload.strategy)
        }
      }
    })

    socket.on('avatar_updated', (payload: { jid: string; avatar_url: string }) => {
      updateContactAvatar(payload.jid, payload.avatar_url)
    })

    socket.on('bot_log', (entry: BotLogEntry) => {
      const { selectedLogBotId: botId } = useDashboardStore.getState()
      // If a specific bot is selected, only show that bot's entries
      if (!botId || entry.bot_id === botId) {
        appendBotLog(entry)
      }
    })

    socket.on('bot_log_snapshot', (entries: BotLogEntry[]) => {
      appendBotLogs(entries)
    })

    // Poll bot list every 10 s so the log filter dropdown stays current
    const botListInterval = setInterval(() => {
      const { apiToken } = useDashboardStore.getState()
      fetchBotList(apiToken)
    }, 10_000)

    return () => {
      clearInterval(botListInterval)
      socket.disconnect()
      socketRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Subscribe to the selected JID's room whenever it changes
  useEffect(() => {
    const socket = socketRef.current
    if (!socket) return

    // Unsubscribe from previous JID will happen via subscribe_user — server
    // handles room management.
    if (selectedJid) {
      socket.emit('subscribe_user', { jid: selectedJid })
    }
  }, [selectedJid])

  // Re-subscribe to the correct log room whenever the selected bot changes
  useEffect(() => {
    const socket = socketRef.current
    if (!socket || !socket.connected) return
    // Unsubscribe from all log rooms first (no-op if not joined)
    socket.emit('unsubscribe_logs', {})
    socket.emit('unsubscribe_logs', selectedLogBotId ? { bot_id: selectedLogBotId } : {})
    // Subscribe to the new selection
    socket.emit('subscribe_logs', selectedLogBotId ? { bot_id: selectedLogBotId } : {})
  }, [selectedLogBotId])
}
