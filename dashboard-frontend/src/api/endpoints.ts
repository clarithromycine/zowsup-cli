import apiClient from './client'
import type {
  UserProfile,
  ChatHistoryResponse,
  Statistics,
  AIThoughtsResponse,
  StrategyResponse,
  StrategyHistoryResponse,
  StrategyConflictsResponse,
  StrategyConfig,
} from '../types'

// ---- Health ----

export async function fetchHealth(): Promise<{ status: string }> {
  const { data } = await apiClient.get('/health')
  return data
}

// ---- Contacts ----

export interface ContactSummary {
  user_jid: string
  last_message: string | null
  last_timestamp: number | null
  message_count: number
}

export async function fetchContacts(): Promise<ContactSummary[]> {
  const { data } = await apiClient.get('/contacts')
  return data.contacts as ContactSummary[]
}

// ---- User Profile ----

export async function fetchUserProfile(jid: string): Promise<UserProfile> {
  const { data } = await apiClient.get('/user-profile', { params: { jid } })
  return data
}

// ---- Chat History ----

export async function fetchChatHistory(
  jid: string,
  page = 1,
  pageSize = 50,
): Promise<ChatHistoryResponse> {
  const { data } = await apiClient.get('/chat-history', {
    params: { jid, page, page_size: pageSize },
  })
  return data
}

// ---- Statistics ----

export async function fetchStatistics(): Promise<Statistics> {
  const { data } = await apiClient.get('/statistics')
  return data
}

// ---- AI Thoughts ----

export async function fetchUserAIThoughts(
  jid: string,
  page = 1,
  pageSize = 20,
): Promise<AIThoughtsResponse> {
  const { data } = await apiClient.get('/user-ai-thoughts', {
    params: { jid, page, page_size: pageSize },
  })
  return data
}

// ---- Strategy ----

export async function fetchStrategy(jid?: string): Promise<StrategyResponse> {
  const { data } = await apiClient.get('/strategy', { params: jid ? { jid } : {} })
  return data
}

export async function fetchStrategyHistory(jid?: string): Promise<StrategyHistoryResponse> {
  const { data } = await apiClient.get('/strategy/history', { params: jid ? { jid } : {} })
  return data
}

export async function postApplyStrategy(
  jid: string,
  config: StrategyConfig,
  note?: string,
): Promise<{ strategy_id: number; jid: string; config: StrategyConfig }> {
  const { data } = await apiClient.post('/apply-strategy', { jid, config, note })
  return data
}

export async function postApplyGlobalStrategy(
  config: StrategyConfig,
  note?: string,
): Promise<{ strategy_id: number; config: StrategyConfig }> {
  const { data } = await apiClient.post('/apply-global-strategy', { config, note })
  return data
}

export async function postRollbackStrategy(
  jid: string | null,
  steps = 1,
): Promise<{ rolled_back_to: number; jid: string | null }> {
  const { data } = await apiClient.post('/strategy/rollback', { jid, steps })
  return data
}

export async function fetchStrategyConflicts(jid: string): Promise<StrategyConflictsResponse> {
  const { data } = await apiClient.get('/strategy/conflicts', { params: { jid } })
  return data
}

// ---- Bot Control (Phase 5) ----

export interface BotStatus {
  running: boolean
  jid: string | null
  pid: number | null
  started_at: number | null
  uptime_seconds: number | null
}

export async function fetchBotStatus(): Promise<BotStatus> {
  const { data } = await apiClient.get('/bot/status')
  return data
}

export async function postBotLoginScan(): Promise<{ ok: boolean; pid: number }> {
  const { data } = await apiClient.post('/bot/login-scan')
  return data
}

export async function postBotLoginLinkcode(
  phone: string,
): Promise<{ ok: boolean; link_code: string }> {
  const { data } = await apiClient.post('/bot/login-linkcode', { phone })
  return data
}

export async function postBotLogout(): Promise<{ ok: boolean; pid: number }> {
  const { data } = await apiClient.post('/bot/logout')
  return data
}

export async function postBotStart(
  phone: string,
): Promise<{ ok: boolean; pid: number }> {
  const { data } = await apiClient.post('/bot/start', { phone })
  return data
}
