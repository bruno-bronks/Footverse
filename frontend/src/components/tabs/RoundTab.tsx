import { useState } from 'react'
import { api } from '../../api/client'
import type { SeasonState, RoundResult } from '../../types'

interface Props {
  clubId: string
  season: SeasonState | null
  onScore: () => void
}

export default function RoundTab({ clubId, season, onScore }: Props) {
  const [result, setResult] = useState<RoundResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const rodadasJogadas = season?.rodadas_jogadas ?? 0
  const rodadasTotal = season?.rodadas_total ?? 38
  const finished = season?.status === 'ENCERRADA' || rodadasJogadas >= rodadasTotal

  async function score() {
    setError(null)
    setLoading(true)
    const rodadaId = `rod_${rodadasJogadas + 1}`
    try {
      const r = await api.scoreRound(clubId, rodadaId)
      setResult(r)
      onScore()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao pontuar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Status da temporada */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Rodada</div>
          <div style={{ fontSize: 24, fontWeight: 800 }}>
            {rodadasJogadas + (result ? 0 : 0)}/{rodadasTotal}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Pontos</div>
          <div style={{ fontSize: 24, fontWeight: 800 }}>{season?.pontos.toFixed(1) ?? '—'}</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Status</div>
          <div style={{ fontWeight: 600 }}>{season?.status ?? '—'}</div>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <button
            className="btn-primary"
            style={{ padding: '10px 24px', fontSize: 15 }}
            disabled={loading || finished}
            onClick={score}
          >
            {loading ? 'Pontuando...' : finished ? 'Temporada encerrada' : `▶ Pontuar rodada ${rodadasJogadas + 1}`}
          </button>
        </div>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {result && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <div style={{ fontWeight: 700 }}>Rodada {result.rodada_id}</div>
            <div style={{
              fontSize: 22, fontWeight: 800,
              color: result.pontos >= 0 ? 'var(--green)' : 'var(--red)',
            }}>
              {result.pontos >= 0 ? '+' : ''}{result.pontos.toFixed(2)} pts
            </div>
          </div>

          <table>
            <thead>
              <tr>
                <th>Jogador</th>
                <th>Slot</th>
                <th>Nota</th>
                <th>Pts</th>
                <th>G</th>
                <th>A</th>
                <th>Def</th>
                <th>CS</th>
              </tr>
            </thead>
            <tbody>
              {result.breakdown
                .sort((a, b) => b.pontos - a.pontos)
                .map(p => (
                <tr key={p.player_id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{p.player_id}</td>
                  <td>{p.slot}</td>
                  <td style={{ fontWeight: 600 }}>{p.nota.toFixed(1)}</td>
                  <td style={{
                    fontWeight: 700,
                    color: p.pontos > 0 ? 'var(--green)' : p.pontos < 0 ? 'var(--red)' : 'var(--text-muted)',
                  }}>
                    {p.pontos >= 0 ? '+' : ''}{p.pontos.toFixed(2)}
                  </td>
                  <td>{p.gols || '—'}</td>
                  <td>{p.assistencias || '—'}</td>
                  <td>{p.defesas || '—'}</td>
                  <td>{p.clean_sheet ? '✓' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {finished && !result && (
        <div className="success-msg">
          Todas as {rodadasTotal} rodadas foram jogadas. Vá para a aba Temporada para encerrar.
        </div>
      )}
    </div>
  )
}
