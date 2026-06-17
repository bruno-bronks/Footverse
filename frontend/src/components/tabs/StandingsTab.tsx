import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import type { StandingEntry } from '../../types'

interface Props {
  divisao: string
  myClubId: string
}

const DIVISOES = ['SERIE_A', 'SERIE_B', 'SERIE_C', 'SERIE_D']

export default function StandingsTab({ divisao, myClubId }: Props) {
  const [selectedDiv, setSelectedDiv] = useState(divisao)
  const [rows, setRows] = useState<StandingEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getStandings(selectedDiv)
      .then(setRows)
      .catch(e => setError(e instanceof Error ? e.message : 'Erro ao carregar'))
      .finally(() => setLoading(false))
  }, [selectedDiv])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Seletor de divisão */}
      <div style={{ display: 'flex', gap: 6 }}>
        {DIVISOES.map(d => (
          <button
            key={d}
            onClick={() => setSelectedDiv(d)}
            style={{
              background: selectedDiv === d ? 'var(--accent)' : 'var(--surface)',
              color: selectedDiv === d ? '#fff' : 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: '5px 12px',
              fontSize: 12,
            }}
          >
            {d.replace('SERIE_', 'Série ')}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ color: 'var(--text-muted)', padding: 20 }}>Carregando...</div>
      )}

      {error && <div className="error-msg">{error}</div>}

      {!loading && !error && rows.length === 0 && (
        <div style={{ color: 'var(--text-muted)', padding: 20 }}>
          Nenhum clube nesta divisão ainda.
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['#', 'Clube', 'Pts', 'Rodadas', 'Status'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', textAlign: 'left',
                    color: 'var(--text-muted)', fontWeight: 600, fontSize: 12,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const isMe = row.club_id === myClubId
                return (
                  <tr
                    key={row.club_id}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: isMe ? 'rgba(61,127,255,0.08)' : undefined,
                    }}
                  >
                    <td style={{ padding: '10px 14px', fontWeight: 700, width: 36 }}>
                      {row.posicao}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ fontWeight: isMe ? 700 : 400 }}>{row.nome}</span>
                      {isMe && (
                        <span style={{
                          marginLeft: 8, fontSize: 10, color: 'var(--accent)',
                          background: 'rgba(61,127,255,0.15)', padding: '1px 6px', borderRadius: 4,
                        }}>
                          você
                        </span>
                      )}
                      {row.gerenciado_por_ia && (
                        <span
                          title="Clube gerenciado por IA"
                          style={{
                            marginLeft: 8, fontSize: 10, color: '#a78bfa',
                            background: 'rgba(167,139,250,0.15)', padding: '1px 6px', borderRadius: 4,
                          }}
                        >
                          🤖 IA
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '10px 14px', fontWeight: 600 }}>
                      {row.pontos.toFixed(1)}
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)' }}>
                      {row.rodadas_jogadas}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        fontSize: 11, padding: '2px 7px', borderRadius: 4,
                        background: row.status === 'ENCERRADA' ? 'rgba(34,197,94,0.15)' : 'rgba(250,204,21,0.15)',
                        color: row.status === 'ENCERRADA' ? 'var(--green)' : '#ca8a04',
                      }}>
                        {row.status === 'ENCERRADA' ? 'Encerrada' : 'Em andamento'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
