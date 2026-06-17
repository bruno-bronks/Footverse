import { useState, useEffect } from 'react'
import { AUTH_KEY } from './api/client'
import AuthSetup from './components/AuthSetup'
import ClubSetup from './components/ClubSetup'
import Dashboard from './components/Dashboard'

const STORAGE_KEY = 'fv_club_id'

type Screen = 'auth' | 'club-setup' | 'dashboard'

function getInitialScreen(): Screen {
  if (!localStorage.getItem(AUTH_KEY)) return 'auth'
  if (!localStorage.getItem(STORAGE_KEY)) return 'club-setup'
  return 'dashboard'
}

export default function App() {
  const [screen, setScreen] = useState<Screen>(getInitialScreen)
  const [clubId, setClubId] = useState<string | null>(
    () => localStorage.getItem(STORAGE_KEY),
  )

  useEffect(() => {
    if (clubId) localStorage.setItem(STORAGE_KEY, clubId)
    else localStorage.removeItem(STORAGE_KEY)
  }, [clubId])

  function handleRegistered() {
    setScreen(clubId ? 'dashboard' : 'club-setup')
  }

  function handleClubCreated(id: string) {
    setClubId(id)
    setScreen('dashboard')
  }

  function handleReset() {
    setClubId(null)
    setScreen('club-setup')
  }

  if (screen === 'auth') {
    return <AuthSetup onRegistered={handleRegistered} />
  }

  if (screen === 'club-setup' || !clubId) {
    return <ClubSetup onCreate={handleClubCreated} />
  }

  return <Dashboard clubId={clubId} onReset={handleReset} />
}
