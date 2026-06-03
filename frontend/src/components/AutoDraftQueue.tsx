import { useState } from 'react'
import clsx from 'clsx'
import { approveDraft, downloadDraftPdf, type DraftDocument } from '../services/api'
import { pushToast } from './Toaster'

interface Props {
  drafts: DraftDocument[]
  onApprove: (instanceId: string) => void
}

const RISK_TONE: Record<string, string> = {
  low: 'bg-accent/15 text-accent-soft',
  medium: 'bg-amber-500/15 text-amber-300',
  high: 'bg-red-500/15 text-red-300',
}

function DraftCard({ draft, onApprove }: { draft: DraftDocument; onApprove: (id: string) => void }) {
  const [busy, setBusy] = useState<'pdf' | 'approve' | null>(null)
  const [showNotes, setShowNotes] = useState(false)
  const notes = draft.advisor_notes

  async function handleDownload() {
    setBusy('pdf')
    try {
      await downloadDraftPdf(draft.instance_id, `${draft.obligation_name}.pdf`)
    } catch {
      pushToast('Could not download the PDF — try again.', 'error')
    } finally {
      setBusy(null)
    }
  }

  async function handleApprove() {
    setBusy('approve')
    try {
      await approveDraft(draft.instance_id)
      pushToast(`Filed: ${draft.obligation_name}. Penalty avoided.`, 'success')
      onApprove(draft.instance_id)
    } catch {
      pushToast('Approval failed — try again.', 'error')
    } finally {
      setBusy(null)
    }
  }

  const fields = Object.entries(draft.pre_filled_fields)

  return (
    <div className="os-card p-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <h3 className="font-semibold text-ink leading-tight">{draft.obligation_name}</h3>
          <p className="text-xs text-inkFaint mt-0.5">
            {draft.period} · {draft.fields_count} fields pre-filled · {draft.document_type.toUpperCase()}
          </p>
        </div>
        <span className="os-chip text-[11px] px-2.5 py-1 capitalize">
          {draft.status.replace(/_/g, ' ')}
        </span>
      </div>

      {/* Pre-filled fields */}
      {fields.length > 0 && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {fields.map(([k, v]) => (
            <div key={k} className="bg-panel2 border border-edge rounded-lg px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-inkFaint">{k.replace(/_/g, ' ')}</p>
              <p className="text-sm text-inkSoft truncate">{String(v) || <span className="text-inkFaint italic">—</span>}</p>
            </div>
          ))}
        </div>
      )}

      {/* Advisor notes */}
      {notes && (
        <div className="mt-4">
          <button
            onClick={() => setShowNotes((s) => !s)}
            className="flex items-center gap-2 text-xs font-semibold text-inkMute hover:text-ink transition-colors"
          >
            <span className={clsx('px-1.5 py-0.5 rounded-md text-[10px] font-bold uppercase', RISK_TONE[notes.risk_level] ?? RISK_TONE.medium)}>
              {notes.risk_level} risk
            </span>
            {showNotes ? 'Hide filing guidance' : 'Show filing guidance'}
          </button>
          {showNotes && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <NoteList title="Documents required" items={notes.documents_required} accent="text-accent-soft" />
              <NoteList title="Common mistakes" items={notes.common_mistakes} accent="text-red-400" />
              <NoteList title="Filing checklist" items={notes.filing_checklist} accent="text-inkSoft" />
            </div>
          )}
          {showNotes && notes.risk_reason && (
            <p className="mt-2 text-xs text-inkMute italic">{notes.risk_reason}</p>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2">
        <button onClick={handleDownload} disabled={busy !== null} className="os-btn-ghost text-xs px-3 py-1.5 flex items-center gap-1.5">
          {busy === 'pdf'
            ? <span className="w-3.5 h-3.5 border-2 border-inkMute border-t-transparent rounded-full animate-spin" />
            : <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>}
          Download PDF
        </button>
        <button onClick={handleApprove} disabled={busy !== null} className="os-btn-accent text-xs px-3 py-1.5 ml-auto flex items-center gap-1.5">
          {busy === 'approve'
            ? <span className="w-3.5 h-3.5 border-2 border-canvas border-t-transparent rounded-full animate-spin" />
            : <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
          Approve &amp; File
        </button>
      </div>
    </div>
  )
}

function NoteList({ title, items, accent }: { title: string; items: string[]; accent: string }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wider text-inkFaint mb-1.5">{title}</p>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className={clsx('flex gap-1.5', 'text-inkMute')}>
            <span className={clsx('flex-shrink-0', accent)}>•</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function AutoDraftQueue({ drafts, onApprove }: Props) {
  if (drafts.length === 0) {
    return (
      <div className="text-center py-10 text-inkFaint">
        <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm font-medium text-inkMute">No drafts in the queue</p>
        <p className="text-xs mt-1">Hit “Prepare Draft” on any obligation to auto-fill its filing here.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {drafts.map((d) => (
        <DraftCard key={d.instance_id} draft={d} onApprove={onApprove} />
      ))}
    </div>
  )
}
