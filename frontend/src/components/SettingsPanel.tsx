import { useEffect, useState } from 'react'
import { Download, FileUp, FolderPlus, Pencil, Play, RefreshCw, Square, Trash2 } from 'lucide-react'
import type { Area, AuditEntry, AuditFilters, Camera, SchedulerRun, SchedulerStatus } from '../types'
import { api } from '../lib/api'
import { CredentialManager } from './CredentialManager'
import { PublicScanControl } from './PublicScanControl'

interface Props { areas: Area[]; cameras: Camera[]; dataDir: string; gatewayMessage: string; onRefresh: () => void }

export function SettingsPanel({ areas, cameras, dataDir, gatewayMessage, onRefresh }: Props) {
  const [name, setName] = useState('')
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null)
  const [logs, setLogs] = useState<AuditEntry[]>([])
  const [auditPage, setAuditPage] = useState({ page: 1, pages: 0, total: 0 })
  const [filters, setFilters] = useState<AuditFilters>({ page: 1, page_size: 20 })
  const [runs, setRuns] = useState<SchedulerRun[]>([])
  const [actions, setActions] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const loadAutomation = async (nextFilters = filters) => {
    const [nextScheduler, nextLogs, nextRuns, nextActions] = await Promise.all([api.scheduler(), api.auditLogs(nextFilters), api.schedulerRuns(), api.auditActions()])
    setScheduler(nextScheduler); setLogs(nextLogs.items)
    setRuns(nextRuns); setActions(nextActions)
    setAuditPage({ page: nextLogs.page, pages: nextLogs.pages, total: nextLogs.total })
  }
  useEffect(() => { loadAutomation().catch(error => setMessage(error instanceof Error ? error.message : 'Unable to load automation settings')) }, [])
  useEffect(() => {
    if (!scheduler || scheduler.state === 'stopped') return
    const timer = window.setInterval(() => loadAutomation().catch(() => undefined), 1000)
    return () => window.clearInterval(timer)
  }, [scheduler?.state])
  const create = async () => { if (name.trim()) { await api.createArea(name.trim()); setName(''); onRefresh() } }
  const rename = async (area: Area) => { const next = prompt('Rename area', area.name); if (next?.trim()) { await api.renameArea(area.id, next.trim()); onRefresh() } }
  const remove = async (area: Area) => { if (confirm(`Delete ${area.name}? Cameras will become unassigned.`)) { await api.deleteArea(area.id); onRefresh() } }
  const importFile = async (file?: File) => {
    if (!file) return
    setBusy(true); setMessage('')
    try {
      const format = file.name.toLowerCase().endsWith('.json') ? 'json' : 'csv'
      const result = await api.importAllowlist(format, await file.text())
      setMessage(`Imported: ${result.created} created, ${result.updated} updated, ${result.rejected} rejected`)
      await loadAutomation()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Import failed') }
    finally { setBusy(false) }
  }
  const saveScheduler = async () => {
    if (!scheduler) return
    setBusy(true)
    try { setScheduler(await api.updateScheduler(scheduler)); setMessage('Scheduler settings saved'); await loadAutomation() }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Unable to save scheduler') }
    finally { setBusy(false) }
  }
  const runNow = async () => {
    if (scheduler) setScheduler({ ...scheduler, running: true, state: 'running' })
    api.runScheduler().then(async result => { setMessage(`Scan complete: ${result.scanned} scanned, ${result.failed} failed, ${result.cancelled} cancelled`); await loadAutomation() })
      .catch(error => setMessage(error instanceof Error ? error.message : 'Scheduled scan failed'))
  }
  const stopRun = async () => { setScheduler(await api.stopScheduler()); setMessage('Stop requested; the active target is being cancelled safely.') }
  const applyFilters = async () => { const next = { ...filters, page: 1 }; setFilters(next); await loadAutomation(next) }
  const changePage = async (page: number) => { const next = { ...filters, page }; setFilters(next); await loadAutomation(next) }
  return <section className="settings-panel">
    <div className="panel-heading"><span className="eyebrow">SYSTEM SETTINGS</span><h1>Organize your monitor</h1><p>Areas describe physical camera locations. Groups remain available through the API for cross-area logical sets.</p></div>
    <div className="automation-overview"><section><strong>Recent scheduler runs</strong>{runs.length ? runs.map(run => <span key={run.id}>{new Date(run.started_at).toLocaleString()} · {run.status} · {run.succeeded}/{run.targets_count} succeeded · {run.failed} failed · {run.cancelled} cancelled · {run.duration_seconds?.toFixed(2) || '0.00'}s</span>) : <span>No runs recorded yet.</span>}</section><label>Action autocomplete<select value={filters.action || ''} onChange={event => setFilters({ ...filters, action: event.target.value })}><option value="">All actions</option>{actions.map(action => <option key={action} value={action}>{action}</option>)}</select></label></div>
    <CredentialManager cameras={cameras} />
    <PublicScanControl />
    <div className="settings-grid">
      <article className="setting-card"><h3>Areas</h3><div className="inline-form"><input value={name} onChange={e => setName(e.target.value)} placeholder="New area name" onKeyDown={e => e.key === 'Enter' && create()} /><button className="primary" onClick={create}><FolderPlus size={16} />Add</button></div>
        <div className="area-list">{areas.map(area => <div key={area.id}><span><i />{area.name}<small>{area.camera_count} cameras</small></span><div><button className="icon-button" onClick={() => rename(area)}><Pencil size={15} /></button><button className="icon-button danger" onClick={() => remove(area)}><Trash2 size={15} /></button></div></div>)}</div>
      </article>
      <article className="setting-card"><h3>Runtime</h3><dl><div><dt>Storage</dt><dd>{dataDir}</dd></div><div><dt>Media gateway</dt><dd className={gatewayMessage === 'READY' ? 'ok-text' : 'warning-text'}>{gatewayMessage}</dd></div><div><dt>Credential UI</dt><dd>Secrets hidden · adapter reserved</dd></div></dl></article>
      <article className="setting-card automation-card"><h3>Authorized target allowlist</h3><p className="setting-help">Import CSV or JSON. Required fields: name and host. Existing hosts are updated.</p><label className="file-button"><FileUp size={16} />{busy ? 'Working…' : 'Import CSV / JSON'}<input type="file" accept=".csv,.json,text/csv,application/json" disabled={busy} onChange={event => { importFile(event.target.files?.[0]); event.target.value = '' }} /></label>{message && <p className="setting-message">{message}</p>}</article>
      <article className="setting-card automation-card"><div className="setting-title-row"><h3>External scan scheduler</h3>{scheduler && <span className={`scheduler-state state-${scheduler.state}`}>{scheduler.state}</span>}</div>{scheduler ? <><label className="toggle-row"><input type="checkbox" checked={scheduler.enabled} onChange={event => setScheduler({ ...scheduler, enabled: event.target.checked })} />Enable scheduled scans</label><div className="scheduler-fields"><label>Interval (minutes)<input type="number" min="5" max="10080" value={scheduler.interval_minutes} onChange={event => setScheduler({ ...scheduler, interval_minutes: Number(event.target.value) })} /></label><label>Mode<select value={scheduler.scan_mode} onChange={event => setScheduler({ ...scheduler, scan_mode: event.target.value as 'quick' | 'deep' })}><option value="quick">Quick</option><option value="deep">Deep</option></select></label></div><small className="setting-help">Last run: {scheduler.last_run ? new Date(scheduler.last_run).toLocaleString() : 'Never'}</small><div className="setting-actions"><button className="primary" disabled={busy} onClick={saveScheduler}>Save</button>{scheduler.state === 'stopped' ? <button className="secondary" disabled={busy} onClick={runNow}><Play size={14} />Run now</button> : <button className="secondary danger" disabled={scheduler.state === 'stopping'} onClick={stopRun}><Square size={13} />Stop</button>}</div></> : <p className="setting-help">Loading scheduler…</p>}</article>
      <article className="setting-card audit-card"><div className="setting-title-row"><h3>Audit log</h3><div className="setting-actions"><a className="secondary" href={api.auditExportUrl(filters)} download><Download size={14} />CSV</a><button className="icon-button" onClick={() => loadAutomation()} aria-label="Refresh audit log"><RefreshCw size={15} /></button></div></div><div className="audit-filters"><label>From<input type="date" value={filters.date_from?.slice(0, 10) || ''} onChange={event => setFilters({ ...filters, date_from: event.target.value ? `${event.target.value}T00:00:00Z` : '' })} /></label><label>To<input type="date" value={filters.date_to?.slice(0, 10) || ''} onChange={event => setFilters({ ...filters, date_to: event.target.value ? `${event.target.value}T23:59:59Z` : '' })} /></label><label>Action<input value={filters.action || ''} placeholder="scheduler.updated" onChange={event => setFilters({ ...filters, action: event.target.value })} /></label><label>Status<select value={filters.status || ''} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="">All</option><option value="success">Success</option><option value="partial">Partial</option><option value="failed">Failed</option><option value="cancelled">Cancelled</option></select></label><button className="secondary" onClick={applyFilters}>Apply</button></div><div className="audit-list">{logs.length ? logs.map(entry => <div key={entry.id}><span className={['failed', 'cancelled'].includes(entry.status) ? 'warning-text' : 'ok-text'}>{entry.status}</span><strong>{entry.action}</strong><small>{entry.target_name || 'System'} · {new Date(entry.created_at).toLocaleString()}</small></div>) : <p className="setting-help">No matching audit events.</p>}</div><div className="audit-pagination"><span>{auditPage.total} events · Page {auditPage.page} of {auditPage.pages || 1}</span><div><button className="secondary" disabled={auditPage.page <= 1} onClick={() => changePage(auditPage.page - 1)}>Previous</button><button className="secondary" disabled={auditPage.page >= auditPage.pages} onClick={() => changePage(auditPage.page + 1)}>Next</button></div></div></article>
    </div>
  </section>
}
