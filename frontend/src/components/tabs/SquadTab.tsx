import { useState, useEffect, useCallback } from 'react'
import { api } from '../../api/client'
import type { SquadPlayer } from '../../types'
import { fvs, sectorBadge } from '../../types'

interface Props { clubId: string }

interface ListingState {
  [playerId: string]: 'listed' | 'pending' | null
}

const SECTOR_ORDER = ['GOL', 'DEF', 'MEI', 'ATA']

export default function SquadTab({ clubId }: Props) {
  const [squad, setSquad] = useState<SquadPlayer[]>([])
  const [loading, setLoading] = useState(true)
  const [listings, setListings] = useState<ListingState>({})
  const [prices, setPrices] = useState<Record<string, string>>({})
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const refresh = useCallback(() => {
    api.getSquad(clubId).then(s => { setSquad(s); setLoading(false) })
  }, [clubId])

  useEffect(() => { refresh() }, [refresh])

  async function handleList(playerId: string) {
    const preco = parseInt(prices[playerId] ?? '0', 10)
    if (!preco || preco <= 0) {
      setMsg({ type: 'err', text: 'Informe um preço válido (> 0 FV$)' })
      return
    }
    setListings(l => ({ ...l, [playerId]: 'pending' }))
    setMsg(null)
    try {
      await api.listPlayer(clubId, playerId, preco)
      setListings(l => ({ ...l, [playerId]: 'listed' }))
      setMsg({ type: 'ok', text: `Jogador listado por ${fvs(preco)}` })
    } catch (e) {
      setListings(l => ({ ...l, [playerId]: null }))
      setMsg({ type: 'err', text: e instanceof Error ? e.message : 'Erro ao listar' })
    }
  }

  async function handleDelist(playerId: string) {
    setListings(l => ({ ...l, [playerId]: 'pending' }))
    setMsg(null)
    try {
      await api.delistPlayer(clubId, playerId)
      setListings(l => ({ ...l, [playerId]: null }))
      setMsg({ type: 'ok', text: 'Listagem cancelada' })
    } catch (e) {
      setListings(l => ({ ...l, [playerId]: 'listed' }))
      setMsg({ type: 'err', text: e instanceof Error ? e.message : 'Erro ao cancelar' })
    }
  }

  if (loading) return <div style={{ color: 'var(--text-muted)' }}>Carregando elenco...</div>
  if (squad.length === 0) return (
    <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
      Elenco vazio — compre jogadores no Mercado.
    </div>
  )

  const bySector = SECTOR_ORDER.reduce<Record<string, SquadPlayer[]>>((acc, s) => {
    acc[s] = squad.filter(p => p.setor === s).sort((a, b) => b.ovr - a.ovr)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {msg && <div className={msg.type === 'ok' ? 'success-msg' : 'error-msg'}>{msg.text}</div>}
      <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
        {squad.length} jogadores no elenco
      </div>

      {SECTOR_ORDER.map(setor => {
        const players = bySector[setor]
        if (!players.length) return null
        return (
          <div key={setor} className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
              <span className={sectorBadge(setor)}>{setor}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 8 }}>
                {players.length} jogador{players.length > 1 ? 'es' : ''}
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Posição</th>
                  <th>OVR</th>
                  <th>Forma</th>
                  <th>Idade</th>
                  <th>Valor</th>
                  <th>Vender</th>
                </tr>
              </thead>
              <tbody>
                {players.map(p => {
                  const state = listings[p.player_id]
                  const isListed = state === 'listed'
                  const isPending = state === 'pending'
                  return (
                    <tr key={p.player_id}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)' }}>
                        {p.player_id}
                      </td>
                      <td><strong>{p.posicao}</strong></td>
                      <td>
                        <span style={{
                          fontWeight: 700,
                          color: p.ovr >= 80 ? 'var(--green)' : p.ovr >= 65 ? 'var(--yellow)' : 'var(--text)',
                        }}>{p.ovr}</span>
                      </td>
                      <td>{p.forma}</td>
                      <td>{p.idade}</td>
                      <td>{fvs(p.valor_fvs)}</td>
                      <td style={{ minWidth: 200 }}>
                        {isListed ? (
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            <span style={{
                              fontSize: 11, padding: '2px 7px', borderRadius: 4,
                              background: 'rgba(250,204,21,0.15)', color: '#ca8a04',
                            }}>À venda</span>
                            <button
                              className="btn-secondary"
                              style={{ padding: '3px 8px', fontSize: 11 }}
                              disabled={isPending}
                              onClick={() => handleDelist(p.player_id)}
                            >
                              Cancelar
                            </button>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            <input
                              type="number"
                              placeholder="Preço FV$"
                              value={prices[p.player_id] ?? ''}
                              onChange={e => setPrices(prev => ({ ...prev, [p.player_id]: e.target.value }))}
                              style={{ width: 110, padding: '3px 8px', fontSize: 12 }}
                            />
                            <button
                              className="btn-secondary"
                              style={{ padding: '3px 8px', fontSize: 11 }}
                              disabled={isPending}
                              onClick={() => handleList(p.player_id)}
                            >
                              {isPending ? '...' : 'Listar'}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )
      })}
    </div>
  )
}
