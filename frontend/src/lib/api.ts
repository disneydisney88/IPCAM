import type { AllowlistImportResult, Area, AuditFilters, AuditPage, Camera, CameraTelemetry, ExternalScanResult, ExternalTarget, LiveStream, NetworkInterface, SavedView, SchedulerRun, SchedulerStatus } from '../types'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Request failed')
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export const api = {
  cameras: () => request<Camera[]>('/api/cameras'),
  areas: () => request<Area[]>('/api/areas'),
  views: () => request<SavedView[]>('/api/views'),
  interfaces: () => request<NetworkInterface[]>('/api/system/network/interfaces'),
  mediaHealth: () => request<{ available: boolean; running: boolean; message: string }>('/api/media/health'),
  ensureMock: () => request<{ created: number; total: number }>('/api/mock/ensure', { method: 'POST' }),
  favorite: (id: number, favorite: boolean) => request<Camera>(`/api/cameras/${id}/favorite`, { method: 'PUT', body: JSON.stringify({ favorite }) }),
  updateCamera: (id: number, changes: Record<string, unknown>) => request<Camera>(`/api/cameras/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  createCamera: (payload: Record<string, unknown>) => request<Camera>('/api/cameras', { method: 'POST', body: JSON.stringify(payload) }),
  createArea: (name: string) => request<Area>('/api/areas', { method: 'POST', body: JSON.stringify({ name }) }),
  renameArea: (id: number, name: string) => request<Area>(`/api/areas/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
  deleteArea: (id: number) => request<void>(`/api/areas/${id}`, { method: 'DELETE' }),
  createView: (payload: Omit<SavedView, 'id'>) => request<SavedView>('/api/views', { method: 'POST', body: JSON.stringify(payload) }),
  deleteView: (id: number) => request<void>(`/api/views/${id}`, { method: 'DELETE' }),
  startScan: (cidr: string, mock: boolean) => request<{ id: number; events_url: string }>('/api/scans', { method: 'POST', body: JSON.stringify({ cidr, mock }) }),
  externalTargets: () => request<ExternalTarget[]>('/api/external-targets'),
  createExternalTarget: (payload: Record<string, unknown>) => request<ExternalTarget>('/api/external-targets', { method: 'POST', body: JSON.stringify(payload) }),
  importAllowlist: (format: 'csv' | 'json', content: string) => request<AllowlistImportResult>('/api/external-targets/import', { method: 'POST', body: JSON.stringify({ format, content }) }),
  scheduler: () => request<SchedulerStatus>('/api/scheduler'),
  updateScheduler: (payload: Pick<SchedulerStatus, 'enabled' | 'interval_minutes' | 'scan_mode' | 'target_timeout_seconds'>) => request<SchedulerStatus>('/api/scheduler', { method: 'PUT', body: JSON.stringify(payload) }),
  runScheduler: () => request<{ scanned: number; failed: number; cancelled: number }>('/api/scheduler/run', { method: 'POST' }),
  stopScheduler: () => request<SchedulerStatus>('/api/scheduler/stop', { method: 'POST' }),
  schedulerRuns: () => request<SchedulerRun[]>('/api/scheduler/runs?limit=10'),
  auditActions: () => request<string[]>('/api/audit-logs/actions'),
  cameraLive: (id: number, kind: 'main' | 'sub' = 'sub') => request<LiveStream>(`/api/cameras/${id}/live?kind=${kind}`),
  telemetry: (ids: number[]) => request<CameraTelemetry[]>(`/api/telemetry?ids=${ids.join(',')}`),
  captureSnapshot: (id: number) => request<{ available: boolean; snapshot_url?: string; message?: string }>(`/api/cameras/${id}/snapshot`, { method: 'POST' }),
  refreshGeoip: (id: number) => request<Camera>(`/api/cameras/${id}/geoip`, { method: 'POST' }),
  enrichSpecs: (id: number) => request<Camera>(`/api/cameras/${id}/enrich-specs`, { method: 'POST' }),
  setCameraCredentials: (id: number, payload: { username: string; password: string; rtsp_path: string; stream_kind: 'main' | 'sub' }) => request<{ configured: boolean }>(`/api/cameras/${id}/credentials`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteCameraCredentials: (id: number, kind: 'main' | 'sub' = 'sub') => request<void>(`/api/cameras/${id}/credentials?kind=${kind}`, { method: 'DELETE' }),
  dashboardSummary: () => request<any>('/api/dashboard/summary'),
  publicScanStatus: () => request<any>('/api/public-scan'),
  adminSetup: (password: string, token = '') => request<{ configured: boolean }>('/api/admin/setup', { method: 'POST', headers: token ? { 'X-Admin-Unlock': token } : {}, body: JSON.stringify({ password }) }),
  adminUnlock: (password: string) => request<{ unlock_token: string; expires_in: number }>('/api/admin/unlock', { method: 'POST', body: JSON.stringify({ password }) }),
  configurePublicScan: (enabled: boolean, token: string) => request<any>(`/api/public-scan?enabled=${enabled}`, { method: 'PUT', headers: { 'X-Admin-Unlock': token } }),
  previewPublicScan: (payload: Record<string, unknown>, token: string) => request<any>('/api/public-scan/preview', { method: 'POST', headers: { 'X-Admin-Unlock': token }, body: JSON.stringify(payload) }),
  startPublicScan: (payload: Record<string, unknown>, token: string) => request<any>('/api/public-scan/start', { method: 'POST', headers: { 'X-Admin-Unlock': token }, body: JSON.stringify(payload) }),
  stopPublicScan: (token: string) => request<any>('/api/public-scan/stop', { method: 'POST', headers: { 'X-Admin-Unlock': token } }),
  auditLogs: (filters: AuditFilters = {}) => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) })
    return request<AuditPage>(`/api/audit-logs?${params}`)
  },
  auditExportUrl: (filters: AuditFilters = {}) => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => { if (!['page', 'page_size'].includes(key) && value !== undefined && value !== '') params.set(key, String(value)) })
    return `/api/audit-logs/export.csv?${params}`
  },
  scanExternalTarget: (payload: {
    target_id?: string
    host?: string
    port_overrides?: string | null
    name?: string
    mode?: 'quick' | 'deep'
  }) => request<ExternalScanResult>('/api/external-targets/scan', {
    method: 'POST',
    body: JSON.stringify({ mode: 'quick', ...payload }),
  }),
}
