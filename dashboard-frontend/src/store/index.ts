import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type {
  UserProfile,
  ChatMessage,
  Statistics,
  AIThought,
  StrategyConfig,
  StrategyRecord,
} from '../types'

// ---- Types ----

interface ContactEntry {
  jid: string
  display_name: string
  last_message: string | null
  last_timestamp: number | null
  unread: number
}

interface DashboardState {
  // Connection
  apiToken: string
  wsConnected: boolean

  // Contact list
  contacts: ContactEntry[]
  selectedJid: string | null

  // Chat
  messages: ChatMessage[]
  messagesPage: number
  messagesTotal: number
  messagesLoading: boolean

  // Profile
  profile: UserProfile | null
  profileLoading: boolean

  // AI Thoughts
  thoughts: AIThought[]
  thoughtsPage: number
  thoughtsTotal: number

  // Statistics
  stats: Statistics | null
  statsLoading: boolean

  // Strategy
  currentStrategy: StrategyConfig | null
  globalStrategy: StrategyConfig
  strategyHistory: StrategyRecord[]

  // UI
  siderCollapsed: boolean
}

interface DashboardActions {
  setApiToken: (token: string) => void
  setWsConnected: (v: boolean) => void

  setContacts: (contacts: ContactEntry[]) => void
  selectJid: (jid: string | null) => void
  incrementUnread: (jid: string) => void
  clearUnread: (jid: string) => void

  setMessages: (messages: ChatMessage[], page: number, total: number) => void
  prependMessage: (msg: ChatMessage) => void
  setMessagesLoading: (v: boolean) => void

  setProfile: (profile: UserProfile | null) => void
  setProfileLoading: (v: boolean) => void

  setThoughts: (thoughts: AIThought[], page: number, total: number) => void

  setStats: (stats: Statistics) => void
  setStatsLoading: (v: boolean) => void

  setCurrentStrategy: (config: StrategyConfig | null) => void
  setGlobalStrategy: (config: StrategyConfig) => void
  setStrategyHistory: (history: StrategyRecord[]) => void

  setSiderCollapsed: (v: boolean) => void
}

type StoreState = DashboardState & DashboardActions

// ---- Store ----

const DEFAULT_GLOBAL_STRATEGY: StrategyConfig = {
  response_style: 'casual',
  tone: 'friendly',
  language: 'auto',
}

export const useDashboardStore = create<StoreState>()(
  immer((set) => ({
    // ---- Initial State ----
    apiToken: localStorage.getItem('dashboard_api_token') ?? '',
    wsConnected: false,

    contacts: [],
    selectedJid: null,

    messages: [],
    messagesPage: 1,
    messagesTotal: 0,
    messagesLoading: false,

    profile: null,
    profileLoading: false,

    thoughts: [],
    thoughtsPage: 1,
    thoughtsTotal: 0,

    stats: null,
    statsLoading: false,

    currentStrategy: null,
    globalStrategy: DEFAULT_GLOBAL_STRATEGY,
    strategyHistory: [],

    siderCollapsed: false,

    // ---- Actions ----
    setApiToken: (token) =>
      set((s) => {
        s.apiToken = token
      }),

    setWsConnected: (v) =>
      set((s) => {
        s.wsConnected = v
      }),

    setContacts: (contacts) =>
      set((s) => {
        s.contacts = contacts
      }),

    selectJid: (jid) =>
      set((s) => {
        s.selectedJid = jid
        s.messages = []
        s.messagesPage = 1
        s.messagesTotal = 0
        s.profile = null
        s.thoughts = []
      }),

    incrementUnread: (jid) =>
      set((s) => {
        const c = s.contacts.find((x: ContactEntry) => x.jid === jid)
        if (c) c.unread += 1
      }),

    clearUnread: (jid) =>
      set((s) => {
        const c = s.contacts.find((x: ContactEntry) => x.jid === jid)
        if (c) c.unread = 0
      }),

    setMessages: (messages, page, total) =>
      set((s) => {
        s.messages = messages
        s.messagesPage = page
        s.messagesTotal = total
      }),

    prependMessage: (msg) =>
      set((s) => {
        // Only add to the messages list when it belongs to the currently selected JID
        if (msg.user_jid === s.selectedJid) {
          if (!s.messages.some((m: ChatMessage) => m.id === msg.id)) {
            s.messages.unshift(msg)
            s.messagesTotal += 1
          }
        }
        // Upsert the contact entry regardless of which JID is selected
        const c = s.contacts.find((x: ContactEntry) => x.jid === msg.user_jid)
        if (c) {
          c.last_message = msg.content
          c.last_timestamp = msg.timestamp
        } else {
          // Brand-new contact — add to top of the list
          s.contacts.unshift({
            jid: msg.user_jid,
            display_name: msg.user_jid
              .replace(/@s\.whatsapp\.net$/, '')
              .replace(/@.*$/, ''),
            last_message: msg.content,
            last_timestamp: msg.timestamp,
            unread: 0,
          })
        }
      }),

    setMessagesLoading: (v) =>
      set((s) => {
        s.messagesLoading = v
      }),

    setProfile: (profile) =>
      set((s) => {
        s.profile = profile
      }),

    setProfileLoading: (v) =>
      set((s) => {
        s.profileLoading = v
      }),

    setThoughts: (thoughts, page, total) =>
      set((s) => {
        s.thoughts = thoughts
        s.thoughtsPage = page
        s.thoughtsTotal = total
      }),

    setStats: (stats) =>
      set((s) => {
        s.stats = stats
      }),

    setStatsLoading: (v) =>
      set((s) => {
        s.statsLoading = v
      }),

    setCurrentStrategy: (config) =>
      set((s) => {
        s.currentStrategy = config
      }),

    setGlobalStrategy: (config) =>
      set((s) => {
        s.globalStrategy = config
      }),

    setStrategyHistory: (history) =>
      set((s) => {
        s.strategyHistory = history
      }),

    setSiderCollapsed: (v) =>
      set((s) => {
        s.siderCollapsed = v
      }),
  })),
)
