export type CameraStatus = 'LIVE' | 'OFFLINE' | 'AUTH REQUIRED' | 'STREAM ERROR' | 'NEW' | 'SCANNING'

export interface StreamInfo {
  id: number
  kind: 'main' | 'sub'
  codec: string | null
  width: number | null
  height: number | null
  fps: number | null
  validated: boolean
}

export interface Camera {
  id: number
  name: string
  ip: string
  manufacturer: string
  model: string
  firmware: string | null
  status: CameraStatus
  area_id: number | null
  area_name: string | null
  favorite: boolean
  connection_type: 'lan' | 'internet'
  host: string | null
  resolved_ip: string | null
  snapshot_url: string | null
  model_specs: Record<string, unknown> | null
  sort_order: number
  ptz_support: boolean
  audio_support: boolean
  is_mock: boolean
  groups: string[]
  streams: StreamInfo[]
}

export interface Area { id: number; name: string; camera_count: number }
export interface NetworkInterface { name: string; ip: string; subnet: string; gateway: string | null; suggested_cidr: string }
export interface ViewItem { camera_id: number; position: number; layout: Record<string, unknown> }
export interface SavedView {
  id: number
  name: string
  grid_size: 1 | 4 | 9 | 16
  filters: Record<string, unknown>
  stream_preference: 'main' | 'sub'
  items: ViewItem[]
}
export interface GridPosition { i: string; x: number; y: number; w: number; h: number; minW?: number; minH?: number }
export interface ScanProgress { status: string; checked: number; total: number; candidates: number; onvif: number; streams: number }

export interface ExternalTarget {
  id: string
  name: string
  host: string
  port_overrides: string | null
  enabled: boolean
  notes: string | null
  last_scan: string | null
  created_at: string
}

export interface ExternalScanResult {
  name: string
  target: string
  host: string
  resolved_ip: string | null
  open_ports: number[]
  brand: string | null
  auth_required: boolean
  fingerprints: Array<Record<string, unknown>>
  candidates: {
    rtsp: string[]
    snapshot: string[]
  }
}

export interface AllowlistImportResult { created: number; updated: number; rejected: number; errors: Array<{ row: number; error: string }> }
export interface SchedulerStatus { enabled: boolean; interval_minutes: number; scan_mode: 'quick' | 'deep'; target_timeout_seconds: number; running: boolean; state: 'running' | 'stopping' | 'stopped'; last_run: string | null; next_run: string | null }
export interface SchedulerRun { id: number; status: string; started_at: string; completed_at: string | null; targets_count: number; succeeded: number; failed: number; cancelled: number; duration_seconds: number | null }
export interface LiveStream { available: boolean; state: string; message: string; player_url: string | null }
export interface AuditEntry { id: number; action: string; status: string; target_id: string | null; target_name: string | null; details: Record<string, unknown>; created_at: string }
export interface AuditPage { items: AuditEntry[]; page: number; page_size: number; total: number; pages: number }
export interface AuditFilters { page?: number; page_size?: number; date_from?: string; date_to?: string; action?: string; status?: string }
