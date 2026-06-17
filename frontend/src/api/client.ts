import type {
  Club, MarketPlayer, SquadPlayer, SeasonState,
  LineupState, RoundResult, SeasonResult, StandingEntry,
} from '../types'

export const AUTH_KEY = 'fv_api_key'

function getApiKey(): string | null {
  return localStorage.getItem(AUTH_KEY)
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = body ? { 'Content-Type': 'application/json' } : {}
  const key = getApiKey()
  if (key) headers['Authorization'] = `Bearer ${key}`

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(err.detail ?? err.message ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

const get  = <T>(p: string)             => request<T>('GET', p)
const post = <T>(p: string, b?: unknown) => request<T>('POST', p, b)
const put  = <T>(p: string, b: unknown)  => request<T>('PUT', p, b)

// ── Clube ──────────────────────────────────────────────────────────────────
export const api = {
  createClub: (user_id: string, nome: string, cores: string[]) =>
    post<Club>('/clubs', { user_id, nome, cores }),

  getClub: (id: string) =>
    get<Club>(`/clubs/${id}`),

  getSquad: (id: string) =>
    get<SquadPlayer[]>(`/clubs/${id}/squad`),

  getSeason: (id: string) =>
    get<SeasonState>(`/clubs/${id}/season`),

  getLineup: (id: string) =>
    get<LineupState>(`/clubs/${id}/lineup`),

  // ── Mercado ──────────────────────────────────────────────────────────────
  getMarket: () =>
    get<MarketPlayer[]>('/market'),

  buyPlayer: (clubId: string, playerId: string) =>
    post<{ saldo_final: number }>(`/clubs/${clubId}/transfers`, { player_id: playerId }),

  // ── Loop ──────────────────────────────────────────────────────────────────
  setLineup: (
    clubId: string,
    formacao: string,
    titulares: { player_id: string; posicao: string }[],
    reservas: string[],
  ) => put<{ valida: boolean }>(`/clubs/${clubId}/lineup`, { formacao, titulares, reservas }),

  scoreRound: (clubId: string, rodadaId: string) =>
    post<RoundResult>(`/clubs/${clubId}/rounds/${rodadaId}`),

  closeSeason: (clubId: string) =>
    post<SeasonResult>(`/clubs/${clubId}/season/close`),

  // ── Mercado P2P ───────────────────────────────────────────────────────────
  listPlayer: (clubId: string, playerId: string, preco_fvs: number) =>
    post<{ player_id: string; seller_club_id: string; preco_fvs: number }>(
      `/clubs/${clubId}/squad/${playerId}/list`, { preco_fvs }),

  delistPlayer: (clubId: string, playerId: string) =>
    request<void>('DELETE', `/clubs/${clubId}/squad/${playerId}/list`),

  // ── Auth ──────────────────────────────────────────────────────────────────
  register: (user_id: string) =>
    post<{ user_id: string; api_key: string }>('/auth/register', { user_id }),

  // ── Standings ─────────────────────────────────────────────────────────────
  getStandings: (divisao: string) =>
    get<StandingEntry[]>(`/divisions/${encodeURIComponent(divisao)}/standings`),

  // ── Relógio de mundo (Fase 3) ───────────────────────────────────────────────
  getClockStatus: () =>
    get<ClockStatus>('/admin/clock'),

  // ── Feed de notícias (Fase 4) ────────────────────────────────────────────────
  getNews: (clubId?: string, limit = 20) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (clubId) params.set('club_id', clubId)
    return get<NewsItem[]>(`/news?${params.toString()}`)
  },
}

export interface NewsItem {
  ts: number
  club_id: string
  tipo: 'RODADA' | 'TEMPORADA_ENCERRADA' | 'DECISAO_IA' | 'PERSONALIDADE' | 'TRANSFERENCIA_P2P' | 'FUNDACAO'
  texto: string | null
  resultado: string | null
}

export interface ClockStatus {
  last_tick_at: string | null
  next_tick_in: number
  round_duration_seconds: number
}

export interface WorldEvent {
  club_id: string
  tipo: 'RODADA' | 'TEMPORADA_ENCERRADA'
  rodada_id: string | null
  pontos: number | null
  resultado: string | null
}

/** Assina eventos do relógio de mundo para um clube via SSE. Retorna função de cleanup. */
export function subscribeToEvents(clubId: string, onEvent: (e: WorldEvent) => void): () => void {
  const es = new EventSource(`/clubs/${clubId}/events`)
  es.onmessage = ev => {
    try {
      onEvent(JSON.parse(ev.data) as WorldEvent)
    } catch {
      // mensagem malformada (ex: heartbeat) — ignora
    }
  }
  return () => es.close()
}
