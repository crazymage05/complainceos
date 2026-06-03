import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  message?: string
}

/**
 * App-wide error boundary. Catches render-time exceptions so a single broken
 * component never blanks the whole dashboard, and offers a reload.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="min-h-screen bg-canvas text-ink flex items-center justify-center p-6">
        <div className="os-panel p-8 max-w-md text-center">
          <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-lg font-bold text-ink mb-1">Something went wrong</h1>
          <p className="text-sm text-inkMute mb-2">
            The dashboard hit an unexpected error. Your data is safe.
          </p>
          {this.state.message && (
            <p className="text-xs text-inkFaint font-mono bg-panel2 border border-edge rounded-lg px-3 py-2 mb-5 break-words">
              {this.state.message}
            </p>
          )}
          <button
            onClick={() => window.location.reload()}
            className="os-btn-accent px-5 py-2.5 text-sm"
          >
            Reload ComplianceOS
          </button>
        </div>
      </div>
    )
  }
}
