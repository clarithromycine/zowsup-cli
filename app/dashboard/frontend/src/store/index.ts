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
  push_name?: string | null
  last_message: string | null
  last_timestamp: number | null
  unread: number
  avatar_url?: string | null
  bot_jid?: string | null
}

export interface BotInfo {
  phone: string
  jid: string | null
  running: boolean
  uptime_seconds: number | null
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

  // Logs
  botLogs: BotLogEntry[]

  // Multi-account
  activeBots: BotInfo[]
  selectedLogBotId: string | null

  // UI
  siderCollapsed: boolean

  // Triggers GroupInfo re-fetch when a group message arrives
  groupInfoRevision: number

  // Incremented when bot status changes (e.g. agent bot starts/stops)
  // so AppLayout can react immediately without waiting for the poll interval
  botAccountsRevision: number

  // Translation: per-jid enabled flag + target language
  translationEnabled: Record<string, boolean>
  translationTargetLang: string

  // Per-conversation AI disable (human takeover).
  // true = AI disabled for this JID; absent/false = AI enabled.
  aiDisabledJids: Record<string, boolean>
}

export interface BotLogEntry {
  ts: string
  level: string
  logger: string
  message: string
  bot_id?: string
}

interface DashboardActions {
  setApiToken: (token: string) => void
  setWsConnected: (v: boolean) => void

  setContacts: (contacts: ContactEntry[]) => void
  updateContactAvatar: (jid: string, avatar_url: string | null) => void
  selectJid: (jid: string | null) => void
  incrementUnread: (jid: string) => void
  clearUnread: (jid: string) => void

  setMessages: (messages: ChatMessage[], page: number, total: number) => void
  prependMessage: (msg: ChatMessage) => void
  updateMessageTranslation: (id: number, translated_content: string) => void
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

  setActiveBots: (bots: BotInfo[]) => void
  setSelectedLogBotId: (id: string | null) => void

  appendBotLog: (entry: BotLogEntry) => void
  appendBotLogs: (entries: BotLogEntry[]) => void
  clearBotLogs: () => void

  bumpBotAccountsRevision: () => void

  // Translation actions
  toggleTranslation: (jid: string) => void
  setTranslationEnabled: (jid: string, enabled: boolean) => void
  setTranslationTargetLang: (lang: string) => void

  // AI toggle actions (per-conversation human takeover)
  toggleAiForJid: (jid: string) => void
  setAiForJid: (jid: string, enabled: boolean) => void
}

type StoreState = DashboardState & DashboardActions

// ---- Store ----

const DEFAULT_GLOBAL_STRATEGY: StrategyConfig = {
  response_style: 'casual',
  tone: 'friendly',
  language: 'auto',
}

// Remove legacy localStorage translation cache (translations now stored in DB)
localStorage.removeItem('msg_translations')

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

    botLogs: [],

    activeBots: [],
    selectedLogBotId: null,

    groupInfoRevision: 0,
    botAccountsRevision: 0,

    translationEnabled: JSON.parse(localStorage.getItem('translation_enabled') ?? '{}') as Record<string, boolean>,
    translationTargetLang: localStorage.getItem('translation_target_lang') ?? 'zh',

    aiDisabledJids: JSON.parse(localStorage.getItem('ai_disabled_jids') ?? '{}') as Record<string, boolean>,

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
        s.contacts = [...contacts].sort(
          (a: ContactEntry, b: ContactEntry) => (b.last_timestamp ?? 0) - (a.last_timestamp ?? 0)
        )
      }),

    updateContactAvatar: (jid, avatar_url) =>
      set((s) => {
        const c = s.contacts.find((x: ContactEntry) => x.jid === jid)
        if (c) c.avatar_url = avatar_url
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
          if (msg.bot_jid) c.bot_jid = msg.bot_jid
          // Update push_name from incoming message notify
          if (msg.direction === 'in' && !msg.user_jid.endsWith('@g.us') && msg.notify)
            c.push_name = msg.notify
        } else {
          // Brand-new contact — add to list
          s.contacts.push({
            jid: msg.user_jid,
            display_name: msg.user_jid
              .replace(/@s\.whatsapp\.net$/, '')
              .replace(/@.*$/, ''),
            push_name: msg.direction === 'in' && !msg.user_jid.endsWith('@g.us') ? (msg.notify ?? null) : null,
            last_message: msg.content,
            last_timestamp: msg.timestamp,
            unread: 0,
            bot_jid: msg.bot_jid ?? null,
          })
        }
        // Bump groupInfoRevision so GroupInfo re-fetches when a group message arrives
        if (msg.user_jid.endsWith('@g.us')) {
          s.groupInfoRevision += 1
        }
        // Re-sort by most recent message, keeping active JID visually tracked via selectedJid state
        s.contacts.sort((a: ContactEntry, b: ContactEntry) =>
          (b.last_timestamp ?? 0) - (a.last_timestamp ?? 0)
        )
      }),

    setMessagesLoading: (v) =>
      set((s) => {
        s.messagesLoading = v
      }),

    updateMessageTranslation: (id, translated_content) =>
      set((s) => {
        const idx = s.messages.findIndex((m: ChatMessage) => m.id === id)
        if (idx !== -1) {
          s.messages[idx].translated_content = translated_content
        }
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

    setActiveBots: (bots) =>
      set((s) => {
        s.activeBots = bots
      }),

    setSelectedLogBotId: (id) =>
      set((s) => {
        s.selectedLogBotId = id
        s.botLogs = []
      }),

    appendBotLog: (entry) =>
      set((s) => {
        s.botLogs.push(entry)
        if (s.botLogs.length > 500) s.botLogs.shift()
      }),

    appendBotLogs: (entries) =>
      set((s) => {
        s.botLogs.push(...entries)
        if (s.botLogs.length > 500) s.botLogs.splice(0, s.botLogs.length - 500)
      }),

    clearBotLogs: () =>
      set((s) => {
        s.botLogs = []
      }),

    bumpBotAccountsRevision: () =>
      set((s) => {
        s.botAccountsRevision += 1
      }),

    toggleTranslation: (jid) =>
      set((s) => {
        s.translationEnabled[jid] = !s.translationEnabled[jid]
        localStorage.setItem('translation_enabled', JSON.stringify(s.translationEnabled))
      }),

    setTranslationEnabled: (jid, enabled) =>
      set((s) => {
        s.translationEnabled[jid] = enabled
        localStorage.setItem('translation_enabled', JSON.stringify(s.translationEnabled))
      }),

    setTranslationTargetLang: (lang) =>
      set((s) => {
        s.translationTargetLang = lang
        localStorage.setItem('translation_target_lang', lang)
      }),

    toggleAiForJid: (jid) =>
      set((s) => {
        s.aiDisabledJids[jid] = !s.aiDisabledJids[jid]
        localStorage.setItem('ai_disabled_jids', JSON.stringify(s.aiDisabledJids))
      }),

    setAiForJid: (jid, enabled) =>
      set((s) => {
        s.aiDisabledJids[jid] = !enabled
        localStorage.setItem('ai_disabled_jids', JSON.stringify(s.aiDisabledJids))
      }),
  })),
)
