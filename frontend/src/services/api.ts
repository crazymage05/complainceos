import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// ─── TypeScript Interfaces ───────────────────────────────────────────────────

export interface BusinessProfile {
  business_name: string
  owner_name: string
  business_type: 'proprietorship' | 'partnership' | 'pvt_ltd' | 'llp'
  state: string
  industry: string
  employee_count: number
  annual_turnover_inr: number
  registrations: string[]
}

export interface DNASummary {
  total_obligations: number
  high_priority: number
  frameworks: string[]
  risk_score: number
  created_at: string
}

export interface ObligationInstance {
  instance_id: string
  obligation_name: string
  framework: string
  deadline: string
  decay_score: number
  predicted_penalty_inr: number
  status: 'pending' | 'in_progress' | 'filed' | 'overdue'
  period: string
  description: string
}

export interface RegChange {
  regulation_id: string
  change_type: string
  description: string
  effective_date: string
}

export interface RippleImpact {
  obligation_name: string
  obligation_id: string
  impact_type: 'direct' | 'indirect'
  description: string
}

export interface RippleReport {
  change_title: string
  effective_date: string
  direct_impacts: RippleImpact[]
  indirect_impacts: RippleImpact[]
  total_affected: number
  severity: 'high' | 'medium' | 'low'
}

export interface PenaltyPreview {
  instance_id: string
  obligation_name: string
  base_penalty_inr: number
  per_day_penalty_inr: number
  estimated_days_late: number
  total_estimated_penalty_inr: number
  is_first_offense: boolean
  penalty_breakdown: string
}

export interface DraftDocument {
  instance_id: string
  obligation_name: string
  period: string
  pre_filled_fields: Record<string, string>
  fields_count: number
  document_type: string
  status: 'pending_review' | 'approved' | 'filed'
  generated_at: string
}

export interface FilingHistory {
  filing_id: string
  obligation_name: string
  period: string
  filed_date: string | null
  deadline: string
  days_late: number
  penalty_paid_inr: number
  status: 'on_time' | 'late' | 'pending'
}

// ─── Score Color Utility ─────────────────────────────────────────────────────

export function getScoreColor(score: number): 'red' | 'amber' | 'green' {
  if (score < 20) return 'red'
  if (score <= 40) return 'amber'
  return 'green'
}

export function getScoreTailwind(score: number) {
  if (score < 20) return { border: 'border-red-500', text: 'text-red-600', bg: 'bg-red-50', badge: 'bg-red-100 text-red-700' }
  if (score <= 40) return { border: 'border-amber-500', text: 'text-amber-600', bg: 'bg-amber-50', badge: 'bg-amber-100 text-amber-700' }
  return { border: 'border-green-500', text: 'text-green-600', bg: 'bg-green-50', badge: 'bg-green-100 text-green-700' }
}

// ─── API Functions ───────────────────────────────────────────────────────────

export async function createBusiness(
  data: BusinessProfile
): Promise<{ business_id: string; dna: DNASummary }> {
  const res = await api.post('/api/business/onboard', data)
  return res.data
}

export async function getObligations(
  businessId: string
): Promise<ObligationInstance[]> {
  const res = await api.get(`/api/business/${businessId}/obligations`)
  return res.data
}

export async function checkRipple(
  businessId: string,
  change: RegChange
): Promise<RippleReport> {
  const res = await api.post(`/api/business/${businessId}/ripple`, change)
  return res.data
}

export async function getPenaltyPreview(
  instanceId: string
): Promise<PenaltyPreview> {
  const res = await api.get(`/api/obligations/${instanceId}/penalty-preview`)
  return res.data
}

export async function generateDraft(
  instanceId: string
): Promise<DraftDocument> {
  const res = await api.post(`/api/obligations/${instanceId}/draft`)
  return res.data
}

export async function approveDraft(
  instanceId: string
): Promise<{ status: string }> {
  const res = await api.post(`/api/obligations/${instanceId}/approve`)
  return res.data
}

export async function getFilingHistory(
  businessId: string
): Promise<FilingHistory[]> {
  const res = await api.get(`/api/business/${businessId}/history`)
  return res.data
}
