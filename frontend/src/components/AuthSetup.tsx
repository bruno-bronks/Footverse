import { useState } from 'react'
import { api, AUTH_KEY } from '../api/client'

interface Props {
  onRegistered: () => void
}

const USER_KEY = 'fv_user_id'

function getOrCreateUserId(): string {
  const existing = localStorage.getItem(USER_KEY)
  if (existing) return existing
  const id = `u_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`
  localStorage.setItem(USER_KEY, id)
  return id
}

export default function AuthSetup({ onRegistered }: Props) {
  const userId = getOrCreateUserId()
  const [loading, setLoading] = useState(false)
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleRegister() {
    setError(null)
    setLoading(true)
    try {
      const res = await api.register(userId)
      localStorage.setItem(AUTH_KEY, res.api_key)
      setApiKey(res.api_key)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao registrar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <div className="card" style={{ width: 400, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.5px' }}>⚽ Footverse</div>
          <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>Multiplayer — Fase 2</div>
        </div>

        {!apiKey ? (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label>Seu ID de jogador</label>
              <div style={{
                padding: '8px 12px', borderRadius: 6, background: 'var(--surface)',
                border: '1px solid var(--border)', fontFamily: 'monospace', fontSize: 13,
              }}>
                {userId}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Gerado automaticamente e salvo neste dispositivo.
              </div>
            </div>

            {error && <div className="error-msg">{error}</div>}

            <button className="btn-primary" onClick={handleRegister} disabled={loading}>
              {loading ? 'Registrando...' : 'Criar conta e obter chave API'}
            </button>
          </>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ color: 'var(--green)', fontWeight: 600 }}>
                Conta criada com sucesso!
              </label>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Sua chave API (guarde em local seguro — não será exibida novamente):
              </div>
              <div style={{
                padding: '8px 12px', borderRadius: 6, background: 'var(--surface)',
                border: '1px solid var(--green)', fontFamily: 'monospace', fontSize: 11,
                wordBreak: 'break-all',
              }}>
                {apiKey}
              </div>
            </div>

            <button className="btn-primary" onClick={onRegistered}>
              Continuar →
            </button>
          </>
        )}
      </div>
    </div>
  )
}
