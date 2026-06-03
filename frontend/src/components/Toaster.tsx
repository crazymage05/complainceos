import { useEffect, useState } from 'react'
import clsx from 'clsx'
import { onApiError } from '../services/api'

export type ToastType = 'info' | 'success' | 'error'

interface Toast {
  id: number
  message: string
  type: ToastType
}

type Listener = (toast: Toast) => void
const listeners = new Set<Listener>()
let nextId = 1

/** Fire a toast from anywhere in the app. */
export function pushToast(message: string, type: ToastType = 'info') {
  const toast: Toast = { id: nextId++, message, type }
  listeners.forEach((fn) => fn(toast))
}

const TONE: Record<ToastType, { bar: string; icon: JSX.Element }> = {
  info: {
    bar: 'border-l-accent',
    icon: (
      <svg className="w-4 h-4 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  success: {
    bar: 'border-l-accent',
    icon: (
      <svg className="w-4 h-4 text-accent-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  error: {
    bar: 'border-l-red-500',
    icon: (
      <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  },
}

export default function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    const add: Listener = (toast) => {
      setToasts((prev) => [...prev, toast])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toast.id))
      }, 5000)
    }
    listeners.add(add)
    // Surface API errors as toasts automatically. Rate-limit/quota notices come
    // through as 'info' so they don't read as alarming app errors.
    const offErr = onApiError((msg, kind) => add({ id: nextId++, message: msg, type: kind }))
    return () => {
      listeners.delete(add)
      offErr()
    }
  }, [])

  function dismiss(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 w-full max-w-sm px-4 pointer-events-none">
      {toasts.map((t) => {
        const tone = TONE[t.type]
        return (
          <div
            key={t.id}
            className={clsx(
              'pointer-events-auto os-card bg-panel2 border-l-4 shadow-glow px-4 py-3 flex items-start gap-3 animate-[fadein_0.2s_ease]',
              tone.bar,
            )}
          >
            <span className="flex-shrink-0 mt-0.5">{tone.icon}</span>
            <p className="text-sm text-inkSoft flex-1 leading-snug">{t.message}</p>
            <button
              onClick={() => dismiss(t.id)}
              className="flex-shrink-0 text-inkFaint hover:text-ink transition-colors"
              aria-label="Dismiss"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )
      })}
    </div>
  )
}
