import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { onAuthChange } from './services/firebase'
import type { User } from 'firebase/auth'
import Onboarding from './components/Onboarding'
import Dashboard from './components/Dashboard'
import Login from './components/Login'

function SpinnerFull() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-500 text-sm font-medium">Loading ComplianceOS…</p>
      </div>
    </div>
  )
}

function RequireAuth({ user, children }: { user: User | null; children: JSX.Element }) {
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RootRedirect({ user }: { user: User | null }) {
  if (!user) return <Navigate to="/login" replace />
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
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
        <Route
          path="/"
          element={<RootRedirect user={user} />}
        />
        <Route
          path="/onboarding"
          element={
            <RequireAuth user={user}>
              <Onboarding />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RequireAuth user={user}>
              <Dashboard user={user!} />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
