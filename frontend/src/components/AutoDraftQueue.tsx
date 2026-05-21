import { useState } from 'react'
import { approveDraft } from '../services/api'
import type { DraftDocument } from '../services/api'
import clsx from 'clsx'

interface AutoDraftQueueProps {
  drafts: DraftDocument[]
  onApprove: (instanceId: string) => void
}

interface ToastState {
  message: string
  type: 'success' | 'error'
}

export default function AutoDraftQueue({ drafts, onApprove }: AutoDraftQueueProps) {
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  const visible = drafts.filter((d) => !dismissed.has(d.instance_id))

  function showToast(message: string, type: 'success' | 'error') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3500)
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
            toast.type === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-red-600 text-white'
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
          <p className="text-xs mt-1">Drafts will appear here when obligations are due</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide pb-3 pr-4">Obligation</th>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide pb-3 pr-4">Period</th>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide pb-3 pr-4">Type</th>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide pb-3 pr-4">Fields Pre-filled</th>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide pb-3 pr-4">Generated</th>
                <th className="pb-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {visible.map((draft) => (
                <tr key={draft.instance_id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-3.5 pr-4">
                    <p className="font-medium text-gray-900">{draft.obligation_name}</p>
                  </td>
                  <td className="py-3.5 pr-4 text-gray-600">{draft.period}</td>
                  <td className="py-3.5 pr-4">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
                      {draft.document_type}
                    </span>
                  </td>
                  <td className="py-3.5 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden w-20">
                        <div
                          className="h-full bg-green-400 rounded-full"
                          style={{ width: `${Math.min(100, (draft.fields_count / 10) * 100)}%` }}
                        />
                      </div>
                      <span className="text-gray-700 font-medium">{draft.fields_count} fields</span>
                    </div>
                  </td>
                  <td className="py-3.5 pr-4 text-gray-500 text-xs">
                    {new Date(draft.generated_at).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short'
                    })}
                  </td>
                  <td className="py-3.5 text-right">
                    <button
                      onClick={() => handleApprove(draft.instance_id)}
                      disabled={loadingId === draft.instance_id}
                      className="px-3 py-1.5 bg-green-500 hover:bg-green-600 disabled:bg-green-300 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 ml-auto"
                    >
                      {loadingId === draft.instance_id ? (
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                      Review & Approve
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
