import { useState, useEffect, useCallback, useRef } from 'react'
import { api, subscribeToEvents } from '../api/client'
import type { ClockStatus, WorldEvent } from '../api/client'
import type { Club, SeasonState } from '../types'
import { fvs } from '../types'
import MarketTab from './tabs/MarketTab'
import SquadTab from './tabs/SquadTab'
import LineupTab from './tabs/LineupTab'
import RoundTab from './tabs/RoundTab'
import SeasonTab from './tabs/SeasonTab'
import StandingsTab from './tabs/StandingsTab'
import NewsTab from './tabs/NewsTab'

type Tab = 'market' | 'squad' | 'lineup' | 'round' | 'season' | 'standings' | 'news'

interface Props {
  clubId: string
  onReset: () => void
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return 'agora'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function Dashboard({ clubId, onReset }: Props) {
  const [club, setClub] = useState<Club | null>(null)
  const [season, setSeason] = useState<SeasonState | null>(null)
  const [tab, setTab] = useState<Tab>('market')
  const [error, setError] = useState<string | null>(null)
  const [clock, setClock] = useState<ClockStatus | null>(null)
  const [liveEvent, setLiveEvent] = useState<WorldEvent | null>(null)
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([
        api.getClub(clubId),
        api.getSeason(clubId).catch(() => null),
      ])
      setClub(c)
      setSeason(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar clube')
    }
  }, [clubId])

  useEffect(() => { refresh() }, [refresh])

  // relógio de mundo: status inicial + atualização periódica do countdown
  useEffect(() => {
    api.getClockStatus().then(setClock).catch(() => {})
    const id = setInterval(() => {
      setClock(c => c ? { ...c, next_tick_in: Math.max(0, c.next_tick_in - 30) } : c)
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  // eventos em tempo real (SSE): rodada auto-pontuada ou temporada encerrada
  useEffect(() => {
    const unsubscribe = subscribeToEvents(clubId, event => {
      setLiveEvent(event)
      refresh()
      api.getClockStatus().then(setClock).catch(() => {})
      if (dismissTimer.current) clearTimeout(dismissTimer.current)
      dismissTimer.current = setTimeout(() => setLiveEvent(null), 8000)
    })
    return unsubscribe
  }, [clubId, refresh])

  if (error) return (
    <div style={{ padding: 24 }}>
      <div className="error-msg">{error}</div>
      <button className="btn-secondary" style={{ marginTop: 12 }} onClick={onReset}>
        ← Voltar
      </button>
    </div>
  )

  if (!club) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--text-muted)' }}>
      Carregando...
    </div>
  )

  const tabs: { key: Tab; label: string }[] = [
    { key: 'market',    label: 'Mercado' },
    { key: 'squad',     label: 'Elenco' },
    { key: 'lineup',    label: 'Escalação' },
    { key: 'round',     label: 'Rodada' },
    { key: 'season',    label: 'Temporada' },
    { key: 'standings', label: 'Classificação' },
    { key: 'news',      label: 'Notícias' },
  ]

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 16px 40px' }}>
      {/* Notificação de evento ao vivo */}
      {liveEvent && (
        <div style={{
          position: 'fixed', top: 16, right: 16, zIndex: 100, maxWidth: 320,
          background: 'var(--surface)', border: '1px solid var(--accent)', borderRadius: 8,
          padding: '12px 16px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        }}>
          <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 700, marginBottom: 4 }}>
            ⏱ Relógio de mundo
          </div>
          {liveEvent.tipo === 'RODADA' ? (
            <div style={{ fontSize: 13 }}>
              Rodada pontuada automaticamente: <strong>{liveEvent.pontos?.toFixed(1)} pts</strong>
            </div>
          ) : (
            <div style={{ fontSize: 13 }}>
              Temporada encerrada — resultado: <strong>{liveEvent.resultado}</strong>
            </div>
          )}
        </div>
      )}

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 0', borderBottom: '1px solid var(--border)', marginBottom: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 8, flexShrink: 0,
            background: club.cores.length >= 2
              ? `linear-gradient(135deg, ${club.cores[0]} 50%, ${club.cores[1]} 50%)`
              : club.cores[0] ?? '#3d7fff',
          }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{club.nome}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{club.divisao}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
          {season && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Rodadas</div>
              <div style={{ fontWeight: 600 }}>
                {season.rodadas_jogadas}/{season.rodadas_total}
              </div>
            </div>
          )}
          {season && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Pontos</div>
              <div style={{ fontWeight: 600 }}>{season.pontos.toFixed(1)}</div>
            </div>
          )}
          {clock && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Próxima rodada</div>
              <div style={{ fontWeight: 600 }}>{formatCountdown(clock.next_tick_in)}</div>
            </div>
          )}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Saldo</div>
            <div style={{ fontWeight: 600, color: 'var(--green)' }}>{fvs(club.saldo_fvs)}</div>
          </div>
          <button className="btn-secondary" style={{ fontSize: 12 }} onClick={onReset}>
            Trocar clube
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              background: tab === t.key ? 'var(--accent)' : 'var(--surface)',
              color: tab === t.key ? '#fff' : 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: '6px 14px',
              fontSize: 13,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'market'    && <MarketTab    clubId={clubId} onPurchase={refresh} />}
      {tab === 'squad'     && <SquadTab     clubId={clubId} />}
      {tab === 'lineup'    && <LineupTab    clubId={clubId} onSave={refresh} />}
      {tab === 'round'     && <RoundTab     clubId={clubId} season={season} onScore={refresh} />}
      {tab === 'season'    && <SeasonTab    clubId={clubId} season={season} onClose={refresh} />}
      {tab === 'standings' && <StandingsTab divisao={club.divisao} myClubId={clubId} />}
      {tab === 'news'      && <NewsTab      myClubId={clubId} />}
    </div>
  )
}
