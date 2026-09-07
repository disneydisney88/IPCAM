import { useState } from 'react'
import { ArrowLeft, ArrowRight, Check, LoaderCircle, Radio, X } from 'lucide-react'
import { api } from '../lib/api'

interface Props { mock: boolean; onClose: () => void; onSaved: () => void }

export function AddCameraWizard({ mock, onClose, onSaved }: Props) {
  const [step, setStep] = useState(1)
  const [host, setHost] = useState(mock ? '192.168.1.120' : '')
  const [name, setName] = useState('New Camera')
  const [stream, setStream] = useState<'main' | 'sub'>('sub')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const next = async () => {
    if (step === 1 && !host.trim()) return setError('Enter an IP address or host name')
    setError('')
    if (step === 2) { setBusy(true); await new Promise(resolve => setTimeout(resolve, 550)); setBusy(false) }
    setStep(value => Math.min(5, value + 1))
  }
  const save = async () => {
    setBusy(true); setError('')
    try {
      await api.createCamera({ name, ip: host, manufacturer: mock ? 'Generic ONVIF' : 'Unknown', model: 'Discovered camera' })
      onSaved(); onClose()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save camera') }
    finally { setBusy(false) }
  }
  return <div className="modal-backdrop"><section className="modal wizard-modal">
    <header><div><span className="eyebrow">ADD CAMERA</span><h2>Guided setup</h2></div><button className="icon-button" onClick={onClose}><X /></button></header>
    <div className="wizard-steps">{[1,2,3,4,5].map(value => <span className={value <= step ? 'active' : ''} key={value}>{value < step ? <Check size={14} /> : value}</span>)}</div>
    <div className="wizard-body">
      {step === 1 && <><h3>Where is the camera?</h3><p>Enter a private LAN address. Credentials are never shown in the camera URL returned to the browser.</p><label>IP / Host<input autoFocus value={host} onChange={e => setHost(e.target.value)} placeholder="192.168.1.120" /></label><label>Camera name<input value={name} onChange={e => setName(e.target.value)} /></label></>}
      {step === 2 && <><h3>Probe camera</h3><p>We will check light camera ports and ONVIF capabilities without brute-force credential attempts.</p><div className="probe-card"><Radio /><div><strong>{host}</strong><span>{busy ? 'Checking ONVIF and RTSP…' : 'Ready to probe'}</span></div></div></>}
      {step === 3 && <><h3>Select preferred stream</h3><p>Grid view should use the lower-bandwidth sub stream whenever possible.</p><div className="stream-options"><button className={stream === 'sub' ? 'active' : ''} onClick={() => setStream('sub')}><strong>Sub Stream</strong><span>640×360 · H264 · Recommended for grid</span></button><button className={stream === 'main' ? 'active' : ''} onClick={() => setStream('main')}><strong>Main Stream</strong><span>1920×1080+ · Use for fullscreen</span></button></div></>}
      {step === 4 && <><h3>Preview</h3><div className="wizard-preview"><Radio size={30} /><strong>{mock ? 'MOCK PREVIEW READY' : 'Preview requires discovered RTSP profile'}</strong><span>{host} · {stream.toUpperCase()} STREAM</span></div></>}
      {step === 5 && <><h3>Ready to save</h3><div className="summary-list"><div><span>Name</span><strong>{name}</strong></div><div><span>Address</span><strong>{host}</strong></div><div><span>Grid stream</span><strong>{stream}</strong></div><div><span>Status</span><strong className="new-text">NEW</strong></div></div></>}
    </div>
    {error && <p className="error-banner">{error}</p>}
    <footer className="wizard-footer"><button className="secondary" disabled={step === 1 || busy} onClick={() => setStep(value => value - 1)}><ArrowLeft size={16} />Back</button>{step < 5 ? <button className="primary" onClick={next} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />}Continue</button> : <button className="primary" onClick={save} disabled={busy}><Check size={16} />Save Camera</button>}</footer>
  </section></div>
}

