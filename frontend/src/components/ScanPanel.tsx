import { useEffect, useMemo, useState } from 'react'
import { Activity, CheckCircle2, Globe, Radar, X } from 'lucide-react'
import { api } from '../lib/api'
import type { ExternalScanResult, ExternalTarget, ScanProgress } from '../types'

interface Props {
  cidr: string
  mock: boolean
  onClose: () => void
  onComplete: () => void
}

type ScanMode = 'local' | 'external'

const terminalSteps = ['DNS resolution', 'Open Ports', 'Brand Detected', 'Password Verification'] as const
const LAST_EXTERNAL_TARGET_KEY = 'ipcam.lastExternalTarget'

type ExternalScanSource =
  | { kind: 'host'; value: string; label: string }
  | { kind: 'target'; value: string; label: string }

function readLastExternalTarget(): { id: string; host: string; name: string } | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(LAST_EXTERNAL_TARGET_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<{ id: string; host: string; name: string }>
    if (!parsed.host) return null
    return { id: parsed.id || '', host: parsed.host, name: parsed.name || parsed.host }
  } catch {
    return null
  }
}

function writeLastExternalTarget(target: { id?: string; host: string; name?: string }) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(LAST_EXTERNAL_TARGET_KEY, JSON.stringify({
    id: target.id || '',
    host: target.host,
    name: target.name || target.host,
  }))
}

