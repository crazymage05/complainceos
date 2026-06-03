import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { onAuthChange } from './services/firebase'
import type { User } from 'firebase/auth'
import Onboarding from './components/Onboarding'
import Dashboard from './components/Dashboard'
import Login from './components/Login'
import ReviewObligations from './components/ReviewObligations'
import Landing from './components/Landing'
import NotFound from './components/NotFound'
import ErrorBoundary from './components/ErrorBoundary'
import Toaster from './components/Toaster'

function SpinnerFull() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-accent border-t-transparent rounded-full animate-spin" />
        <p className="text-inkMute text-sm font-medium">Loading ComplianceOS…</p>
      </div>
    </div>
  )
}

function RequireAuth({ user, children }: { user: User | null; children: JSX.Element }) {
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RootRedirect({ user }: { user: User | null }) {
  if (!user) return <Landing signedIn={false} />
  const businessId = localStorage.getItem('business_id')
  if (!businessId) return <Onboarding />
  return <Navigate to="/dashboard" replace />
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  useEffect(() => {
    const unsub = onAuthChange((u) => {
      setUser(u)
      setAuthLoading(false)
    })
    return unsub
  }, [])

  if (authLoading) return <SpinnerFull />

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/welcome" element={<Landing signedIn={!!user} />} />
          <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/" element={<RootRedirect user={user} />} />
          <Route
            path="/onboarding"
            element={<RequireAuth user={user}><Onboarding /></RequireAuth>}
          />
          <Route
            path="/review"
            element={<RequireAuth user={user}><ReviewObligations /></RequireAuth>}
          />
          <Route
            path="/dashboard"
            element={<RequireAuth user={user}><Dashboard user={user!} /></RequireAuth>}
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </ErrorBoundary>
  )
}
