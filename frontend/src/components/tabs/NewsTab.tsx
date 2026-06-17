import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import type { NewsItem } from '../../api/client'

interface Props {
  myClubId: string
}

const TIPO_INFO: Record<NewsItem['tipo'], { icone: string; cor: string; label: string }> = {
  FUNDACAO:           { icone: '🏟️', cor: 'var(--text-muted)', label: 'Fundação' },
  DECISAO_IA:         { icone: '🤖', cor: '#a78bfa', label: 'Decisão de IA' },
  PERSONALIDADE:      { icone: '🔄', cor: '#facc15', label: 'Mudança de postura' },
  TRANSFERENCIA_P2P:  { icone: '💸', cor: 'var(--green)', label: 'Transferência' },
  TEMPORADA_ENCERRADA:{ icone: '🏁', cor: '#3d7fff', label: 'Fim de temporada' },
  RODADA:             { icone: '⚽', cor: 'var(--text-muted)', label: 'Rodada' },
}

function formatTimeAgo(ts: number): string {
  const diffSec = Math.max(0, Date.now() / 1000 - ts)
  if (diffSec < 60) return 'agora'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}min atrás`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h atrás`
  return `${Math.floor(diffSec / 86400)}d atrás`
}

export default function NewsTab({ myClubId }: Props) {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [onlyMine, setOnlyMine] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getNews(onlyMine ? myClubId : undefined, 50)
      .then(setItems)
      .catch(e => setError(e instanceof Error ? e.message : 'Erro ao carregar notícias'))
      .finally(() => setLoading(false))
  }, [onlyMine, myClubId])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <button
          onClick={() => setOnlyMine(false)}
          style={{
            background: !onlyMine ? 'var(--accent)' : 'var(--surface)',
            color: !onlyMine ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: 6, padding: '5px 12px', fontSize: 12,
          }}
        >
          Todo o mundo
        </button>
        <button
          onClick={() => setOnlyMine(true)}
          style={{
            background: onlyMine ? 'var(--accent)' : 'var(--surface)',
            color: onlyMine ? '#fff' : 'var(--text-muted)',
            border: '1px solid var(--border)', borderRadius: 6, padding: '5px 12px', fontSize: 12,
          }}
        >
          Só o meu clube
        </button>
      </div>

      {loading && <div style={{ color: 'var(--text-muted)', padding: 20 }}>Carregando...</div>}
      {error && <div className="error-msg">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
          Nenhuma notícia ainda — o mundo está só começando.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.map((item, i) => {
            const info = TIPO_INFO[item.tipo] ?? { icone: '•', cor: 'var(--text-muted)', label: item.tipo }
            const isMine = item.club_id === myClubId
            return (
              <div
                key={i}
                className="card"
                style={{
                  display: 'flex', gap: 12, alignItems: 'flex-start', padding: '12px 16px',
                  borderLeft: isMine ? '3px solid var(--accent)' : undefined,
                }}
              >
                <span style={{ fontSize: 20, lineHeight: 1 }}>{info.icone}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 2 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: info.cor }}>
                      {info.label}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {formatTimeAgo(item.ts)}
                    </span>
                  </div>
                  <div style={{ fontSize: 13 }}>{item.texto ?? '—'}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