export function ScanPanel({ cidr, mock, onClose, onComplete }: Props) {
  const [mode, setMode] = useState<ScanMode>('local')
  const [progress, setProgress] = useState<ScanProgress>({ status: 'READY', checked: 0, total: 0, candidates: 0, onvif: 0, streams: 0 })
  const [error, setError] = useState('')
  const [externalTargets, setExternalTargets] = useState<ExternalTarget[]>([])
  const [externalTargetsLoading, setExternalTargetsLoading] = useState(false)
  const [externalTargetsError, setExternalTargetsError] = useState('')
  const [externalHost, setExternalHost] = useState(mock ? '203.0.113.10' : readLastExternalTarget()?.host ?? '')
  const [externalResult, setExternalResult] = useState<ExternalScanResult | null>(null)
  const [terminalIndex, setTerminalIndex] = useState(0)
  const [scanningExternal, setScanningExternal] = useState(false)
  const [lastExternalTarget, setLastExternalTarget] = useState(readLastExternalTarget())

  const percent = useMemo(() => progress.total ? Math.round(progress.checked / progress.total * 100) : 0, [progress])
  const enabledExternalTargets = useMemo(() => externalTargets.filter(target => target.enabled), [externalTargets])

  useEffect(() => {
    if (mode !== 'external') return
    let cancelled = false
    setExternalTargetsLoading(true)
    setExternalTargetsError('')
    api.externalTargets()
      .then(targets => {
        if (cancelled) return
        setExternalTargets(targets)
        setLastExternalTarget(readLastExternalTarget())
        if (!externalHost.trim()) {
          const fallback = readLastExternalTarget()
          if (fallback?.host) setExternalHost(fallback.host)
          else if (targets.find(target => target.enabled)) setExternalHost(targets.find(target => target.enabled)?.host || '')
          else if (mock) setExternalHost('203.0.113.10')
        }
      })
      .catch(err => {
        if (cancelled) return
        setExternalTargetsError(err instanceof Error ? err.message : 'Unable to load authorized targets')
      })
      .finally(() => {
        if (!cancelled) setExternalTargetsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [mode, mock])

  const runExternalScan = async (source: ExternalScanSource, remember = true) => {
    setError('')
    setExternalResult(null)
    setTerminalIndex(0)
    setScanningExternal(true)
    const timer = window.setInterval(() => {
      setTerminalIndex(index => Math.min(index + 1, terminalSteps.length - 1))
    }, 260)
    try {
      const result = await api.scanExternalTarget(source.kind === 'target' ? { target_id: source.value } : { host: source.value })
      setExternalResult(result)
      if (remember) {
        writeLastExternalTarget({ id: source.kind === 'target' ? source.value : '', host: result.host || source.value, name: result.name || source.label })
        setLastExternalTarget(readLastExternalTarget())
      }
      onComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to probe external target')
    } finally {
      window.clearInterval(timer)
      setTerminalIndex(terminalSteps.length - 1)
      setScanningExternal(false)
    }
  }

  const startLocal = async () => {
    setError('')
    setExternalResult(null)
    try {
      const scan = await api.startScan(cidr, mock)
      const source = new EventSource(scan.events_url)
      source.addEventListener('progress', event => setProgress(JSON.parse((event as MessageEvent).data)))
      source.addEventListener('complete', event => {
        setProgress(JSON.parse((event as MessageEvent).data))
        source.close()
        onComplete()
      })
      source.onerror = () => {
        source.close()
        setError('Scan connection interrupted')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start scan')
    }
  }

  const startExternal = async () => {
    if (!externalHost.trim()) {
      setError('請輸入公網 IP 或 Hostname')
      return
    }
    await runExternalScan({ kind: 'host', value: externalHost.trim(), label: externalHost.trim() })
  }

  const scanSavedTarget = async (target: ExternalTarget) => {
    await runExternalScan({ kind: 'target', value: target.id, label: target.name }, true)
  }

  const scanLastTarget = async () => {
    const recent = lastExternalTarget?.id
      ? enabledExternalTargets.find(target => target.id === lastExternalTarget.id)
      : undefined
    if (recent) {
      await scanSavedTarget(recent)
      return
    }
    if (lastExternalTarget?.host) {
      await runExternalScan({ kind: 'host', value: lastExternalTarget.host, label: lastExternalTarget.name || lastExternalTarget.host }, false)
      return
    }
    setError('沒有可重掃的外部目標')
  }

  return (
    <div className="modal-backdrop">
      <section className="modal scan-modal">
        <header>
          <div>
            <span className="eyebrow">NETWORK DISCOVERY</span>
            <h2>{mode === 'local' ? 'Scan your private network' : 'Scan a single authorized external target'}</h2>
          </div>
          <button className="icon-button" onClick={onClose}><X /></button>
        </header>

        <div className="scan-mode-toggle">
          <button className={mode === 'local' ? 'active' : ''} onClick={() => setMode('local')}>Local Subnet Scan</button>
          <button className={mode === 'external' ? 'active' : ''} onClick={() => setMode('external')}><Globe size={14} />External IP Target</button>
        </div>

        {mode === 'local' ? (
          <>
            <div className={`radar ${progress.status === 'RUNNING' ? 'active' : ''}`}><Radar size={44} /><i /><i /></div>
            <p className="scan-target">Scanning <strong>{cidr}</strong></p>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${percent}%` }} /></div>
            <div className="scan-stats">
              <div><strong>{progress.checked}<small> / {progress.total || '—'}</small></strong><span>Devices checked</span></div>
              <div><strong>{progress.candidates}</strong><span>Possible cameras</span></div>
              <div><strong>{progress.onvif}</strong><span>ONVIF cameras</span></div>
              <div><strong>{progress.streams}</strong><span>Streams found</span></div>
            </div>
            {error && <p className="error-banner">{error}</p>}
            {progress.status === 'COMPLETED'
              ? <button className="primary full" onClick={onClose}><CheckCircle2 size={17} />Scan complete</button>
              : <button className="primary full" onClick={startLocal} disabled={progress.status === 'RUNNING'}><Activity size={17} />{progress.status === 'RUNNING' ? 'Scanning…' : 'Start Scan'}</button>}
          </>
        ) : (
          <>
            <div className="external-quick-actions">
              <div className="scan-hint">
                <span>一鍵掃描授權目標</span>
                <small>點一下就會自動跑 DNS、Port、Brand 與 Auth 檢查。</small>
              </div>
              <div className="quick-action-row">
                <button
                  className="secondary"
                  onClick={scanLastTarget}
                  disabled={scanningExternal || !lastExternalTarget}
                >
                  <Globe size={14} />
                  Scan Last Target
                </button>
                {enabledExternalTargets.map(target => (
                  <button
                    key={target.id}
                    className="secondary"
                    onClick={() => scanSavedTarget(target)}
                    disabled={scanningExternal}
                    title={target.notes || target.host}
                  >
                    <Activity size={14} />
                    {target.name}
                  </button>
                ))}
              </div>
            </div>

            <div className="external-form">
              <label>
                Target Host / IP
                <input
                  autoFocus
                  value={externalHost}
                  onChange={e => setExternalHost(e.target.value)}
                  placeholder="請輸入公網 IP 或 Hostname (例如: 203.0.113.10 或 camera.example.com:8554)"
                />
              </label>
            </div>
            {externalTargetsLoading && <p className="scan-subtle">Loading authorized targets…</p>}
            {externalTargetsError && <p className="error-banner">{externalTargetsError}</p>}
            {!externalTargetsLoading && enabledExternalTargets.length > 0 && (
              <div className="external-target-list">
                {enabledExternalTargets.map(target => (
                  <button
                    key={target.id}
                    className="external-target-chip"
                    onClick={() => scanSavedTarget(target)}
                    disabled={scanningExternal}
                    title={target.notes || target.host}
                  >
                    <strong>{target.name}</strong>
                    <span>{target.host}</span>
                    {target.port_overrides && <small>Ports: {target.port_overrides}</small>}
                  </button>
                ))}
              </div>
            )}
            <div className="terminal-box">
              {terminalSteps.map((step, index) => (
                <div key={step} className={`terminal-line ${index <= terminalIndex ? 'active' : ''}`}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{step}</strong>
                  <em>{index < terminalIndex ? 'done' : index === terminalIndex ? 'running' : 'waiting'}</em>
                </div>
              ))}
            </div>
            {externalResult && (
              <div className="external-result">
                <strong>{externalResult.brand || 'Unknown brand'}</strong>
                <span>{externalResult.host}{externalResult.resolved_ip ? ` · ${externalResult.resolved_ip}` : ''}</span>
                <small>{externalResult.open_ports.length} open ports · {externalResult.auth_required ? 'AUTH REQUIRED' : 'No auth challenge detected'}</small>
                {externalResult.location && (
                  <small>
                    {externalResult.location.is_private
                      ? '📍 Private / reserved range · GeoIP lookup skipped'
                      : `📍 ${[externalResult.location.city, externalResult.location.country].filter(Boolean).join(', ') || 'Unknown location'}${externalResult.location.latitude != null && externalResult.location.longitude != null ? ` · ${externalResult.location.latitude.toFixed(4)}, ${externalResult.location.longitude.toFixed(4)}` : ''}${externalResult.location.isp ? ` · ${externalResult.location.isp}` : ''}`}
                  </small>
                )}
              </div>
            )}
            {error && <p className="error-banner">{error}</p>}
            <button className="primary full" onClick={startExternal} disabled={scanningExternal || !externalHost.trim()}>
              <Activity size={17} />
              {scanningExternal ? 'Scanning…' : 'Start Scan'}
            </button>
          </>
        )}
      </section>
    </div>
  )
}
