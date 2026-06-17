import { useState } from 'react'
import { api } from '../../api/client'
import type { SeasonState, SeasonResult } from '../../types'
import { fvs } from '../../types'

interface Props {
  clubId: string
  season: SeasonState | null
  onClose: () => void
}

const RESULTADO_COLOR: Record<string, string> = {
  CAMPEAO:   'var(--yellow)',
  PROMOVIDO: 'var(--green)',
  PERMANECE: 'var(--text)',
  REBAIXADO: 'var(--red)',
}

const RESULTADO_LABEL: Record<string, string> = {
  CAMPEAO:   '🏆 Campeão!',
  PROMOVIDO: '⬆ Promovido',
  PERMANECE: '⟳ Permanece',
  REBAIXADO: '⬇ Rebaixado',
}

export default function SeasonTab({ clubId, season, onClose }: Props) {
  const [result, setResult] = useState<SeasonResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canClose = season
    && season.status !== 'ENCERRADA'
    && season.rodadas_jogadas >= season.rodadas_total

  async function close() {
    setError(null)
    setLoading(true)
    try {
      const r = await api.closeSeason(clubId)
      setResult(r)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao encerrar temporada')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Estado atual */}
      {season && (
        <div className="card" style={{ display: 'flex', gap: 32 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Temporada</div>
            <div style={{ fontSize: 22, fontWeight: 800 }}>{season.temporada}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Divisão</div>
            <div style={{ fontWeight: 700 }}>{season.divisao}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Rodadas</div>
            <div style={{ fontWeight: 700 }}>{season.rodadas_jogadas}/{season.rodadas_total}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Pontos</div>
            <div style={{ fontWeight: 700 }}>{season.pontos.toFixed(1)}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Status</div>
            <div style={{ fontWeight: 700, color: season.status === 'ENCERRADA' ? 'var(--text-muted)' : 'var(--green)' }}>
              {season.status}
            </div>
          </div>
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}

      {/* Botão encerrar */}
      {!result && (
        <div className="card">
          {canClose ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                Todas as rodadas foram jogadas. Encerre a temporada para receber a premiação e avançar.
              </div>
              <button
                className="btn-danger"
                style={{ alignSelf: 'flex-start' }}
                disabled={loading}
                onClick={close}
              >
                {loading ? 'Encerrando...' : 'Encerrar temporada'}
              </button>
            </div>
          ) : season?.status === 'ENCERRADA' ? (
            <div style={{ color: 'var(--text-muted)' }}>
              Temporada já encerrada. A próxima começa automaticamente ao comprar e escalar.
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)' }}>
              Jogue todas as {season?.rodadas_total ?? 38} rodadas na aba Rodada para poder encerrar.
              Faltam {(season?.rodadas_total ?? 38) - (season?.rodadas_jogadas ?? 0)} rodadas.
            </div>
          )}
        </div>
      )}

      {/* Resultado */}
      {result && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Resultado da Temporada {result.temporada}</div>

          <div style={{
            fontSize: 32, fontWeight: 900,
            color: RESULTADO_COLOR[result.resultado] ?? 'var(--text)',
          }}>
            {RESULTADO_LABEL[result.resultado] ?? result.resultado}
          </div>

          <div style={{ display: 'flex', gap: 32 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Posição final</div>
              <div style={{ fontWeight: 700, fontSize: 20 }}>#{result.posicao_final}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Divisão anterior</div>
              <div style={{ fontWeight: 600 }}>{result.divisao_anterior}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Nova divisão</div>
              <div style={{ fontWeight: 700, color: RESULTADO_COLOR[result.resultado] ?? 'var(--text)' }}>
                {result.divisao_nova}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Premiação</div>
              <div style={{ fontWeight: 700, color: 'var(--green)', fontSize: 18 }}>
                {fvs(result.premiacao_fvs)}
              </div>
            </div>
          </div>

          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Continue na aba Mercado para reforçar o elenco para a próxima temporada.
          </div>
        </div>
      )}
    </div>
  )
}
