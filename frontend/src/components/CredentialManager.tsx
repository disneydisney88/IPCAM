import { useState } from 'react'
import { KeyRound, Trash2 } from 'lucide-react'
import type { Camera } from '../types'
import { api } from '../lib/api'

export function CredentialManager({ cameras }: { cameras: Camera[] }) {
  const [cameraId, setCameraId] = useState(cameras[0]?.id || 0)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [path, setPath] = useState('/')
  const [message, setMessage] = useState('')
  const save = async () => { await api.setCameraCredentials(cameraId, { username, password, rtsp_path: path, stream_kind: 'sub' }); setPassword(''); setMessage('Credential encrypted with Windows DPAPI and saved.') }
  const remove = async () => { await api.deleteCameraCredentials(cameraId); setPassword(''); setMessage('Credential removed.') }
  return <article className="setting-card automation-card"><h3>Camera credentials</h3><p className="setting-help">Passwords stay masked and never return from the API.</p><div className="credential-form"><select value={cameraId} onChange={event => setCameraId(Number(event.target.value))}>{cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name} · {camera.host || camera.ip}</option>)}</select><input value={username} onChange={event => setUsername(event.target.value)} placeholder="Username" autoComplete="username" /><input type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Password" autoComplete="new-password" /><input value={path} onChange={event => setPath(event.target.value)} placeholder="RTSP path" /></div><div className="setting-actions"><button className="primary" disabled={!cameraId || !username || !password} onClick={save}><KeyRound size={14} />Add / Update</button><button className="secondary danger" disabled={!cameraId} onClick={remove}><Trash2 size={14} />Delete</button></div>{message && <p className="setting-message">{message}</p>}</article>
}
