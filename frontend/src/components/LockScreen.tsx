import { useState } from 'react'
import { KeyRound, Loader2, Lock, ShieldCheck } from 'lucide-react'

interface Props {
  mode: 'setup' | 'locked'
  busy: boolean
  error: string
  onSubmit: (password: string) => void
}

export function LockScreen({ mode, busy, error, onSubmit }: Props) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const localError = mode === 'setup' && password.length > 0 && password.length < 12
    ? 'Password must be at least 12 characters'
    : mode === 'setup' && confirm.length > 0 && confirm !== password
      ? 'Passwords do not match'
      : ''

  const submit = () => {
    if (busy || localError || !password) return
    onSubmit(password)
  }

  return (
    <div className="lock-screen">
      <form className="lock-card" onSubmit={event => { event.preventDefault(); submit() }}>
        <div className="lock-icon">{mode === 'setup' ? <ShieldCheck size={30} /> : <Lock size={30} />}</div>
        <strong>IPCAM MONITOR</strong>
        <span>{mode === 'setup' ? 'Create your admin password to finish setup' : 'Dashboard locked · enter admin password'}</span>
        <input
          autoFocus
          type="password"
          value={password}
          onChange={event => setPassword(event.target.value)}
          placeholder={mode === 'setup' ? 'New admin password (min 12 chars)' : 'Admin password'}
          disabled={busy}
        />
        {mode === 'setup' && (
          <input
            type="password"
            value={confirm}
            onChange={event => setConfirm(event.target.value)}
            placeholder="Confirm password"
            disabled={busy}
          />
        )}
        {(localError || error) && <em>{localError || error}</em>}
        <button type="submit" className="primary" disabled={busy || !password || Boolean(localError) || (mode === 'setup' && !confirm)}>
          {busy ? <Loader2 size={16} className="spin" /> : <KeyRound size={16} />}
          {busy ? 'Verifying…' : mode === 'setup' ? 'Set Password & Unlock' : 'Unlock Dashboard'}
        </button>
        <small>Session auto-locks after 15 minutes · 5 failed attempts lock for 5 minutes</small>
      </form>
    </div>
  )
}
