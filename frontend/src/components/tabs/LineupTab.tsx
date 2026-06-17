import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import type { SquadPlayer } from '../../types'
import { FORMATION_SLOTS, SLOT_SECTOR, sectorBadge } from '../../types'

interface Props {
  clubId: string
  onSave: () => void
}

const FORMATIONS = Object.keys(FORMATION_SLOTS)

export default function LineupTab({ clubId, onSave }: Props) {
  const [squad, setSquad] = useState<SquadPlayer[]>([])
  const [formation, setFormation] = useState('4-3-3')
  const [assignments, setAssignments] = useState<Record<number, string>>({})
  const [reservas, setReservas] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getSquad(clubId),
      api.getLineup(clubId).catch(() => null),
    ]).then(([sq, lineup]) => {
      setSquad(sq)
      if (lineup) {
        setFormation(lineup.formacao)
        const a: Record<number, string> = {}
        lineup.titulares.forEach((t, i) => { a[i] = t.player_id })
        setAssignments(a)
        setReservas(lineup.reservas)
      }
      setLoading(false)
    })
  }, [clubId])

  // Reset assignments when formation changes
  function changeFormation(f: string) {
    setFormation(f)
    setAssignments({})
    setMsg(null)
  }

  const slots = FORMATION_SLOTS[formation] ?? []

  function eligiblePlayers(slot: string): SquadPlayer[] {
    const sector = SLOT_SECTOR[slot]
    const used = new Set(Object.values(assignments))
    return squad.filter(p => p.setor === sector && !used.has(p.player_id))
  }

  function setSlot(index: number, playerId: string) {
    setAssignments(prev => {
      const next = { ...prev }
      // Remove the player from any other slot first
      for (const k of Object.keys(next)) {
        if (next[+k] === playerId) delete next[+k]
      }
      if (playerId) next[index] = playerId
      else delete next[index]
      return next
    })
  }

  function toggleReserva(pid: string) {
    const titulares = new Set(Object.values(assignments))
    if (titulares.has(pid)) return // can't bench a starter
    setReservas(prev =>
      prev.includes(pid) ? prev.filter(p => p !== pid) : [...prev, pid]
    )
  }

  async function handleSave() {
    setMsg(null)
    const titulares = slots.map((slot, i) => ({
      player_id: assignments[i] ?? '',
      posicao: slot,
    }))
    if (titulares.some(t => !t.player_id)) {
      setMsg({ type: 'err', text: 'Preencha todos os 11 slots antes de salvar.' })
      return
    }
    setSaving(true)
    try {
      await api.setLineup(clubId, formation, titulares, reservas)
      setMsg({ type: 'ok', text: 'Escalação salva com sucesso!' })
      onSave()
    } catch (e) {
      setMsg({ type: 'err', text: e instanceof Error ? e.message : 'Erro ao salvar' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div style={{ color: 'var(--text-muted)' }}>Carregando...</div>
  if (squad.length === 0) return (
    <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
      Elenco vazio — compre jogadores no Mercado primeiro.
    </div>
  )

  const filledCount = Object.keys(assignments).length
  const starters = new Set(Object.values(assignments))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {msg && <div className={msg.type === 'ok' ? 'success-msg' : 'error-msg'}>{msg.text}</div>}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div>
          <label>Formação</label>
          <select value={formation} onChange={e => changeFormation(e.target.value)} style={{ width: 140 }}>
            {FORMATIONS.map(f => <option key={f}>{f}</option>)}
          </select>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 16 }}>
          {filledCount}/11 slots preenchidos
        </div>
        <button
          className="btn-primary"
          style={{ marginTop: 16, marginLeft: 'auto' }}
          disabled={saving || filledCount < 11}
          onClick={handleSave}
        >
          {saving ? 'Salvando...' : 'Salvar escalação'}
        </button>
      </div>

      {/* Slot grid */}
      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
        {slots.map((slot, i) => {
          const sector = SLOT_SECTOR[slot]
          const options = eligiblePlayers(slot)
          const current = squad.find(p => p.player_id === assignments[i])
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className={sectorBadge(sector)} style={{ minWidth: 44, textAlign: 'center' }}>
                {slot}
              </span>
              <select
                value={assignments[i] ?? ''}
                onChange={e => setSlot(i, e.target.value)}
                style={{ flex: 1 }}
              >
                <option value="">— selecionar —</option>
                {current && (
                  <option value={current.player_id}>
                    {current.player_id} · OVR {current.ovr}
                  </option>
                )}
                {options.map(p => (
                  <option key={p.player_id} value={p.player_id}>
                    {p.player_id} · {p.posicao} · OVR {p.ovr}
                  </option>
                ))}
              </select>
            </div>
          )
        })}
      </div>

      {/* Reservas */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 10 }}>
          Reservas ({reservas.length})
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {squad.filter(p => !starters.has(p.player_id)).map(p => (
            <button
              key={p.player_id}
              onClick={() => toggleReserva(p.player_id)}
              style={{
                background: reservas.includes(p.player_id) ? 'var(--accent)' : 'var(--surface2)',
                color: reservas.includes(p.player_id) ? '#fff' : 'var(--text-muted)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '4px 10px',
                fontSize: 12,
              }}
            >
              {p.player_id} · {p.posicao} · OVR {p.ovr}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
