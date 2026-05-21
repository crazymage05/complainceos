import { useState } from 'react'
import { approveDraft } from '../services/api'
import type { DraftDocument, AdvisorNotes } from '../services/api'
import clsx from 'clsx'

interface AutoDraftQueueProps {
  drafts: DraftDocument[]
  onApprove: (instanceId: string) => void
}

interface ToastState {
  message: string
  type: 'success' | 'error'
}

const RISK_STYLES: Record<string, string> = {
  high: 'bg-red-50 text-red-700 border-red-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-green-50 text-green-700 border-green-200',
}

const RISK_DOT: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-green-500',
}

function AdvisorPanel({ notes }: { notes: AdvisorNotes }) {
  const risk = notes.risk_level ?? 'medium'
  return (
    <div className={clsx('mt-3 rounded-xl border p-4 text-xs space-y-3', RISK_STYLES[risk])}>
      {/* Risk header */}
      <div className="flex items-center gap-2 font-semibold">
        <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', RISK_DOT[risk])} />
        <span className="capitalize">{risk} Risk</span>
        <span className="font-normal text-current opacity-80">— {notes.risk_reason}</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {notes.documents_required.length > 0 && (
          <div>
            <p className="font-semibold mb-1 opacity-70 uppercase tracking-wide text-[10px]">Documents needed</p>
            <ul className="space-y-0.5">
              {notes.documents_required.map((d, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-0.5 flex-shrink-0 opacity-60">•</span>
                  {d}
                </li>
              ))}
            </ul>
          </div>
        )}

        {notes.common_mistakes.length > 0 && (
          <div>
            <p className="font-semibold mb-1 opacity-70 uppercase tracking-wide text-[10px]">Common mistakes</p>
            <ul className="space-y-0.5">
              {notes.common_mistakes.map((m, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-0.5 flex-shrink-0 text-red-500">!</span>
                  {m}
                </li>
              ))}
            </ul>
          </div>
        )}

        {notes.filing_checklist.length > 0 && (
          <div>
            <p className="font-semibold mb-1 opacity-70 uppercase tracking-wide text-[10px]">Filing checklist</p>
            <ol className="space-y-0.5 list-none">
              {notes.filing_checklist.map((step, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="flex-shrink-0 font-bold">{i + 1}.</span>
                  {step.replace(/^Step \d+:\s*/i, '')}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}

export default function AutoDraftQueue({ drafts, onApprove }: AutoDraftQueueProps) {
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const [expandedAdvisor, setExpandedAdvisor] = useState<Set<string>>(new Set())

  const visible = drafts.filter((d) => !dismissed.has(d.instance_id))

  function showToast(message: string, type: 'success' | 'error') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3500)
  }

  function toggleAdvisor(id: string) {
    setExpandedAdvisor((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function handleApprove(instanceId: string) {
    setLoadingId(instanceId)
    try {
      await approveDraft(instanceId)
      onApprove(instanceId)
      setDismissed((prev) => new Set([...prev, instanceId]))
      showToast('Document approved and queued for filing.', 'success')
    } catch {
      showToast('Approval failed. Please try again.', 'error')
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="relative">
      {/* Toast */}
      {toast && (
        <div
          className={clsx(
            'fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 transition-all',
            toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
          )}
        >
          {toast.type === 'success' ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
          {toast.message}
        </div>
      )}

      {visible.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-sm font-medium">No documents pending review</p>
          <p className="text-xs mt-1">Click "Generate Draft" on any obligation to start</p>
        </div>
      ) : (
        <div className="space-y-4">
          {visible.map((draft) => {
            const advisorOpen = expandedAdvisor.has(draft.instance_id)
            const hasAdvisor = !!draft.advisor_notes
            return (
              <div
                key={draft.instance_id}
                className="bg-gray-50 rounded-xl border border-gray-100 p-4"
              >
                {/* Main row */}
                <div className="flex items-start gap-4 flex-wrap sm:flex-nowrap">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-900 text-sm">{draft.obligation_name}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
                      <span>{draft.period}</span>
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full font-medium border border-blue-100">
                        {draft.document_type}
                      </span>
                      <span>{draft.fields_count} fields pre-filled</span>
                      <span>
                        Generated {new Date(draft.generated_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {hasAdvisor && (
                      <button
                        onClick={() => toggleAdvisor(draft.instance_id)}
                        className={clsx(
                          'px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors flex items-center gap-1.5',
                          advisorOpen
                            ? 'bg-purple-100 text-purple-700 border-purple-200'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-purple-300 hover:text-purple-600'
                        )}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        AI Advice
                      </button>
                    )}
                    <button
                      onClick={() => handleApprove(draft.instance_id)}
                      disabled={loadingId === draft.instance_id}
                      className="px-3 py-1.5 bg-green-500 hover:bg-green-600 disabled:bg-green-300 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      {loadingId === draft.instance_id ? (
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                      Approve & File
                    </button>
                  </div>
                </div>

                {/* Gemini advisor panel */}
                {hasAdvisor && advisorOpen && (
                  <AdvisorPanel notes={draft.advisor_notes!} />
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
