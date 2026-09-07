import { useEffect, useState } from 'react'
import type { ExternalTarget } from '../types'
import { api } from '../lib/api'

export function PublicScanControl() {
  const [status, setStatus] = useState<any>(null)
  const [targets, setTargets] = useState<ExternalTarget[]>([])
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [token, setToken] = useState('')
  const [targetId, setTargetId] = useState('')
  const [message, setMessage] = useState('Public Scan is disabled by default.')
  const load = async () => { const [next, allowed] = await Promise.all([api.publicScanStatus(), api.externalTargets()]); setStatus(next); setTargets(allowed.filter(item => item.enabled)); if (!targetId && allowed[0]) setTargetId(allowed[0].id) }
  useEffect(() => { load() }, [])
  const unlock = async () => { try { if (!status?.admin_configured) { await api.adminSetup(password); await load() } const result = await api.adminUnlock(password); setToken(result.unlock_token); setPassword(''); setMessage('Admin unlocked for 15 minutes.') } catch (error) { setMessage(error instanceof Error ? error.message : 'Unlock failed') } }
  const changePassword = async () => { try { await api.adminSetup(newPassword, token); setToken(''); setNewPassword(''); setMessage('Admin password changed. Unlock again with the new password.') } catch (error) { setMessage(error instanceof Error ? error.message : 'Password change failed') } }
  const toggle = async () => { const next = await api.configurePublicScan(!status.enabled, token); setStatus({ ...status, ...next }); setMessage(next.enabled ? 'Authorized Public Scan enabled.' : 'Public Scan disabled.') }
  const start = async () => { const config = { target_id: targetId, rate_limit: 2, concurrency: 4, timeout_seconds: 10 }; const preview = await api.previewPublicScan(config, token); if (!confirm(`Scan ${preview.target_count} authorized targets in ${preview.target_range}?`)) return; await api.startPublicScan(config, token); setMessage('Public scan queued.'); await load() }
  const stop = async () => { await api.stopPublicScan(token); setMessage('Stop requested.'); await load() }
  return <article className="setting-card automation-card"><h3>Authorized Public Scan</h3><p className="setting-help">{status?.admin_configured ? 'Admin password configured.' : 'First use: create an Admin password (12+ characters).'} Only enabled allowlist IP/CIDR entries; maximum 256 targets. Local Scan is unaffected.</p><div className="credential-form"><input type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder={status?.admin_configured ? 'Admin password' : 'Create Admin password (12+ characters)'} autoComplete={status?.admin_configured ? 'current-password' : 'new-password'} /><button className="secondary" disabled={password.length < 12} onClick={unlock}>{status?.admin_configured ? 'Admin Unlock' : 'Set Password & Unlock'}</button><select value={targetId} onChange={event => setTargetId(event.target.value)}>{targets.map(target => <option key={target.id} value={target.id}>{target.name} — {target.host}</option>)}</select></div>{token && <div className="credential-form"><input type="password" value={newPassword} onChange={event => setNewPassword(event.target.value)} placeholder="New Admin password (12+ characters)" autoComplete="new-password" /><button className="secondary" disabled={newPassword.length < 12} onClick={changePassword}>Change Password</button></div>}<div className="setting-actions"><button className="secondary" disabled={!token} onClick={toggle}>{status?.enabled ? 'Disable Public Scan' : 'Enable Public Scan'}</button><button className="primary" disabled={!token || !status?.enabled || !targetId} onClick={start}>Preview & Start</button><button className="secondary danger" disabled={!token || status?.state !== 'running'} onClick={stop}>Stop</button></div><p className="setting-message">{message}</p></article>
}
