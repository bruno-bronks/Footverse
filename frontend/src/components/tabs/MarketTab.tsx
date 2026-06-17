import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import type { MarketPlayer } from '../../types'
import { fvs, sectorBadge } from '../../types'

interface Props {
  clubId: string
  onPurchase: () => void
}

const SECTOR_ORDER: Record<string, number> = { GOL: 0, DEF: 1, MEI: 2, ATA: 3 }

export default function MarketTab({ clubId, onPurchase }: Props) {
  const [players, setPlayers] = useState<MarketPlayer[]>([])
  const [loading, setLoading] = useState(true)
  const [buying, setBuying] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [filter, setFilter] = useState('')
  const [showP2POnly, setShowP2POnly] = useState(false)

  useEffect(() => {
    api.getMarket().then(p => {
      const sorted = [...p].sort((a, b) =>
        (SECTOR_ORDER[a.setor] ?? 9) - (SECTOR_ORDER[b.setor] ?? 9) || b.ovr - a.ovr
      )
      setPlayers(sorted)
      setLoading(false)
    })
  }, [])

  async function buy(playerId: string) {
    setBuying(playerId)
    setMsg(null)
    try {
      const result = await api.buyPlayer(clubId, playerId)
      setPlayers(prev => prev.filter(p => p.player_id !== playerId))
      setMsg({ type: 'ok', text: `Comprado! Novo saldo: ${fvs(result.saldo_final)}` })
      onPurchase()
    } catch (e) {
      setMsg({ type: 'err', text: e instanceof Error ? e.message : 'Erro' })
    } finally {
      setBuying(null)
    }
  }

  let visible = filter
    ? players.filter(p =>
        p.player_id.includes(filter) ||
        p.posicao.includes(filter.toUpperCase()) ||
        p.setor.includes(filter.toUpperCase())
      )
    : players

  if (showP2POnly) visible = visible.filter(p => p.vendedor_club_id !== null)

  const p2pCount = players.filter(p => p.vendedor_club_id !== null).length

  if (loading) return <div style={{ color: 'var(--text-muted)' }}>Carregando mercado...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {msg && <div className={msg.type === 'ok' ? 'success-msg' : 'error-msg'}>{msg.text}</div>}

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          placeholder="Filtrar por posição ou setor (ex: GOL, DEF)…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{ maxWidth: 300 }}
        />
        {p2pCount > 0 && (
          <button
            onClick={() => setShowP2POnly(v => !v)}
            style={{
              background: showP2POnly ? 'var(--accent)' : 'var(--surface)',
              color: showP2POnly ? '#fff' : 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: 6, padding: '5px 12px', fontSize: 12,
            }}
          >
            Só P2P ({p2pCount})
          </button>
        )}
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          {visible.length} jogadores disponíveis
        </span>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Pos</th>
              <th>Setor</th>
              <th>OVR</th>
              <th>Idade</th>
              <th>Valor</th>
              <th>Tipo</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(p => (
              <tr key={p.player_id}>
                <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-muted)' }}>
                  {p.player_id}
                </td>
                <td><strong>{p.posicao}</strong></td>
                <td><span className={sectorBadge(p.setor)}>{p.setor}</span></td>
                <td>{p.ovr}</td>
                <td>{p.idade}</td>
                <td>{fvs(p.valor_fvs)}</td>
                <td>
                  {p.vendedor_club_id ? (
                    <span style={{
                      fontSize: 11, padding: '2px 7px', borderRadius: 4,
                      background: 'rgba(250,204,21,0.15)', color: '#ca8a04',
                    }}>P2P</span>
                  ) : (
                    <span style={{
                      fontSize: 11, padding: '2px 7px', borderRadius: 4,
                      background: 'var(--surface)', color: 'var(--text-muted)',
                    }}>NPC</span>
                  )}
                </td>
                <td>
                  <button
                    className="btn-primary"
                    style={{ padding: '4px 12px', fontSize: 12 }}
                    disabled={buying === p.player_id || p.vendedor_club_id === clubId}
                    onClick={() => buy(p.player_id)}
                  >
                    {buying === p.player_id ? '...' : 'Comprar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visible.length === 0 && (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
            Nenhum jogador encontrado.
          </div>
        )}
      </div>
    </div>
  )
}
