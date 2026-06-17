import { useState } from 'react'
import { api } from '../api/client'

interface Props {
  onCreate: (clubId: string) => void
}

const COLORS = ['#1e40af', '#7c3aed', '#b91c1c', '#047857', '#b45309', '#0f172a']
const USER_KEY = 'fv_user_id'

export default function ClubSetup({ onCreate }: Props) {
  const [nome, setNome] = useState('')
  const [cor1, setCor1] = useState(COLORS[0])
  const [cor2, setCor2] = useState(COLORS[4])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const userId = localStorage.getItem(USER_KEY) ?? 'anon'
      const club = await api.createClub(userId, nome, [cor1, cor2])
      onCreate(club.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <div className="card" style={{ width: 380, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.5px' }}>⚽ Footverse</div>
          <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>Crie seu clube para começar</div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label>Nome do clube</label>
            <input
              value={nome}
              onChange={e => setNome(e.target.value)}
              placeholder="Ex: Atlético Futuro"
              minLength={3}
              maxLength={40}
              required
            />
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <label>Cor primária</label>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                {COLORS.map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setCor1(c)}
                    style={{
                      width: 28, height: 28, borderRadius: '50%', background: c, padding: 0,
                      border: cor1 === c ? '2px solid #fff' : '2px solid transparent',
                    }}
                  />
                ))}
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <label>Cor secundária</label>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                {COLORS.map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setCor2(c)}
                    style={{
                      width: 28, height: 28, borderRadius: '50%', background: c, padding: 0,
                      border: cor2 === c ? '2px solid #fff' : '2px solid transparent',
                    }}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Preview do escudo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 8,
              background: `linear-gradient(135deg, ${cor1} 50%, ${cor2} 50%)`,
            }} />
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              {nome || 'Nome do clube'}
            </span>
          </div>

          {error && <div className="error-msg">{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Criando...' : 'Criar clube'}
          </button>
        </form>
      </div>
    </div>
  )
}
