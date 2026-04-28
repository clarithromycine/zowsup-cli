import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'
import { useDashboardStore } from '../store'
import type { WsNewMessagePayload, WsProfileUpdatedPayload, WsStrategyAppliedPayload } from '../types'

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
  const setWsConnected = useDashboardStore((s) => s.setWsConnected)
  const prependMessage = useDashboardStore((s) => s.prependMessage)
  const setProfile = useDashboardStore((s) => s.setProfile)
  const setCurrentStrategy = useDashboardStore((s) => s.setCurrentStrategy)
  const setGlobalStrategy = useDashboardStore((s) => s.setGlobalStrategy)
  const incrementUnread = useDashboardStore((s) => s.incrementUnread)

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
    })

    socket.on('disconnect', () => {
      setWsConnected(false)
    })

    socket.on('new_message', (payload: WsNewMessagePayload) => {
      const { selectedJid: currentJid } = useDashboardStore.getState()
      prependMessage(payload.message)
      if (payload.jid !== currentJid) {
        incrementUnread(payload.jid)
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

    return () => {
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
}
