export interface Club {
  id: string
  user_id: string
  nome: string
  escudo: string | null
  cores: string[]
  divisao: string
  pontos_temporada: number
  saldo_fvs: number
}

export interface MarketPlayer {
  player_id: string
  posicao: string
  setor: string
  ovr: number
  idade: number
  valor_fvs: number
  vendedor_club_id: string | null  // null = NPC; preenchido = oferta P2P
}

export interface SquadPlayer {
  player_id: string
  posicao: string
  setor: string
  ovr: number
  forma: number
  idade: number
  valor_fvs: number
}

export interface SeasonState {
  temporada: number
  divisao: string
  status: string
  rodadas_jogadas: number
  rodadas_total: number
  pontos: number
}

export interface TitularOut {
  player_id: string
  slot: string
}

export interface LineupState {
  formacao: string
  titulares: TitularOut[]
  reservas: string[]
}

export interface PlayerScore {
  player_id: string
  slot: string
  pontos: number
  nota: number
  gols: number
  assistencias: number
  defesas: number
  gols_sofridos: number
  clean_sheet: boolean
}

export interface RoundResult {
  club_id: string
  rodada_id: string
  pontos: number
  breakdown: PlayerScore[]
}

export interface SeasonResult {
  temporada: number
  divisao_anterior: string
  posicao_final: number
  resultado: string
  divisao_nova: string
  premiacao_fvs: number
  status: string
}

export interface StandingEntry {
  posicao: number
  club_id: string
  nome: string
  divisao: string
  pontos: number
  temporada: number
  rodadas_jogadas: number
  status: string
  gerenciado_por_ia: boolean
}

export interface ApiError {
  error: string
  message: string
}

// Formações suportadas com seus slots na ordem GOL→DEF→MEI→ATA
export const FORMATION_SLOTS: Record<string, string[]> = {
  '4-3-3':   ['GOL','ZAG','ZAG','LAT','LAT','VOL','MEI','MEI','EXT','EXT','ATA'],
  '4-4-2':   ['GOL','ZAG','ZAG','LAT','LAT','VOL','VOL','MEI','MEI','ATA','ATA'],
  '3-5-2':   ['GOL','ZAG','ZAG','ZAG','LAT','LAT','VOL','VOL','MEIA','ATA','ATA'],
  '4-2-3-1': ['GOL','ZAG','ZAG','LAT','LAT','VOL','VOL','MEIA','MEIA','MEIA','ATA'],
  '5-3-2':   ['GOL','ZAG','ZAG','ZAG','LAT','LAT','VOL','MEI','MEI','ATA','ATA'],
  '3-4-3':   ['GOL','ZAG','ZAG','ZAG','LAT','LAT','VOL','MEI','EXT','EXT','ATA'],
}

export const SLOT_SECTOR: Record<string, string> = {
  GOL: 'GOL', ZAG: 'DEF', LAT: 'DEF',
  VOL: 'MEI', MEI: 'MEI', MEIA: 'MEI',
  EXT: 'ATA', ATA: 'ATA',
}

export function fvs(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `FV$${(v / 1_000_000).toFixed(1)}M`
  return `FV$${v.toLocaleString('pt-BR')}`
}

export function sectorBadge(setor: string): string {
  return `badge badge-${setor.toLowerCase()}`
}
